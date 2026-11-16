# Plano de refatoração do helpdesk

Data de conclusão da revisão: 2026-11-16. O plano compara a tag de partida, a etapa desacoplada e a versão atual. Métrica `I` significa instabilidade; reduzir I nas features é o sinal desejado. A latência e os contratos são gates separados.

## Componentes-alvo e critérios de pronto

| Componente | Estratégia | Critério de pronto |
|---|---|---|
| `classification`, `suggestion`, `extraction` | Injetar ports e remover SDK/modelo físico das regras | Caracterização preservada na v2; I menor que a linha de base; nenhum import de adaptador |
| `report` | Separar armazenamento e gateway; processar lotes de 150 com concorrência limitada | Resposta de job em até 1 s; 5.000 tickets completos; falha visível em até 60 s; nenhuma resposta 504 |
| `adapters.gateway_client` | Concentrar chamadas HTTP OpenAI-compatíveis e chaves | Único componente de `app/` que chama o gateway; sem nome físico/provider secret; timeout síncrono de 14 s |
| `gateway/config.yaml` | Manter aliases, custo, timeout, fallback e governança fora das features | Uma tentativa por destino; troca de modelo via gateway; recusas por budget/RPM comprovadas por calls |
| `main` | Compor as features e expor SSE/request-reply | SSE com chunk inicial no prazo e erro midstream explícito; relatório request-reply |
| `schemas` | Manter modelos Pydantic concretos | Contratos de API válidos e exceção de métrica explicada |

## Estratégia e sequência

1. Reproduzir as dores de v1, preservar a aplicação original na tag `v1-coupled` e fixar os contratos HTTP por teste.
2. Fazer piloto de inversão de dependência: extrair `TextGenerationGateway`, implementar um cliente HTTP e injetá-lo na classificação; medir antes/depois e executar caracterização.
3. Revisar o plano após comparar demora, acoplamento e qualidade dos modelos mini. Não usar mini na extração.
4. Estender ports/adaptadores a todas as features, configurar LiteLLM e marcar `v2-decoupled` antes de mudar os modos de resposta.
5. Implementar fluxo síncrono, SSE e request-reply, com fallbacks, governança e testes de aceite dedicados.
6. Recalcular a métrica para v1, v2 e main; inspecionar o gráfico e reproduzir v1 desde o checkout da tag.

## Piloto e medições

O piloto concentrou chamadas em `adapters.gateway_client` e moveu seleção de deployment ao gateway. Na estrutura original, features tinham `I=0,75` (`report=0,80`); na etapa desacoplada, as quatro features medem `I=0,67`. O piloto preservou a caracterização na v2. Para o caminho de sugestão, a observação v1 foi 15,97 s com texto entregue só no fim; no fluxo SSE final, o primeiro fragmento chegou em 0,874 s. Para o relatório mensal, a v1 chegou a 504 na borda; o fluxo final aceitou o job em 0,013 s e completou os 5.000 tickets em 21,08 s. Essas medições são evidências de chamadas individuais neste Compose; não são SLA de produção.

Os CSVs `v1-coupled`, `v2-decoupled` e `main` são calculados pelo mesmo `metrics/measure.py`. A versão atual não cria abstrações artificiais para melhorar a fórmula; o único componente concreto na zona de dor é `schemas`, estável por natureza e justificado em ADR.

## Revisão justificada

A primeira hipótese de resiliência era enviar erro ao SSE em qualquer falha. A observação de `midstream_error` mostrou que o LiteLLM tentava fallback e devolvia um stream completo, contrariando o contrato que pede evento `error` após iniciar a transmissão. A implementação passou a desabilitar fallback automático apenas para cada conexão SSE e tenta capacidade técnica/fraca explicitamente antes do primeiro chunk. Depois do primeiro chunk, a conexão termina com `event: error`. F1/F3 e extração mantêm fallback roteado no gateway.

Outra revisão veio da comparação `large`/`mini`: a extração mini retornou pedido errado (`#530720` em vez de `#605065`) e produto ausente. Portanto F4 usa apenas `large` equivalente e retorna 502 se ambos falharem. A sugestão aceita saída mini menor; classificação/tópicos aceitam o modo mini segundo os testes do provider fake.

## Handoff para agente de IA

**Solicitação entregue:** implementar as decisões com o teste de caracterização e a métrica como gates; preservar `provider-fake/`, `edge/` e `data/`; usar os CSVs da tag como base; provar toda política de fallback pelo `/admin/calls`; nunca considerar teste de status suficiente sem comparar o corpo.

**Base de medição fornecida:** o script calcula Ca (dependências internas recebidas), Ce (internas de saída), `I=Ce/(Ca+Ce)`, A (proporção de classes abstratas) e `D=|A+I-1|`. Cabeçalho exigido: `component,ca,ce,i,a,d`. Zona de dor: `A<0,5`, `I<0,5`, `D>=0,5` simultaneamente.

**Resultado do handoff:** as features da v2 reduziram I de 0,75–0,80 para 0,67; F1 normal foi observado em 1,10 s; timeout do deployment primário foi resolvido em 6,12 s via equivalente; SSE mostrou primeiro chunk em 0,874 s; F3 entregou 5.000 tickets em 21,08 s; falha conjunta dos providers apareceu como estado `failed` em 2,01 s. Os contratos e governança estão cobertos por `tests/acceptance/`.

## Como validar

```sh
docker compose up -d --build --wait
docker compose exec -T -e HELPDESK_URL=http://edge app python -m unittest discover -s /tests/characterization -v
docker compose exec -T -e HELPDESK_URL=http://edge -e LITELLM_MASTER_KEY=sk-litellm-gateway-dev app python -m unittest discover -s /tests/acceptance -v
python metrics/measure.py app/helpdesk main
```
