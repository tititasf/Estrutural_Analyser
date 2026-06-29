$ErrorActionPreference = "Stop"

$appRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $appRoot
$venvPath = Join-Path $projectRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"

$python312 = & py -3.12 -c "import sys; print(sys.executable)"
if ($LASTEXITCODE -ne 0 -or -not $python312) {
    throw "Python 3.12 nao foi encontrado. Instale-o antes de configurar o projeto."
}

if (-not (Test-Path $pythonPath)) {
    Write-Host "Criando ambiente virtual Python 3.12 em $venvPath"
    & py -3.12 -m venv $venvPath
}

& $pythonPath (Join-Path $appRoot "scripts\verify_python_runtime.py")
& $pythonPath -m pip install --upgrade pip setuptools wheel

$requirementFiles = @(
    "requirements.txt",
    "requirements_cognitive.txt",
    "_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\requirements.txt"
)

foreach ($relativePath in $requirementFiles) {
    $requirementPath = Join-Path $appRoot $relativePath
    if (Test-Path $requirementPath) {
        Write-Host "Instalando dependencias de $relativePath"
        & $pythonPath -m pip install -r $requirementPath --no-input --progress-bar off
    }
    else {
        Write-Warning "Arquivo de requisitos ausente: $requirementPath"
    }
}

& $pythonPath (Join-Path $appRoot "scripts\verify_python_runtime.py") --check-imports
Write-Host "Ambiente Python 3.12 configurado: $pythonPath"
