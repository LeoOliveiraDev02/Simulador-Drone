@echo off
chcp 65001 >nul
if not "%~1"=="log" (
  if not exist "%~dp0logs" mkdir "%~dp0logs"
  echo Rodando %~nx0 ... a janela fecha sozinha quando terminar.
  call "%~f0" log > "%~dp0logs\%~n0.log" 2>&1
  echo FIM %date% %time% >> "%~dp0logs\%~n0.log"
  exit /b
)
if not exist "C:\drone\predio\testes" mkdir "C:\drone\predio\testes"
del /q "C:\drone\predio\testes\*.*" >nul 2>&1
start "" /wait "D:\JOGOS\UE_5.8\_PredioDrone_jogo\Windows\PredioDrone.exe" -tour -pastatestes=C:/drone/predio/testes -windowed -resx=1920 -resy=1080
type "C:\drone\predio\testes\tour_resultado.txt"
dir "C:\drone\predio\testes"
