import json
import os
import tempfile
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st

from core.config import TEMPLATES_DIR


def _discover_templates() -> dict[str, Path]:
    """Return {stem: path} for all .json files in data/templates/."""
    if not TEMPLATES_DIR.exists():
        return {}
    return {p.stem: p for p in sorted(TEMPLATES_DIR.glob("*.json"))}


def _process_file(uploaded_file, eye: str, template_path: Path, debug: bool = False):
    """
    Save uploaded file to a temp location, convert PDF→PNG if needed,
    run extraction, clean up temp files.

    Returns:
        debug=False: normalized dict or None on failure.
        debug=True:  (dict, list[dict]) or (None, []) on failure.
    """
    from core.converter import convert_from_path
    from core.pipeline import extract

    suffix = Path(uploaded_file.name).suffix.lower()
    temp_files: list[str] = []

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            uploaded_file.seek(0)
            tmp.write(uploaded_file.read())
            source_path = tmp.name
            temp_files.append(source_path)

        images_to_process: list[str] = []

        if suffix == ".pdf":
            pages = convert_from_path(source_path)
            for img in pages:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as png_tmp:
                    img.save(png_tmp.name, "PNG")
                    images_to_process.append(png_tmp.name)
                    temp_files.append(png_tmp.name)
        else:
            images_to_process.append(source_path)

        if debug:
            all_debug = []
            results = []
            for img_path in images_to_process:
                data, dbg = extract(img_path, template_path, eye, debug=True)
                results.append(data)
                all_debug.extend(dbg)
            data_out = results[0] if len(results) == 1 else results
            return data_out, all_debug
        else:
            results = []
            for img_path in images_to_process:
                data = extract(img_path, template_path, eye)
                results.append(data)
            return results[0] if len(results) == 1 else results

    except Exception as e:
        st.error(f"Extraction failed for {uploaded_file.name}: {e}")
        return (None, []) if debug else None

    finally:
        for f in temp_files:
            try:
                os.unlink(f)
            except OSError:
                pass


def single_view():
    st.title("Single Extract")

    templates = _discover_templates()
    if not templates:
        st.error(f"No templates found in `{TEMPLATES_DIR}`. Add a `.json` template file first.")
        return

    # --- Sidebar controls ---
    with st.sidebar:
        st.divider()
        template_name = st.selectbox("Template", list(templates.keys()))
        template_path = templates[template_name]
        st.divider()
        debug_mode = st.checkbox("Debug mode", value=False)

    # --- File uploaders ---
    le_col, re_col = st.columns(2)

    with le_col:
        st.subheader("Left Eye (LE)")
        le_file = st.file_uploader(
            "Upload image or PDF",
            type=["png", "jpg", "jpeg", "pdf"],
            key="single_le_uploader",
        )
        if le_file and le_file.type != "application/pdf":
            st.image(le_file, use_container_width=True)

    with re_col:
        st.subheader("Right Eye (RE)")
        re_file = st.file_uploader(
            "Upload image or PDF",
            type=["png", "jpg", "jpeg", "pdf"],
            key="single_re_uploader",
        )
        if re_file and re_file.type != "application/pdf":
            st.image(re_file, use_container_width=True)

    # --- Run button ---
    if st.button("Run Extraction", type="primary"):
        if le_file is None and re_file is None:
            st.warning("Upload at least one file before running.")
            return

        results: dict[str, dict] = {}
        debug_info: dict[str, list] = {}

        with st.spinner("Running OCR extraction..."):
            if le_file:
                if debug_mode:
                    data, dbg = _process_file(le_file, "LE", template_path, debug=True)
                    if data is not None:
                        results["LE"] = data
                        debug_info["LE"] = dbg
                else:
                    data = _process_file(le_file, "LE", template_path)
                    if data is not None:
                        results["LE"] = data

            if re_file:
                if debug_mode:
                    data, dbg = _process_file(re_file, "RE", template_path, debug=True)
                    if data is not None:
                        results["RE"] = data
                        debug_info["RE"] = dbg
                else:
                    data = _process_file(re_file, "RE", template_path)
                    if data is not None:
                        results["RE"] = data

        if results:
            st.session_state["single_results"] = results
            st.session_state["single_debug"] = debug_info
            st.success(f"Extraction complete — {', '.join(results.keys())} eye(s) processed.")
        else:
            st.session_state.pop("single_results", None)
            st.session_state.pop("single_debug", None)

    # --- Download section ---
    results = st.session_state.get("single_results")
    if not results:
        return

    st.divider()
    st.subheader("Results")

    fmt = st.radio("Download format", ["CSV", "JSON"], horizontal=True)

    # Build a flat list of records (one row per eye)
    records = []
    for eye, data in results.items():
        if isinstance(data, list):
            for row in data:
                records.append({"eye": eye, **row})
        else:
            records.append({"eye": eye, **data})

    if fmt == "CSV":
        df = pd.DataFrame(records)
        download_data = df.to_csv(index=False)
        mime = "text/csv"
        filename = "extracted_data.csv"
    else:
        download_data = json.dumps(records, indent=2)
        mime = "application/json"
        filename = "extracted_data.json"

    st.download_button(
        label=f"Download {fmt}",
        data=download_data,
        file_name=filename,
        mime=mime,
    )

    with st.expander("Preview"):
        st.dataframe(pd.DataFrame(records), use_container_width=True)

    # --- Debug panel ---
    debug_info = st.session_state.get("single_debug", {})
    if debug_mode and debug_info:
        st.divider()
        with st.expander("Debug — Crops & OCR Text", expanded=True):
            eyes_present = [e for e in ["LE", "RE"] if e in debug_info]
            tabs = st.tabs(eyes_present)
            for tab, eye in zip(tabs, eyes_present):
                with tab:
                    for entry in debug_info[eye]:
                        section_label = f"`{entry['section']}` — *{entry['type']}*"
                        st.markdown(f"**{section_label}**")

                        if entry["type"] in ("map", "map_signed"):
                            col_orig, col_proc = st.columns(2)
                            with col_orig:
                                st.caption("Original crop")
                                st.image(entry["crop"][:, :, ::-1], use_container_width=True)
                            with col_proc:
                                st.caption("After gridline removal")
                                st.image(entry["processed"][:, :, ::-1], use_container_width=True)
                        else:
                            st.image(entry["crop"][:, :, ::-1], use_container_width=True)

                        st.code(entry["raw_text"] or "(no text detected)", language=None)
                        st.divider()
