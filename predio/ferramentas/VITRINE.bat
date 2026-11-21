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
echo === montar a vitrine de testes
del /q "D:\DronePredio\logs\construir_vitrine_progresso.txt" >nul 2>&1
start "" /wait "D:\JOGOS\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "D:\DronePredio\PredioDrone\PredioDrone.uproject" -ExecutePythonScript="D:/DronePredio/unreal/construir_vitrine.py" -unattended -nosplash -NoLiveCoding
type "D:\DronePredio\logs\construir_vitrine_progresso.txt"
findstr /c:"TUDO PRONTO" "D:\DronePredio\logs\construir_vitrine_progresso.txt" >nul || ( echo VITRINE FALHOU & exit /b 1 )
echo === empacotar (jogo unico: menu + campo + predio)
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -noP4 -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -iostore -compressed -prereqs -archive -archivedirectory="D:\DronePredio\jogo" -unattended -utf8output -NoCodeSign
if errorlevel 1 ( echo EMPACOTAMENTO FALHOU & exit /b 1 )
echo === atalho unico na area de trabalho
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ATALHO_JOGO.ps1"
echo === teste: voo pela vitrine (fotos do chao e das arvores)
if not exist "D:\DronePredio\testes\vitrine" mkdir "D:\DronePredio\testes\vitrine"
del /q "D:\DronePredio\testes\vitrine\*.*" >nul 2>&1
start "" /wait "%EXE%" -mapa=Vitrine -NotInstalled -tour -vento=35 -pastatestes=D:/DronePredio/testes/vitrine -windowed -resx=1920 -resy=1080
type "D:\DronePredio\testes\vitrine\tour_resultado.txt"
echo TUDO OK
