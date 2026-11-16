# Instala o simulador Meshtasticator e o ambiente Python fora do repositório.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 [-Base "E:\pasta\de\trabalho"]

param(
    [string]$Base = "E:\UFF\Pesquisa Operacional"
)

$ErrorActionPreference = "Stop"
$sim  = Join-Path $Base "Meshtasticator"
$venv = Join-Path $Base "venv-lora"
$repo = Split-Path -Parent $PSScriptRoot

# Versão do simulador usada no trabalho (fixada para o experimento ser reproduzível)
$simCommit = "17ceb8231079d87b070abc6132181e4c6b20202d"

Write-Host "1/4 Criando a pasta de trabalho $Base"
New-Item -ItemType Directory -Force -Path $Base | Out-Null

Write-Host "2/4 Baixando o simulador (Meshtasticator)"
if (-not (Test-Path $sim)) {
    git clone https://github.com/meshtastic/Meshtasticator.git $sim
}
git -C $sim fetch --quiet
git -C $sim checkout --quiet $simCommit
Write-Host "    simulador na versão $simCommit"

Write-Host "3/4 Criando o ambiente Python em $venv"
if (-not (Test-Path $venv)) {
    py -3 -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"
& $py -m pip install --upgrade pip --quiet

Write-Host "4/4 Instalando dependências (simulador + projeto)"
& $py -m pip install -r (Join-Path $sim "requirements.txt")
& $py -m pip install -r (Join-Path $repo "requirements.txt")

Write-Host ""
Write-Host "Pronto. Para testar o simulador:"
Write-Host "  & `"$venv\Scripts\Activate.ps1`""
Write-Host "  cd `"$sim`""
Write-Host "  python loraMesh.py 10"
