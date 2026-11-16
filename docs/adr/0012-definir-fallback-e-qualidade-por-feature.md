# 0012. Definir fallback e qualidade por feature

- Status: aceita
- Data: 2026-11-16
- Nível: solução

## Contexto

Os modelos `large` de OpenAI e Anthropic são equivalentes. O provider fake demonstra degradar qualidade em tarefas diferentes: mini extrai o número errado e não identifica produto; resposta mini tem 200–300 tokens enquanto large passa de 500; classificação tem saída igual entre tamanhos; a agregação de tópicos funciona com mini no cenário fornecido.

## Opções consideradas

1. Usar mini sempre que `large` falhar em qualquer feature.
2. Falhar qualquer chamada sem `large`.
3. Separar fallback técnico de fallback por qualidade e decidir por feature.

## Decisão

Adotar a opção 3. O gateway repete uma vez erros transitórios HTTP 500/503/429, com backoff mínimo de 0,5 s; timeout e outros erros não são repetidos. Depois tenta um deployment `large` equivalente do outro provider. F1/F3/F4 têm no máximo duas tentativas por deployment e até dois fallbacks. F2 desabilita retry/fallback automáticos na conexão e tenta cada alias uma vez antes do primeiro chunk; isso permite enviar `event: error` sem trocar o modelo depois que o cliente recebeu texto. Se os dois `large` falharem: F1 e F3 podem degradar para mini; F2 aceita mini somente antes do primeiro chunk; F4 retorna HTTP 502 e não usa mini.

## Consequências

O modelo fraco é uma decisão explícita de produto por feature. A sugestão não pode trocar de modelo depois de o cliente já ter recebido texto. A extração prioriza precisão sobre disponibilidade. `/admin/calls` permite contar tentativas e confirmar o modelo efetivamente usado.

## Evidência

`provider-fake/tests/test_provider_fake.py::test_extract_large_is_right_and_mini_is_wrong` demonstra `#605065` / `mouse sem fio` no large e `#530720` / `null` no mini. `test_suggest_large_longer_than_mini` compara os tokens de saída. `tests/acceptance/test_runtime_contracts.py` prova fallback técnico na classificação e ausência de mini na extração.
