@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "fase1\project.godot" (
  echo Descompactando a Fase 1...
  tar -xf "fase1.zip"
)
echo Abrindo o Simulador de Drone - Fase 1...
start "" "%~dp0Godot\Godot_v4.7.2-stable_win64.exe" --path "%~dp0fase1"
