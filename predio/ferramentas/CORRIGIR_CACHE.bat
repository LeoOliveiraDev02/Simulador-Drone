@echo off
chcp 65001 >nul
if not "%~1"=="log" (
  if not exist "%~dp0logs" mkdir "%~dp0logs"
  echo Arrumando o cache do Unreal e refazendo tudo ...
  call "%~f0" log > "%~dp0logs\%~n0.log" 2>&1
  echo FIM %date% %time% >> "%~dp0logs\%~n0.log"
  exit /b
)
rem O cache antigo (Zen) foi parar em DDC\ mas o Unreal procura em DDC\Zen.
set "D=D:\DronePredio\DDC"
taskkill /im UnrealEditor.exe /f
taskkill /im ShaderCompileWorker.exe /f >nul 2>&1
timeout /t 8 /nobreak >nul
taskkill /im zenserver.exe /f
timeout /t 4 /nobreak >nul
if exist "%D%\Zen" rmdir /s /q "%D%\Zen"
mkdir "%D%\Zen"
for %%I in (.sentry-native auth cache cas gc logs projects sessions) do if exist "%D%\%%I" move "%D%\%%I" "%D%\Zen\%%I"
for %%I in (root_manifest state_marker) do if exist "%D%\%%I" move "%D%\%%I" "%D%\Zen\%%I"
dir "%D%"
dir "%D%\Zen"
timeout /t 5 /nobreak >nul
start "" "D:\DronePredio\REFAZER_TUDO.bat"
echo REFAZER iniciado
