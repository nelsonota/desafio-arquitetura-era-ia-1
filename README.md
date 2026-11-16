# Helpdesk: diagnóstico da v1

A aplicação recebida usa FastAPI e chama diretamente dois SDKs. Esta etapa preserva o código original e registra sua linha de base; não há gateway nem fallback implementados ainda.

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
