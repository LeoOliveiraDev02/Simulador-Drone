cab () 
{ 
    printf '@echo off\r\nchcp 65001 >nul\r\nif not "%%~1"=="log" (\r\n  if not exist "%%~dp0logs" mkdir "%%~dp0logs"\r\n  echo Rodando %%~nx0 ... a janela fecha sozinha quando terminar.\r\n  call "%%~f0" log > "%%~dp0logs\\%%~n0.log" 2>&1\r\n  echo FIM %%date%% %%time%% >> "%%~dp0logs\\%%~n0.log"\r\n  exit /b\r\n)\r\n'
}
