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
echo === compilar
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\Build.bat" PredioDroneEditor Win64 Development -Project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -WaitMutex -NoHotReloadFromIDE
if errorlevel 1 ( echo COMPILACAO FALHOU & exit /b 1 )
echo === empacotar (jogo unico: menu + campo + predio)
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -noP4 -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -iostore -compressed -prereqs -archive -archivedirectory="D:\DronePredio\jogo" -unattended -utf8output -NoCodeSign
if errorlevel 1 ( echo EMPACOTAMENTO FALHOU & exit /b 1 )
echo === atalho unico na area de trabalho
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ATALHO_JOGO.ps1"
echo === testes: chao, decolar e pousar (predio e fazenda)
for %%P in (pouso_predio pouso_campo) do (
  if not exist "D:\DronePredio\testes\%%P" mkdir "D:\DronePredio\testes\%%P"
  del /q "D:\DronePredio\testes\%%P\*.*" >nul 2>&1
)
start "" /wait "%EXE%" -NotInstalled -testepouso -pastatestes=D:/DronePredio/testes/pouso_predio -windowed -resx=1920 -resy=1080
start "" /wait "%EXE%" -mapa=Campo -NotInstalled -testepouso -pastatestes=D:/DronePredio/testes/pouso_campo -windowed -resx=1920 -resy=1080
echo --- predio
type "D:\DronePredio\testes\pouso_predio\teste_pouso.txt"
echo --- campo
type "D:\DronePredio\testes\pouso_campo\teste_pouso.txt"
echo TUDO OK
