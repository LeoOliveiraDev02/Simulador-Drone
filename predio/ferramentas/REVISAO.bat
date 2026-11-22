@echo off
chcp 65001 >nul
if not "%~1"=="log" (
  if not exist "%~dp0logs" mkdir "%~dp0logs"
  echo Rodando %~nx0 ... a janela fecha sozinha quando terminar.
  call "%~f0" log > "%~dp0logs\%~n0.log" 2>&1
  echo FIM %date% %time% >> "%~dp0logs\%~n0.log"
  exit /b
)
rem revisão dos 3 mapas sem recompilar: voo de teste com fotos em cada um + fotos do menu
set "EXE=D:\DronePredio\jogo\Windows\PredioDrone.exe"
taskkill /im PredioDrone.exe /f >nul 2>&1
for %%M in (campo predio usina menu) do (
  if not exist "D:\DronePredio\testes\revisao_%%M" mkdir "D:\DronePredio\testes\revisao_%%M"
  del /q "D:\DronePredio\testes\revisao_%%M\*.*" >nul 2>&1
)
echo === menu (cartoes dos mapas)
start "" /wait "%EXE%" -NotInstalled -fotomenu -pastatestes=D:/DronePredio/testes/revisao_menu -windowed -resx=1920 -resy=1080
echo === fazenda
start "" /wait "%EXE%" -mapa=Campo -NotInstalled -tour -pastatestes=D:/DronePredio/testes/revisao_campo -windowed -resx=1920 -resy=1080
echo === predio
start "" /wait "%EXE%" -NotInstalled -tour -pastatestes=D:/DronePredio/testes/revisao_predio -windowed -resx=1920 -resy=1080
echo === usina
start "" /wait "%EXE%" -mapa=Usina -NotInstalled -tour -pastatestes=D:/DronePredio/testes/revisao_usina -windowed -resx=1920 -resy=1080
for %%M in (campo predio usina) do type "D:\DronePredio\testes\revisao_%%M\tour_resultado.txt"
echo TUDO OK
