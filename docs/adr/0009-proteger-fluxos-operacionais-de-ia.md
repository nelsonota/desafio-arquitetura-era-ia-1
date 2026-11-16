# 0009. Proteger os fluxos operacionais de IA

- Status: aceita
- Data: 2026-11-16
- Nível: corporativa

## Contexto

O helpdesk executa classificação, sugestão de resposta, relatório e extração de pedidos. Falha e latência de um fornecedor não podem derrubar todos os usos nem produzir dados incorretos na automação de devolução. O enunciado exige prova por chamada observada, limite de tentativas, recusa por orçamento e RPM e contratos adequados ao usuário.

## Opções consideradas

1. Permitir que cada feature integre diretamente com o fornecedor e trate falhas à sua maneira.
2. Centralizar política de acesso e roteamento no gateway, mantendo decisão de experiência ligada ao contrato de cada feature.
3. Tratar todas as features como chamadas síncronas idênticas.

## Decisão

Adotar a opção 2. Credenciais de fornecedores, preços, orçamento, RPM, timeout e roteamento ficam no gateway. Cada feature recebe um modo e uma política de qualidade própria, declarados em ADRs e verificáveis pela borda e por `/admin/calls`. O app recebe uma chave virtual limitada; a master key não é usada por chamadas normais da aplicação.

## Consequências

É necessário provisionar uma chave virtual, registrar custos por token para o provider simulado e manter testes de falha. `provider-fake`, `edge` e `data` continuam como dependências externas imutáveis. Alterações futuras em modo de execução exigem revisar os contratos do consumidor e a prova de latência.

## Evidência

`compose.yaml` provisiona a chave app com `max_budget=10` e `rpm_limit=120`. `gateway/config.yaml` define preços, timeout, retries e destinos. `tests/acceptance/test_runtime_contracts.py` verifica falhas, políticas por feature e governança.
