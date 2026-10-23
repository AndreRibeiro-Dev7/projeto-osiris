# Logs seguros da aplicação

O Osiris envia os logs para a saída padrão do processo. Em produção, cada linha
é um objeto JSON que pode ser pesquisado diretamente no painel **Logs** do
serviço `osiris-api` no Render.

Cada requisição registra somente:

- data e hora, nível e nome do logger;
- identificador único da requisição (`request_id`);
- método HTTP e modelo da rota, sem parâmetros pessoais;
- código da resposta e duração em milissegundos.

O identificador também é devolvido no cabeçalho `X-Request-ID`. Ele permite
localizar a requisição no Render sem registrar corpo, cabeçalhos de autenticação,
endereço IP ou query string.

## Proteção de dados

O formatador central remove automaticamente e-mails, senhas, tokens Bearer,
JWTs, chaves de API, códigos de verificação e credenciais presentes em URLs. O
access log padrão do Uvicorn fica desativado para impedir que parâmetros da URL
sejam registrados fora desse filtro.

Mesmo com essa proteção, mensagens novas nunca devem incluir corpos completos,
objetos de usuário, segredos ou credenciais. Registre apenas o evento e os
identificadores técnicos necessários para investigá-lo.

## Configuração

As variáveis disponíveis são:

- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`;
- `LOG_JSON`: ativa JSON também fora de produção.

Quando `ENVIRONMENT=production`, o formato JSON é ativado automaticamente. A
configuração recomendada no Render é `LOG_LEVEL=INFO`; `DEBUG` deve ser usado
somente durante uma investigação controlada e temporária.

## Validação após o deploy

1. Abra o painel do serviço `osiris-api` no Render e entre em **Logs**.
2. Acesse `/api/v1/health` e confirme um evento `request.completed` em JSON.
3. Confira `route`, `status_code`, `duration_ms` e `request_id`.
4. Confirme que não aparecem query strings, e-mails, senhas ou tokens.
5. Copie o `request_id` da resposta e verifique que ele localiza o mesmo evento.

O item correspondente do checklist de produção só deve ser marcado depois dessa
validação no serviço publicado.
