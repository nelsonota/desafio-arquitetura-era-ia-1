# 0001. Mapear a instabilidade antes de refatorar

- Status: aceita
- Data: 2026-11-16
- Nível: software

## Contexto

Participantes: Arquiteta de software (AS), Especialista em métricas (EM) e Responsável pelo helpdesk (RH). A equipe iniciou a análise com a pergunta da AS: “Qual problema queremos resolver primeiro: acoplamento, lentidão ou indisponibilidade?”

O RH respondeu que o escopo desta discussão é aumentar a estabilidade estrutural dos módulos da aplicação. A sugestão bloqueante e a indisponibilidade do provider são sintomas relacionados, mas o alvo mensurável aqui é a métrica I definida em `teste.html`: `I = Ce / (Ce + Ca)`. Como I representa instabilidade, estabilidade maior corresponde a I menor.

A EM perguntou se deveríamos refatorar `main` primeiro porque sua instabilidade medida é a maior. A medição atual mostra `main I=1,00`, mas ele é o ponto de composição HTTP e importa as quatro features e os schemas. Tratá-lo como regra de negócio distorceria o objetivo; a primeira prioridade será os módulos de feature.

## Opções consideradas

1. Mirar a redução de I dos módulos de feature e acompanhar `main` separadamente como composição.
2. Tentar reduzir I de todos os módulos, incluindo o ponto de entrada, sem considerar seus papéis.
3. Trocar o foco para disponibilidade operacional e implementar retries/fallback.

## Decisão

Escolhemos a opção 1. A linha de base é `classification I=0,75`, `extraction I=0,75`, `suggestion I=0,75` e `report I=0,80`; `main I=1,00` será reportado, mas não é alvo primário. A meta proposta para a próxima medição é I menor que a linha de base para cada feature refatorada, sem mudar contratos externos.

## Consequências

O plano mede e compara os módulos-alvo com o mesmo script. Não alegaremos melhoria antes de executar a refatoração e gerar a medição posterior. Resiliência operacional fica fora deste ADR.

## Evidência

Linha de base: `metrics/results/v1-coupled.csv`. Reproduzir com `python metrics/measure.py app/helpdesk v1-coupled`.

## Discussão — rodada 1

**EM perguntou:** “A métrica I mede estabilidade ou instabilidade?”

**AS respondeu:** “Instabilidade. Portanto, para aumentar estabilidade precisamos reduzir I; aumentar o valor de I seria o contrário.”

**RH perguntou:** “Por que não começar pelo `main`, que tem I=1?”

**AS respondeu:** “Ele é o composition root e importa as rotas de feature. A prioridade de negócio é tornar as features menos dependentes de detalhes voláteis.”

**Consenso da rodada:** definir estabilidade como redução de I e começar pelas features, mantendo o papel de `main` explícito.
