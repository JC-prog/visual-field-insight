@echo off
setlocal

set "ROOT=%~dp0.."
set "VF_MODELS_DIR=%ROOT%\dist\app\models"
set "PADDLE_PDX_CACHE_HOME=%ROOT%\dist\app\models\paddlex"
set "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True"
set "PYTHON=%ROOT%\dist\app\python\python.exe"

if not exist "%PYTHON%" (
    echo ERROR: dist Python not found at %PYTHON%
    echo Run scripts\build_portable.bat first.
    exit /b 1
)

:: Debug images are saved to test\debug_output\ by default.
:: Pass --no-debug to skip, or --save-debug PATH to change the folder.
"%PYTHON%" "%~dp0evaluate.py" %* 2>nul
