
# Define paths
$scriptPath = "c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\src\interfaces\Abcd_Excel.py"
$excelPath = "c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\P2.xlsx"
$generatedScript = "c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\SCRIPTS_ROBOS\Subsolo_ABCD\P1_ABCD.scr"
$destinationScript = "c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\ferramentas_LOAD_LISP\script_PAZ.scr"

# Run the python script
Write-Host "Running Abcd_Excel.py..."
python $scriptPath $excelPath "E"

# Check if file exists
if (Test-Path $generatedScript) {
    Write-Host "Script generated successfully."
    # Copy file
    Copy-Item -Path $generatedScript -Destination $destinationScript -Force
    Write-Host "Copied to $destinationScript"
}
else {
    Write-Error "Failed to generate script."
    exit 1
}
