param(
    [string]$BaseUrl = "https://osiris-api-5ujk.onrender.com"
)

$ErrorActionPreference = "Stop"
$BaseUrl = $BaseUrl.Trim().TrimEnd("/")

function ConvertTo-PlainText([Security.SecureString]$SecureValue) {
    if ($null -eq $SecureValue) {
        throw "O valor protegido não foi informado."
    }

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Read-Required([string]$Prompt) {
    $value = Read-Host $Prompt
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "O campo '$Prompt' é obrigatório. Execute o script novamente."
    }
    return $value.Trim()
}

Write-Host "Configuração inicial segura do Projeto Osiris" -ForegroundColor Green
Write-Host "Digite cada resposta somente depois que o respectivo campo aparecer."

$businessName = Read-Required "Nome da barbearia"
$businessPhone = Read-Required "Telefone da barbearia (somente números)"
$ownerEmail = Read-Required "E-mail de acesso"
$secureToken = Read-Host "Cole o NOVO OWNER_BOOTSTRAP_TOKEN" -AsSecureString
$securePassword = Read-Host "Crie uma NOVA senha com pelo menos 12 caracteres" -AsSecureString

$setupToken = ConvertTo-PlainText $secureToken
$password = ConvertTo-PlainText $securePassword

if ($password.Length -lt 12) {
    throw "A senha precisa ter pelo menos 12 caracteres."
}

try {
    $businessBody = @{
        name = $businessName
        phone = $businessPhone
        timezone = "America/Sao_Paulo"
        loyalty_enabled = $true
        loyalty_target = 10
        loyalty_reward = "1 atendimento grátis"
        monthly_revenue_goal_cents = 600000
    } | ConvertTo-Json

    Write-Host "Criando a empresa..."
    $business = Invoke-RestMethod `
        -Method Post `
        -Uri "$BaseUrl/api/v1/businesses" `
        -ContentType "application/json; charset=utf-8" `
        -Body ([Text.Encoding]::UTF8.GetBytes($businessBody))

    $ownerBody = @{
        business_id = $business.id
        email = $ownerEmail
        password = $password
    } | ConvertTo-Json

    Write-Host "Criando o proprietário..."
    $owner = Invoke-RestMethod `
        -Method Post `
        -Uri "$BaseUrl/api/v1/auth/bootstrap-owner" `
        -Headers @{ "X-Setup-Token" = $setupToken } `
        -ContentType "application/json; charset=utf-8" `
        -Body ([Text.Encoding]::UTF8.GetBytes($ownerBody))

    Write-Host "Conta criada com sucesso para $($owner.email)." -ForegroundColor Green
    Write-Host "Acesse: $BaseUrl/dashboard/"
}
finally {
    $setupToken = $null
    $password = $null
    $secureToken = $null
    $securePassword = $null
}
