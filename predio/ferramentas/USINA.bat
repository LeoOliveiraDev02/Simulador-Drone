@echo off
chcp 65001 >nul
if not "%~1"=="log" (
  if not exist "%~dp0logs" mkdir "%~dp0logs"
  echo Rodando %~nx0 ... a janela fecha sozinha quando terminar.
  call "%~f0" log > "%~dp0logs\%~n0.log" 2>&1
  echo FIM %date% %time% >> "%~dp0logs\%~n0.log"
  exit /b
)
rem MAPA 3 - usina siderurgica abandonada: compila, monta o mapa, empacota, atalho, voo de teste com fotos
set "UE-LocalDataCachePath=D:\DronePredio\DDC"
set "EXE=D:\DronePredio\jogo\Windows\PredioDrone.exe"
taskkill /im UnrealEditor.exe /f >nul 2>&1
taskkill /im PredioDrone.exe /f >nul 2>&1
taskkill /im PredioDrone-Win64-Shipping.exe /f >nul 2>&1
echo === compilar
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\Build.bat" PredioDroneEditor Win64 Development -Project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -WaitMutex -NoHotReloadFromIDE
if errorlevel 1 ( echo COMPILACAO FALHOU & exit /b 1 )
if "%PULAR_MAPA%"=="1" goto empacotar
echo === montar a usina
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0rodar_editor.ps1" -Script "D:/DronePredio/unreal/construir_usina.py" -Progresso "D:\DronePredio\logs\construir_usina_progresso.txt"
if errorlevel 1 ( echo USINA FALHOU & exit /b 1 )
if exist "%~dp0refazer_vitrine.flag" (
  echo === montar a vitrine de testes
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0rodar_editor.ps1" -Script "D:/DronePredio/unreal/construir_vitrine.py" -Progresso "D:\DronePredio\logs\construir_vitrine_progresso.txt"
  del /q "%~dp0refazer_vitrine.flag"
)
:empacotar
echo === empacotar (jogo unico: menu + fazenda + predio + usina)
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -noP4 -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -iostore -compressed -prereqs -archive -archivedirectory="D:\DronePredio\jogo" -unattended -utf8output -NoCodeSign
if errorlevel 1 ( echo EMPACOTAMENTO FALHOU & exit /b 1 )
echo === atalho unico na area de trabalho
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ATALHO_JOGO.ps1"
echo === teste: voo pela usina (fotos)
if not exist "D:\DronePredio\testes\usina" mkdir "D:\DronePredio\testes\usina"
del /q "D:\DronePredio\testes\usina\*.*" >nul 2>&1
start "" /wait "%EXE%" -mapa=Usina -NotInstalled -tour -vento=15 -pastatestes=D:/DronePredio/testes/usina -windowed -resx=1920 -resy=1080
type "D:\DronePredio\testes\usina\tour_resultado.txt"
echo TUDO OK
