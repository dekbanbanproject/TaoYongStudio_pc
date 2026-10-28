# TaoYongStudio Installer Compiler
$ErrorActionPreference = "Stop"

$rootDir = (Split-Path -Parent $PSScriptRoot)
Set-Location $rootDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  TaoYongStudio Installer Compiler                        " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Project root: $rootDir"

# 1. Locate C# compiler
$cscPaths = @(
    "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)
$csc = $cscPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $csc) {
    Write-Error "Microsoft .NET C# compiler (csc.exe) not found."
    exit 1
}
Write-Host "[1/4] Using C# Compiler: $csc" -ForegroundColor Green

# 2. Package source files into temporary zip
$tempZip = Join-Path $env:TEMP "TaoYongStudio_Package_$([Guid]::NewGuid().ToString('N')).zip"
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }

Write-Host "[2/4] Packaging files into archive..." -ForegroundColor Yellow
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zip = [System.IO.Compression.ZipFile]::Open($tempZip, [System.IO.Compression.ZipArchiveMode]::Create)

$filesToPack = Get-ChildItem -Path $rootDir -Recurse -File | Where-Object {
    $rel = $_.FullName.Substring($rootDir.Length + 1)
    $rel -notmatch '^(\.git|\.venv|cache|logs|output|secrets|scratch|\.gemini|mockups)\\?' -and
    $rel -notmatch '(__pycache__|\.pyc$|\.pyo$)' -and
    $rel -notmatch '^config\.json$' -and
    $rel -notmatch '^client_secret.*\.json$' -and
    $rel -notmatch 'TaoYongStudio_Setup.*\.exe$' -and
    $rel -notmatch '^plans\\(requests|results|cancelled|product_prompts)\\' -and
    $rel -notmatch '^plans\\(product_ideas\.json|ideas\.json\.bak)$' -and
    $rel -notmatch '^scripts\\(inbox|done|failed|removed|compilations)\\' -and
    $rel -notmatch '^nextseller\\data\\' -and
    $rel -notmatch 'installer\\bin\\?'
}

Write-Host "      Adding $($filesToPack.Count) files..."
foreach ($f in $filesToPack) {
    $rel = $f.FullName.Substring($rootDir.Length + 1)
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f.FullName, $rel, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
}
$zip.Dispose()

$zipItem = Get-Item $tempZip
$zipSizeMB = [math]::Round($zipItem.Length / 1MB, 2)
Write-Host "      Archive created successfully: $zipSizeMB MB" -ForegroundColor Green

# 3. Compile Installer Executable
$installerCs = Join-Path $rootDir "installer\TaoYongInstaller.cs"
$iconPath = Join-Path $rootDir "studio\app.ico"
$outputExe = Join-Path $rootDir "TaoYongStudio_Setup.exe"

Write-Host "[3/4] Compiling TaoYongStudio_Setup.exe..." -ForegroundColor Yellow

$cscArgs = @(
    "/nologo",
    "/target:winexe",
    "/win32icon:$iconPath",
    "/r:System.dll",
    "/r:System.Windows.Forms.dll",
    "/r:System.Drawing.dll",
    "/r:System.IO.Compression.dll",
    "/r:System.IO.Compression.FileSystem.dll",
    "/resource:$tempZip,DataZip",
    "/resource:$iconPath,AppIcon",
    "/out:$outputExe",
    $installerCs
)

$proc = Start-Process -FilePath $csc -ArgumentList $cscArgs -Wait -PassThru -NoNewWindow
if ($proc.ExitCode -ne 0) {
    if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
    Write-Error "Compilation failed with exit code $($proc.ExitCode)"
    exit $proc.ExitCode
}

# 4. Cleanup
if (Test-Path $tempZip) { Remove-Item $tempZip -Force }

if (Test-Path $outputExe) {
    $exeItem = Get-Item $outputExe
    $exeSizeMB = [math]::Round($exeItem.Length / 1MB, 2)
    Write-Host "[4/4] COMPILATION COMPLETED SUCCESSFULLY!" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "  Installer executable created: " -ForegroundColor White
    Write-Host "  File: $outputExe" -ForegroundColor Yellow
    Write-Host "  Size: $exeSizeMB MB" -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Cyan
} else {
    Write-Error "Output executable was not created."
    exit 1
}
