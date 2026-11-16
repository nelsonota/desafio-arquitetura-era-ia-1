# Helpdesk com AI Gateway

## Visão geral

A aplicação FastAPI usa portas e adaptadores e chama modelos exclusivamente pelo LiteLLM Proxy self-hosted. O app conhece as capacidades lógicas `ticket-classification`, `order-extraction`, `reply-suggestion` e `ticket-topics`; modelos físicos, chaves de provider, preços, timeout e fallback ficam em `gateway/config.yaml`. Uma falha técnica tenta um deployment `large` equivalente de outro provider; na F2, a app coordena os aliases antes do primeiro chunk para preservar o contrato SSE. Classificação, tópicos e sugestão podem degradar para `mini` conforme seus contratos; extração retorna erro em vez de produzir campo incorreto.

`app/helpdesk/adapters/gateway_client.py` é o único componente de `app/` que executa chamadas HTTP ao gateway. Os módulos de feature dependem dos contratos de `ports.py`, não do adaptador.

Classificação e extração respondem de forma síncrona; sugestão usa SSE; relatório cria um job assíncrono e expõe seu estado. O app recebe uma chave virtual LiteLLM de USD 10/mês e 120 RPM. As credenciais OpenAI/Anthropic só são fornecidas ao gateway e ao simulador. O arquivo de tarefas em memória é suficiente para o escopo do desafio, que não exige recuperar jobs após reinício.

## Diagnóstico da v1

Os comandos abaixo foram exercitados pela borda `localhost:8000`; `/admin/calls` no provider fake registra destino, tarefa, status, streaming e duração.

1. **Relatório mensal excede a borda.** `curl -i -X POST localhost:8000/reports/topics -H 'Content-Type: application/json' -d '{"start":"2026-08-01","end":"2026-08-31"}'` retornou 504 após cerca de 30 s. `/admin/calls` registrou lotes `topics` ainda sendo processados. Causa em v1: `app/helpdesk/report.py` fazia lotes de 150 sequencialmente e `main.py` só respondia ao concluir.
2. **Sugestão bloqueia o atendente.** `curl -i -X POST localhost:8000/tickets/reply-suggestion -H 'Content-Type: application/json' -d '{"ticket_id":"TK-00042","text":"Meu pedido #481516 não chegou e já passou do prazo, urgente"}'` retornou 200 em 15,97 s, sem texto antes do final; `/admin/calls` mostrou `suggest`, `stream=false`, 606 tokens. Causa: v1 `suggestion.py` aguardava a conclusão síncrona do SDK Anthropic.
3. **Falha do provider derruba uma feature.** `curl -X POST localhost:8090/admin/failures -H 'Content-Type: application/json' -d '{"provider":"openai","mode":"error_500"}'` e depois uma chamada de classificação pela borda retornaram 500. `/admin/calls` não mostrou tentativa em outro destino. Causa: `classification.py`/`extraction.py` chamavam diretamente o cliente OpenAI em `llm.py`, sem fallback.
4. **Trocar modelo exigia rebuild.** `rg -n 'MODEL = ' app/helpdesk/config.py` mostrava nomes físicos em constantes importadas pelas features; trocar uma constante exigia reconstruir a imagem app. Essa dor foi confirmada por inspeção, não por um redeploy medido da imagem v1.

Restaure o provider fake após os experimentos com `curl -X POST localhost:8090/admin/reset`.

## Como rodar

```sh
cp .env.example .env
docker compose up -d --build --wait
curl -s localhost:8000/health
docker compose exec -T -e HELPDESK_URL=http://edge app python -m unittest discover -s /tests/characterization -v
docker compose exec -T -e HELPDESK_URL=http://edge -e LITELLM_MASTER_KEY=sk-litellm-gateway-dev app python -m unittest discover -s /tests/acceptance -v
python metrics/measure.py app/helpdesk main
```

No PowerShell, use `Copy-Item .env.example .env`. Se alterar `LITELLM_MASTER_KEY` no `.env`, passe o mesmo valor no `-e LITELLM_MASTER_KEY=...` da suíte de aceitação. O serviço app não recebe `FAKE_OPENAI_KEY` nem `FAKE_ANTHROPIC_KEY`. A porta de entrada das APIs é a borda em `http://localhost:8000`.

A LiteLLM Admin UI fica em `http://localhost:4000/ui`; no ambiente local, entre com `admin` / `admin`. Altere esses valores no `.env` quando compartilhar o ambiente.

Validação desta revisão: caracterização da main 7/7; caracterização nas tags v1 e v2 7/7 em cada uma; suíte de execução e governança 12/12.

