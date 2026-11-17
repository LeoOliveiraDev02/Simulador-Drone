@echo off
chcp 65001 >nul
if not "%~1"=="log" (
  if not exist "%~dp0logs" mkdir "%~dp0logs"
  echo Rodando %~nx0 ... a janela fecha sozinha quando terminar.
  call "%~f0" log > "%~dp0logs\%~n0.log" 2>&1
  echo FIM %date% %time% >> "%~dp0logs\%~n0.log"
  exit /b
)
echo === Visual Studio (vswhere) ===
"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe" -all -prerelease -products * -format text
echo === componentes C++ ===
"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe" -all -prerelease -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
echo === Windows SDK ===
dir "C:\Program Files (x86)\Windows Kits\10\Include" /b
echo === dotnet ===
dotnet --list-sdks
echo === GPU ===
powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select Name,DriverVersion | Format-List; Get-CimInstance Win32_OperatingSystem | Select Caption,Version | Format-List; Get-PSDrive -PSProvider FileSystem | Select Name,Free,Used | Format-Table"
echo === UE ===
type "D:\JOGOS\UE_5.8\Engine\Build\Build.version"
