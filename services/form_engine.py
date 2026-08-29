"""
Form Engine — Reads form definitions from the database and:
  1. Generates HTML for dynamic form rendering
  2. Validates submitted data against field definitions
  3. Stores submitted values in the EAV (record_values) table

Layout elements (heading, paragraph, divider) are rendered but
produce no stored data.
"""

import json
from typing import Optional


# Field types that are layout-only (no data stored)
LAYOUT_TYPES = {"heading", "paragraph", "divider"}

# Field types that collect data
DATA_TYPES = {"text", "number", "dropdown", "radio", "checkbox", "textarea", "date", "time"}


def render_field_html(field: dict) -> str:
    """
    Generate HTML for a single form field based on its type and configuration.

    Args:
        field: dict with keys: id, field_type, field_name, label, required, configuration

    Returns:
        HTML string for the field
    """
    ftype = field["field_type"]
    config = field["configuration"] if isinstance(field["configuration"], dict) else json.loads(field["configuration"] or "{}")
    field_id = field["id"]
    name = field.get("field_name", "")
    label = field.get("label", "")
    required = field.get("required", False)
    req_attr = 'required' if required else ''
    req_star = '<span class="required-star">*</span>' if required else ''

    if ftype == "heading":
        level = config.get("level", 2)
        text = config.get("text", "")
        return f'<h{level} class="form-heading">{text}</h{level}>'

    elif ftype == "paragraph":
        text = config.get("text", "")
        style = config.get("style", "info")
        return f'<p class="form-paragraph form-paragraph--{style}">{text}</p>'

    elif ftype == "divider":
        return '<hr class="form-divider">'

    elif ftype == "text":
        placeholder = config.get("placeholder", "")
        max_length = config.get("max_length", 255)
        return f'''
        <div class="form-group">
            <label for="field_{field_id}">{label}{req_star}</label>
            <input type="text" id="field_{field_id}" name="{name}"
                   placeholder="{placeholder}" maxlength="{max_length}"
                   class="form-input" {req_attr}>
        </div>'''

    elif ftype == "number":
        min_val = config.get("min", "")
        max_val = config.get("max", "")
        step = config.get("step", 1)
        placeholder = config.get("placeholder", "")
        min_attr = f'min="{min_val}"' if min_val != "" and min_val is not None else ""
        max_attr = f'max="{max_val}"' if max_val != "" and max_val is not None else ""
        return f'''
        <div class="form-group">
            <label for="field_{field_id}">{label}{req_star}</label>
            <input type="number" id="field_{field_id}" name="{name}"
                   placeholder="{placeholder}" step="{step}" {min_attr} {max_attr}
                   class="form-input" {req_attr}>
        </div>'''

    elif ftype == "dropdown":
        options = config.get("options", [])
        default = config.get("default", None)
        options_html = '<option value="" disabled selected>Select...</option>'
        for opt in options:
            selected = 'selected' if opt == default else ''
            options_html += f'<option value="{opt}" {selected}>{opt}</option>'
        return f'''
        <div class="form-group">
            <label for="field_{field_id}">{label}{req_star}</label>
            <select id="field_{field_id}" name="{name}" class="form-select" {req_attr}>
                {options_html}
            </select>
        </div>'''

    elif ftype == "radio":
        options = config.get("options", [])
        default = config.get("default", None)
        inline = config.get("inline", False)
        inline_cls = "radio-group--inline" if inline else ""
        radios_html = ""
        for opt in options:
            checked = 'checked' if opt == default else ''
            radios_html += f'''
            <label class="radio-label">
                <input type="radio" name="{name}" value="{opt}" {checked} {req_attr}>
                <span class="radio-custom"></span>
                {opt}
            </label>'''
        return f'''
        <div class="form-group">
            <label class="group-label">{label}{req_star}</label>
            <div class="radio-group {inline_cls}">
                {radios_html}
            </div>
        </div>'''

    elif ftype == "checkbox":
        cb_label = config.get("label", label)
        default = config.get("default", False)
        checked = 'checked' if default else ''
        return f'''
        <div class="form-group form-group--checkbox">
            <label class="checkbox-label">
                <input type="checkbox" id="field_{field_id}" name="{name}"
                       value="true" {checked}>
                <span class="checkbox-custom"></span>
                {cb_label}{req_star}
            </label>
        </div>'''

    elif ftype == "textarea":
        placeholder = config.get("placeholder", "")
        max_length = config.get("max_length", 1000)
        rows = config.get("rows", 4)
        return f'''
        <div class="form-group">
            <label for="field_{field_id}">{label}{req_star}</label>
            <textarea id="field_{field_id}" name="{name}"
                      placeholder="{placeholder}" maxlength="{max_length}"
                      rows="{rows}" class="form-textarea" {req_attr}></textarea>
        </div>'''

    elif ftype == "date":
        default_today = config.get("default_today", True)
        return f'''
        <div class="form-group">
            <label for="field_{field_id}">{label}{req_star}</label>
            <input type="date" id="field_{field_id}" name="{name}"
                   class="form-input" {req_attr}
                   data-default-today="{str(default_today).lower()}">
        </div>'''

    elif ftype == "time":
        default_today = config.get("default_today", True)
        return f'''
        <div class="form-group">
            <label for="field_{field_id}">{label}{req_star}</label>
            <input type="time" id="field_{field_id}" name="{name}"
                   class="form-input" {req_attr}
                   data-default-now="{str(default_today).lower()}">
        </div>'''

    return f'<!-- Unknown field type: {ftype} -->'


def render_form_html(fields: list[dict]) -> str:
    """
    Render the complete form body HTML from a list of field definitions.
    Fields should be sorted by position.
    """
    html_parts = []
    for field in fields:
        if not field.get("is_active", True):
            continue
        html_parts.append(render_field_html(field))
    return "\n".join(html_parts)


def validate_submission(fields: list[dict], submitted: dict[str, str]) -> tuple[bool, list[str]]:
    """
    Validate submitted data against field definitions.

    Args:
        fields: list of active field dicts
        submitted: dict of field_name -> value

    Returns:
        (is_valid, list_of_error_messages)
    """
    errors = []
    for field in fields:
        if field["field_type"] in LAYOUT_TYPES:
            continue
        if not field.get("is_active", True):
            continue

        name = field["field_name"]
        required = field.get("required", False)
        value = submitted.get(name, "").strip()

        if required and not value:
            label = field.get("label", name)
            errors.append(f"{label} is required.")

        # Type-specific validation
        if value and field["field_type"] == "number":
            try:
                float(value)
            except ValueError:
                errors.append(f"{field.get('label', name)} must be a number.")

    return (len(errors) == 0, errors)


def get_data_fields(fields: list[dict]) -> list[dict]:
    """Return only fields that store data (not layout elements)."""
    return [
        f for f in fields
        if f["field_type"] in DATA_TYPES and f.get("is_active", True)
    ]
