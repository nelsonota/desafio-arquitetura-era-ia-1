# 0011. Escolher a execução de cada feature

- Status: aceita
- Data: 2026-11-16
- Nível: solução

## Contexto

A borda encerra uma chamada que fica 30 s sem enviar bytes. A sugestão síncrona anterior levou 15,97 s. Um relatório síncrono de 5.000 tickets excedia a paciência da borda. A extração alimenta uma automação sem revisão humana.

## Opções consideradas

1. Manter as quatro features síncronas.
2. Transmitir tudo via SSE.
3. Escolher o modo por contrato e duração.

## Decisão

Adotar a opção 3:

- **F1 Classificação:** síncrona; resultado completo normalmente em até 3 s. Em falha/timeout, usar equivalente ou devolver erro explícito em até 15 s.
- **F2 Sugestão:** SSE; o primeiro texto chega em até 1,5 s. Eventos `data: {"chunk":...}`, terminal `end` e erro em stream interrompido `error`. Fallback técnico/fraco só ocorre antes do primeiro chunk. Depois do primeiro chunk, erro não é mascarado por troca de modelo.
- **F3 Relatório:** request-reply; POST responde `202`, `Location` e `Retry-After`. Consulta retorna `pending`/`running`/`failed`; conclusão redireciona com `303` ao relatório com 5.000 tickets. Falha fica visível com motivo em até 60 s. Lotes de 150 rodam em paralelo, com no máximo 20 chamadas simultâneas.
- **F4 Extração:** síncrona; usa modelo `large` equivalente, nunca modelo mini. Se os dois deployments equivalentes falham, retorna erro explícito, pois dado incorreto aciona troca/devolução indevida.

## Consequências

F2 exige cliente SSE. F3 mantém estado em memória no processo; o desafio dispensa sobrevivência a reinício. As chamadas síncronas têm timeout HTTP de 14 s. O paralelismo de F3 precisa respeitar o limite RPM do gateway.

## Evidência

Em Compose, a evidência observada pela rede da borda: F1 normal 1,10 s; fallback após timeout do provider 6,12 s; F2 primeiro chunk 0,874 s; F3 POST `202` em 0,013 s e resultado de 5.000 tickets em 21,08 s; F3 com os providers em erro chegou a `failed` com motivo em 2,01 s. A suíte de aceitação mede os contratos.
