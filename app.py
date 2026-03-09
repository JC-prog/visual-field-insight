import os
import sys
from pathlib import Path

import streamlit as st

# Ensure the project root is on sys.path so `core` and `views` are importable.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    st.set_page_config(page_title="Visual Field Insight", layout="wide")

    with st.sidebar:
        st.title("Visual Field Insight")
        st.divider()
        mode = st.radio(
            "Mode",
            options=["Single Extract", "Batch Extract", "Templates"],
            index=0,
        )

    if mode == "Single Extract":
        from views.single_view import single_view
        single_view()
    elif mode == "Batch Extract":
        from views.batch_view import batch_view
        batch_view()
    elif mode == "Templates":
        from views.template_view import template_view
        template_view()


if __name__ == "__main__":
    main()
