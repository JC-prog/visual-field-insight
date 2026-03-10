# Visual Field Insight — User Guide

## Overview

Visual Field Insight extracts structured data from Humphrey Visual Field (HVF) and Virtual Reality Visual Field (VRVF) reports. It reads PDF or image files and outputs the results as a CSV or JSON file that can be opened in Excel or imported into other systems.

---

## Getting Started

1. Open the `dist\` folder on your machine
2. Double-click **`run.bat`**
3. A terminal window will open — wait for it to finish loading (first launch may take up to a minute)
4. Your browser will open automatically at `http://localhost:8501`

> Do not close the terminal window while using the app. Close it when you are done.

---

## Navigation

Use the **sidebar on the left** to switch between the three modes:

| Mode | Purpose |
|---|---|
| **Single Extract** | Extract data from one patient's files immediately |
| **Batch Extract** | Process many patients at once from the input folder |
| **Templates** | View or edit the OCR region configuration |

---

## Single Extract

Use this when you have one patient's files and want results right away.

### Steps

1. Select **Single Extract** in the sidebar
2. Choose the template that matches your report type (e.g. `HVF` or `VRVF`)
3. Upload the **Left Eye (LE)** file and/or the **Right Eye (RE)** file
   - Accepted formats: PDF, PNG, JPG, JPEG
   - You can upload just one eye if needed
4. Click **Run Extraction**
5. Wait for the spinner to finish
6. Choose a download format — **CSV** or **JSON**
7. Click **Download**

### Notes

- PDF files are automatically converted to images before processing
- Results are shown in a preview table below the download button
- Nothing is saved to disk — the download is generated in memory

---

## Batch Extract

Use this to process multiple patients in one go.

### Preparing the Input Folder

Place patient folders inside `data\input\`. Each patient gets their own subfolder. File names **must** include `_LE` or `_RE` (or `_OS` / `_OD`) to identify the eye:

```
data\input\
  Patient001\
    001_HVF_LE.pdf
    001_HVF_RE.pdf
  Patient002\
    002_HVF_LE.pdf
    002_HVF_RE.pdf
```

Files without `_LE`, `_RE`, `_OS`, or `_OD` in the name will be skipped.

### Steps

1. Select **Batch Extract** in the sidebar
2. Choose the template that matches your report type
3. Review the detected files listed on screen
4. Click **Run Batch Extraction**
5. A progress bar will show as each file is processed
6. When complete, the results are saved automatically to `data\output\batch_YYYYMMDD_HHMMSS.csv`
7. A **Download CSV** button also appears so you can save a copy directly from the browser

### Output File

The output CSV has one row per file processed, with columns:

| Column | Description |
|---|---|
| `patient` | Patient folder name |
| `eye` | `LE` or `RE` |
| `file` | Original filename |
| `header_Date` | Test date |
| `header_Age` | Patient age |
| `threshold_map_ST1` … | Threshold map values |
| `total_deviation_ST1` … | Total deviation values |
| `pattern_deviation_ST1` … | Pattern deviation values |
| `ght_vfi_GHT` | Glaucoma Hemifield Test result |
| `ght_vfi_VFI24-2` | Visual Field Index |
| `ght_vfi_MD24-2` | Mean Deviation |
| `ght_vfi_PSD24-2` | Pattern Standard Deviation |

---

## Templates

Templates define which regions of the report image to scan and what fields to extract from each region. You only need this section if the extraction results are incorrect or you are adding a new report type.

### Viewing and Editing a Template

1. Select **Templates** in the sidebar
2. Choose the template file from the dropdown (e.g. `HVF.json`)
3. The full JSON is shown in an editable text area
4. Make your changes
5. Click **Save**
   - The app validates the JSON before saving
   - If there is a syntax error, an error message will appear and nothing will be saved

### Template Structure

Each template file contains two top-level sections — `LE` (left eye) and `RE` (right eye). Within each eye, sections like `header`, `threshold_map`, `total_deviation`, `pattern_deviation`, and `ght_vfi` each define:

- **`crop_region`** — `[x, y, width, height]` in pixels, specifying which part of the image to scan
- **`type`** — how the crop is processed before text is extracted (`"text"` or `"map"`)
- **`labels`** — the ordered list of field names expected in that region

```json
{
  "LE": {
    "header": {
      "crop_region": [0, 370, 1644, 297],
      "type": "text",
      "labels": ["Fixation Monitor", "Date", "Age", ...]
    },
    "threshold_map": {
      "crop_region": [348, 612, 517, 507],
      "type": "map",
      "labels": ["ST1", "ST2", ...]
    }
  },
  "RE": { ... }
}
```

**Section types:**

| `type` | Used for | Behaviour |
|---|---|---|
| `"text"` | Header fields, test details, GHT/VFI summary | OCR runs directly on the cropped region |
| `"map"` | Threshold map, total deviation, pattern deviation | Gridlines are automatically removed before OCR to improve number recognition |

> **Tip:** If values are consistently wrong for a particular field, the `crop_region` coordinates may need adjustment. Use an image viewer that shows pixel coordinates to find the correct region.

---

## File Naming Reference

| Suffix | Meaning |
|---|---|
| `_LE` or `_OS` | Left eye |
| `_RE` or `_OD` | Right eye |

Both conventions are supported. The suffix is case-insensitive (`_le`, `_LE`, `_Le` all work).

---

## Troubleshooting

**The app does not open in the browser**
- Wait up to 60 seconds on first launch for models to load
- If the browser does not open automatically, go to `http://localhost:8501` manually

**Extraction returns empty or incorrect values**
- Confirm the correct template is selected for the report type
- Check that the report image is clear and not rotated
- Try a PNG export of the PDF at high resolution if results are poor

**A file is skipped in batch mode**
- The filename must contain `_LE`, `_RE`, `_OS`, or `_OD`
- The file must be inside a patient subfolder (not directly in `data\input\`)
- Supported formats: PDF, PNG, JPG, JPEG

**The terminal window shows an error on launch**
- Do not move or rename the `app\` folder — the launcher depends on its location relative to `run.bat`
