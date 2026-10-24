# Read-only pull of NextsellerAI products + product_scores from the Pi into nextseller\data\*.csv
# The SQL is sent through stdin inside BEGIN READ ONLY ... ROLLBACK, so no quoting of SQL is needed on the remote shell.
# No password is read or printed: psql uses the container's own POSTGRES_USER / POSTGRES_DB.
# Run it yourself in PowerShell:  .\nextseller\pull_nextseller_products.ps1
param([string]$Ssh = 'pi5', [string]$Container = 'nextsellerai-postgres-1', [int]$Limit = 2000)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8   # keep Thai text intact
$out = Join-Path $PSScriptRoot 'data'
New-Item -ItemType Directory -Force $out | Out-Null
$sql = [ordered]@{
  products = "SELECT id, platform, external_id, name, category, seller_name, original_price, sale_price, commission_rate, rating, sold_count, status, product_url, affiliate_url, image_url FROM products WHERE deleted_at IS NULL ORDER BY updated_at DESC LIMIT $Limit"
  product_scores = "SELECT DISTINCT ON (product_id) product_id, score, decision, reasons, risks, suggested_angles, created_at FROM product_scores ORDER BY product_id, created_at DESC"
}
# no parentheses/quotes-with-spaces in the remote command: the remote sh only sees these simple words
$remote = "docker exec -i $Container sh -c 'psql -X -q -U `$POSTGRES_USER -d `$POSTGRES_DB'"
foreach ($name in $sql.Keys) {
  $stdin = "BEGIN READ ONLY; COPY ($($sql[$name])) TO STDOUT WITH CSV HEADER; ROLLBACK;"
  $file = Join-Path $out "$name.csv"
  $stdin | ssh -o BatchMode=yes $Ssh $remote | Out-File -Encoding utf8 $file
  if ($LASTEXITCODE -ne 0) { throw "ssh/psql failed for $name (exit $LASTEXITCODE)" }
  $n = (Get-Content $file).Count
  Write-Host ("{0}: {1} lines" -f $name, $n)
  if ($n -lt 2) { Write-Warning "$name has no rows; check the container name ($Container) and that the tables exist" }
}
Write-Host "ต่อไป: .venv\Scripts\python nextseller\nextseller_to_import.py"
