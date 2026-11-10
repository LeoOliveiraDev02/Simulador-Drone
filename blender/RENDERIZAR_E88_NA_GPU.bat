@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Simulador de Drone - render do E88 na placa de video
set BLENDER="C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
if not exist %BLENDER% (
  for /d %%D in ("C:\Program Files\Blender Foundation\Blender*") do set BLENDER="%%D\blender.exe"
)
if not exist renders_e88 mkdir renders_e88
echo Usando: %BLENDER%
echo Renderizando 4 fotos em 4K (1024 amostras cada) na placa de video...
echo.
%BLENDER% -b "%~dp0e88_estudio.blend" -P "%~dp0renderizar.py" -- "%~dp0renders_e88"
echo PRONTO > "%~dp0renders_e88\PRONTO.txt"
echo.
echo Terminou! As fotos estao em %~dp0renders_e88
start "" "%~dp0renders_e88"
pause
