@echo off
chcp 65001 >nul
if not "%~1"=="log" (
  echo Movendo o projeto do predio para D:\DronePredio ... a janela fecha sozinha quando terminar.
  call "%~f0" log > "%~dp0MOVER_PREDIO_PARA_D.log" 2>&1
  echo FIM %date% %time% >> "%~dp0MOVER_PREDIO_PARA_D.log"
  exit /b
)
set "N=D:\DronePredio"
set "V=C:\drone\predio"
set "U=D:\JOGOS\UE_5.8"
set "L=%LOCALAPPDATA%\UnrealEngine\Common"
echo === fechando Unreal / jogo / cache
for %%P in (UnrealEditor.exe PredioDrone.exe PredioDrone-Win64-Shipping.exe zenserver.exe UnrealTraceServer.exe ShaderCompileWorker.exe CrashReportClientEditor.exe) do taskkill /im %%P /f >nul 2>&1
timeout /t 4 /nobreak >nul
if not exist "%N%" mkdir "%N%"

echo === tirando os atalhos (junctions) antigos
for %%J in ("%V%\PredioDrone\Saved" "%V%\PredioDrone\Intermediate" "%V%\recursos") do (
  fsutil reparsepoint query %%J >nul 2>&1 && rmdir %%J && echo removido atalho %%J
)

echo === movendo C:\drone\predio para %N%
robocopy "%V%" "%N%" /E /MOVE /XJ /R:2 /W:2 /NFL /NDL /NP /NJH
echo robocopy=%errorlevel%

echo === juntando as pastas que ja estavam no D
call :juntar "%U%\_PredioDrone_Saved" "%N%\PredioDrone\Saved"
call :juntar "%U%\_PredioDrone_Intermediate" "%N%\PredioDrone\Intermediate"
call :juntar "%U%\_PredioDrone_recursos" "%N%\recursos"
call :juntar "%U%\_PredioDrone_jogo" "%N%\jogo"
call :juntar "%U%\_PredioDrone_build" "%N%\build"

echo === cache do Unreal (DDC / Zen) para o D
if exist "%L%\Zen\Data" robocopy "%L%\Zen\Data" "%N%\DDC" /E /MOVE /R:1 /W:1 /NFL /NDL /NP /NJH
if exist "%L%\DerivedDataCache" rmdir /s /q "%L%\DerivedDataCache"
setx UE-LocalDataCachePath "D:\DronePredio\DDC"

echo === arquivos salvos do jogo antigo
if exist "%LOCALAPPDATA%\PredioDrone" robocopy "%LOCALAPPDATA%\PredioDrone" "%N%\jogo\Windows\PredioDrone" /E /MOVE /R:1 /W:1 /NFL /NDL /NP /NJH

echo === chave do .NET SDK apontando para o D
if exist "%N%\ferramentas\netfxsdk" (
  reg add "HKCU\SOFTWARE\Microsoft\Microsoft SDKs\NETFXSDK\4.8" /v KitsInstallationFolder /t REG_SZ /d "%N%\ferramentas\netfxsdk\\" /f
  reg add "HKCU\SOFTWARE\WOW6432Node\Microsoft\Microsoft SDKs\NETFXSDK\4.8" /v KitsInstallationFolder /t REG_SZ /d "%N%\ferramentas\netfxsdk\\" /f
)

rem so apaga a pasta velha se ficou VAZIA (nada e apagado a forca)
if exist "%V%" rmdir "%V%" 2>nul
echo === resultado
if exist "%V%" ( echo AINDA EXISTE %V% & dir /s /b "%V%" ) else ( echo C:\drone\predio nao existe mais )
dir "%N%"
dir "%N%\PredioDrone"
powershell -NoProfile -Command "Get-PSDrive C,D | Select Name,@{n='LivreGB';e={[math]::Round($_.Free/1GB,1)}} | Format-Table"
echo MUDANCA CONCLUIDA
exit /b

:juntar
if not exist "%~1" exit /b
if not exist "%~2" (
  move "%~1" "%~2" >nul && echo movido %~1 para %~2
) else (
  robocopy "%~1" "%~2" /E /MOVE /R:1 /W:1 /NFL /NDL /NP /NJH >nul
  echo juntado %~1 em %~2
)
exit /b
