@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Simulador de Drone - Voo do E88
set GODOT="%~dp0Godot\Godot_v4.7.2-stable_win64.exe"

REM instala (ou atualiza) o projeto quando chega um zip novo
if exist "voo_e88_recursos.zip" (
  echo Instalando o mapa: texturas, arvores e ceu - so na primeira vez, pode demorar...
  tar -xf "voo_e88_recursos.zip"
  move /y "voo_e88_recursos.zip" "voo_e88_recursos_instalado.zip" >nul
)
if exist "voo_e88.zip" (
  echo Instalando a versao nova do voo do E88...
  tar -xf "voo_e88.zip"
  move /y "voo_e88.zip" "voo_e88_instalado.zip" >nul
)
if not exist "voo_e88\.godot\imported" (
  echo.
  echo Preparando os modelos e texturas para a placa de video.
  echo Isso so acontece na primeira vez e leva alguns minutos...
  %GODOT% --headless --path "%~dp0voo_e88" --import
)
echo Abrindo o voo do E88...
start "" %GODOT% --path "%~dp0voo_e88"
