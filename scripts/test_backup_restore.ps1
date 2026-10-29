param(
    [string]$BackupFile = "",
    [switch]$RequireChecksum
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$docker = if ($dockerCommand) {
    $dockerCommand.Source
}
else {
    @(
        (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin\docker.exe"),
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe")
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $docker) {
    throw "Docker nao foi encontrado. Abra o Docker Desktop e tente novamente."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $BackupFile) {
    $latestBackup = Get-ChildItem -LiteralPath (Join-Path $projectRoot "backups") `
        -Filter "osiris-*.dump" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $latestBackup) {
        throw "Nenhum backup osiris-*.dump foi encontrado na pasta backups."
    }
    $BackupFile = $latestBackup.FullName
}

$backup = Get-Item -LiteralPath $BackupFile -ErrorAction Stop
if ($backup.Length -le 0) {
    throw "O arquivo de backup esta vazio."
}

$hashPath = "$($backup.FullName).sha256"
if (Test-Path -LiteralPath $hashPath) {
    $hashContent = (Get-Content -LiteralPath $hashPath -Raw).Trim()
    if ($hashContent -notmatch '^([a-fA-F0-9]{64})\s+(.+)$') {
        throw "O arquivo SHA-256 tem formato invalido."
    }
    $expectedHash = $Matches[1]
    $expectedName = $Matches[2]
    if ($expectedName -cne $backup.Name) {
        throw "O SHA-256 pertence a outro arquivo de backup."
    }
    $hashStream = [System.IO.File]::OpenRead($backup.FullName)
    $hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        $actualHash = [System.BitConverter]::ToString(
            $hashAlgorithm.ComputeHash($hashStream)
        ).Replace("-", "")
    }
    finally {
        $hashStream.Dispose()
        $hashAlgorithm.Dispose()
    }
    if ($actualHash -ne $expectedHash) {
        throw "SHA-256 divergente. A restauracao nao foi iniciada."
    }
    Write-Output "Integridade SHA-256 conferida."
}
elseif ($RequireChecksum) {
    throw "O arquivo SHA-256 e obrigatorio para esta verificacao."
}
else {
    Write-Warning "Backup antigo sem SHA-256. A integridade sera verificada apenas pela restauracao."
}

$backupRoot = $backup.Directory.FullName
$backupName = $backup.Name
$databaseName = "osiris_restore_test"
$containerName = "osiris-restore-test-$PID-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
$postgresPassword = [guid]::NewGuid().ToString("N")
$containerCreated = $false

try {
    & $docker run --detach `
        --name $containerName `
        --network none `
        --tmpfs /var/lib/postgresql/data `
        --env "POSTGRES_PASSWORD=$postgresPassword" `
        --env "POSTGRES_DB=$databaseName" `
        --volume "${backupRoot}:/backups:ro" `
        postgres:16-alpine | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Nao foi possivel iniciar o PostgreSQL temporario."
    }
    $containerCreated = $true

    $ready = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        & $docker exec $containerName pg_isready `
            --username postgres --dbname $databaseName 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) {
        throw "O PostgreSQL temporario nao ficou pronto em 60 segundos."
    }

    & $docker exec $containerName pg_restore `
        --username postgres `
        --dbname $databaseName `
        --no-owner `
        --no-acl `
        --exit-on-error `
        --single-transaction `
        "/backups/$backupName"
    if ($LASTEXITCODE -ne 0) {
        throw "A restauracao falhou com codigo $LASTEXITCODE."
    }

    $requiredTables = @(
        "appointments",
        "barbers",
        "businesses",
        "customers",
        "services",
        "users"
    )
    $quotedTables = ($requiredTables | ForEach-Object { "'$_'" }) -join ","
    $tableQuery = "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ($quotedTables);"
    $foundTables = & $docker exec $containerName psql `
        --username postgres `
        --dbname $databaseName `
        --tuples-only `
        --no-align `
        --set ON_ERROR_STOP=1 `
        --command $tableQuery
    if ($LASTEXITCODE -ne 0) {
        throw "Nao foi possivel validar as tabelas restauradas."
    }
    if ([int]$foundTables -ne $requiredTables.Count) {
        throw "A restauracao nao contem todas as tabelas essenciais do Osiris."
    }

    $summaryQuery = @"
SELECT
    (SELECT count(*) FROM businesses),
    (SELECT count(*) FROM users),
    (SELECT count(*) FROM barbers),
    (SELECT count(*) FROM customers),
    (SELECT count(*) FROM services),
    (SELECT count(*) FROM appointments);
"@
    $rowSummary = & $docker exec $containerName psql `
        --username postgres `
        --dbname $databaseName `
        --tuples-only `
        --no-align `
        --field-separator " | " `
        --set ON_ERROR_STOP=1 `
        --command $summaryQuery
    if ($LASTEXITCODE -ne 0) {
        throw "Nao foi possivel contar os registros restaurados."
    }

    Write-Output "Restauracao validada com sucesso: $($backup.FullName)"
    Write-Output "Empresas | usuarios | barbeiros | clientes | servicos | agendamentos"
    Write-Output $rowSummary.Trim()
    Write-Output "Teste local concluido. Isto nao confirma compatibilidade com novas migracoes."
}
finally {
    if ($containerCreated) {
        & $docker rm --force --volumes $containerName 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Nao foi possivel remover o container temporario: $containerName"
        }
        Write-Output "Container temporario removido; dados em memoria, sem volume persistente."
    }
    Remove-Variable postgresPassword -ErrorAction SilentlyContinue
}
