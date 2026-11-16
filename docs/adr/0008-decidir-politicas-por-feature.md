# 0008. Definir políticas de execução e fallback por feature

- Status: aceita
- Data: 2026-11-16
- Nível: solução

## Contexto

O estado atual chama o gateway de forma síncrona em todas as rotas. A borda encerra respostas após 30 s sem bytes; a sugestão observada levou 15,97 s e o relatório mensal retornou 504. O provider fake documenta que `mini` classifica igual a `large`, que a sugestão mini tem 200–300 tokens contra mais de 500 do large, e que extração mini erra o número e omite o produto. A configuração atual ainda não prova retry, fallback, chave de orçamento ou limite RPM.

## Opções consideradas

1. Manter todas as features síncronas e tratar timeout como erro.
2. Aplicar um único fallback mini para todas as features.
3. Definir execução e qualidade por feature, com streaming para sugestão e request-reply assíncrono para relatório.

## Rodadas de discussão simulada

### Rodada 1 — Arquiteta de solução e engenheiro de operações

**Arquiteta:** O relatório de 5.000 tickets pode continuar síncrono com os atuais lotes de 150?

**Operações:** Não há evidência disso; o relatório mensal já excedeu a janela da borda. A resposta deve aceitar o trabalho e expor estado, sem manter a conexão aberta.

### Rodada 2 — Engenheiro de operações e responsável pela API

**Operações:** Como evitar que o cliente espere sem saber se a sugestão começou?

**API:** SSE envia o primeiro fragmento cedo e mantém o fluxo de texto. Um erro depois do primeiro fragmento deve ser um evento `error`, pois o status HTTP já não pode ser alterado.

### Rodada 3 — Responsável pela API e especialista de qualidade

**API:** Podemos usar mini em todas as indisponibilidades do modelo grande?

**Qualidade:** Não para extração: o cenário de teste entrega número e produto errados. Classificação preserva a resposta e tópicos agrupam o conjunto de teste igual; sugestão é uma degradação explícita, com resposta menor.

### Rodada 4 — Especialista de qualidade e SRE

**Qualidade:** Retry ilimitado melhoraria a chance de sucesso?

**SRE:** Não. Retry precisa de limite por destino e prazo total. Repetir falhas dentro de 30 s pode converter erros rápidos em 504; a regra deve ser configurada e verificada no gateway.

### Rodada 5 — SRE e responsável por segurança

**SRE:** O app pode autenticar usando a master key do proxy?

**Segurança:** Não para operação normal. O app deve usar chave virtual própria com orçamento e RPM; a master key fica restrita ao gateway e ao provisionamento. A configuração atual ainda injeta a master key no app, então esse ponto é uma pendência de implementação, não uma propriedade já comprovada.

### Rodada 6 — Responsável por segurança e arquiteta

**Segurança:** Qual capacidade pode usar fallback técnico?

**Arquiteta:** Capacidades equivalentes entre providers podem usar modelo grande alternativo. A extração só pode usar fallback equivalente, nunca mini. Classificação e tópicos aceitam mini como degradação de qualidade; sugestão aceita mini com conteúdo reduzido. Essa regra precisa constar no mapeamento lógico do gateway.

### Rodada 7 — Arquiteta e todos os participantes

**Arquiteta:** Há consenso sobre a fronteira de execução?

**Participantes:** Sim: classificação e extração síncronas, com resposta ou falha limitada; sugestão em SSE; relatório em request-reply assíncrono. Retry/fallback e credenciais são governados no gateway. A adoção só estará concluída quando os contratos e limites forem demonstrados por testes e chamadas administrativas.

## Decisão

Adotar a opção 3. Classificação deve retornar resultado completo normalmente em até 3 s. Extração permanece síncrona e não usa modelo fraco. Sugestão passa a SSE, com primeiro fragmento em até 1,5 s e evento terminal `end` ou `error`. Relatório recebe `202 Accepted`, `Location` e `Retry-After`; o estado termina em `failed` ou pronto, sem permanecer `running` por mais de 60 s. Toda chamada síncrona deve encerrar em até 15 s. Na data desta decisão, os contratos eram critérios de aceite; sua implementação e evidências estão em ADRs 0011–0013 e `tests/acceptance/`.

## Consequências

O cliente de sugestão precisa interpretar eventos SSE; o painel deve consultar o estado do relatório. A execução assíncrona requer armazenamento de estado e recuperação após reinício, que não podem ser satisfeitos com segurança por um dicionário em memória. O mapeamento e as chaves do LiteLLM precisam de orçamento, limite RPM, timeout e número máximo de tentativas verificáveis. Mini não é fallback aceitável para extração.

## Evidência

- `provider-fake/tests/test_provider_fake.py::test_extract_large_is_right_and_mini_is_wrong`
- `provider-fake/tests/test_provider_fake.py::test_suggest_large_longer_than_mini`
- `edge/nginx.conf`: `proxy_read_timeout 30s`
- Estado atual: `app/helpdesk/main.py` ainda expõe as quatro rotas como síncronas; `gateway/config.yaml` ainda não declara fallbacks ou `router_settings`.
