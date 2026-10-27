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

Essa revisão não modifica dados de produção. A validação com banco e contas
isolados complementa os testes simulados, conforme o resultado registrado abaixo.

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

### Resultado da homologação

Em 26 de outubro de 2026, o proprietário executou o programa no PowerShell e
apresentou a saída completa da homologação:

- PostgreSQL temporário inicializado e todas as migrações aplicadas, da criação
  das tabelas até `3d4e5f6a7b8c` (bloqueio persistente de login);
- teste de integração aprovado: `1 passed in 5.06s`, com duas empresas e seis
  contas fictícias, passando pelos serviços e repositórios reais;
- remoção do container e do banco temporários confirmada, sem criação de volumes.

Essa execução conclui os itens de migrações em homologação, revisão de
autorização e teste de isolamento com duas empresas. Não comprova o deploy da
versão nem substitui a homologação dos demais fluxos comerciais.

### Validação adicional de acesso em 27/10/2026

Foram adicionadas proteções e testes específicos de autenticação:

- Login e recuperação bloqueiam a linha do usuário durante a decisão. Assim,
  requisições simultâneas não perdem contagem de erros nem consomem duas vezes
  o mesmo código de recuperação.
- Cinco senhas incorretas bloqueiam novas tentativas de login por 15 minutos.
  A API responde `429` com `Retry-After`; o navegador mostra o tempo restante.
- Desativar ou reativar uma conta incrementa `auth_version`. A reativação não
  torna válidos tokens antigos. Isso inclui a conta do profissional vinculada
  ao perfil quando o proprietário ativa ou desativa esse perfil.
- Códigos retornados em `development_code` ficam restritos ao ambiente
  explicitamente `development`. Com envio de e-mail desativado ou sem chave,
  produção e homologação recusam solicitação e confirmação com `503`, antes de
  gerar ou consumir códigos. A regra também cobre mudança de e-mail e códigos
  que tenham sido gerados anteriormente.
- A recuperação permite apenas contas de proprietário ativas. Com entrega
  configurada, respostas de solicitação são genéricas para e-mail existente,
  inexistente ou de profissional; senhas novas precisam de confirmação igual.

Antes desta correção, a condição de fallback também permitia código na resposta
quando `EMAIL_DELIVERY_ENABLED=false`, independentemente do ambiente. A correção
fecha essa possibilidade; não é evidência de exploração ou de que essa configuração
tenha sido usada em produção.

A suíte local passou com **343 testes aprovados** e **6 integrações PostgreSQL
puladas**. Ruff, Black e mypy passaram. Os quatro testes de navegador de reserva
e login passaram em 375 e 1280 pixels, incluindo contador regressivo, liberação
após expirar o bloqueio, indisponibilidade do e-mail, senhas diferentes, código
incorreto e retorno ao login após redefinir a senha.

Em 27/10/2026, André executou o script com PostgreSQL temporário: os **seis testes
de integração passaram em 9,74 segundos**, incluindo o novo cenário
`tests/integration/test_auth_database.py`: login, cinco falhas simultâneas, expiração do bloqueio,
solicitação concorrente de recuperação, cinco códigos errados, consumo concorrente
de código válido, revogação de tokens e desativação/reativação de contas e perfil.
O envio de e-mail é simulado nesse teste, mesmo usando configuração de produção;
nenhuma mensagem real é enviada nesse cenário automatizado.
O script confirmou a remoção do container e banco temporários, sem criar volumes.
Essa homologação não usou contas nem banco de produção. O commit `61ffe55` passou
nos três jobs do [GitHub Actions](https://github.com/AndreRibeiro-Dev7/projeto-osiris/actions/runs/40590251626)
e o deploy foi confirmado pela tela do Render apresentada por André.

### Teste manual de entrega do Resend

Em 27/10/2026, André criou uma chave de envio no Resend e informou a conclusão
da configuração no Render de `RESEND_API_KEY`, `RESEND_FROM_EMAIL` e
`EMAIL_DELIVERY_ENABLED`, usando o remetente de teste `Osiris <onboarding@resend.dev>`.
Nenhum segredo foi registrado neste documento.

Após receber instruções para solicitar a recuperação, conferir o código, redefinir
a senha, entrar com a nova senha e verificar a recusa da antiga, André confirmou
a conclusão do fluxo. Essa é uma validação manual relatada pelo usuário, restrita
ao e-mail associado à própria conta Resend, que também corresponde ao proprietário.
Não comprova entrega a outros destinatários nem a confirmação de troca de e-mail.

O domínio próprio ainda não foi cadastrado/verificado. O remetente `resend.dev`
continua apenas para teste; liberar entrega aos demais usuários depende de um
domínio verificado e de um remetente desse domínio.
