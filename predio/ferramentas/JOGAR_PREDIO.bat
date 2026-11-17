@echo off
rem Abre o mapa do PREDIO EM CONSTRUCAO (Unreal 5.8 + AMD FSR 4 + gerador de quadros)
if not exist "D:\DronePredio\jogo\Windows\PredioDrone.exe" (
  echo O jogo ainda nao foi empacotado. Rode EMPACOTAR_JOGO.bat.
  pause
  exit /b
)
start "" "D:\DronePredio\jogo\Windows\PredioDrone.exe" -NotInstalled