## Métrica de acoplamento

`metrics/measure.py` calcula dependências internas: `Ca` (aferentes), `Ce` (eferentes), `I=Ce/(Ca+Ce)`, `A` (proporção de classes abstratas) e `D=|A+I-1|`. O cabeçalho é `component,ca,ce,i,a,d`. Zona de dor significa `A<0,5`, `I<0,5` e `D>=0,5` ao mesmo tempo. Os gráficos usam I no eixo x, A no eixo y e a diagonal A+I=1 como Main Sequence.

| Versão | CSV e gráfico | Leitura |
|---|---|---|
| v1-coupled | [CSV](metrics/results/v1-coupled.csv) · [SVG](metrics/results/v1-coupled.svg) | Features I=0,75 (report 0,80), com dependências concretas de SDK/configuração. `main` I=1 é composição. |
| v2-decoupled | [CSV](metrics/results/v2-decoupled.csv) · [SVG](metrics/results/v2-decoupled.svg) | Features I=0,67 e dependência em ports; `ports` fica em A=1/I=0. |
| main | [CSV](metrics/results/main.csv) · [SVG](metrics/results/main.svg) | Mantém os valores de estrutura da v2: os novos modos estão concentrados em `main` e adaptadores, sem aumentar dependências internas das features. |

`schemas` tem A=0/I=0/D=1 e é a única exceção declarada à zona de dor: representa tipos de valor concretos e estáveis. `main` é o ponto de composição e tem I=1/D=0. O cliente HTTP do gateway e os módulos de feature não são exceções. Os adaptadores têm I=0,5, portanto ficam fora da zona definida, que exige I estritamente menor que 0,5. O ADR [0014](docs/adr/0014-interpretar-metrica-de-acoplamento.md) registra essa leitura. O plano explica piloto, medição, revisão e handoff em [docs/refactoring-plan.md](docs/refactoring-plan.md).

Para reproduzir a medição de uma tag, use um checkout dessa tag e execute `python metrics/measure.py app/helpdesk v1-coupled` ou `python metrics/measure.py app/helpdesk v2-decoupled`. Na main, rode o comando acima e compare os CSVs versionados.

## Capacidades e fallback

Uma tentativa significa uma chamada ao provider por deployment. Chamadas roteadas repetem uma vez falhas HTTP 500/503/429 com backoff mínimo de 0,5 s; timeouts e outros erros não são repetidos. F2 faz uma tentativa por deployment para não substituir uma geração depois do primeiro chunk. Para os fluxos síncronos, o cliente HTTP do app encerra em 14 s. Os tempos por deployment estão no YAML do gateway.

| Capacidade | Feature | Primário | Fallback técnico (1 tentativa) | Se os large falharem | Tentativas máximas por destino |
|---|---|---|---|---|---:|
| `ticket-classification` | F1 Classificação | `gpt-fake-large` (OpenAI) | `claude-fake-large` (Anthropic) | `gpt-fake-mini`; mesma saída observada | 2 |
| `reply-suggestion` | F2 Sugestão | `claude-fake-large` (Anthropic) | `gpt-fake-large` (OpenAI) | `gpt-fake-mini` antes do primeiro chunk; resposta mais curta. Após iniciar SSE, erro vira evento `error`. | 1 |
| `ticket-topics` | F3 Relatório | `claude-fake-large` (Anthropic) | `gpt-fake-large` (OpenAI) | `gpt-fake-mini`; sumarização de lotes. Se ambos providers estiverem indisponíveis, job fica `failed` com motivo. | 2 |
| `order-extraction` | F4 Extração | `gpt-fake-large` (OpenAI) | `claude-fake-large` (Anthropic) | HTTP 502; mini não é usado porque extrai pedido errado e perde produto. | 2 |

Cada fallback técnico é equivalente, entre providers, por contrato do provider fake. A política de modelo fraco por feature tem evidências e decisão em [ADR 0012](docs/adr/0012-definir-fallback-e-qualidade-por-feature.md). Para sugestões, a app tenta capacidades lógicas pela ordem da tabela apenas antes de enviar o primeiro chunk; o gateway não pode mascarar erro de um stream iniciado.

### Resultado quando nenhum modelo large está disponível

