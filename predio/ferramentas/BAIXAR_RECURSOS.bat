@echo off
chcp 65001 >nul
if not "%~1"=="log" (
  if not exist "%~dp0logs" mkdir "%~dp0logs"
  echo Rodando %~nx0 ... a janela fecha sozinha quando terminar.
  call "%~f0" log > "%~dp0logs\%~n0.log" 2>&1
  echo FIM %date% %time% >> "%~dp0logs\%~n0.log"
  exit /b
)
set PY="C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
if not exist %PY% (
  for /d %%D in ("C:\Program Files\Blender Foundation\Blender 5.2\*") do if exist "%%D\python\bin\python.exe" set PY="%%D\python\bin\python.exe"
)
echo usando %PY%
%PY% -I "D:\DronePredio\ferramentas\baixar_recursos_predio.py" "D:\DronePredio\recursos"
