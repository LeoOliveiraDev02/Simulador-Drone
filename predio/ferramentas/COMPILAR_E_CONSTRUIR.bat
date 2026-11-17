@echo off
chcp 65001 >nul
if not "%~1"=="log" (
  if not exist "%~dp0logs" mkdir "%~dp0logs"
  echo Rodando %~nx0 ... a janela fecha sozinha quando terminar.
  call "%~f0" log > "%~dp0logs\%~n0.log" 2>&1
  echo FIM %date% %time% >> "%~dp0logs\%~n0.log"
  exit /b
)
taskkill /im UnrealEditor.exe /f >nul 2>&1
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\Build.bat" PredioDroneEditor Win64 Development -Project="C:\drone\predio\PredioDrone\PredioDrone.uproject" -WaitMutex -NoHotReloadFromIDE
if errorlevel 1 (
  echo COMPILACAO FALHOU
  exit /b 1
)
start "" /wait "D:\JOGOS\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "C:\drone\predio\PredioDrone\PredioDrone.uproject" -ExecutePythonScript="C:/drone/predio/unreal/construir_mapa.py" -unattended -nosplash -NoLiveCoding
echo editor=%errorlevel%
type "C:\drone\predio\logs\construir_mapa_progresso.txt"
