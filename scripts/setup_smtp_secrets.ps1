# Crea o actualiza secretos SMTP en Google Secret Manager para Cloud Run.
# Uso:
#   .\scripts\setup_smtp_secrets.ps1 -ProjectId laslocaswhatsapp
#   .\scripts\setup_smtp_secrets.ps1 -ProjectId laslocaswhatsapp -FromEnv
#
# Ejecutar ANTES del deploy si cloudbuild.yaml incluye secretos SMTP.

param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [switch]$FromEnv
)

$ErrorActionPreference = "Stop"

function Read-EnvValue {
    param([string]$Name)
    if (-not $FromEnv) { return $null }
    $line = Get-Content -Path ".env" -ErrorAction SilentlyContinue |
        Where-Object { $_ -match "^\s*$Name\s*=" } |
        Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
}

function Get-Or-Prompt {
    param([string]$Label, [string]$EnvName, [string]$Default = "")
    $fromFile = Read-EnvValue -Name $EnvName
    if ($fromFile) { return $fromFile }
    if ($Default) {
        $v = Read-Host "$Label [$Default]"
        if ([string]::IsNullOrWhiteSpace($v)) { return $Default }
        return $v
    }
    return Read-Host $Label
}

function Ensure-Secret {
    param([string]$Name)
    gcloud secrets describe $Name --project=$ProjectId 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Creando secreto $Name..."
        gcloud secrets create $Name --project=$ProjectId --replication-policy=automatic
    }
}

function Set-SecretValue {
    param([string]$Name, [string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        Write-Warning "Valor vacío para $Name — omitido"
        return
    }
    $Value | gcloud secrets versions add $Name --project=$ProjectId --data-file=-
    Write-Host "Secreto $Name actualizado."
}

Write-Host "Proyecto GCP: $ProjectId"
gcloud config set project $ProjectId | Out-Null

$adminEmail = Get-Or-Prompt -Label "ADMIN_NOTIFY_EMAIL" -EnvName "ADMIN_NOTIFY_EMAIL"
$smtpHost   = Get-Or-Prompt -Label "SMTP_HOST" -EnvName "SMTP_HOST" -Default "smtp.zoho.com"
$smtpPort   = Get-Or-Prompt -Label "SMTP_PORT" -EnvName "SMTP_PORT" -Default "587"
$smtpUser   = Get-Or-Prompt -Label "SMTP_USER" -EnvName "SMTP_USER" -Default $adminEmail
$smtpPass   = Get-Or-Prompt -Label "SMTP_PASSWORD (app password)" -EnvName "SMTP_PASSWORD"

foreach ($name in @(
    "ADMIN_NOTIFY_EMAIL", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"
)) {
    Ensure-Secret -Name $name
}

Set-SecretValue -Name "ADMIN_NOTIFY_EMAIL" -Value $adminEmail
Set-SecretValue -Name "SMTP_HOST" -Value $smtpHost
Set-SecretValue -Name "SMTP_PORT" -Value $smtpPort
Set-SecretValue -Name "SMTP_USER" -Value $smtpUser
Set-SecretValue -Name "SMTP_PASSWORD" -Value $smtpPass

Write-Host ""
Write-Host "Listo. El próximo deploy (cloudbuild.yaml) montará estos secretos en Cloud Run."
Write-Host "Verificá localmente: python scripts/verify_smtp.py --send-test"
