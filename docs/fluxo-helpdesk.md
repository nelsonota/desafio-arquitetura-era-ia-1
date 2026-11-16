# Fluxo da aplicação helpdesk — v2 desacoplada

## Fluxo geral

```mermaid
flowchart TD
    Client[Cliente HTTP] --> FastAPI[FastAPI: helpdesk.main]
    FastAPI --> Routes[Rotas HTTP e composição]
    Routes --> Feature{Caso de uso}

    Feature --> Classify[classification.classify]
    Feature --> Suggest[suggestion.suggest]
    Feature --> Extract[extraction.extract]
    Feature --> Report[report.topics]

    Classify --> Port[TextGenerationGateway]
    Suggest --> Port
    Extract --> Port
    Report --> Port
    Report --> RepoPort[TicketRepository]

    Port --> GatewayClient[adapters.gateway_client.HttpGatewayClient]
    RepoPort --> FileAdapter[adapters.ticket_file_repository.JsonlTicketRepository]

    GatewayClient --> Gateway[AI Gateway: POST /v1/generate]
    Gateway --> Mapping[Nome lógico para provider/modelo físico]
    Mapping --> FakeProvider[provider-fake]
    FileAdapter --> JSONL[/data/tickets.jsonl]
```

## Caminhos por endpoint

- **`GET /health`** → `main.health()` → retorna `{"status": "ok"}`.
- **`POST /tickets/classification`** → `main.classify_ticket()` → `classification.classify(ticket, gateway)` → `TextGenerationGateway.generate("ticket-classification", "classify", text)` → adaptador HTTP → gateway → valida JSON, categoria e prioridade → `Classification`.
- **`POST /tickets/reply-suggestion`** → `main.suggest_reply()` → `suggestion.suggest(ticket, gateway)` → `generate("reply-suggestion", "suggest", text)` → adaptador HTTP → gateway → `ReplySuggestion`.
- **`POST /tickets/extraction`** → `main.extract_order_data()` → `extraction.extract(ticket, gateway)` → `generate("order-extraction", "extract", text)` → adaptador HTTP → gateway → valida JSON e formato do pedido → `OrderData`.
- **`POST /reports/topics`** → `main.topics_report()` → `report.topics(period, gateway, ticket_repository)` → valida período → `TicketRepository.in_period()` → adaptador lê e filtra JSONL → caso de uso divide em lotes de 150, chama `generate("ticket-topics", "topics", lote)` e agrega tópicos → `TopicsReport`.

## Fronteiras e configuração

`ports.py` define os contratos abstratos `TextGenerationGateway` e `TicketRepository`. Os casos de uso recebem as dependências por argumento e não importam SDKs, configurações de provider ou adaptadores concretos.

`main.py` é o ponto de composição: instancia `HttpGatewayClient` e `JsonlTicketRepository` e os passa aos casos de uso. O único componente em `app/` que envia requisições ao gateway é `adapters/gateway_client.py`.

O serviço `gateway` autentica a chave própria da aplicação, resolve capacidades lógicas conforme `gateway/config.toml` e chama OpenAI ou Anthropic no `provider-fake`. As chaves dos providers ficam no ambiente do gateway, não no serviço `app`. Trocar o modelo físico exige alterar o mapeamento do gateway; o código da aplicação continua usando as capacidades lógicas.

`schemas.py` mantém os contratos HTTP e os tipos de dados concretos. O adaptador de arquivo lê `/data/tickets.jsonl`; o caso de uso do relatório mantém validação de período, loteamento e agregação.
