$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Runtime = Join-Path $ProjectRoot ".runtime"
$FreeCadExeFile = Join-Path $Runtime "freecad-exe.txt"

if (-not (Test-Path -LiteralPath $FreeCadExeFile)) {
    throw "Ambiente não preparado. Execute .\scripts\setup.ps1 primeiro."
}

$FreeCadExe = (Get-Content -Raw $FreeCadExeFile).Trim()
$env:AICAD_PROJECT_ROOT = $ProjectRoot
$userConfig = Join-Path $Runtime "user.cfg"
$systemConfig = Join-Path $Runtime "system.cfg"
$modulePath = Join-Path $ProjectRoot "src\freecad\AiCad"
$pythonPath = Join-Path $ProjectRoot "src"

Start-Process -FilePath $FreeCadExe -ArgumentList @(
    "-M", ('"' + $modulePath + '"'),
    "-P", ('"' + $pythonPath + '"'),
    "-u", ('"' + $userConfig + '"'),
    "-s", ('"' + $systemConfig + '"')
)
