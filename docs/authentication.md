# Autenticação e isolamento por barbearia

O Projeto Osiris usa OAuth2 Password Bearer, tokens JWT HS256 com expiração e
hash Argon2 para senhas. O token contém somente o identificador do usuário; a
barbearia autorizada é carregada do banco em cada requisição.

## Criar o primeiro proprietário

Em desenvolvimento, use uma única vez `POST /api/v1/auth/bootstrap-owner`:

```json
{
  "business_id": "b932827e-a7b0-46b2-9d9e-d30419f89777",
  "email": "proprietario@exemplo.com",
  "password": "uma-senha-forte-com-12-caracteres"
}
```

A rota deixa de aceitar cadastros assim que a barbearia possui um proprietário
e não existe fora do ambiente `development`.

## Entrar pelo Swagger

Clique em **Authorize** e informe o e-mail no campo `username` e a senha no
campo `password`. O Swagger chama `POST /api/v1/auth/token` e passa o bearer
token automaticamente nas rotas protegidas.

Tokens expiram em 60 minutos por padrão. Configure `JWT_SECRET_KEY` com um valor
aleatório de pelo menos 32 bytes e nunca faça commit do arquivo `.env`.

## Isolamento

Todas as rotas com `business_id` exigem autenticação. Um proprietário só pode
acessar o `business_id` associado à sua própria conta. Tokens válidos usados
contra outra barbearia recebem `403 Forbidden`.
