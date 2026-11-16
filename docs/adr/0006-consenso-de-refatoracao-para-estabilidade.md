# 0006. Refatorar as features para depender de contratos estáveis

- Status: aceita
- Data: 2026-11-16
- Nível: solução

## Contexto

Na rodada 6, AS perguntou ao grupo: “Temos consenso sobre a estrutura e sobre como provaremos estabilidade?” EM confirmou que a linha de base mede I alto nas quatro features e que a métrica não permite inferir o resultado sem recalcular o grafo. RH pediu preservar as respostas síncronas e os corpos HTTP nesta etapa, além de não adicionar serviços sem necessidade.

## Opções consideradas

1. Manter a estrutura atual e só parametrizar modelos.
2. Introduzir ports para gateway e leitura de tickets, adaptadores concretos para SDK/arquivo e composição centralizada, preservando schemas e contratos HTTP.
3. Reescrever simultaneamente os fluxos, adicionar fila e armazenamento persistente e mudar o contrato de todas as rotas.

## Decisão

O grupo concorda com a opção 2. A proposta final é:

1. Criar contratos abstratos pequenos para geração por capacidade e leitura dos tickets.
2. Fazer `classification`, `extraction`, `suggestion` e `report` dependerem desses contratos e dos schemas estáveis.
3. Mover integração do gateway/SDK, credenciais, seleção física de modelos e acesso ao arquivo para adaptadores de infraestrutura.
4. Compor implementações no bootstrap/ponto de entrada, sem container externo.
5. Manter `schemas` concreto e estável; documentar a exceção de D alto. Manter `main` como composição, sem exigir que sua I caia artificialmente.
6. Refatorar em piloto, executar testes de caracterização e medir a cada etapa. Só declarar sucesso quando o CSV posterior mostrar I menor que a linha de base nos módulos-alvo, com os testes preservando comportamento.

Não fixamos valores futuros de I porque ainda não existe implementação refatorada nem medição. A meta é reduzir dependências e confirmar o efeito no grafo medido.

## Consequências

As features ficam menos expostas à troca de provider e armazenamento; fakes podem ser injetados em testes. O custo é manter portas, adaptadores e bootstrap, e atualizar assinaturas internas. Resiliência (timeouts, retry, fallback) e mudança para streaming/assíncrono permanecem decisões separadas, exigidas em etapas próprias do desafio.

## Evidência

- Linha de base: `metrics/results/v1-coupled.csv`.
- Reproduzir linha de base: `python metrics/measure.py app/helpdesk v1-coupled`.
- Medição da implementação v2: `metrics/results/v2-decoupled.csv` e `metrics/results/v2-decoupled.svg`. `classification`, `extraction` e `suggestion` passaram de I=0,75 para I=0,67; `report` passou de I=0,80 para I=0,67. `ports` tem A=1,00 e I=0,00.
- Reproduzir medição: `python metrics/measure.py app/helpdesk v2-decoupled`.
- A suíte de caracterização passou contra o Compose atualizado: 7 testes, incluindo corpos de resposta e entradas inválidas. O script wrapper não conseguiu acessar o pipe do Docker quando executado pelo Python; os mesmos passos de cópia e `unittest discover` foram executados diretamente com `docker compose`.
- Confirmar por inspeção que os módulos de feature não importam SDKs, configuração de provider nem adaptadores concretos.
- Atualizar o plano de refatoração com medidas antes/depois do piloto, revisões e registro do handoff ao agente, como pede `teste.html`.

## Discussão — rodada 6 (consenso)

**AS perguntou:** “A proposta mantém o escopo e reduz acoplamento volátil?”

**EM respondeu:** “Sim, desde que os ports contem como abstrações na régua, os imports sejam internos e a métrica seja executada depois. A fórmula não deve ser manipulada para obter um resultado.”

**RH perguntou:** “O que fica fora desta decisão?”

**AS respondeu:** “Retries, fallback, fila e novos contratos de execução. Eles tratam resiliência e experiência, não a estabilidade estrutural que estamos decidindo aqui.”

**Consenso final:** inverter as dependências das features para contratos estáveis, concentrar adaptadores no bootstrap e exigir testes mais medição como prova, sem prometer números antes da implementação.
