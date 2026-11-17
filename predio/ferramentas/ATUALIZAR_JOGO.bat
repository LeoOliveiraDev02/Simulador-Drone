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
taskkill /im PredioDrone-Win64-Shipping.exe /f >nul 2>&1
echo === 1/3 compilar (sem remontar o mapa)
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\Build.bat" PredioDroneEditor Win64 Development -Project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -WaitMutex -NoHotReloadFromIDE
if errorlevel 1 ( echo COMPILACAO FALHOU & exit /b 1 )
echo === 2/3 empacotar
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -noP4 -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -iostore -compressed -prereqs -archive -archivedirectory="D:\DronePredio\jogo" -unattended -utf8output -NoCodeSign
if errorlevel 1 ( echo EMPACOTAMENTO FALHOU & exit /b 1 )
echo === atalho na area de trabalho
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Drone - Predio em Obra.lnk')); $s.TargetPath='D:\DronePredio\jogo\Windows\PredioDrone.exe'; $s.Arguments='-NotInstalled'; $s.WorkingDirectory='D:\DronePredio\jogo\Windows'; $s.IconLocation='D:\DronePredio\jogo\Windows\PredioDrone.exe,0'; $s.Description='Simulador de Drone - mapa do predio em obra (Unreal 5.8 + AMD FSR 4)'; $s.Save(); 'atalho: ' + (Join-Path $d 'Drone - Predio em Obra.lnk')"
echo === 3/3 voo de teste
if not exist "D:\DronePredio\testes" mkdir "D:\DronePredio\testes"
del /q "D:\DronePredio\testes\*.*" >nul 2>&1
start "" /wait "D:\DronePredio\jogo\Windows\PredioDrone.exe" -NotInstalled -tour -pastatestes=D:/DronePredio/testes -windowed -resx=1920 -resy=1080
type "D:\DronePredio\testes\tour_resultado.txt"
echo TUDO OK
