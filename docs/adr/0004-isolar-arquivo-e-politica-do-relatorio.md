# 0004. Isolar leitura de tickets e política do relatório

- Status: aceita
- Data: 2026-11-16
- Nível: software

## Contexto

Na rodada 4, AS perguntou: “`report` tem uma dependência que não é IA; essa dependência também afeta a estabilidade?” `report.py` importa `tickets.py`, que abre o caminho configurado em `config.py` e interpreta JSONL. Além disso, `report.topics()` combina validação temporal, carregamento, divisão em lotes, chamada LLM e agregação.

EM destacou que `report` tem `Ce=4`, `Ca=1`, `I=0,80`. RH perguntou se mudar o formato/armazenamento de tickets deveria exigir reescrever agregação ou chamada de tópicos.

## Opções consideradas

1. Deixar `report` acessar arquivo e provider diretamente.
2. Definir uma porta de leitura de tickets e separar o caso de uso de relatório do adaptador de armazenamento e do gateway de IA.
3. Criar um sistema genérico de jobs e repositórios para todas as entidades, embora só o relatório precise disso hoje.

## Decisão

Escolhemos a opção 2, no menor escopo necessário. `report` receberá contratos para leitura dos tickets e geração de tópicos; um adaptador de arquivo implementará a leitura atual do JSONL e outro adaptador fará a chamada via gateway. O caso de uso continuará responsável por validar período, lotear entradas e agregar resultados.

## Consequências

`report` não dependerá de `tickets.py`, `config.py` nem de SDKs concretos. A composição concreta seleciona o adaptador JSONL existente e o gateway. Não introduzimos fila, banco ou abstração genérica de persistência sem requisito.

## Evidência

Após a implementação, verificar imports de `report.py`, executar teste de caracterização de `/reports/topics` e medir `report` novamente. O tempo total e o contrato de saída devem ser avaliados separadamente da métrica I.

## Discussão — rodada 4

**AS perguntou:** “Como reduzir a dependência de `report` sem transformar a refatoração em plataforma?”

**RH respondeu:** “Preciso que o relatório continue lendo os mesmos 5.000 tickets e devolvendo a mesma estrutura; não há requisito atual de trocar para banco.”

**EM perguntou:** “Vale criar uma camada genérica de repositório para isso?”

**AS respondeu:** “Não. Uma porta pequena para leitura e um adaptador JSONL bastam. Generalizar além do uso atual cria componentes sem evidência de valor.”

**Consenso da rodada:** inverter a leitura de tickets e a chamada LLM apenas no fluxo de relatório, mantendo o loteamento e a agregação no caso de uso.
