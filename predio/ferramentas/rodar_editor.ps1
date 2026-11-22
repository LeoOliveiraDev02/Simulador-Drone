# Roda um script Python no Unreal Editor e espera ele terminar.
# O editor às vezes some da tela mas não fecha (fica preso depois do QUIT_EDITOR): quando o
# arquivo de progresso diz TUDO PRONTO (ou ERRO), espera um pouco e fecha o editor à força.
# Sai com 0 se o script terminou com TUDO PRONTO, 1 se não.
param(
    [Parameter(Mandatory = $true)][string]$Script,
    [Parameter(Mandatory = $true)][string]$Progresso,
    [int]$LimiteMinutos = 90
)
$editor = "D:\JOGOS\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$projeto = "D:\DronePredio\PredioDrone\PredioDrone.uproject"
Remove-Item -ErrorAction SilentlyContinue $Progresso
$p = Start-Process -FilePath $editor -ArgumentList "`"$projeto`" -ExecutePythonScript=`"$Script`" -unattended -nosplash -NoLiveCoding" -PassThru
$inicio = Get-Date
$fimVisto = $null
while ($true) {
    Start-Sleep -Seconds 5
    $texto = ""
    if (Test-Path $Progresso) { $texto = [IO.File]::ReadAllText($Progresso, [Text.Encoding]::UTF8) }
    $acabou = ($texto -match "TUDO PRONTO") -or ($texto -match "ERRO")
    if ($p.HasExited) { break }
    if ($acabou -and -not $fimVisto) { $fimVisto = Get-Date }
    if ($fimVisto -and ((Get-Date) - $fimVisto).TotalSeconds -gt 150) {
        Write-Output "editor não fechou sozinho depois do fim do script: fechando"
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        Get-Process UnrealEditor -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        break
    }
    if (((Get-Date) - $inicio).TotalMinutes -gt $LimiteMinutos) {
        Write-Output "editor passou de $LimiteMinutos minutos: fechando"
        Get-Process UnrealEditor -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        break
    }
}
Start-Sleep -Seconds 3
Get-Process UnrealEditor -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$texto = ""
if (Test-Path $Progresso) { $texto = [IO.File]::ReadAllText($Progresso, [Text.Encoding]::UTF8) }
Write-Output $texto
if ($texto -match "TUDO PRONTO") { exit 0 } else { exit 1 }
