# Criação do primeiro proprietário

O endpoint `POST /api/v1/auth/bootstrap-owner` cria o proprietário principal de
uma barbearia já existente. Não é um cadastro público: em produção, depende de
`OWNER_BOOTSTRAP_ENABLED=true` e do segredo enviado em `X-Setup-Token`.
Sem essa configuração ou com token ausente/incorreto, responde HTTP 404.
Após a configuração inicial, o bootstrap deve permanecer desativado.

## Concorrência

A verificação anterior consultava a barbearia sem bloqueá-la. Solicitações
simultâneas com e-mails diferentes poderiam verificar a ausência de contas antes
que qualquer uma terminasse a criação, permitindo mais de um proprietário principal.

A criação agora bloqueia a linha da barbearia com `SELECT FOR UPDATE` antes de
contar suas contas. As solicitações para a mesma barbearia aguardam a transação
anterior e verificam novamente o cadastro. A primeira criação responde HTTP 201;
as demais encontram a conta existente e respondem HTTP 409.

Não há nova migração. A alteração protege esse fluxo da API; não cria uma restrição
única no banco nem corrige automaticamente eventuais duplicidades anteriores.
Nenhuma conta real foi criada ou alterada durante a preparação.

## Homologação em 29/10/2026

`tests/integration/test_owner_setup_database.py` usa PostgreSQL temporário e
autenticação reais, com empresa e credenciais fictícias. Verifica:

- Bootstrap desativado e token ausente/incorreto sem acesso.
- Empresa inexistente e senha curta sem criação de conta.
- Três solicitações aguardando o bloqueio da mesma barbearia: uma criação e dois conflitos.
- Persistência de uma única conta principal, senha armazenada como hash e login funcional.
- Repetição após criação e desativação do bootstrap.

O teste segura previamente a linha e aguarda as três solicitações alcançarem a
consulta bloqueante antes de liberá-la, evitando depender apenas do acaso no escalonamento.
Ele só aceita banco local com nome de homologação e não usa notificações externas.

Execute com Docker aberto, na pasta do projeto:

```powershell
& ".\.venv-codex\Scripts\python.exe" ".\scripts\test_tenant_isolation.py"
```

A suíte local passou com 374 testes e 17 ignorados (PostgreSQL e Bash/Linux),
em 16,70 segundos. Ruff, Black e mypy também passaram.
André executou a suíte em PostgreSQL temporário: 11 testes aprovados e 1 ignorado
em 22,82 segundos. O cenário confirmou uma única criação em três solicitações
simultâneas e dois conflitos, além dos controles de configuração e autenticação.
O teste opcional de carga não foi executado. O container e o banco temporários
foram removidos sem criação de volume. A publicação desta correção está pendente.
