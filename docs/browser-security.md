# Proteções HTTP e documentação em produção

Em 28/10/2026, a revisão por consultas HTTPS sem autenticação verificou a versão
`e63b8452caea6b41f753dd6c1fd63a9c34364d96` publicada no Render.

| Caminho | Resposta observada |
| --- | --- |
| `/api/v1/health` | HTTP 200, com o commit publicado em `revision` |
| `/dashboard/` | HTTP 200 |
| `/docs` | HTTP 404 |
| `/redoc` | HTTP 404 |
| `/openapi.json` | HTTP 404 |

As cinco respostas incluíram:

- `Strict-Transport-Security: max-age=31536000; includeSubDomains`.
- `X-Content-Type-Options: nosniff` e `X-Frame-Options: DENY`.
- `Referrer-Policy: strict-origin-when-cross-origin`.
- `Permissions-Policy` sem câmera, microfone, geolocalização ou pagamentos.
- Uma política CSP com scripts e conexões limitados à própria origem,
  `frame-ancestors 'none'` e `object-src 'none'`.

A CSP atual mantém `style-src 'self' 'unsafe-inline'` para compatibilidade com
os estilos da interface. Essa permissão não se estende aos scripts.

## Regressão automatizada

O teste `tests/test_production_security.py` cria a aplicação em modo de produção
e verifica as páginas acima, o redirecionamento OAuth da documentação e um caminho
inexistente. Confere que os cabeçalhos também aparecem nas respostas de erro e
que `/api/v1/auth/me` exige autenticação. As diretivas críticas da CSP são
comparadas por seus valores completos, evitando aceitar uma origem adicional
apenas porque a expressão `'self'` ainda está presente.

A documentação deve continuar fechada em produção mesmo se `DEBUG` for alterado.
Outro cenário confirma que Swagger, ReDoc e OpenAPI permanecem disponíveis no
ambiente de desenvolvimento. Não há consulta de banco, mensagem ou alteração
de conta nesses testes.

Os três novos cenários passaram localmente. A suíte completa terminou com
352 testes aprovados e 13 pulados por dependerem de Linux ou PostgreSQL.
Lint e formatação do novo teste também foram aprovados. A inclusão desses
cenários no GitHub Actions depende da publicação do commit desta etapa.

## Escopo da evidência

O comportamento publicado confirma documentação fechada e cabeçalhos presentes.
Não revela o valor real da variável `DEBUG`, a força ou exclusividade da chave JWT,
nem substitui testes de autorização ou uma revisão completa de segurança. O
Blueprint declara `DEBUG=false`; a revisão das variáveis do serviço deve ser feita
no painel de hospedagem, sem copiar segredos para relatórios.
