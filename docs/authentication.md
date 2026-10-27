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

As rotas administrativas de `/api/v1/businesses/{business_id}` exigem
autenticação e perfil `owner`. Um proprietário ou coproprietário só pode acessar
o `business_id` associado à sua própria conta. Tokens válidos usados contra
outra barbearia recebem `403 Forbidden`. O cadastro de uma empresa e as rotas
de agendamento público têm contratos separados e não concedem acesso ao painel
administrativo.

Os IDs enviados dentro da URL ou do corpo também são validados: um endereço da
própria barbearia não permite consultar ou alterar recursos de outra empresa.
Não basta esconder botões na interface; a autorização acontece na API.

Para o perfil de barbeiro, o profissional vinculado deve estar ativo e pertencer
à mesma barbearia da conta. Essa regra é verificada ao entrar e em cada
requisição autenticada. As ações de atendimento também exigem que o agendamento
pertença ao profissional e à barbearia autenticados.

O coproprietário pode operar sua barbearia, mas não pode gerenciar a conta do
proprietário principal. A exclusão de acessos de coproprietários exige a conta
principal e a confirmação da senha atual.

## Revisão automatizada de isolamento

Em 26 de outubro de 2026, a revisão local acrescentou
`tests/test_tenant_isolation.py`, com testes HTTP usando duas empresas fictícias
e repositórios simulados. A suíte verifica:

- rejeição de acessos anônimos, proprietários de outra empresa, coproprietários
  de outra empresa e barbeiros em todas as operações administrativas existentes;
- acesso permitido à lista de clientes da própria empresa para proprietário e
  coproprietário;
- rejeição de IDs de despesas, serviços, clientes e atendimentos de outra empresa
  mesmo quando o `business_id` da URL pertence à conta;
- bloqueio da alteração de atendimento de outro profissional;
- bloqueio de tokens revogados, contas inativas, profissionais inativos e
  vínculos entre conta e profissional de empresas diferentes;
- rejeição desse vínculo inconsistente também no login;
- proteção da conta principal contra alteração pelo coproprietário.

Essa revisão não modifica dados de produção. O checklist de homologação com duas
empresas deve permanecer pendente até a validação com banco e contas isolados no
ambiente de homologação.

## Homologação com PostgreSQL real

Com o Docker Desktop aberto e as dependências de desenvolvimento instaladas,
execute no ambiente Python do projeto:

```powershell
.\.venv-codex\Scripts\python.exe .\scripts\test_tenant_isolation.py
```

O programa cria um PostgreSQL 16 temporário, acessível apenas por `127.0.0.1`,
aplica as migrações Alembic e testa a API com duas empresas e seis contas
fictícias. As requisições passam por login, JWT, autorização, serviços e
repositórios reais, sem substituir dependências. São conferidos clientes,
financeiro, auditoria, contas administrativas e agenda, incluindo a preservação
dos registros após tentativas de alteração indevidas e a confirmação legítima
de um atendimento.

O programa gera credenciais exclusivas para o teste e desativa entregas de e-mail,
Discord e IA no processo filho. O banco não usa volumes e seu container é
removido ao final, mesmo quando uma verificação falha. O programa não aceita uma
URL de banco de produção como argumento.

O job independente `tenant-isolation` do CI repete a homologação em um serviço
PostgreSQL descartável do GitHub Actions. Seus valores de autenticação são
exclusivos desse serviço temporário. A execução normal de `pytest` pula essa
verificação quando o banco de integração não está explicitamente configurado.
