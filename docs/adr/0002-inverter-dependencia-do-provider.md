# 0002. Inverter a dependência do provider

- Status: aceita
- Data: 2026-11-16
- Nível: solução

## Contexto

Na rodada 2, AS perguntou: “Que dependências tornam as features instáveis?” A EM observou que `classification`, `extraction` e `suggestion` importam `config`, `llm` e `schemas`; `report` também importa `tickets`. A linha de base dá Ce=3 para as três primeiras features e Ce=4 para `report`; cada uma tem Ca=1.

RH perguntou: “A troca de SDK e provider deveria exigir alterar regras de negócio?” No código atual, `llm.py` instancia os SDKs oficiais, e features escolhem modelos concretos por constantes em `config.py`. Isso acopla o fluxo de negócio aos detalhes do provider.

## Opções consideradas

1. Manter chamadas diretas e apenas mover nomes de modelo para variáveis de ambiente.
2. Definir contratos internos (ports) para capacidades de IA e fornecer adaptadores concretos fora das features.
3. Fazer cada feature instanciar um cliente SDK próprio.

## Decisão

Escolhemos a opção 2. Criar um módulo interno de contratos, por exemplo `ports.py`, com um protocolo de gateway que represente as operações necessárias. As features dependerão desse protocolo e dos schemas de domínio, não dos SDKs, credenciais, URLs ou nomes físicos dos modelos. A implementação concreta de chamada será um adaptador de infraestrutura.

A meta é reduzir Ce das features removendo dependências de `config` e `llm`; o efeito em I será calculado depois, pois I também depende de Ca e do grafo total.

## Consequências

Será necessário injetar a implementação do gateway nas funções/serviços de feature, e `main` ou um módulo de composição construirá as dependências. Protocolos são abstrações segundo a régua do enunciado. A proposta aumenta o número de peças e exige testes que validem o mesmo comportamento.

## Evidência

O código atual está em `app/helpdesk/llm.py`, `config.py` e nos módulos de feature. Depois da implementação, conferir que as features não importam SDKs, `config` nem o adaptador concreto; comparar Ce/I com uma nova saída do script de `metrics/measure.py`.

## Discussão — rodada 2

**AS perguntou:** “Qual mudança reduz dependência de detalhes voláteis sem espalhar mais lógica?”

**EM respondeu:** “Uma interface interna permite que as features dependam de um contrato estável. A fórmula não garante redução de I só por haver uma interface: precisamos medir o grafo após a mudança.”

**RH perguntou:** “Configuração de modelo basta?”

**AS respondeu:** “Não. Configuração remove nomes concretos do código, mas os módulos de feature ainda conhecem os formatos dos SDKs e as funções de transporte.”

**Consenso da rodada:** introduzir ports e adaptadores; tratar a queda de I como hipótese a verificar, não como resultado presumido.
