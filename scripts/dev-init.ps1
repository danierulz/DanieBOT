# Bootstrap DB local: espera Postgres, migraciones Alembic, seeds.
# Ejecutar desde la raíz del repo: .\scripts\dev-init.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path ".env.dev")) {
    Write-Error "Falta .env.dev en la raíz del proyecto."
}

Write-Host ">> Levantando Postgres (db)..."
docker compose up -d db

$max = 30
$ready = $false
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
for ($i = 1; $i -le $max; $i++) {
    docker compose exec -T db pg_isready -U daniebot -d daniebot_dev 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 2
}
$ErrorActionPreference = $prevEap
if (-not $ready) {
    Write-Error "Postgres no respondió a tiempo. Revisá: docker compose logs db"
}

Write-Host ">> Alembic upgrade head..."
docker compose run --rm app python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ">> Seeds (talles, categorías)..."
docker compose run --rm app python -c "from database.init_db import seed_reference_data; seed_reference_data()"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Listo. Arrancá la app con:"
Write-Host "  docker compose up app"
Write-Host "  http://localhost:5000"
Write-Host ""
Write-Host "Webhook WhatsApp (ngrok):"
Write-Host "  docker compose --profile whatsapp up"
