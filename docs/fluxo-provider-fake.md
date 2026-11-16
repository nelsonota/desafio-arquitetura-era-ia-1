## Fluxo de chamadas do `provider-fake`

```mermaid
flowchart TD
    Client[SDK ou cliente HTTP] --> Route[FastAPI: endpoint]
    Route --> Record["record_call()"]
    Record --> Auth{Chave válida?}
    Auth -->|não| AuthError["finish_call: 401<br/>retorna erro do provider"]
    Auth -->|sim| Model{Modelo existe<br/>e pertence ao provider?}
    Model -->|não| ModelError["finish_call: 404<br/>retorna erro do provider"]
    Model -->|sim| Input{Entrada válida?}
    Input -->|Anthropic: max_tokens inválido| InputError["finish_call: 400"]
    Input -->|válida| Mode["mode_for(provider, model)"]
    Mode --> Generation["Generation(...)"]
    Generation --> Detect["tasks.detect(user_text)"]
    Detect --> Generate["tasks.generate(task, content, size)"]
    Generate --> Tokens["Conta tokens e aplica limite de saída"]
    Tokens --> Failure{Modo de falha?}
    Failure -->|error_500 / error_429 / timeout| FailureResponse["apply_failure()<br/>retorna erro ou aguarda timeout"]
    Failure -->|entrada excede contexto| ContextError["finish_call: 400"]
    Failure -->|normal / slow| Stream{stream?}
    Stream -->|não| Wait["gen.wait_full()"]
    Wait --> FullResponse[Resposta JSON completa]
    Stream -->|sim| Events["gen.stream()"]
    Events --> Midstream{midstream_error?}
    Midstream -->|sim| PartialError[Envia parte da resposta<br/>e evento de erro]
    Midstream -->|não| Complete[Envia resposta SSE completa]
    AuthError --> Finish["finish_call(): status e duração"]
    ModelError --> Finish
    InputError --> Finish
    ContextError --> Finish
    FailureResponse --> Finish
    FullResponse --> Finish
    PartialError --> Finish
    Complete --> Finish
```

## Inferência por API

As duas rotas de inferência seguem a mesma sequência geral: registram a chamada, validam autenticação e modelo, montam uma `Generation`, aplicam o modo de falha, conferem o limite de contexto e respondem em JSON ou SSE.

- **OpenAI** — `POST /openai/v1/chat/completions` → `openai_chat()` → valida `Authorization: Bearer ...` e modelo → extrai mensagens e opções → `Generation(...)` → resposta Chat Completions ou stream SSE no formato OpenAI.
- **Anthropic** — `POST /anthropic/v1/messages` → `anthropic_messages()` → valida `x-api-key` (ou Bearer) e modelo → exige `max_tokens` → `Generation(...)` → resposta Messages ou stream SSE no formato Anthropic.

Em `Generation.__init__()`, o conteúdo da última mensagem do usuário passa por `tasks.detect()`, que separa a linha `TASK:` do texto. `tasks.generate()` então seleciona a função correspondente: `classify()`, `suggest()`, `topics()` ou `extract()` em `tasks.py`. Se a tarefa não for reconhecida, usa `fallback_text()`.

A resposta completa espera em `Generation.wait_full()`. No modo streaming, `Generation.stream()` emite fragmentos; os endpoints os convertem para os eventos SSE específicos de cada API. Ao concluir ou falhar durante o stream, `finish_call()` atualiza status e duração da chamada registrada.

## Administração e utilitários

```mermaid
flowchart LR
    Admin[Cliente administrativo] --> Set["POST /admin/failures<br/>admin_set_failure()"]
    Set --> Validate["Valida provider, modo e modelo"]
    Validate --> Config[provider_failures / model_failures]

    Admin --> Get["GET /admin/failures<br/>admin_get_failures()"]
    Get --> Effective["mode_for(): modelo sobrepõe provider"]

    Admin --> Calls["GET /admin/calls<br/>admin_calls()"]
    Calls --> Deque[Lê chamadas recentes do deque]

    Admin --> Reset["POST /admin/reset<br/>admin_reset()"]
    Reset --> Clear[Limpa falhas e chamadas]

    Client --> Health["GET /health<br/>health()"]
```

As funções de suporte incluem `text_of()` (normaliza conteúdo), `count_tokens()` (estima tokens pelo número de caracteres), `truncate()` (limita a saída), `mode_for()` (determina a falha efetiva) e `openai_error()` / `anthropic_error()` (formatam erros conforme a API). O histórico de chamadas fica no `deque` em memória, limitado às últimas 5.000 entradas.

Arquivos principais: [main.py](/C:/src/mba/desafio-arquitetura-era-ia-1/provider-fake/app/main.py) concentra as rotas e respostas; [tasks.py](/C:/src/mba/desafio-arquitetura-era-ia-1/provider-fake/app/tasks.py) implementa as tarefas simuladas.
