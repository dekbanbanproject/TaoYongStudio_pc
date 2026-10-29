$ErrorActionPreference = 'Stop'
$root = 'F:\DverClips\engine'
$py = "$root\.venv\Scripts\python.exe"
$dist = "$root\dist\taoyong-engine"

Write-Output "[1/3] PyInstaller..."
Push-Location $root
$ErrorActionPreference = 'Continue'
& $py -m PyInstaller --noconfirm --clean "$root\build_sidecar.spec" 2>&1 | Select-Object -Last 4 | Out-String | Write-Output
$ErrorActionPreference = 'Stop'
Pop-Location

Write-Output "[2/3] Trimming googleapiclient discovery cache..."
$docs = "$dist\_internal\googleapiclient\discovery_cache\documents"
$keep = @('youtube.v3.json', 'youtubeAnalytics.v1.json', 'youtubeAnalytics.v2.json', 'youtubereporting.v1.json')
if (Test-Path $docs) {
  $removed = 0
  Get-ChildItem $docs -File | Where-Object { $keep -notcontains $_.Name } | ForEach-Object {
    Remove-Item $_.FullName -Force
    $removed++
  }
  Write-Output "      removed $removed unused discovery documents"
}

Write-Output "[3/3] Result..."
$s = Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum
Write-Output ("      {0} files, {1} MB" -f $s.Count, [int]($s.Sum / 1MB))
Write-Output "      exe: $dist\taoyong-engine.exe"
