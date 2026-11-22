@echo off
rem fecha o Unreal Editor travado (o trabalho dele ja foi salvo)
taskkill /im UnrealEditor.exe /f
timeout /t 3 >nul
