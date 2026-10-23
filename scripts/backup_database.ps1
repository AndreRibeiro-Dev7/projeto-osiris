param(
    [string]$CredentialFile = "",
    [string]$BackupDirectory = "",
    [ValidateRange(1, 3650)]
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $BackupDirectory) {
    $BackupDirectory = Join-Path $projectRoot "backups"
}
if (-not $CredentialFile) {
    $CredentialFile = Join-Path $BackupDirectory ".database-url.xml"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker não foi encontrado. Abra o Docker Desktop e tente novamente."
}

$backupRoot = New-Item -ItemType Directory -Path $BackupDirectory -Force
$backupRoot = $backupRoot.FullName
$credentialPath = [System.IO.Path]::GetFullPath($CredentialFile)
if (Test-Path -LiteralPath $credentialPath) {
    $databaseUrl = Import-Clixml -LiteralPath $credentialPath
}
else {
    $databaseUrl = Read-Host "Cole a External Database URL completa" -AsSecureString
}
if ($databaseUrl -isnot [System.Security.SecureString]) {
    throw "O arquivo de credencial não contém uma URL protegida válida."
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$backupName = "osiris-$timestamp.dump"
$backupPath = Join-Path $backupRoot $backupName
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($databaseUrl)

try {
    $plainDatabaseUrl = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    docker run --rm `
        -v "${backupRoot}:/backups" `
        postgres:16-alpine `
        pg_dump "$plainDatabaseUrl" --format=custom --no-owner --no-acl --file="/backups/$backupName"
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump terminou com código $LASTEXITCODE."
    }
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    Remove-Variable plainDatabaseUrl,databaseUrl,pointer -ErrorAction SilentlyContinue
}

$backup = Get-Item -LiteralPath $backupPath
if ($backup.Length -le 0) {
    Remove-Item -LiteralPath $backupPath -Force
    throw "O backup foi criado vazio e removido."
}

docker run --rm `
    -v "${backupRoot}:/backups" `
    postgres:16-alpine `
    pg_restore --list "/backups/$backupName" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Remove-Item -LiteralPath $backupPath -Force
    throw "O arquivo falhou na validação do pg_restore e foi removido."
}

$hash = Get-FileHash -LiteralPath $backupPath -Algorithm SHA256
$hashPath = "$backupPath.sha256"
Set-Content -LiteralPath $hashPath -Value "$($hash.Hash)  $backupName" -Encoding ascii

$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -LiteralPath $backupRoot -File |
    Where-Object {
        $_.LastWriteTime -lt $cutoff -and
        ($_.Name -like "osiris-*.dump" -or $_.Name -like "osiris-*.dump.sha256")
    } |
    Remove-Item -Force

Write-Output "Backup validado: $backupPath"
Write-Output "Tamanho: $([math]::Round($backup.Length / 1MB, 2)) MB"
Write-Output "SHA-256: $($hash.Hash)"

