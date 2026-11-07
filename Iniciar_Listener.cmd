@echo off
title F1 2026 Showrunner - Discord Listener
cd /d "%~dp0"
echo ==================================================================
echo    F1 2026 SIMULATOR - DISCORD SHOWRUNNER LISTENER
echo ==================================================================
echo [DIRETORIO] %~dp0

set "PYTHON_EXE=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYTHON_EXE%" (
    for /f "delims=" %%i in ('where python.exe 2^>nul') do (
        set "PYTHON_EXE=%%i"
        goto :found
    )
)
:found
if not exist "%PYTHON_EXE%" (
    echo [ERRO] Python nao encontrado.
    pause
    exit /b 1
)

echo [PYTHON]    %PYTHON_EXE%
echo [STATUS]    Iniciando listener do Discord (#geral + DMs privadas)...
echo [INFO]      Pressione Ctrl+C para encerrar com seguranca.
echo ==================================================================
echo.

set PYTHONUNBUFFERED=1
"%PYTHON_EXE%" -m src.orchestrator_cli --action watch-discord %*
if errorlevel 1 (
    echo.
    echo [AVISO] Listener encerrado com codigo %errorlevel%.
    pause
)
