@echo off
chcp 65001 >nul
setlocal
REM ============================================================
REM  Simulador de Drone - cena de teste grafico (Godot 4.7.2)
REM  1) baixa o Godot (se precisar)  2) baixa texturas/modelos
REM  3) importa  4) tira os prints  5) abre a cena para explorar
REM ============================================================
cd /d "%~dp0"
set GODOT_DIR=%~dp0ferramentas\godot
set GODOT=%GODOT_DIR%\Godot_v4.7.2-stable_win64.exe

if not exist "%GODOT%" (
  echo Baixando o Godot 4.7.2...
  mkdir "%GODOT_DIR%" 2>nul
  powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_win64.exe.zip' -OutFile '%GODOT_DIR%\godot.zip'; Expand-Archive -Force '%GODOT_DIR%\godot.zip' '%GODOT_DIR%'"
)

REM Python: usa o do sistema ou o que vem com o Blender
set PY=python
where python >nul 2>nul || set PY="C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"

echo Baixando texturas e modelos (Poly Haven, CC0)...
%PY% baixar_recursos.py godot

echo Importando recursos (demora alguns minutos na primeira vez)...
"%GODOT%" --headless --path godot --import

echo Tirando os prints em qualidade maxima...
"%GODOT%" --path godot --resolution 1920x1080 -- --prints --esperar=240

echo Prints salvos em godot\prints
start "" "%~dp0godot\prints"

echo Abrindo a cena para explorar (botao direito + mouse, WASD, 1/2/3, F12)...
"%GODOT%" --path godot --resolution 1920x1080
endlocal