| Feature | Se mini estiver disponível | Se mini também falhar |
|---|---|---|
| F1 Classificação | HTTP 200 com classificação do mini | HTTP 502 explícito |
| F2 Sugestão | HTTP 200 SSE, texto menor e `event: end`, se falha ocorrer antes do primeiro chunk | HTTP 200 SSE com `event: error`; se o stream já começou, a mesma falha explícita encerra a transmissão |
| F3 Relatório | Consulta de estado retorna 303 para resultado; resultado HTTP 200 | Estado HTTP 200 `failed`, com motivo, em até 60 s |
| F4 Extração | Mini nunca é tentado | HTTP 502 explícito; nenhuma extração insegura |

## Fluxos pela borda

### F1 — Classificar ticket (síncrono)

```sh
curl -i -X POST localhost:8000/tickets/classification -H 'Content-Type: application/json' -d '{"ticket_id":"TK-00042","text":"Meu pedido #481516 não chegou e já passou do prazo, urgente"}'
```

Retorna o objeto completo com `ticket_id`, `category` e `priority`. A medição local normal foi 1,10 s. Com o modelo primário em `timeout`, o equivalente respondeu em 6,12 s. Para um erro HTTP 500, houve duas tentativas no primário separadas por 0,65 s; o fallback concluiu a chamada em 3,566 s. Nenhuma resposta foi 504.

### F2 — Sugerir resposta (SSE)

```sh
curl -N -X POST localhost:8000/tickets/reply-suggestion -H 'Content-Type: application/json' -d '{"ticket_id":"TK-00042","text":"Meu pedido #481516 não chegou e já passou do prazo, urgente"}'
```

Cada `data` contém um fragmento `chunk`; sucesso termina em `event: end`. O primeiro trecho medido chegou em 0,874 s. Para verificar erro no meio do stream, configure `anthropic/claude-fake-large` como `midstream_error` no endpoint `/admin/failures`; o cliente recebe `event: error` com a mensagem `A geração foi interrompida`.

```sh
curl -X POST localhost:8090/admin/failures -H 'Content-Type: application/json' -d '{"provider":"anthropic","model":"claude-fake-large","mode":"midstream_error"}'
curl -N -X POST localhost:8000/tickets/reply-suggestion -H 'Content-Type: application/json' -d '{"ticket_id":"TK-00042","text":"Meu pedido #481516 não chegou e já passou do prazo, urgente"}'
curl -X POST localhost:8090/admin/reset
```

### F3 — Relatório de temas (request-reply)

```sh
curl -i -X POST localhost:8000/reports/topics -H 'Content-Type: application/json' -d '{"start":"2026-08-01","end":"2026-08-31"}'
```

Guarde o caminho do cabeçalho `Location` e consulte-o repetidamente:

```sh
curl -i localhost:8000/reports/topics/status/<id>
```

Enquanto processa, recebe 200 com `pending`/`running`; em falha, 200 com `state=failed` e motivo; quando conclui, recebe 303 para `/reports/topics/<id>`. O browser/curl pode seguir o redirecionamento para obter o corpo final. O período de agosto retorna 5.000 tickets; o POST medido foi 0,013 s e a conclusão 21,08 s.

### F4 — Extrair dados do pedido (síncrono)

```sh
curl -i -X POST localhost:8000/tickets/extraction -H 'Content-Type: application/json' -d '{"ticket_id":"TK-00042","text":"Meu pedido #481516 do mouse sem fio não chegou"}'
```

Retorna `order_number` no formato `#` + seis dígitos e `product` ou `null`. Se os dois destinos large falharem, a resposta é 502 explícita e não há tentativa mini.

## Troca de modelo físico

1. Edite apenas o modelo e o endpoint correspondentes no `gateway/config.yaml`, mantendo o alias lógico.
2. Reinicie só o gateway: `docker compose restart gateway` (aguarde ficar saudável com `docker compose ps`).
3. Compare o container do app antes/depois (`docker compose ps app`) e faça uma chamada pela borda.
4. Confirme em `curl -s localhost:8090/admin/calls` que `/admin/calls` registrou o novo provider/modelo. Nenhum rebuild/restart do app é necessário.

Prova executada nesta versão: alterei temporariamente `ticket-classification` de `gpt-fake-large` para `gpt-fake-mini`, usei `docker compose restart gateway` e a chamada seguinte apareceu em `/admin/calls` como `openai/gpt-fake-mini`. O ID do container `app` permaneceu igual; depois restaurei o YAML original e reiniciei apenas o gateway.

## Roteiro de governança

Use no ambiente local com master key padrão `sk-litellm-gateway-dev`. Chaves temporárias de exemplo devem ter pelo menos 16 caracteres.

