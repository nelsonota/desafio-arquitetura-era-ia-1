# Fluxo da aplicação helpdesk — v2 desacoplada

## Fluxo geral

```mermaid
flowchart TD
    Client[Cliente HTTP] --> FastAPI[FastAPI: helpdesk.main]
    FastAPI --> Health["GET /health: health()"]
    FastAPI --> ClassifyRoute["POST /tickets/classification: classify_ticket()"]
    FastAPI --> SuggestRoute["POST /tickets/reply-suggestion: suggest_reply()"]
    FastAPI --> ExtractRoute["POST /tickets/extraction: extract_order_data()"]
    FastAPI --> ReportRoute["POST /reports/topics: topics_report()"]

    ClassifyRoute --> Classify["classification.classify(ticket, gateway)"]
    SuggestRoute --> Suggest["suggestion.suggest(ticket, gateway)"]
    ExtractRoute --> Extract["extraction.extract(ticket, gateway)"]
    ReportRoute --> Report["report.topics(period, gateway, ticket_repository)"]

    Classify --> GenerationPort[TextGenerationGateway]
    Suggest --> GenerationPort
    Extract --> GenerationPort
    Report --> GenerationPort
    Report --> TicketPort[TicketRepository]

    GenerationPort --> GatewayAdapter["adapters.gateway_client.HttpGatewayClient"]
    TicketPort --> FileAdapter["adapters.ticket_file_repository.JsonlTicketRepository"]

    GatewayAdapter --> Gateway["AI Gateway: POST /v1/generate"]
    Gateway --> Resolve["Resolve capability in gateway/config.toml"]
    Resolve --> Providers[provider-fake: OpenAI or Anthropic API]
    FileAdapter --> TicketsFile["/data/tickets.jsonl"]
```

## Fluxos por endpoint

- **`GET /health`** → `main.health()` → retorna `{"status": "ok"}`.
- **`POST /tickets/classification`** → `main.classify_ticket()` → `classification.classify(ticket, gateway)` → `TextGenerationGateway.generate("ticket-classification", "classify", text)` → `HttpGatewayClient` → gateway resolve o modelo configurado → interpreta o JSON e valida categoria e prioridade → retorna `Classification`.
- **`POST /tickets/reply-suggestion`** → `main.suggest_reply()` → `suggestion.suggest(ticket, gateway)` → `generate("reply-suggestion", "suggest", text)` → adaptador HTTP → gateway → retorna `ReplySuggestion`.
- **`POST /tickets/extraction`** → `main.extract_order_data()` → `extraction.extract(ticket, gateway)` → `generate("order-extraction", "extract", text)` → adaptador HTTP → gateway → interpreta o JSON e valida o formato do pedido → retorna `OrderData`.
- **`POST /reports/topics`** → `main.topics_report()` → `report.topics(period, gateway, ticket_repository)` → valida o período → `TicketRepository.in_period()` → adaptador lê e filtra o JSONL → divide os tickets em lotes de 150 → chama `generate("ticket-topics", "topics", lote)` por lote → agrega e ordena tópicos → retorna `TopicsReport`.

## Fronteiras de dependência

- `ports.py` define os contratos `TextGenerationGateway` e `TicketRepository` como `Protocol`.
- Os módulos de feature dependem dos ports e dos schemas; não importam os SDKs nem os adaptadores concretos.
- `main.py` é o ponto de composição: instancia `HttpGatewayClient` e `JsonlTicketRepository` e os injeta nos casos de uso.
- `adapters/gateway_client.py` é o único componente em `app/` que chama o gateway.
- O gateway escolhe provider e modelo físico pelo nome lógico em `gateway/config.toml`. As chaves de OpenAI e Anthropic ficam no serviço `gateway`, fora do ambiente de `app`.
- `schemas.py` mantém os contratos HTTP e os tipos de dados da aplicação. O caso de uso do relatório mantém validação, loteamento e agregação; o adaptador de arquivo faz a leitura do JSONL.
