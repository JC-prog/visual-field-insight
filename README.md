# Visual Field Insight

OCR-based data extraction tool for visual field test reports, built with [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) and [Streamlit](https://streamlit.io).

Supports:
- **HVF** — Humphrey Visual Field (Zeiss Humphrey Field Analyzer)
- **VRVF** — Virtual Reality Visual Field

---

## Features

- **Single Extract** — Upload one or two HVF/VRVF files (PDF or image), run OCR, download results as CSV or JSON
- **Batch Extract** — Process entire patient folders from `data/input/` and export a combined CSV to `data/output/`
- **Template Editor** — View and edit OCR region templates directly in the browser
- Offline-capable — models are bundled; no internet required on the target machine

---

## Project Structure

**Source (this repo):**

```
visual-field-insight/
├── app.py                  # Streamlit entry point
├── core/
│   ├── ocr.py              # PaddleOCR singleton (offline-safe)
│   ├── converter.py        # PDF → image via pymupdf
│   ├── normalize.py        # OCR text → structured data
│   └── pipeline.py         # extract(image, template, eye) → flat dict
├── views/
│   ├── single_view.py      # Single-file extraction UI
│   ├── batch_view.py       # Batch extraction UI
│   └── template_view.py    # Template JSON editor UI
├── data/
│   ├── input/              # Patient folders for batch processing
│   ├── output/             # Batch CSV results
│   └── templates/
│       ├── HVF.json        # HVF template (LE + RE)
│       └── VRVF.json       # VRVF template (LE + RE)
├── models/                 # Bundled PaddleOCR models (not in repo)
├── scripts/
│   └── build_portable.bat  # Portable Windows build script
└── requirements.txt
```

**Distributed package (`dist\`, what end users receive):**

```
dist/
├── run.bat                 # Double-click to launch
├── data/
│   ├── input/              # Drop patient folders here (batch mode)
│   ├── output/             # Batch CSV results appear here
│   └── templates/          # Edit OCR templates here
└── app/                    # App bundle — no need to touch
    ├── python/             # Embedded Python runtime
    └── models/             # Bundled PaddleOCR models (~600 MB)
```

---

## Usage

### Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Single Extract

1. Select **Single Extract** in the sidebar
2. Choose the template (HVF or VRVF)
3. Upload the Left Eye and/or Right Eye file (PDF, PNG, JPG)
4. Click **Run Extraction**
5. Download results as **CSV** or **JSON**

### Batch Extract

Organise input files into patient subfolders under `data/input/`. Each filename must include `_LE` or `_RE` (alternatively `_OS` or `_OD`) to indicate the eye side:

```
data/input/
  Patient001/
    001_HVF_LE.pdf
    001_HVF_RE.pdf
  Patient002/
    002_HVF_LE.pdf
    002_HVF_RE.pdf
```

1. Select **Batch Extract** in the sidebar
2. Choose the template
3. Review the detected files
4. Click **Run Batch Extraction**
5. Results are saved to `data/output/batch_<timestamp>.csv` and available for download

### Template Editor

1. Select **Templates** in the sidebar
2. Choose the template file to edit
3. Modify the JSON (crop regions or labels) in the text area
4. Click **Save**

---

## Templates

Templates are JSON files in `data/templates/` with a top-level `"LE"` and `"RE"` key for each eye. Each section defines a crop region `[x, y, width, height]` and a list of field labels:

```json
{
  "LE": {
    "header": {
      "crop_region": [0, 370, 1644, 297],
      "labels": ["Fixation Monitor", "Date", "Age", ...]
    },
    "threshold_map": {
      "crop_region": [348, 612, 517, 507],
      "labels": ["ST1", "ST2", ...]
    }
  },
  "RE": { ... }
}
```

To add a new template type, create a new `.json` file in `data/templates/` following the same structure.

---

## Portable Build (Offline Deployment)

The target machine requires no Python installation. Run the build script once on an internet-connected machine:

```batch
scripts\build_portable.bat
```

This produces a `dist\` folder (~1.4 GB) containing an embedded Python runtime, all dependencies, bundled OCR models, and a `run.bat` launcher. Copy the entire `dist\` folder to the target machine and double-click `run.bat`.

> **Prerequisites:** Populate `models\` with the PaddleOCR model cache before building. Run the app once locally so models are downloaded, then copy the cache into `models\`.
