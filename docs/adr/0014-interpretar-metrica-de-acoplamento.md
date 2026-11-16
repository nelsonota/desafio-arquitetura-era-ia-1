# 0014. Interpretar a métrica sem distorcer o desenho

- Status: aceita
- Data: 2026-11-16
- Nível: software

## Contexto

O enunciado fixa Ca, Ce, I, A e D e classifica zona de dor quando, simultaneamente, A < 0,5, I < 0,5 e D >= 0,5. Os dados exigem comparação de v1, v2 e main, sem ajustar a fórmula ao resultado.

## Opções consideradas

1. Otimizar todos os valores D por meio de classes abstratas artificiais.
2. Aplicar a fórmula sem exceções ou interpretação dos papéis.
3. Manter a régua fixa, explicar módulos estáveis por natureza e excluir composição da exceção proibida para gateway/features.

## Decisão

Adotar a opção 3. `schemas` representa contratos de valor concretos e estáveis, com A=0 e I=0; é a única exceção de zona de dor. `main` é raiz de composição e é interpretado como coordenador; isso não o torna exceção a um módulo de feature. O cliente HTTP de gateway e os quatro módulos de feature não podem ser exceção. A Main Sequence é a diagonal A+I=1 no gráfico I (x) × A (y), e D=|A+I-1|.

## Consequências

O script e o grafo devem ser idênticos entre as três saídas. Alterações nos imports para melhorar métrica sem justificativa arquitetural são proibidas. A exceção de `schemas` deve aparecer nos gráficos e na leitura do README.

## Evidência

`metrics/measure.py` implementa a régua e grava cabeçalho `component,ca,ce,i,a,d`; comparar os CSVs de cada versão e revisar `metrics/results/main.csv`.
