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
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="C:\drone\predio\PredioDrone\PredioDrone.uproject" -noP4 -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -iostore -compressed -prereqs -archive -archivedirectory="D:\JOGOS\UE_5.8\_PredioDrone_jogo" -unattended -utf8output -NoCodeSign
echo codigo=%errorlevel%
dir "D:\JOGOS\UE_5.8\_PredioDrone_jogo\Windows"
