@echo off
chcp 65001 >nul
if not "%~1"=="log" (
  if not exist "%~dp0logs" mkdir "%~dp0logs"
  echo Rodando %~nx0 ... a janela fecha sozinha quando terminar.
  call "%~f0" log > "%~dp0logs\%~n0.log" 2>&1
  echo FIM %date% %time% >> "%~dp0logs\%~n0.log"
  exit /b
)
if not exist "D:\DronePredio\testes" mkdir "D:\DronePredio\testes"
del /q "D:\DronePredio\testes\*.*" >nul 2>&1
start "" /wait "D:\DronePredio\jogo\Windows\PredioDrone.exe" -NotInstalled -tour -pastatestes=D:/DronePredio/testes -windowed -resx=1920 -resy=1080
type "D:\DronePredio\testes\tour_resultado.txt"
dir "D:\DronePredio\testes"
