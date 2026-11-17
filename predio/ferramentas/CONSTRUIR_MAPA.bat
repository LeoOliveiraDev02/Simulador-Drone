@echo off
chcp 65001 >nul
if not "%~1"=="log" (
  if not exist "%~dp0logs" mkdir "%~dp0logs"
  echo Rodando %~nx0 ... a janela fecha sozinha quando terminar.
  call "%~f0" log > "%~dp0logs\%~n0.log" 2>&1
  echo FIM %date% %time% >> "%~dp0logs\%~n0.log"
  exit /b
)
rem cache do Unreal (shaders etc.) fica no D, na pasta do projeto
set "UE-LocalDataCachePath=D:\DronePredio\DDC"
taskkill /im UnrealEditor.exe /f >nul 2>&1
start "" /wait "D:\JOGOS\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "D:\DronePredio\PredioDrone\PredioDrone.uproject" -ExecutePythonScript="D:/DronePredio/unreal/construir_mapa.py" -unattended -nosplash -NoLiveCoding -log
echo codigo=%errorlevel%
type "D:\DronePredio\logs\construir_mapa_progresso.txt"
