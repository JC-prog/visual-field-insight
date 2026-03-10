# Changelog

All notable changes to this project will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.1.0] — 2026-03-10

### Added
- `"type"` field in template sections — `"text"` for key-value header fields, `"map"` for numeric visual field grids
- Gridline removal pre-processing (`remove_gridlines()` in `core/pipeline.py`) applied automatically to all sections with `"type": "map"` before OCR, improving number extraction accuracy

### Changed
- `core/normalize.py` now routes normalization by the section's `"type"` field instead of matching hardcoded section names — any custom section name works as long as `"type"` is set correctly
- `core/pipeline.py` applies gridline removal conditionally per section based on `"type"`

### Removed
- `utils/ocr.py` and the `utils/` directory — gridline removal logic consolidated into `core/pipeline.py`

---

## [1.0.0] — 2026-03-10

### Added
- Streamlit web UI with sidebar navigation (Single Extract, Batch Extract, Templates)
- **Single Extract** — upload LE and/or RE files (PDF/PNG/JPG), run OCR, download results as CSV or JSON in-memory (no disk writes)
- **Batch Extract** — scan `data/input/` for patient subfolders, process all files, save combined CSV to `data/output/`
- **Template Editor** — view and edit OCR region templates as JSON directly in the browser, with validation before save
- Eye detection from filename: supports `_LE`/`_RE` and `_OS`/`_OD` conventions (case-insensitive)
- Consolidated template format — `HVF.json` and `VRVF.json` each contain both `LE` and `RE` eye definitions in a single file
- `core/config.py` — runtime path detection that works in both development (repo root) and distributed (`dist/app/`) layouts
- Portable Windows build script (`scripts/build_portable.bat`) producing a clean 3-item dist layout: `run.bat`, `data/`, `app/`
- Offline-first OCR — PaddleOCR models bundled in `app/models/`; no internet required on target machine

### Changed
- Rebuilt from `vf-extractor` with a simpler flat module structure (`core/`) instead of a pip-installable package
- Templates consolidated from four separate eye-specific files (`HVF_LE.json`, `HVF_RE.json`, `VRVF_left.json`, `VRVF_RE.json`) into two unified files
- Single Extract no longer saves intermediate files to `data/output/` — results are generated in-memory for download only
- Dist layout restructured: app source, Python runtime, and models moved into `dist/app/`; user-facing `data/` folder placed at `dist/` root

### Removed
- Unused stubs (`detectors/`, `parsers/`, `utils/` directories from old project)
- Dependency on `setup.py` / pip-installable package structure
