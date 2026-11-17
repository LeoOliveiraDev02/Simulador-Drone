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
rem O Unreal pede o ".NET Framework SDK" so para registrar um modulo do editor (SwarmInterface)
rem que ja vem pronto (pre-compilado) no Unreal instalado. Em vez de instalar o SDK (precisa de
rem administrador), aponto a chave do USUARIO para uma pasta vazia. Para desfazer:
rem   reg delete "HKCU\SOFTWARE\Microsoft\Microsoft SDKs\NETFXSDK\4.8" /f
mkdir "D:\DronePredio\ferramentas\netfxsdk\include\um" 2>nul
mkdir "D:\DronePredio\ferramentas\netfxsdk\lib\um\x64" 2>nul
reg add "HKCU\SOFTWARE\Microsoft\Microsoft SDKs\NETFXSDK\4.8" /v KitsInstallationFolder /t REG_SZ /d "D:\DronePredio\ferramentas\netfxsdk\\" /f
reg add "HKCU\SOFTWARE\WOW6432Node\Microsoft\Microsoft SDKs\NETFXSDK\4.8" /v KitsInstallationFolder /t REG_SZ /d "D:\DronePredio\ferramentas\netfxsdk\\" /f
call "D:\JOGOS\UE_5.8\Engine\Build\BatchFiles\Build.bat" PredioDroneEditor Win64 Development -Project="D:\DronePredio\PredioDrone\PredioDrone.uproject" -WaitMutex -NoHotReloadFromIDE
echo codigo=%errorlevel%
