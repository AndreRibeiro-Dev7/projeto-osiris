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
Set-Location "C:\Users\andre\Documents\Codex\2026-09-01\ret\projeto-osiris-publish"
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

## Teste seguro de restauração

O teste usa o backup mais recente e confere o SHA-256 quando o arquivo lateral
`.dump.sha256` está presente. Hash divergente, formato inválido ou nome diferente
interrompem o processo antes de iniciar o Docker. Para exigir esse arquivo:

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\test_backup_restore.ps1" -RequireChecksum
```

Backups antigos sem hash continuam aceitos no modo padrão, com aviso explícito;
isso não reconstrói nem comprova sua integridade original. Um hash armazenado junto
ao backup detecta alterações acidentais, mas não autentica sua origem caso ambos
os arquivos sejam adulterados.

O teste cria um PostgreSQL temporário sem rede e sem porta pública,
restaura os dados, confere as tabelas essenciais e exibe a quantidade de registros.
O contêiner e o banco temporário são removidos ao final, inclusive se ocorrer erro.
O diretório de dados usa `tmpfs`, sem volume persistente. A restauração usa uma
única transação e para no primeiro erro. A remoção inclui eventuais volumes
anônimos do contêiner de teste; uma falha de limpeza é informada com seu nome.

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\test_backup_restore.ps1"
```

Para testar um arquivo específico:

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\test_backup_restore.ps1" `
    -BackupFile ".\backups\osiris-2026-09-22_23-00.dump"
```

Esse processo é completamente local: ele não utiliza a URL nem as credenciais do
banco de produção.

Restaurar um backup antigo não confirma compatibilidade com as migrações atuais.
Esse teste confere a restauração e as seis tabelas essenciais; não aplica novas
migrações e não substitui o ensaio de atualização em um ambiente isolado.

## Revisão do script em 29/10/2026

Os testes de `tests/test_backup_restore_script.py` usam Docker simulado e arquivos
fictícios. Cobrem hash válido, backup antigo sem hash, hash obrigatório ausente,
metadados inválidos, alteração do arquivo, nome divergente, falha de restauração
e falha de limpeza, no Windows PowerShell e no PowerShell moderno. A seleção do
comando simulado é conferida antes de executar o script, impedindo acesso ao
Docker real nesses testes. O job `backup-script` executa esses testes no Windows.

Os 16 cenários simulados passaram localmente em 22,19 segundos; os dois testes
de configuração também passaram e cinco cenários Bash/Linux foram ignorados
no Windows. Nenhum backup real foi aberto pelos testes simulados.

André executou a restauração real isolada em 29/10/2026 com o arquivo
`osiris-2026-09-22_23-00.dump`. Foram recuperados 1 empresa, 1 usuário,
5 barbeiros, 80 clientes, 9 serviços e 25.202 agendamentos. O script confirmou
a remoção do contêiner temporário, com dados em memória e sem volume persistente.
O aviso de ausência de SHA-256 era esperado para essa cópia antiga; o resultado
não comprova seu hash original nem a compatibilidade com migrações posteriores.
A publicação desta revisão e a aprovação do novo job no CI estão pendentes.

## Recuperação

Em perda de dados recente, prefira **Render → osiris-db → Recovery → Point-in-Time
Recovery**. O Render cria um novo banco isolado para validação antes da troca da
conexão da API.

Nunca teste restauração sobre o banco de produção. Use um banco vazio e isolado.
Para retenção externa independente do computador, siga a documentação oficial do
Render para um Cron Job que envie `pg_dump` ao Amazon S3.

