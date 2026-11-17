@echo off
chcp 65001 >nul
if not "%~1"=="log" (
  if not exist "%~dp0logs" mkdir "%~dp0logs"
  echo Rodando %~nx0 ... a janela fecha sozinha quando terminar.
  call "%~f0" log > "%~dp0logs\%~n0.log" 2>&1
  echo FIM %date% %time% >> "%~dp0logs\%~n0.log"
  exit /b
)
set DEST=D:\JOGOS\UE_5.8\Engine\Plugins\Marketplace
set TMPX=C:\drone\predio\baixados\amd_extraido
if not exist "%DEST%" mkdir "%DEST%"
if exist "%TMPX%" rmdir /s /q "%TMPX%"
mkdir "%TMPX%"
tar -xf C:\drone\predio\baixados\amd_fsr_parte1.zip -C "%TMPX%"
tar -xf C:\drone\predio\baixados\amd_fsr_parte2.zip -C "%TMPX%"
robocopy "%TMPX%\plugins_fsr\FSR" "%DEST%\FSR" /E /NFL /NDL /NJH
robocopy "%TMPX%\plugins_fsr\FSRMovieRenderPipeline" "%DEST%\FSRMovieRenderPipeline" /E /NFL /NDL /NJH
robocopy "%TMPX%\plugins_antilag2\AntiLag2" "%DEST%\AntiLag2" /E /NFL /NDL /NJH
dir "%DEST%"
