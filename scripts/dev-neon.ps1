# Bootstrap contra Neon (sin Postgres en Docker).
# Uso: .\scripts\dev-neon.ps1
#      .\scripts\dev-neon.ps1 -UpApp

param(
    [switch]$UpApp,
    [switch]$SeedOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path ".env.neon")) {
    Write-Host "Falta .env.neon. Copiá la plantilla:"
    Write-Host "  copy .env.neon.example .env.neon"
    Write-Host "Pegá DATABASE_URL desde https://console.neon.tech/"
    exit 1
}

$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.neon.yml")

if (-not $SeedOnly) {
    Write-Host ">> Alembic upgrade head (Neon)..."
    docker compose @Compose run --rm app python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host ">> Seeds (talles, categorías)..."
docker compose @Compose run --rm app python -c "from database.init_db import seed_reference_data; seed_reference_data()"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Listo. Neon configurado."
Write-Host "  App en Docker: docker compose -f docker-compose.yml -f docker-compose.neon.yml up app"
Write-Host "  URL: http://localhost:8080"
Write-Host ""
Write-Host "Sin Docker (más simple): copiá DATABASE_URL a .env y ejecutá python main.py"

if ($UpApp) {
    docker compose @Compose up app
}
