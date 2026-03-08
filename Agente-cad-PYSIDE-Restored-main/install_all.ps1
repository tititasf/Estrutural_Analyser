taskkill /F /IM python.exe -ErrorAction SilentlyContinue

$py = "C:\Python314\python.exe"
$files = @(
    "requirements.txt",
    "requirements_cognitive.txt",
    "_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\requirements.txt"
)

foreach ($f in $files) {
    if (Test-Path $f) {
        Write-Host "Lendo arquivo $f"
        foreach ($line in (Get-Content $f)) {
            $line = $line.Trim()
            if ($line -match '^[a-zA-Z0-9]') {
                # Pega a parte principal da restricao ignorando espaços dps
                $req = $line.Split(' ')[0]
                Write-Host "`n---> INSTALANDO: $req <---"
                try {
                    & $py -u -m pip install $req --no-input --keyring-provider disabled --progress-bar off
                }
                catch {
                    Write-Host "Erro instalando $req"
                }
            }
        }
    }
    else {
        Write-Host "Arquivo faltante: $f"
    }
}
Write-Host "FINALIZADO"
