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
echo === recursos do campo (texturas e modelos da Godot)
if not exist "D:\DronePredio\recursos_campo\" (
  powershell -NoProfile -Command "Expand-Archive -Force 'C:\drone\voo_e88_recursos.zip' 'D:\DronePredio\recursos_campo'"
)
echo === montar o mapa do campo
del /q "D:\DronePredio\logs\construir_campo_progresso.txt" >nul 2>&1
start "" /wait "D:\JOGOS\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "D:\DronePredio\PredioDrone\PredioDrone.uproject" -ExecutePythonScript="D:/DronePredio/unreal/construir_campo.py" -unattended -nosplash -NoLiveCoding
type "D:\DronePredio\logs\construir_campo_progresso.txt"
findstr /c:"TUDO PRONTO" "D:\DronePredio\logs\construir_campo_progresso.txt" >nul || ( echo CAMPO FALHOU & exit /b 1 )
echo TUDO OK
