# 0010. Mapear capacidades lógicas no gateway

- Status: aceita
- Data: 2026-11-16
- Nível: solução

## Contexto

Os nomes físicos `gpt-fake-*` e `claude-fake-*` variam com provider, tamanho e custo. O código da aplicação precisa chamar somente capacidades estáveis, e a troca de deployment deve exigir reinício do gateway. Credenciais físicas não devem chegar ao app.

## Opções consideradas

1. Manter nomes físicos no app e parametrizar por variável de ambiente.
2. Definir aliases por capacidade no LiteLLM e configurar deployments e fallbacks no gateway.
3. Criar uma interface de gateway customizada e uma configuração de mapeamento no app.

## Decisão

Adotar a opção 2. O app chama `ticket-classification`, `order-extraction`, `reply-suggestion` e `ticket-topics`. O arquivo `gateway/config.yaml` associa aliases aos modelos físicos, endpoints, preços, timeouts e alvos técnicos/mini. Para chamadas roteadas, o proxy repete uma vez somente falhas HTTP 500/503/429, com backoff; não repete timeout nem erro desconhecido. Cada destination recebe no máximo duas tentativas, com até dois fallbacks. F2 substitui a repetição automática por uma tentativa por deployment para preservar a fronteira do stream.

## Consequências

Uma troca física altera apenas `gateway/config.yaml`, seguida de recriação do serviço `gateway`. Sugestão usa fallback explícito na aplicação para poder encerrar um stream já iniciado com o evento de erro exigido; cada chamada continua usando um alias lógico do gateway e `disable_fallbacks` evita uma segunda tentativa invisível do proxy.

## Evidência

`rg -n 'gpt-fake|claude-fake' app/` e a busca por chaves de provider na árvore do app devem retornar vazio. O roteiro de troca e validação por `/admin/calls` está no README.