```sh
curl -s -X POST localhost:8090/admin/reset
curl -s -X POST localhost:4000/key/generate -H 'Authorization: Bearer sk-litellm-gateway-dev' -H 'Content-Type: application/json' -d '{"key":"sk-budget-probe-key-0001","models":["ticket-classification"],"max_budget":0.000001,"budget_duration":"monthly"}'
curl -i -X POST localhost:4000/v1/chat/completions -H 'Authorization: Bearer sk-budget-probe-key-0001' -H 'Content-Type: application/json' -d '{"model":"ticket-classification","messages":[{"role":"user","content":"TASK: classify\nurgente"}]}'
curl -s localhost:8090/admin/calls
curl -i -X POST localhost:4000/v1/chat/completions -H 'Authorization: Bearer sk-budget-probe-key-0001' -H 'Content-Type: application/json' -d '{"model":"ticket-classification","messages":[{"role":"user","content":"TASK: classify\nurgente"}]}'
curl -s localhost:8090/admin/calls

curl -s -X POST localhost:4000/key/generate -H 'Authorization: Bearer sk-litellm-gateway-dev' -H 'Content-Type: application/json' -d '{"key":"sk-rpm-probe-key-0001","models":["ticket-classification"],"rpm_limit":1}'
curl -i -X POST localhost:4000/v1/chat/completions -H 'Authorization: Bearer sk-rpm-probe-key-0001' -H 'Content-Type: application/json' -d '{"model":"ticket-classification","messages":[{"role":"user","content":"TASK: classify\nurgente"}]}'
curl -s localhost:8090/admin/calls
curl -i -X POST localhost:4000/v1/chat/completions -H 'Authorization: Bearer sk-rpm-probe-key-0001' -H 'Content-Type: application/json' -d '{"model":"ticket-classification","messages":[{"role":"user","content":"TASK: classify\nurgente"}]}'
curl -s localhost:8090/admin/calls

curl -s -X POST localhost:4000/key/delete -H 'Authorization: Bearer sk-litellm-gateway-dev' -H 'Content-Type: application/json' -d '{"keys":["sk-budget-probe-key-0001","sk-rpm-probe-key-0001"]}'
curl -s -X POST localhost:8090/admin/reset
```

Para cada chave, a primeira chamada chega ao provider. A segunda deve retornar 429 por orçamento ou RPM, e a lista de `/admin/calls` deve manter a mesma contagem antes/depois da recusa. A suíte automatizada executa as mesmas provas com chaves temporárias aleatórias e as exclui.

## Mapa de decisões

| ADR | Nível | Resumo |
|---|---|---|
| [0001](docs/adr/0001-mapear-instabilidade.md) | software | Medir estabilidade e priorizar módulos de feature. |
| [0002](docs/adr/0002-inverter-dependencia-do-provider.md) | solução | Inverter dependência do provider por ports/adaptadores. |
| [0003](docs/adr/0003-manter-o-dominio-no-centro.md) | software | Manter contratos de domínio independentes dos SDKs. |
| [0004](docs/adr/0004-isolar-arquivo-e-politica-do-relatorio.md) | software | Isolar repositório de tickets e caso de uso do relatório. |
| [0005](docs/adr/0005-compor-dependencias-no-ponto-de-entrada.md) | solução | Concentrar composição no ponto de entrada. |
| [0006](docs/adr/0006-consenso-de-refatoracao-para-estabilidade.md) | solução | Consolidar estrutura e gates de teste/métrica. |
| [0007](docs/adr/0007-provisionar-login-da-admin-ui.md) | solução | Justificar PostgreSQL exigido pela sessão da Admin UI. |
| [0008](docs/adr/0008-decidir-politicas-por-feature.md) | solução | Simular discussões e decidir execução e qualidade por feature. |
| [0009](docs/adr/0009-proteger-fluxos-operacionais-de-ia.md) | corporativa | Proteger acesso, custo e estabilidade operacional da IA. |
| [0010](docs/adr/0010-mapear-capacidades-no-gateway.md) | solução | Mapear aliases e deployments no LiteLLM. |
| [0011](docs/adr/0011-escolher-execucao-por-feature.md) | solução | Definir sync, SSE e request-reply pelos contratos. |
| [0012](docs/adr/0012-definir-fallback-e-qualidade-por-feature.md) | solução | Declarar fallback técnico e modelo fraco por feature. |
| [0013](docs/adr/0013-limitar-acesso-custo-e-tentativas.md) | software | Aplicar chaves, preço, budget, RPM, timeout e retry limitado. |
| [0014](docs/adr/0014-interpretar-metrica-de-acoplamento.md) | software | Interpretar Main Sequence e exceção `schemas`. |
