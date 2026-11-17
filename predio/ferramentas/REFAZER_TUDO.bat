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
taskkill /im PredioDrone.exe /f >nul 2>&1
echo === 1/4 compilar editor
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\Build.bat" PredioDroneEditor Win64 Development -Project="C:\drone\predio\PredioDrone\PredioDrone.uproject" -WaitMutex -NoHotReloadFromIDE
if errorlevel 1 ( echo COMPILACAO FALHOU & exit /b 1 )
echo === 2/4 montar o mapa
start "" /wait "D:\JOGOS\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "C:\drone\predio\PredioDrone\PredioDrone.uproject" -ExecutePythonScript="C:/drone/predio/unreal/construir_mapa.py" -unattended -nosplash -NoLiveCoding
type "C:\drone\predio\logs\construir_mapa_progresso.txt"
findstr /c:"TUDO PRONTO" "C:\drone\predio\logs\construir_mapa_progresso.txt" >nul || ( echo MAPA FALHOU & exit /b 1 )
echo === 3/4 empacotar
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="C:\drone\predio\PredioDrone\PredioDrone.uproject" -noP4 -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -iostore -compressed -prereqs -archive -archivedirectory="D:\JOGOS\UE_5.8\_PredioDrone_jogo" -unattended -utf8output -NoCodeSign
if errorlevel 1 ( echo EMPACOTAMENTO FALHOU & exit /b 1 )
echo === 4/4 voo de teste
if not exist "C:\drone\predio\testes" mkdir "C:\drone\predio\testes"
del /q "C:\drone\predio\testes\*.*" >nul 2>&1
start "" /wait "D:\JOGOS\UE_5.8\_PredioDrone_jogo\Windows\PredioDrone.exe" -tour -pastatestes=C:/drone/predio/testes -windowed -resx=1920 -resy=1080
type "C:\drone\predio\testes\tour_resultado.txt"
echo TUDO OK
