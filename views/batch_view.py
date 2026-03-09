import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from core.config import TEMPLATES_DIR, INPUT_DIR, OUTPUT_DIR

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


def _discover_templates() -> dict[str, Path]:
    if not TEMPLATES_DIR.exists():
        return {}
    return {p.stem: p for p in sorted(TEMPLATES_DIR.glob("*.json"))}


def _detect_eye(filename: str) -> str | None:
    """Return 'LE' or 'RE' from filename, or None if ambiguous."""
    stem = Path(filename).stem.upper()
    has_le = "_LE" in stem or "_OS" in stem
    has_re = "_RE" in stem or "_OD" in stem
    if has_le and not has_re:
        return "LE"
    if has_re and not has_le:
        return "RE"
    return None


def _scan_input_dir() -> dict[str, list[Path]]:
    """Return {patient_name: [file_path, ...]} for each subdir in INPUT_DIR."""
    patients: dict[str, list[Path]] = {}
    if not INPUT_DIR.exists():
        return patients
    for patient_dir in sorted(INPUT_DIR.iterdir()):
        if not patient_dir.is_dir():
            continue
        files = [
            f for f in sorted(patient_dir.iterdir())
            if f.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        if files:
            patients[patient_dir.name] = files
    return patients


def batch_view():
    st.title("Batch Extract")

    templates = _discover_templates()
    if not templates:
        st.error(f"No templates found in `{TEMPLATES_DIR}`.")
        return

    # --- Template selection (sidebar) ---
    with st.sidebar:
        st.divider()
        template_name = st.selectbox("Template", list(templates.keys()))
        template_path = templates[template_name]

    st.caption(
        f"Place patient folders inside `data/input/`. "
        "Each file must contain `_LE` or `_RE` (or `_OS`/`_OD`) in its name."
    )

    if not INPUT_DIR.exists():
        st.warning(
            "Input directory not found: `data/input/`\n\n"
            "Expected structure:\n"
            "```\ndata/input/\n  Patient001/\n    001_HVF_LE.pdf\n    001_HVF_RE.pdf\n```"
        )
        return

    patients = _scan_input_dir()

    if not patients:
        st.info(
            "No patient folders with supported files found in `data/input/`.\n\n"
            "Expected structure:\n"
            "```\ndata/input/\n  Patient001/\n    001_HVF_LE.pdf\n    001_HVF_RE.pdf\n```"
        )
        return

    # --- Preview detected files ---
    total_files = sum(len(files) for files in patients.values())
    with st.expander(f"Detected {len(patients)} patient(s), {total_files} file(s)", expanded=True):
        for name, files in patients.items():
            lines = []
            for f in files:
                eye = _detect_eye(f.name)
                label = eye if eye else "? (skipped — no _LE/_RE/_OS/_OD)"
                lines.append(f"- {f.name} &nbsp; `{label}`")
            st.markdown(f"**{name}**  \n" + "  \n".join(lines))

    # --- Run button ---
    if not st.button("Run Batch Extraction", type="primary"):
        return

    from core.converter import convert_from_path
    from core.pipeline import extract

    all_rows: list[dict] = []
    errors: list[str] = []

    progress = st.progress(0)
    status = st.empty()
    processed = 0

    for patient_name, files in patients.items():
        for file_path in files:
            eye = _detect_eye(file_path.name)

            if eye is None:
                errors.append(
                    f"{patient_name}/{file_path.name}: skipped — "
                    "filename must contain `_LE`, `_RE`, `_OS`, or `_OD`"
                )
                processed += 1
                progress.progress(processed / total_files)
                continue

            status.text(f"Processing {patient_name} — {file_path.name} ({eye})...")

            temp_files: list[str] = []
            images_to_process: list[str] = []

            try:
                if file_path.suffix.lower() == ".pdf":
                    pages = convert_from_path(str(file_path))
                    for img in pages:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            img.save(tmp.name, "PNG")
                            images_to_process.append(tmp.name)
                            temp_files.append(tmp.name)
                else:
                    images_to_process.append(str(file_path))

                for img_path in images_to_process:
                    data = extract(img_path, template_path, eye)
                    row = {
                        "patient": patient_name,
                        "eye": eye,
                        "file": file_path.name,
                        **data,
                    }
                    all_rows.append(row)

            except Exception as e:
                errors.append(f"{patient_name}/{file_path.name}: {e}")

            finally:
                for tmp in temp_files:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass

            processed += 1
            progress.progress(processed / total_files)

    status.empty()
    progress.empty()

    if errors:
        with st.expander(f"{len(errors)} file(s) skipped or failed"):
            for err in errors:
                st.warning(err)

    if not all_rows:
        st.error("No data was extracted. Check that the template matches your files.")
        return

    df = pd.DataFrame(all_rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = OUTPUT_DIR / f"batch_{timestamp}.csv"
    df.to_csv(csv_path, index=False)

    st.success(
        f"Extracted {len(all_rows)} record(s) from {len(patients)} patient(s). "
        f"Saved to `data/output/batch_{timestamp}.csv`."
    )

    st.download_button(
        label="Download CSV",
        data=df.to_csv(index=False),
        file_name=f"batch_{timestamp}.csv",
        mime="text/csv",
    )

    with st.expander("Preview"):
        st.dataframe(df, use_container_width=True)
