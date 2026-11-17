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
taskkill /im PredioDrone.exe /f >nul 2>&1
echo === 1/4 compilar editor
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\Build.bat" PredioDroneEditor Win64 Development -Project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -WaitMutex -NoHotReloadFromIDE
if errorlevel 1 ( echo COMPILACAO FALHOU & exit /b 1 )
echo === 2/4 montar o mapa
del /q "D:\DronePredio\logs\construir_mapa_progresso.txt" >nul 2>&1
start "" /wait "D:\JOGOS\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "D:\DronePredio\PredioDrone\PredioDrone.uproject" -ExecutePythonScript="D:/DronePredio/unreal/construir_mapa.py" -unattended -nosplash -NoLiveCoding
type "D:\DronePredio\logs\construir_mapa_progresso.txt"
findstr /c:"TUDO PRONTO" "D:\DronePredio\logs\construir_mapa_progresso.txt" >nul || ( echo MAPA FALHOU & exit /b 1 )
echo === 3/4 empacotar
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -noP4 -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -iostore -compressed -prereqs -archive -archivedirectory="D:\DronePredio\jogo" -unattended -utf8output -NoCodeSign
if errorlevel 1 ( echo EMPACOTAMENTO FALHOU & exit /b 1 )
echo === 4/4 voo de teste
if not exist "D:\DronePredio\testes" mkdir "D:\DronePredio\testes"
del /q "D:\DronePredio\testes\*.*" >nul 2>&1
start "" /wait "D:\DronePredio\jogo\Windows\PredioDrone.exe" -NotInstalled -tour -pastatestes=D:/DronePredio/testes -windowed -resx=1920 -resy=1080
type "D:\DronePredio\testes\tour_resultado.txt"
del /q "D:\JOGOS\UE_5.8\MOVER_PREDIO_PARA_D.bat" >nul 2>&1
del /q "D:\JOGOS\UE_5.8\MOVER_PREDIO_PARA_D.log" >nul 2>&1
echo TUDO OK
