# Visual Field Insight — User Guide

## Contents

1. [Installation](#1-installation)
2. [Starting the App](#2-starting-the-app)
3. [Single Extract](#3-single-extract)
4. [Batch Extract](#4-batch-extract)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. Installation

You will receive a ZIP file (e.g. `VisualFieldInsight.zip`).

1. **Extract** the ZIP to a location of your choice, for example:
   ```
   C:\VisualFieldInsight\
   ```
2. The extracted folder should look like this:
   ```
   VisualFieldInsight\
   ├── run.bat          ← launch the app by double-clicking this
   ├── data\
   │   ├── input\       ← place patient files here (Batch Extract)
   │   ├── output\      ← batch results are saved here automatically
   │   └── templates\   ← OCR configuration files (do not modify)
   └── app\             ← application files (do not modify)
   ```

> **No installation required.** Python and all required components are included. An internet connection is not needed.

---

## 2. Starting the App

1. Open the `VisualFieldInsight\` folder
2. Double-click **`run.bat`**
3. A black terminal window will appear — leave it open while using the app
4. Your web browser will open automatically at `http://localhost:8501`

> **First launch may take up to 60 seconds** while the app loads its models.
> If the browser does not open automatically, navigate to `http://localhost:8501` manually.

To close the app, close the terminal window.

---

## 3. Single Extract

Use **Single Extract** to process one patient's report immediately and download the results.

### Steps

1. Click **Single Extract** in the left sidebar
2. Select the **template** that matches your report type:
   - `HVF` — Humphrey Visual Field
   - `VRVF` — Virtual Reality Visual Field
3. Upload the patient's file(s):
   - Click **Left Eye (LE)** to upload the left eye report
   - Click **Right Eye (RE)** to upload the right eye report
   - You can upload one or both eyes
   - Accepted formats: **PDF, PNG, JPG, JPEG**
4. Click **Run Extraction**
5. When complete, a results table will appear
6. Choose a download format and click **Download**:
   - **CSV** — opens in Excel
   - **JSON** — for use in other systems

> Results are not saved to disk automatically in Single Extract. Use the Download button to save them.

---

## 4. Batch Extract

Use **Batch Extract** to process multiple patients in one go. Results are saved automatically to the `data\output\` folder.

### Setting Up the Input Folder

Place patient files inside `data\input\`. Each patient must have their own subfolder. File names **must** include `_LE` or `_RE` (or `_OS` / `_OD`) to identify which eye the file belongs to.

**Example folder structure:**

```
data\input\
  Patient001\
    001_HVF_LE.pdf
    001_HVF_RE.pdf
  Patient002\
    002_HVF_LE.pdf
    002_HVF_RE.pdf
  Patient003\
    003_HVF_RE.pdf
```

**File naming rules:**

| Suffix | Eye |
|---|---|
| `_LE` or `_OS` | Left eye |
| `_RE` or `_OD` | Right eye |

- The suffix is **case-insensitive** (`_le`, `_LE`, and `_Le` all work)
- Files without a recognised suffix will be **skipped**
- Files placed directly in `data\input\` (not inside a patient subfolder) will be **skipped**

### Steps

1. Place all patient folders in `data\input\` (see above)
2. Click **Batch Extract** in the left sidebar
3. Select the **template** that matches your report type (`HVF` or `VRVF`)
4. Review the list of detected files shown on screen
5. Click **Run Batch Extraction**
6. A progress bar will update as each file is processed
7. When complete:
   - Results are saved to `data\output\batch_YYYYMMDD_HHMMSS.csv`
   - A **Download CSV** button also appears in the browser

### Output File

The CSV file has one row per processed file. Key columns:

| Column | Description |
|---|---|
| `patient` | Patient folder name |
| `eye` | `LE` or `RE` |
| `file` | Original filename |
| `header_Date` | Test date |
| `header_Age` | Patient age at test |
| `threshold_map_ST1` … | Threshold sensitivity values |
| `total_deviation_ST1` … | Total deviation values |
| `pattern_deviation_ST1` … | Pattern deviation values |
| `ght_vfi_GHT` | Glaucoma Hemifield Test result |
| `ght_vfi_VFI24-2` | Visual Field Index (%) |
| `ght_vfi_MD24-2` | Mean Deviation (dB) |
| `ght_vfi_PSD24-2` | Pattern Standard Deviation (dB) |

---

## 5. Troubleshooting

**The browser does not open after double-clicking `run.bat`**
- Wait up to 60 seconds — the first launch loads the OCR models
- If the browser still does not open, go to `http://localhost:8501` manually

**The terminal window closes immediately**
- Do not move or rename the `app\` folder — the launcher depends on its location
- Open a Command Prompt, navigate to the `VisualFieldInsight\` folder, and run `run.bat` manually to see any error messages

**A file is skipped in Batch Extract**
- Check that the filename contains `_LE`, `_RE`, `_OS`, or `_OD`
- Check that the file is inside a patient subfolder, not directly in `data\input\`
- Supported formats: PDF, PNG, JPG, JPEG

**Extraction returns empty or unexpected values**
- Make sure the correct template is selected for the report type
- The report image should be clear and not rotated or cropped
- Try a PDF export at the highest available resolution if the source image is low quality
