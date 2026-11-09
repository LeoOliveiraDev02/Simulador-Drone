@echo off
chcp 65001 >nul
REM Simulador de Drone - Fase 1: abre a bancada com os 4 drones no Godot 4.7.2
cd /d "%~dp0"
set GODOT_DIR=%~dp0..\ferramentas\godot
set GODOT=%GODOT_DIR%\Godot_v4.7.2-stable_win64.exe
if not exist "%GODOT%" (
  echo Baixando o Godot 4.7.2 (so na primeira vez)...
  mkdir "%GODOT_DIR%" 2>nul
  powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_win64.exe.zip' -OutFile '%GODOT_DIR%\godot.zip'; Expand-Archive -Force '%GODOT_DIR%\godot.zip' '%GODOT_DIR%'"
)
if not exist ".godot" (
  echo Preparando os modelos (primeira vez demora um pouco)...
  "%GODOT%" --headless --path . --import
)
"%GODOT%" --path .
