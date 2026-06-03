# Borra tags viejos de GCR, conservando las N mas recientes (ahorro de almacenamiento).
# Uso: .\scripts\gcp_prune_images.ps1 [-Keep 8] [-Project laslocaswhatsapp]

param(
    [int]$Keep = 8,
    [string]$Project = "laslocaswhatsapp",
    [string]$Image = "gcr.io/laslocaswhatsapp/laslocaswhatsapp"
)

$ErrorActionPreference = "Stop"

Write-Host "Listando tags de $Image (proyecto $Project)..."
$json = gcloud container images list-tags $Image `
    --project $Project `
    --sort-by=TIMESTAMP `
    --format=json `
    --limit=500 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Error $json
}

$tags = $json | ConvertFrom-Json
$total = $tags.Count
if ($total -le $Keep) {
    Write-Host "Solo hay $total tags; nada que borrar (Keep=$Keep)."
    exit 0
}

$toDelete = $tags | Select-Object -First ($total - $Keep)
Write-Host "Conservando $Keep mas recientes; borrando $($toDelete.Count) tags viejos..."

$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'

foreach ($row in $toDelete) {
    $digest = $row.digest
    if (-not $digest) { continue }
    $ref = "${Image}@${digest}"
    Write-Host "  delete $ref"
    gcloud container images delete $ref --project $Project --force-delete-tags --quiet 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "No se pudo borrar $ref (exit $LASTEXITCODE)"
    }
}

$ErrorActionPreference = $prevEap
Write-Host "Listo."
