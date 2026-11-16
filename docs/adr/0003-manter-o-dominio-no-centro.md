# 0003. Manter regras e contratos de domínio no centro

- Status: aceita
- Data: 2026-11-16
- Nível: software

## Contexto

Na rodada 3, RH perguntou: “A extração de pedido e a classificação precisam saber qual provider as executou?” Não: os métodos só precisam receber o texto e obter dados estruturados. EM acrescentou que `schemas` já tem `Ca=5`, `Ce=0`, `I=0`, enquanto os módulos de feature têm `I=0,75–0,80`.

AS perguntou se deveríamos tornar `schemas` abstrato para melhorar a Main Sequence. O enunciado recomenda interpretar a métrica criticamente: tipos de valor concretos e estáveis podem naturalmente ter D alto. `schemas.py` reúne contratos Pydantic, não é uma fronteira de integração que precise de Protocol.

## Opções consideradas

1. Fazer os schemas dependerem dos adaptadores e refletirem os payloads de cada provider.
2. Manter tipos de entrada/saída independentes e colocar a tradução de provider no adaptador.
3. Introduzir abstrações artificiais nos schemas apenas para elevar A ou reduzir D.

## Decisão

Escolhemos a opção 2. Os tipos `TicketInput`, `Classification`, `ReplySuggestion`, `OrderData`, `PeriodInput`, `Topic` e `TopicsReport` permanecem contratos da aplicação. Adaptadores convertem entre esses contratos e os formatos do gateway/provider. `schemas` é aceito como módulo estável por natureza; não será alterado para otimizar a fórmula.

## Consequências

O domínio não fica preso a formatos OpenAI/Anthropic. A tradução exige código no adaptador e testes de contrato. A exceção de `schemas` deve ser declarada na leitura da métrica/ADR final, conforme o enunciado.

## Evidência

Verificar imports: `schemas.py` deve continuar sem dependência dos adaptadores e SDKs. Testes de caracterização devem continuar verificando os corpos HTTP das quatro features.

## Discussão — rodada 3

**RH perguntou:** “Se o provider mudar o formato de resposta, os schemas da API precisam mudar?”

**AS respondeu:** “Não. O adaptador traduz o formato externo para os modelos internos.”

**EM perguntou:** “`schemas` tem D=1; devemos adicionar uma classe abstrata?”

**AS respondeu:** “Não. Seria otimização artificial. O módulo já é estável (I=0) e representa valores concretos; documentamos a exceção em vez de deformar o desenho.”

**Consenso da rodada:** preservar contratos independentes e não perseguir D baixo às custas do modelo de domínio.
