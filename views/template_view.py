import json
from pathlib import Path

import streamlit as st

from core.config import TEMPLATES_DIR


def _discover_templates() -> dict[str, Path]:
    if not TEMPLATES_DIR.exists():
        return {}
    return {p.name: p for p in sorted(TEMPLATES_DIR.glob("*.json"))}


def template_view():
    st.title("Templates")

    templates = _discover_templates()

    if not templates:
        st.info(f"No templates found in `{TEMPLATES_DIR}`.")
        st.caption("Create a `.json` file there to get started.")
        return

    selected_name = st.selectbox("Select template", list(templates.keys()))
    template_path = templates[selected_name]

    # Load current content
    raw = template_path.read_text(encoding="utf-8")

    st.caption(f"Editing: `data/templates/{selected_name}`")

    edited = st.text_area(
        "Template JSON",
        value=raw,
        height=600,
        key=f"template_editor_{selected_name}",
    )

    col_save, col_msg = st.columns([1, 4])

    with col_save:
        save_clicked = st.button("Save", type="primary")

    if save_clicked:
        try:
            parsed = json.loads(edited)
        except json.JSONDecodeError as e:
            col_msg.error(f"Invalid JSON: {e}")
            return

        template_path.write_text(
            json.dumps(parsed, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        col_msg.success("Template saved.")
