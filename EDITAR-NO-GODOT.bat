@echo off
cd /d "%~dp0"
if not exist "fase1\project.godot" tar -xf "fase1.zip"
start "" "%~dp0Godot\Godot_v4.7.2-stable_win64.exe" -e --path "%~dp0fase1"
