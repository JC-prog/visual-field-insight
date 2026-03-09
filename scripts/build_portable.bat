@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM build_portable.bat
REM
REM Builds a self-contained portable folder in dist\ with a
REM clean 3-item layout for end users:
REM
REM   dist\
REM   ├── run.bat          <- double-click to launch
REM   ├── data\            <- user-facing (input / output / templates)
REM   └── app\             <- app bundle (runtime + models + source)
REM
REM Requirements:
REM   - Internet-connected machine
REM   - models\ must be populated before building
REM     (run the app once so PaddleOCR downloads its models,
REM      then copy the cache to models\ in the project root)
REM
REM Output: ~1.4 GB
REM ============================================================

pushd "%~dp0.."
set "ROOT=%CD%"
popd
set "DIST=%ROOT%\dist"
set "APP=%DIST%\app"
set "PY_VERSION=3.12.10"
set "PY_ZIP=python-%PY_VERSION%-embed-amd64.zip"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/%PY_ZIP%"

echo.
echo === Visual Field Insight Portable Builder ===
echo Project root : %ROOT%
echo Output       : %DIST%
echo.

REM --- Check models/ exists ---
if not exist "%ROOT%\models\" (
    echo ERROR: models\ directory not found.
    echo Run the app once on an internet-connected machine so PaddleOCR downloads
    echo its models, then copy the cache to models\ before building.
    pause
    exit /b 1
)

REM --- Clean and create dist ---
if exist "%DIST%" (
    echo Removing existing dist\...
    rmdir /s /q "%DIST%"
)
mkdir "%DIST%"
mkdir "%APP%"

REM ---- Step 1: Download Python embeddable ----
echo [1/6] Downloading Python %PY_VERSION% embeddable...
curl -L -o "%APP%\%PY_ZIP%" "%PY_URL%"
if errorlevel 1 (
    echo ERROR: Failed to download Python embeddable. Check your connection.
    pause
    exit /b 1
)
mkdir "%APP%\python"
tar -xf "%APP%\%PY_ZIP%" -C "%APP%\python"
if errorlevel 1 (
    echo ERROR: Failed to extract Python embeddable zip.
    pause
    exit /b 1
)
del "%APP%\%PY_ZIP%"

REM ---- Step 2: Enable site-packages ----
echo [2/6] Configuring embeddable Python...
set "PTH_FILE=%APP%\python\python312._pth"
if not exist "%PTH_FILE%" (
    echo ERROR: Expected file not found: %PTH_FILE%
    pause
    exit /b 1
)
powershell -Command "(Get-Content '%PTH_FILE%') -replace '#import site', 'import site' | Set-Content '%PTH_FILE%'"

REM ---- Step 3: Install pip ----
echo [3/6] Installing pip...
curl -L -o "%APP%\get-pip.py" https://bootstrap.pypa.io/get-pip.py
if errorlevel 1 (
    echo ERROR: Failed to download get-pip.py.
    pause
    exit /b 1
)
"%APP%\python\python.exe" "%APP%\get-pip.py" --no-warn-script-location
del "%APP%\get-pip.py"

REM ---- Step 4: Install dependencies ----
echo [4/6] Installing Python packages (this will take a while)...
powershell -Command ^
    "$raw = [System.IO.File]::ReadAllBytes('%ROOT%\requirements.txt');" ^
    "$text = if ($raw[1] -eq 0) { [System.Text.Encoding]::Unicode.GetString($raw) } else { [System.Text.Encoding]::UTF8.GetString($raw) };" ^
    "[System.IO.File]::WriteAllText('%APP%\requirements.txt', $text, [System.Text.UTF8Encoding]::new($false))"

"%APP%\python\python.exe" -m pip install -r "%APP%\requirements.txt" ^
    --no-warn-script-location ^
    --no-cache-dir
if errorlevel 1 (
    echo ERROR: Package installation failed.
    pause
    exit /b 1
)

REM ---- Step 5: Copy application source and models ----
echo [5/6] Copying application files...
copy  "%ROOT%\app.py"       "%APP%\app.py"
xcopy /E /I /Q "%ROOT%\core"       "%APP%\core"
xcopy /E /I /Q "%ROOT%\views"      "%APP%\views"
xcopy /E /I /Q "%ROOT%\.streamlit" "%APP%\.streamlit"
xcopy /E /I /Q "%ROOT%\models"     "%APP%\models"

REM User-facing data folder at dist root
mkdir "%DIST%\data\input"
mkdir "%DIST%\data\output"
mkdir "%DIST%\data\templates"
xcopy /E /I /Q "%ROOT%\data\templates" "%DIST%\data\templates"

REM ---- Step 6: Write launcher at dist root ----
echo [6/6] Writing launcher...
(
    echo @echo off
    echo cd /d "%%~dp0"
    echo set "VF_MODELS_DIR=%%~dp0app\models"
    echo set "PADDLE_PDX_CACHE_HOME=%%~dp0app\models\paddlex"
    echo set "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True"
    echo app\python\python.exe -m streamlit run app\app.py --server.port 8501 --server.headless false
    echo pause
) > "%DIST%\run.bat"

echo.
echo === Build complete! ===
echo.
echo   dist\
echo   ├── run.bat       ^<-- double-click to launch
echo   ├── data\         ^<-- drop patient files in data\input\
echo   └── app\          ^<-- runtime + models (no need to touch)
echo.
echo Copy the entire dist\ folder to the target PC and run run.bat.
echo.
pause
