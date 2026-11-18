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
set "EXE=D:\DronePredio\jogo\Windows\PredioDrone.exe"
taskkill /im UnrealEditor.exe /f >nul 2>&1
taskkill /im PredioDrone.exe /f >nul 2>&1
taskkill /im PredioDrone-Win64-Shipping.exe /f >nul 2>&1
echo === compilar (sem remontar os mapas)
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\Build.bat" PredioDroneEditor Win64 Development -Project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -WaitMutex -NoHotReloadFromIDE
if errorlevel 1 ( echo COMPILACAO FALHOU & exit /b 1 )
echo === empacotar (jogo unico: menu + campo + predio)
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -noP4 -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -iostore -compressed -prereqs -archive -archivedirectory="D:\DronePredio\jogo" -unattended -utf8output -NoCodeSign
if errorlevel 1 ( echo EMPACOTAMENTO FALHOU & exit /b 1 )
echo === atalho unico na area de trabalho
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ATALHO_JOGO.ps1"
echo === testes: fotos do menu principal, voo pelos aros do campo, voo pelo predio
for %%P in (menu campo predio) do (
  if not exist "D:\DronePredio\testes\%%P" mkdir "D:\DronePredio\testes\%%P"
  del /q "D:\DronePredio\testes\%%P\*.*" >nul 2>&1
)
start "" /wait "%EXE%" -NotInstalled -fotomenu -pastatestes=D:/DronePredio/testes/menu -windowed -resx=1920 -resy=1080
start "" /wait "%EXE%" -mapa=Campo -NotInstalled -tour -pastatestes=D:/DronePredio/testes/campo -windowed -resx=1920 -resy=1080
start "" /wait "%EXE%" -NotInstalled -tour -pastatestes=D:/DronePredio/testes/predio -windowed -resx=1920 -resy=1080
echo --- campo
type "D:\DronePredio\testes\campo\tour_resultado.txt"
echo --- predio
type "D:\DronePredio\testes\predio\tour_resultado.txt"
dir /b "D:\DronePredio\testes\menu"
echo TUDO OK
