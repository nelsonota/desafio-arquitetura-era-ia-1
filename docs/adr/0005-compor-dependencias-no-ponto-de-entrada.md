# 0005. Compor as dependências no ponto de entrada

- Status: aceita
- Data: 2026-11-16
- Nível: solução

## Contexto

Na rodada 5, EM perguntou: “Se as features deixam de importar adaptadores, quem os conecta?” `main.py` é o ponto de entrada HTTP e hoje chama módulos de feature diretamente. A linha de base o mede como `Ca=0`, `Ce=5`, `I=1,00`; isso é esperado para um componente de composição que direciona chamadas.

RH perguntou se reduzir o I de `main` deve ser critério de aceite. AS respondeu que esconder ou repartir a composição só para alterar a métrica seria uma mudança cosmética. O objetivo é que regras de negócio e infraestrutura dependam de contratos adequados, não fazer todo módulo ter I baixo.

## Opções consideradas

1. Fazer cada feature construir seu próprio adaptador.
2. Instanciar adaptadores e injetá-los no ponto de composição, mantendo `main` como raiz de composição ou delegando a um módulo explícito de bootstrap.
3. Adicionar um container de injeção de dependência externo.

## Decisão

Escolhemos a opção 2. Um único ponto de composição construirá o adaptador de gateway, o leitor de tickets e os casos de uso; rotas HTTP chamarão os casos de uso com dependências explícitas. Não adicionamos container externo sem necessidade demonstrada.

O I de `main` pode permanecer alto, pois representa dependência de componentes que coordena. O critério é manter esse acoplamento concentrado na borda e não propagá-lo aos módulos de regra de negócio.

## Consequências

O bootstrap conhece implementações concretas, como esperado. Testes poderão injetar fakes sem acessar provider ou arquivo real. A mudança de assinaturas das funções será interna; os contratos HTTP permanecem inalterados nesta fase.

## Evidência

Inspecionar a composição para confirmar que apenas o bootstrap importa adaptadores concretos. Testes de caracterização continuam passando. A medição pode mostrar `main I=1`; esse valor não invalida a decisão se as features reduzirem I e os detalhes ficarem concentrados na borda.

## Discussão — rodada 5

**EM perguntou:** “Um `main` com I=1 significa que a refatoração falhou?”

**AS respondeu:** “Não por si só. Ele deve depender das rotas e construir as implementações. O risco é as features dependerem de detalhes concretos, não o composition root coordenar o sistema.”

**RH perguntou:** “Cada feature deve criar o próprio cliente?”

**AS respondeu:** “Não. Isso espalharia configuração e dificultaria testes. Uma composição explícita permite trocar implementações e injetar fakes.”

**Consenso da rodada:** concentrar dependências concretas no bootstrap e aceitar o I alto de `main` como característica do papel de composição.
