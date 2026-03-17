import re
from typing import Any, Dict, List


def normalize_header_data(raw_data: str, template_labels: List[str]) -> Dict[str, str]:
    """
    Parse key-value pairs from raw OCR text (e.g. header/test_details sections).

    Expects raw_data to have OCR blocks joined by newlines (one block per line).
    Each block is checked against template_labels after stripping a trailing colon,
    so "Date:" matches the label "Date". The token immediately following a matched
    label is taken as its value, unless it is itself a label.

    Values that contain commas (e.g. "III, White", "Sep 08, 2025") or colons
    (e.g. "11:33 AM", "03:57") are preserved intact because newline splitting
    does not disturb internal punctuation.
    """
    label_set = set(template_labels)
    tokens = [t.strip() for t in raw_data.split('\n') if t.strip()]

    normalized = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        candidate = token.rstrip(':').strip()
        if candidate in label_set:
            if i + 1 < len(tokens) and tokens[i + 1].rstrip(':').strip() not in label_set:
                normalized[candidate] = tokens[i + 1]
                i += 2
            else:
                normalized[candidate] = ""
                i += 1
        else:
            # Handle merged "LABEL: value" tokens (e.g. "VFI: 99.24%", "MD: -1.32 dB")
            # that PaddleOCR returns as a single detection block.
            colon_idx = token.find(':')
            if colon_idx != -1:
                left = token[:colon_idx].strip()
                right = token[colon_idx + 1:].strip()
                if left in label_set and right:
                    normalized[left] = right
            i += 1

    for label in template_labels:
        if label not in normalized:
            normalized[label] = ""

    return normalized


def normalize_map_data(raw_data: str, template_labels: List[str]) -> Dict[str, str]:
    """
    Extract signed integer values from raw OCR text and map them sequentially
    to template labels. Handles common OCR noise (merged values, trailing dots/dashes,
    pipes, non-numeric artifacts).
    """
    normalized_input = raw_data.replace('|', ' ')
    initial_parts = [p.strip() for p in normalized_input.split(',')]

    parts = []
    for part in initial_parts:
        if ' ' in part and re.search(r'[^\s]', part):
            parts.extend([p.strip() for p in part.split(' ') if p.strip()])
        elif part:
            parts.append(part)

    # Extract the numeric content from each token using search rather than fullmatch.
    # This handles noisy tokens like "17.." → "17" and "32--" → "32" that would fail
    # a strict fullmatch. The <\s*-?\d+ branch handles "<0" and "< -1" style values.
    EXTRACT_NUMERIC = re.compile(r'<\s*-?\d+|-?\d+')

    numeric_values = []
    for part in parts:
        match = EXTRACT_NUMERIC.search(part)
        if match:
            cleaned_value = match.group(0).replace(" ", "")
            numeric_values.append(cleaned_value)

    normalized: Dict[str, str] = {}
    for i, label in enumerate(template_labels):
        normalized[label] = numeric_values[i] if i < len(numeric_values) else ""

    return normalized


def normalize_data(template: Dict[str, Any], extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten extracted OCR data into a single dict using template labels.
    Keys are prefixed with section name: e.g. "header_Date", "threshold_map_ST1".
    """
    final_output = {}

    for section_name, section_def in template.items():
        raw_section_data = extracted_data.get(section_name, "")
        template_labels = section_def.get("labels", [])

        if not template_labels or not raw_section_data:
            final_output[section_name] = raw_section_data
            continue

        section_type = section_def.get("type", "text")

        if section_type == "text":
            normalized_section = normalize_header_data(raw_section_data, template_labels)
            for key, value in normalized_section.items():
                final_output[f"{section_name}_{key}"] = value

        elif section_type in ("map", "map_signed"):
            # "map"        — unsigned values (threshold map); blob filter applied upstream
            # "map_signed" — signed values (deviation maps); blob filter skipped upstream
            # Both use the same numeric extraction logic here
            normalized_section = normalize_map_data(raw_section_data, template_labels)
            for key, value in normalized_section.items():
                final_output[f"{section_name}_{key}"] = value

    return final_output
