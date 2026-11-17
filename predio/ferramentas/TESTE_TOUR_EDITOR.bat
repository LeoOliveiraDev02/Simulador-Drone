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
if not exist "D:\DronePredio\testes" mkdir "D:\DronePredio\testes"
del /q "D:\DronePredio\testes\*.*" >nul 2>&1
taskkill /im UnrealEditor.exe /f >nul 2>&1
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\Build.bat" PredioDroneEditor Win64 Development -Project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -WaitMutex -NoHotReloadFromIDE
start "" /wait "D:\JOGOS\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "D:\DronePredio\PredioDrone\PredioDrone.uproject" -game -tour -pastatestes=D:/DronePredio/testes -windowed -resx=1920 -resy=1080 -nosplash -unattended
type "D:\DronePredio\testes\tour_resultado.txt"
dir "D:\DronePredio\testes"
