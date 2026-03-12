# Changelog

All notable changes to this project will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.4.2] — 2026-03-12

### Changed
- Test case folders (`001/`, `002/`, …) moved from `test/` into a new `test_data/` directory at the project root. `test_data/` is gitignored so patient data is never committed.
- `test/evaluate.py`: discovery now searches `test_data/` (project root) instead of `test/`; `results.md` continues to be written to `test/`.

---

## [1.4.1] — 2026-03-12

### Changed
- `scripts/build_portable.bat`: build artefacts are now cached in a `cache\` folder at the project root so they are not re-downloaded on every rebuild.
  - Python embeddable zip (`python-3.12.10-embed-amd64.zip`) — downloaded once and reused from `cache\`.
  - `get-pip.py` — downloaded once and reused from `cache\`.
  - pip packages — `--no-cache-dir` replaced with `--cache-dir cache\pip`; downloaded wheels are reused across rebuilds.
  - First build behaviour is unchanged; subsequent builds skip all three downloads.

---

## [1.4.0] — 2026-03-10

### Added
- **OCR accuracy evaluation framework** (`test/evaluate.py`) — auto-discovers `*_ground_truth.md` files under `test/`, runs the full pipeline against each paired image, and reports per-section exact-match accuracy and MAE for numeric map sections. Debug images (original crop, gridline-removed crop, PaddleOCR bounding-box overlay) are saved to `test/debug_output/` by default; pass `--no-debug` to suppress or `--save-debug DIR` to redirect.
- `test/run_eval.bat` — convenience runner that invokes `evaluate.py` via the dist Python with the required environment variables set; all CLI arguments are forwarded.
- Ground truth file format: `<id>_<TEMPLATE>_<EYE>_ground_truth.md` (e.g. `001_HVF_LE_ground_truth.md`) with named section headings (`Header`, `Threshold Map`, `Total Deviation`, `Pattern Deviation`, `GHT/VFI`) and alternating label/value tokens for text sections or sequential numeric tokens for map sections.

### Changed
- `core/pipeline.py`: added `_sort_by_reading_order()` — clusters detected OCR boxes into rows by y-gap threshold (30 px) and sorts within each row left-to-right by x-centre before sequential label mapping. Fixes reading-order errors in grid layouts where PaddleOCR occasionally returns cells near row boundaries out of sequence.
- Debug mode in Single Extract: `"map_signed"` sections now show two images side by side (original crop and gridline-removed crop), consistent with `"map"` sections.

---

## [1.3.0] — 2026-03-10

### Added
- **`"map_signed"` section type** in templates — deviation maps (`total_deviation`, `pattern_deviation`) now declare `"type": "map_signed"` to preserve minus signs during preprocessing. Blob filtering is skipped for these sections because minus sign ink area after thresholding can fall below any safe size threshold.
- `remove_gridlines()` gains a `blob_filter` parameter (default `True`): set automatically to `False` for `"map_signed"` sections so minus signs are never erased.
- `_MIN_BLOB_AREA = 50` constant in `core/pipeline.py` — residual tick-mark and intersection artifacts below this area (px²) are removed for `"map"` (unsigned) sections only.

### Changed
- `HVF.json` and `VRVF.json`: `total_deviation` and `pattern_deviation` sections (both LE and RE) updated from `"type": "map"` to `"type": "map_signed"`.
- `core/pipeline.py` `extract()`: branches on `"map"` vs `"map_signed"` to call `remove_gridlines()` with the appropriate `blob_filter` setting.
- `core/normalize.py` `normalize_data()`: `"map_signed"` is now handled identically to `"map"` — both route through `normalize_map_data()`.
- Debug mode panel label updated: shows `"map"` or `"map_signed"` type next to each section name.

---

## [1.2.0] — 2026-03-10

### Added
- **Debug mode** in Single Extract — sidebar checkbox reveals a per-section panel showing the original crop, the gridline-removed crop (for `"map"` sections), and the raw OCR text, making it easy to diagnose crop region and extraction issues

### Changed
- `remove_gridlines()` in `core/pipeline.py`: dilation kept at `(3×3) ×1` to avoid erasing minus signs that sit close to gridlines. Residual tick-mark and intersection artifacts are handled by the regex in `normalize_map_data()` rather than by a blob-size filter (a blob filter was trialled and removed — minus signs are thin strokes whose ink area after thresholding falls below any safe threshold)
- `normalize_map_data()` in `core/normalize.py`: replaced strict `re.fullmatch` with `re.search` — numeric content is now extracted from noisy merged tokens (`17..` → `17`, `32--` → `32`) instead of being silently dropped, preventing label-mapping shifts
- `normalize_header_data()` in `core/normalize.py`: replaced comma/colon splitting with newline-based token matching — values that contain commas (`III, White`, `Sep 08, 2025`) or colons (`11:33 AM`, `03:57`) are now extracted intact instead of being truncated at the first delimiter
- `core/pipeline.py`: `"text"` sections now join OCR blocks with `\n` (was `,`) so block boundaries are preserved through to normalization

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
