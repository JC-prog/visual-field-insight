# Distribution Guide

This document explains how to build and deliver the portable version of Visual Field Insight to a target machine that has no internet connection and no Python installation.

---

## Overview

The build script packages everything into a single `dist\` folder:

```
dist\
├── run.bat          ← user double-clicks this to launch
├── data\
│   ├── input\       ← patient folders go here (batch mode)
│   ├── output\      ← batch results are saved here
│   └── templates\   ← OCR templates (editable in-app)
└── app\
    ├── python\      ← embedded Python 3.12 runtime
    ├── models\      ← bundled PaddleOCR models (~600 MB)
    ├── core\        ← extraction logic
    ├── views\       ← Streamlit UI
    └── app.py       ← entry point
```

Copy the entire `dist\` folder to the target machine. No installation required.

---

## Prerequisites (Build Machine Only)

The build must be run on an **internet-connected Windows machine**.

- Windows 10 or 11
- `curl` available (built into Windows 10+)
- `tar` available (built into Windows 10+)
- The `models\` folder must be populated before building (see below)

---

## Step 1 — Populate the Models Folder

PaddleOCR downloads its models on first use. You need to trigger this download once on the build machine, then copy the cache into `models\`.

**Option A — Run the app locally first**

1. Install dependencies in a local Python environment:
   ```
   pip install -r requirements.txt
   ```
2. Launch the app:
   ```
   streamlit run app.py
   ```
3. Upload any test image and run an extraction. PaddleOCR will download its models automatically.
4. Find the downloaded model cache. By default PaddleOCR stores them at:
   ```
   %USERPROFILE%\.paddleocr\
   ```
   or inside `models\paddlex\` if `VF_MODELS_DIR` was set.
5. Copy the cache contents into `models\paddlex\` in the project root:
   ```
   xcopy /E /I "%USERPROFILE%\.paddleocr" "models\paddlex"
   ```

**Option B — Copy models from an existing dist**

If you already have a working `dist\` from a previous build, copy `dist\app\models\` back to `models\` in the project root:
```
xcopy /E /I "dist\app\models" "models"
```

---

## Step 2 — Run the Build Script

From the project root, run:
```
scripts\build_portable.bat
```

The script will:
1. Download Python 3.12.10 embeddable runtime
2. Configure the runtime for offline use
3. Install all dependencies from `requirements.txt`
4. Copy app source, models, and templates into `dist\app\`
5. Create `dist\data\` with empty `input\` and `output\` folders
6. Write `dist\run.bat`

Build time is approximately **15–30 minutes** depending on internet speed. The output will be approximately **1.4 GB**.

---

## Step 3 — Verify the Build

Before delivering, do a quick smoke test on the build machine:

1. Open `dist\run.bat`
2. Wait for the browser to open (up to 60 seconds on first launch)
3. Upload a test file in Single Extract and confirm results are returned
4. Place a test patient folder in `dist\data\input\` and run Batch Extract

If extraction works, the build is good.

---

## Step 4 — Deliver to Target Machine

Copy the entire `dist\` folder to the target machine. Methods:
- USB drive
- Network share
- Any file transfer tool

**Do not rename or restructure the folder.** The launcher (`run.bat`) references `app\` by relative path.

Recommended delivery location on the target machine:
```
C:\VisualFieldInsight\
```

Instruct the user to double-click `run.bat` to launch the app.

---

## Updating the App

To update an existing installation on the target machine:

| What changed | Action |
|---|---|
| Source code only (`core\`, `views\`, `app.py`) | Copy updated files into `dist\app\` on the target, overwriting the old ones |
| Dependencies or Python version | Run a full rebuild and replace the entire `dist\` folder |
| Templates only | Copy updated `data\templates\*.json` into `dist\data\templates\` |
| OCR models | Copy updated models into `dist\app\models\` |

> **Note:** When replacing the full `dist\` folder, preserve the contents of `dist\data\input\` and `dist\data\output\` if the user has data there.

---

## Troubleshooting the Build

**`models\` directory not found**
Populate `models\` before running the build script. See Step 1.

**pip install fails**
Check that the build machine has internet access. Some packages are large — ensure there is enough disk space (at least 3 GB free during build).

**`python312._pth` not found**
The Python embeddable version must be exactly 3.12.x. If the download failed or the zip is corrupt, delete `dist\` and re-run the script.

**Target machine: browser does not open**
The first launch can take up to 60 seconds while PaddleOCR initialises. If the browser still does not open, navigate to `http://localhost:8501` manually.

**Target machine: `run.bat` closes immediately**
The terminal window closes if the app crashes on startup. Open a Command Prompt, navigate to `dist\`, and run `run.bat` manually to see the error output.
