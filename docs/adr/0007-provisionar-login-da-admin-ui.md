# 0007. Provisionar credenciais para a LiteLLM Admin UI

- Status: aceita
- Data: 2026-11-16
- Nível: solução

## Contexto

A stack usa LiteLLM Proxy e agora precisa permitir login na Admin UI com o usuário solicitado `admin` e a senha `admin`. O mecanismo de login `UI_USERNAME` / `UI_PASSWORD` do proxy registra o administrador e cria uma sessão autenticada no banco; portanto, requer uma URL PostgreSQL (`DATABASE_URL`). O Compose anterior não tinha banco.

## Opções consideradas

1. Usar apenas a master key do proxy para acesso à API e deixar a UI sem login configurado.
2. Adicionar PostgreSQL local persistente e configurar as credenciais de UI no serviço LiteLLM.
3. Trocar a UI por outra interface ou implementar autenticação própria.

## Decisão

Escolhemos a opção 2. O Compose adiciona `litellm-db` com PostgreSQL 16 Alpine e volume `litellm_db_data`. O serviço LiteLLM recebe `DATABASE_URL`, `UI_USERNAME=admin` e `UI_PASSWORD=admin`; os valores podem ser sobrescritos por `LITELLM_DB_PASSWORD`, `LITELLM_UI_USERNAME` e `LITELLM_UI_PASSWORD` no `.env`.

## Consequências

A interface pode criar e autenticar a conta de administrador e manter seu estado entre reinicializações. O banco é um serviço adicional, necessário pelo requisito de login da UI. Os valores `admin` / `admin` são credenciais locais de desenvolvimento e devem ser alterados para qualquer ambiente compartilhado.

## Evidência

`docker compose ps` deve mostrar `litellm-db` e `gateway` saudáveis. A UI fica em `http://localhost:4000/ui`; entrar com `admin` / `admin` deve abrir a LiteLLM Admin UI. `gateway` recebe o banco via `DATABASE_URL`, e os dados ficam no volume `litellm_db_data`.
