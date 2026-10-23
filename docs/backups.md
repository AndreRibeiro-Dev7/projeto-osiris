# Backup e recuperação

O banco de produção usa um plano pago do Render Postgres. O Render mantém backup
contínuo para recuperação ponto a ponto (PITR). No workspace Hobby, a janela de
recuperação é de 3 dias; em Pro ou superior, 7 dias.

## Segunda camada local

O script deste projeto cria um `pg_dump` em formato customizado,
valida o arquivo com `pg_restore --list`, registra o SHA-256 e remove somente
backups do Osiris mais antigos que o período de retenção.

Pré-requisitos:

- Docker Desktop aberto.
- IP público do computador autorizado temporariamente como `/32` nas regras do
  PostgreSQL. Se o provedor alterar esse IP, o backup falhará até a regra ser
  atualizada. Remova essa autorização depois que a cópia terminar.

Execute no PowerShell quando desejar uma cópia lógica adicional:

```powershell
Set-Location "C:\Users\andre\Documents\Codex\2026-07-28\criar\projeto-osiris"
powershell -ExecutionPolicy Bypass -File ".\scripts\backup_database.ps1"
```

A URL externa é solicitada como texto oculto e mantida somente na memória durante
a execução. A pasta `backups/` não entra no Git.

Confira o resultado:

```powershell
Get-ChildItem ".\backups\osiris-*.dump" | Sort-Object LastWriteTime -Descending
```

O resultado esperado é um arquivo `.dump` com tamanho maior que zero e seu arquivo
`.sha256` correspondente. O próprio script já valida o conteúdo com `pg_restore`.

## Recuperação

Em perda de dados recente, prefira **Render → osiris-db → Recovery → Point-in-Time
Recovery**. O Render cria um novo banco isolado para validação antes da troca da
conexão da API.

Nunca teste restauração sobre o banco de produção. Use um banco vazio e isolado.
Para retenção externa independente do computador, siga a documentação oficial do
Render para um Cron Job que envie `pg_dump` ao Amazon S3.

