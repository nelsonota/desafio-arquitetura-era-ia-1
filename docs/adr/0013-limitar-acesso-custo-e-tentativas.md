# 0013. Limitar acesso, custo e tentativas no gateway

- Status: aceita
- Data: 2026-11-16
- Nível: software

## Contexto

Sem custo configurado, orçamento por chave não consegue comparar o uso com um teto. Sem RPM, uma degradação do provider pode multiplicar chamadas. Uma chave master compartilhada com o app ampliaria o impacto de vazamento.

## Opções consideradas

1. Usar master key no app e depender apenas de limites de provider.
2. Provisionar chave virtual de aplicação, informar custos do fake e fixar limites e tentativas.
3. Deixar orçamento e RPM como configuração manual não verificada.

## Decisão

Adotar a opção 2. O gateway gera de modo idempotente a chave `GATEWAY_APP_KEY`, escopada às quatro capacidades primárias e seus aliases de fallback, com orçamento de USD 10/mês e 120 RPM. A master key autentica chamadas administrativas de provisionamento e governança. O app recebe só a chave virtual. Preços correspondem ao README do provider fake. `router_settings` limita retries a uma repetição em HTTP 500/503/429, com backoff de pelo menos 0,5 s; timeouts não são repetidos. Há no máximo dois fallbacks e timeouts por deployment (5 s classificação, 10 s extração, 20 s tópicos, 55 s streaming). F2 pede explicitamente zero retries/fallbacks automáticos no stream.

## Consequências

O orçamento é recontado pelo LiteLLM/PostgreSQL; chave virtual depende do banco da Admin UI. Testes de orçamento e RPM criam chaves temporárias e as removem em `finally`. O timeout de classificação permite failover equivalente após uma falha de até 5 s e mantém o caminho testado abaixo de 15 s. Timeout total do socket do app permanece 14 s para as rotas síncronas.

## Evidência

`tests/acceptance/test_runtime_contracts.py::test_gateway_budget_and_rpm_rejections_never_reach_provider` confirmou HTTP 429 nos dois casos e contagem inalterada em `/admin/calls`. `/key/info` autentica a chave de app antes de marcar o gateway saudável.
