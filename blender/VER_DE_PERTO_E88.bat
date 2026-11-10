@echo off
cd /d "%~dp0"
set BLENDER="C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
if not exist %BLENDER% (
  for /d %%D in ("C:\Program Files\Blender Foundation\Blender*") do set BLENDER="%%D\blender.exe"
)
start "" %BLENDER% "%~dp0e88_estudio.blend" --python "%~dp0ver_de_perto.py"
