# Helpdesk: linha de base v1 e refatoração v2

A linha de base v1 usava FastAPI e chamava diretamente dois SDKs. As medições e o diagnóstico abaixo registram esse estado. A aplicação atual implementa a v2 desacoplada: casos de uso dependem de ports, adaptadores ficam na infraestrutura e toda chamada de modelo passa pelo serviço self-hosted `gateway`.

## Arquitetura v2 desacoplada

`app/helpdesk/ports.py` declara `TextGenerationGateway` e `TicketRepository`. As features recebem essas dependências; `main.py` compõe o cliente HTTP do gateway e o repositório JSONL. `app/helpdesk/adapters/gateway_client.py` é o único componente da aplicação que chama o gateway. O serviço `gateway` usa LiteLLM Proxy com o mapeamento versionado em `gateway/config.yaml`; as chaves dos providers ficam somente no ambiente do LiteLLM e do `provider-fake`.

As capacidades lógicas são `ticket-classification`, `order-extraction`, `reply-suggestion` e `ticket-topics`. Para trocar um modelo físico, altere o modelo correspondente em `gateway/config.yaml` e recrie somente o serviço `gateway`:

```sh
docker compose up -d --build gateway
```

O app recebe apenas `GATEWAY_API_KEY` e `GATEWAY_URL`; as variáveis `FAKE_OPENAI_KEY` e `FAKE_ANTHROPIC_KEY` são injetadas no gateway e no provider-fake. `LITELLM_MASTER_KEY` autentica as chamadas da aplicação ao proxy. O Compose define um valor local padrão, ou você pode defini-lo em `.env`.

Para reproduzir a medição da v2:

```sh
python metrics/measure.py app/helpdesk v2-decoupled
```

O fluxo atualizado está em [docs/fluxo-helpdesk.md](docs/fluxo-helpdesk.md). A suíte de caracterização não foi alterada.

## Como rodar

```sh
cp .env.example .env
docker compose up -d --build --wait
python tests/run_characterization.py
python metrics/measure.py app/helpdesk v1-coupled
```

No Windows, use `Copy-Item .env.example .env` no lugar de `cp`. A suíte usa a borda `edge` dentro da rede Compose, com a mesma configuração exposta em `localhost:8000`. O script de medição aceita o diretório `app/helpdesk` de outro checkout e o nome de saída; escreve CSV e SVG em `metrics/results/`. Para reproduzir a tag, por exemplo: `python metrics/measure.py ../v1/app/helpdesk v1-coupled`.

## Diagnóstico da v1

Medições realizadas com o Compose original. As chamadas abaixo usam `curl` e JSON; `/admin/calls` registra a evidência. Reinicie o estado com `curl -X POST localhost:8090/admin/reset` antes de cada experimento.

1. **Relatório mensal:** `curl -i -X POST localhost:8000/reports/topics -H 'Content-Type: application/json' -d '{"start":"2026-08-01","end":"2026-08-31"}'` retornou **504 em 30,03 s**. `GET localhost:8090/admin/calls` mostrou chamadas `anthropic/claude-fake-large`, `task=topics`, `stream=false`, com lotes já concluídos em ~9,8 s e outras ainda em andamento após o 504. Causa: `app/helpdesk/report.py` processa lotes sequencialmente e `main.py` mantém a resposta síncrona; a borda fecha a conexão após 30 s sem bytes. O trabalho continua após a desistência da borda.
2. **Sugestão bloqueante:** `curl -i -X POST localhost:8000/tickets/reply-suggestion -H 'Content-Type: application/json' -d '{"ticket_id":"TK-00042","text":"Meu pedido #481516 não chegou e já passou do prazo, urgente"}'` retornou **200 em 15,97 s**, com a resposta inteira no corpo. Em `/admin/calls`, `anthropic/claude-fake-large`, `task=suggest`, `stream=false`, status 200, 606 tokens de saída e duração 15.951 ms. `suggestion.py` aguarda `llm.call_anthropic`, que não solicita streaming.
3. **Provider indisponível:** `curl -X POST localhost:8090/admin/failures -H 'Content-Type: application/json' -d '{"provider":"openai","mode":"error_500"}'`, seguido de `curl -i -X POST localhost:8000/tickets/classification -H 'Content-Type: application/json' -d '{"ticket_id":"TK-00042","text":"urgente"}'`, retornou **500 em 1,26 s**. `/admin/calls` mostrou tentativas `openai/gpt-fake-large`, `task=classify`, status 500; não houve fallback. `classification.py` chama OpenAI diretamente por `llm.py`; `extraction.py` depende do mesmo provider. Restaure com `curl -X POST localhost:8090/admin/reset`.
4. **Troca de modelo:** `rg 'MODEL = ' app/helpdesk/config.py` mostra os quatro nomes físicos fixos no código. `classification.py`, `suggestion.py`, `report.py` e `extraction.py` usam essas constantes; `app/Dockerfile` copia `helpdesk` para a imagem. Assim, trocar o modelo exige editar a constante e reconstruir/recriar a aplicação (`docker compose up -d --build app`). Esta conclusão é inspeção do código e da imagem, não uma troca medida em execução.

## Métrica da v1

A análise estática conta módulos Python, dependências internas distintas e classes abstratas conforme a régua do desafio. O resultado está em `metrics/results/v1-coupled.csv` e `metrics/results/v1-coupled.svg`. `llm` tem Ca=4, Ce=1, I=0,2, A=0 e D=0,8; `config` tem Ca=6 e D=1; `schemas` tem Ca=5 e D=1. A interpretação e as exceções arquiteturais serão decididas junto da refatoração; as medições de v2 e da versão final dependem dessas etapas posteriores.
