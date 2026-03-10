import re
from typing import Any, Dict, List


def normalize_header_data(raw_data: str, template_labels: List[str]) -> Dict[str, str]:
    """
    Parse key-value pairs from raw OCR text (e.g. header/test_details sections).
    Matches OCR tokens to template labels and extracts the value that follows each label.
    """
    normalized = {}

    temp_data = raw_data.replace(':,', ';').replace(':', ';').replace(',', ';')
    parts = [p.strip() for p in temp_data.split(';') if p.strip()]

    for i in range(len(parts)):
        current_part = parts[i]
        if current_part in template_labels:
            key = current_part
            value = None
            if i + 1 < len(parts):
                next_part = parts[i + 1]
                if next_part not in template_labels:
                    value = next_part
                    parts[i + 1] = ""
            normalized[key] = value if value is not None else ""

    for label in template_labels:
        if label not in normalized:
            normalized[label] = ""

    return normalized


def normalize_map_data(raw_data: str, template_labels: List[str]) -> Dict[str, str]:
    """
    Extract signed integer values from raw OCR text and map them sequentially
    to template labels. Handles common OCR noise (merged values, trailing dots, pipes).
    """
    normalized_input = raw_data.replace('|', ' ')
    initial_parts = [p.strip() for p in normalized_input.split(',')]

    parts = []
    for part in initial_parts:
        if ' ' in part and re.search(r'[^\s]', part):
            parts.extend([p.strip() for p in part.split(' ') if p.strip()])
        elif part:
            parts.append(part)

    # Matches: "-5", "31.", "+2", "<0", "< -1"
    SIGNED_INTEGER_PATTERN = re.compile(r'^\s*(<?\s*[+-]?\d+)\.?\s*$')

    numeric_values = []
    for part in parts:
        match = SIGNED_INTEGER_PATTERN.match(part)
        if match:
            cleaned_value = match.group(1).replace(" ", "")
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

        elif section_type == "map":
            normalized_section = normalize_map_data(raw_section_data, template_labels)
            for key, value in normalized_section.items():
                final_output[f"{section_name}_{key}"] = value

    return final_output
