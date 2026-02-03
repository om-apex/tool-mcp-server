"""Document generation tools: generate_branded_html, list_company_configs.

Approach (TECH-038, TECH-039, TECH-040):
  Generate multi-page HTML where each logical page section has branded header/footer.
  The HTML is opened in a browser and printed to PDF (Cmd+P -> Save as PDF).

Storage modes (TASK-164):
  - Local: Templates and configs read from Google Drive shared folder
  - Supabase: Templates and configs read from Supabase (for cloud/remote access)
"""

import json
import re
from pathlib import Path
from typing import Optional

import markdown as md_lib

from mcp.types import Tool, TextContent

from . import ToolModule
from .helpers import get_backend
from ..storage import LocalStorage
from ..supabase_client import (
    is_supabase_available,
    get_document_templates as sb_get_templates,
    get_document_template as sb_get_template,
    upsert_document_template as sb_upsert_template,
    get_company_configs as sb_get_configs,
    get_company_config as sb_get_config,
    upsert_company_config as sb_upsert_config,
    has_document_templates_table,
    has_company_configs_table,
)

READING = ["list_company_configs", "list_document_templates", "view_document_template", "get_brand_assets"]
WRITING = ["generate_branded_html", "generate_company_document", "sync_templates_to_supabase"]

# Known company config locations relative to shared drive root
COMPANY_CONFIG_PATHS = [
    "om-ai",
    "om-luxe",
    "om-scm",
    "",  # root = Om Apex Holdings
]


def _is_local_storage() -> bool:
    """Check if we're using local storage (has filesystem access)."""
    backend = get_backend()
    return isinstance(backend, LocalStorage)


def _get_shared_drive_root() -> Path:
    """Get the shared drive root from the current storage backend."""
    backend = get_backend()
    if isinstance(backend, LocalStorage):
        return backend.shared_drive_root
    # For non-local backends, this will fail - callers should check _is_local_storage() first
    raise RuntimeError("Local storage not available - use Supabase for templates")


def _use_supabase_for_templates() -> bool:
    """Check if we should use Supabase for templates (non-local or Supabase available)."""
    if _is_local_storage():
        return False  # Prefer local when available
    return is_supabase_available() and has_document_templates_table()


def _use_supabase_for_configs() -> bool:
    """Check if we should use Supabase for company configs."""
    if _is_local_storage():
        return False  # Prefer local when available
    return is_supabase_available() and has_company_configs_table()


def _find_company_config(start_path: str) -> dict:
    """Walk up from start_path to find company-config.json."""
    current = Path(start_path).resolve()
    if current.is_file():
        current = current.parent

    while current != current.parent:
        config_file = current / "company-config.json"
        if config_file.exists():
            return json.loads(config_file.read_text(encoding="utf-8"))
        current = current.parent

    return _default_config()


def _find_company_config_by_name(company: str) -> Optional[dict]:
    """Find company-config.json by company name from known paths or Supabase."""
    # Try Supabase first if not using local storage
    if _use_supabase_for_configs():
        config_row = sb_get_config(company)
        if config_row:
            return config_row.get("config", {})

    # Fall back to local storage
    if not _is_local_storage():
        return None

    try:
        root = _get_shared_drive_root()
    except RuntimeError:
        return None

    for subdir in COMPANY_CONFIG_PATHS:
        config_path = root / subdir / "company-config.json" if subdir else root / "company-config.json"
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
                name = config.get("company", {}).get("name", "").lower()
                short = config.get("company", {}).get("short_name", "").lower()
                if company.lower() in name or company.lower() in short:
                    return config
            except Exception:
                continue
    return None


def _default_config() -> dict:
    return {
        "company": {
            "name": "Om Apex Holdings LLC",
            "short_name": "Om Apex Holdings",
            "display_name_line1": "Om Apex",
            "display_name_line2": "Holdings",
            "is_parent": True,
            "subsidiary_of": None,
            "tagline": "Intelligent backbone for your Business.",
        },
        "brand": {
            "primary_color": "#C9A227",
            "accent_color": "#1E4D7C",
            "secondary_text_color": "#9A9FB0",
            "body_text_color": "#2D2D2D",
            "heading_font": "Georgia, serif",
            "body_font": "'Segoe UI', Arial, sans-serif",
            "logo": "om-logo.png",
            "logo_dir": "brand-assets",
        },
        "contact": {
            "address_line1": "900 Wilde Run CT",
            "address_line2": "Roswell, GA 30075",
            "phone": "123-456-7890",
        },
    }


def _find_document_config(start_path: str) -> Optional[dict]:
    """Walk up from start_path to find document-config.json."""
    current = Path(start_path).resolve()
    if current.is_file():
        current = current.parent
    while current != current.parent:
        config_file = current / "document-config.json"
        if config_file.exists():
            return json.loads(config_file.read_text(encoding="utf-8"))
        current = current.parent
    return None


def _resolve_logo_path(config: dict, start_path: str) -> str:
    """Resolve the logo path from brand config or by walking up directories."""
    logo_filename = config["brand"]["logo"]
    logo_dir = config["brand"].get("logo_dir", "brand-assets")

    # First, try logo_dir as relative to the shared drive root
    try:
        root = _get_shared_drive_root()
        candidate = root / logo_dir / logo_filename
        if candidate.exists():
            return str(candidate.resolve())
    except RuntimeError:
        pass

    # Fall back to walking up from start_path
    current = Path(start_path).resolve()
    if current.is_file():
        current = current.parent

    check = current
    while check != check.parent:
        candidate = check / logo_dir / logo_filename
        if candidate.exists():
            return str(candidate.resolve())
        candidate = check / logo_filename
        if candidate.exists():
            return str(candidate.resolve())
        check = check.parent

    return logo_filename


def _build_footer_left(config: dict) -> str:
    company = config["company"]
    if company.get("is_parent", False):
        return company["name"]
    else:
        return (
            f'{company["name"]}<br>'
            f"— A subsidiary of —<br>"
            f'{company.get("subsidiary_of", "Om Apex Holdings LLC")}'
        )


def _build_header_html(config: dict, logo_uri: str) -> str:
    brand = config["brand"]
    contact = config["contact"]
    company = config["company"]

    return f"""<div class="doc-header-left">
      <img class="doc-header-logo" src="{logo_uri}" alt="">
      <span class="doc-header-company">{company['display_name_line1']}<br>{company['display_name_line2']}</span>
    </div>
    <div class="doc-header-address">
      <table>
        <tr style="vertical-align:top;">
          <td><svg width="14" height="14" viewBox="0 0 24 24"><path fill="#EA4335" d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z"/></svg></td>
          <td>{contact['address_line1']}<br>{contact['address_line2']}</td>
        </tr>
        <tr><td colspan="2" style="padding:1px 0;"><hr style="border:none;border-top:1px solid #D0D0D0;margin:0;"></td></tr>
        <tr>
          <td style="vertical-align:middle;">&#x260E;</td>
          <td style="vertical-align:middle;">{contact['phone']}</td>
        </tr>
      </table>
    </div>"""


def _build_footer_html(config: dict) -> str:
    company = config["company"]
    footer_left = _build_footer_left(config)

    return f"""<span class="doc-footer-left">{footer_left}</span>
    <span class="doc-footer-tagline">{company['tagline']}</span>
    <span class="doc-footer-page"></span>"""


def _build_branded_css(config: dict) -> str:
    """Build CSS for browser-based print-to-PDF rendering.

    Uses @media print with @page for proper pagination, and screen styles
    for preview. Header/footer are repeated via position:fixed for print.
    """
    brand = config["brand"]

    return f"""
    /* ── Screen preview: simulate pages ── */
    @media screen {{
        body {{
            max-width: 8.5in;
            margin: 0 auto;
            padding: 20px;
        }}
    }}

    /* ── Print layout ── */
    @page {{
        size: letter;
        margin: 80px 60px 60px 60px;
    }}

    @media print {{
        body {{ margin: 0; padding: 0; }}
        .page-header {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 80px;
            padding: 0 60px;
            background: #fff;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .page-footer-bar {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 8px 60px 20px 60px;
            border-top: 1px solid {brand["accent_color"]};
            background: #fff;
            font-size: 10px;
            color: {brand["secondary_text_color"]};
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
    }}

    body {{
        font-family: {brand["body_font"]};
        line-height: 1.6;
        color: {brand["body_text_color"]};
        font-size: 12px;
    }}

    /* ── Header styles ── */
    .page-header {{
        border-bottom: 1px solid {brand["accent_color"]};
        padding-bottom: 8px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        height: 80px;
        overflow: hidden;
    }}
    .doc-header-left {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    .doc-header-logo {{
        height: 72px;
        width: auto;
    }}
    .doc-header-company {{
        font-family: {brand["heading_font"]};
        font-weight: 600;
        font-size: 18px;
        color: {brand["primary_color"]};
        letter-spacing: 1px;
        line-height: 1.2;
    }}
    .doc-header-address {{
        color: {brand["secondary_text_color"]};
        font-size: 9px;
        line-height: 1.2;
    }}
    .doc-header-address table {{
        border-collapse: collapse;
    }}
    .doc-header-address td {{
        padding: 0 0 0 6px;
        vertical-align: top;
        text-align: left;
        border: none;
        background: transparent;
    }}
    .doc-header-address td:first-child {{
        padding-left: 0;
        font-size: 12px;
    }}

    /* ── Footer bar ── */
    .page-footer-bar {{
        border-top: 1px solid {brand["accent_color"]};
        padding-top: 8px;
        margin-top: 30px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: {brand["secondary_text_color"]};
        font-size: 10px;
    }}
    .doc-footer-left {{
        flex: 1;
        text-align: left;
        line-height: 1.2;
        font-size: 8px;
    }}
    .doc-footer-tagline {{
        flex: 1;
        text-align: center;
        font-style: italic;
        font-size: 12px;
    }}
    .doc-footer-page {{
        flex: 1;
        text-align: right;
        white-space: nowrap;
    }}
    @media print {{
        .doc-footer-page::after {{
            content: counter(page);
        }}
    }}

    /* ── Cover page ── */
    .cover-page {{
        page-break-after: always;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        min-height: 600px;
        text-align: center;
        padding-top: 80px;
    }}
    .cover-title {{
        font-family: {brand["heading_font"]};
        font-size: 32px;
        color: {brand["primary_color"]};
        font-weight: 700;
        margin-bottom: 8px;
    }}
    .cover-tagline {{
        font-size: 13px;
        color: {brand["accent_color"]};
        font-style: italic;
        margin-bottom: 50px;
        letter-spacing: 0.5px;
    }}
    .cover-purpose {{
        font-family: {brand["heading_font"]};
        font-size: 18px;
        color: {brand["primary_color"]};
        font-weight: 400;
        margin-bottom: 10px;
    }}
    .cover-divider {{
        width: 80px;
        height: 2px;
        background: {brand["accent_color"]};
        margin: 20px auto;
    }}
    .cover-meta {{
        font-size: 11px;
        color: #555;
        line-height: 1.4;
    }}
    .cover-meta strong {{ color: {brand["body_text_color"]}; }}

    /* ── TOC section ── */
    .toc-section {{
        page-break-after: always;
    }}
    .toc-section h2 {{
        border-bottom: none;
    }}

    /* ── Content styles ── */
    h1 {{
        font-family: {brand["body_font"]};
        font-size: 22px;
        font-weight: 600;
        color: {brand["primary_color"]};
        margin-top: 16px;
        margin-bottom: 10px;
        border-bottom: 0.5px solid {brand["accent_color"]};
        padding-bottom: 6px;
        line-height: 1.3;
        page-break-before: always;
    }}
    h1:first-of-type {{
        page-break-before: avoid;
    }}
    h2 {{
        font-family: {brand["body_font"]};
        font-size: 14px;
        font-weight: 600;
        color: {brand["primary_color"]};
        margin-top: 18px;
        margin-bottom: 8px;
    }}
    h3 {{
        font-family: {brand["body_font"]};
        font-size: 12px;
        font-weight: 600;
        color: {brand["primary_color"]};
        margin-top: 14px;
        margin-bottom: 6px;
    }}
    p {{
        margin: 6px 0 10px 0;
        font-size: 12px;
    }}
    table {{
        border-collapse: collapse;
        width: 100%;
        margin: 12px 0;
        font-size: 11px;
    }}
    th, td {{
        padding: 5px 8px;
        text-align: left;
        border-bottom: 1px solid #E8E8E8;
    }}
    th {{
        background-color: {brand["primary_color"]};
        color: white;
        font-weight: bold;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        padding: 6px 8px;
    }}
    tr:nth-child(even) td {{
        background-color: #F8F9FA;
    }}
    code {{
        background-color: #f4f4f4;
        padding: 1px 4px;
        border-radius: 3px;
        font-family: 'Courier New', 'Monaco', monospace;
        font-size: 0.85em;
    }}
    pre {{
        background-color: #f4f4f4;
        padding: 10px;
        border-radius: 4px;
        overflow-x: auto;
        border-left: 3px solid {brand["primary_color"]};
        font-size: 8pt;
    }}
    pre code {{
        background-color: transparent;
        padding: 0;
    }}
    ul, ol {{
        margin: 6px 0;
        padding-left: 20px;
    }}
    li {{
        margin: 3px 0;
    }}
    hr {{
        border: none;
        border-top: 0.5px solid #ddd;
        margin: 14px 0;
    }}
    strong {{
        color: #2c3e50;
        font-weight: 600;
    }}
    blockquote {{
        border-left: 3px solid {brand["accent_color"]};
        padding-left: 12px;
        color: #555;
        font-style: italic;
        margin: 10px 0;
    }}
    a {{
        color: {brand["body_text_color"]};
        text-decoration: none;
    }}
    """


def _build_cover_page(doc_config: dict, brand: dict) -> str:
    product = doc_config.get("product", {})
    doc = doc_config.get("document", {})

    name = product.get("name", "")
    tagline = product.get("tagline", "")
    purpose = doc.get("purpose", "")
    abbr = doc.get("abbreviation", "")
    version = doc.get("version", "")
    date = doc.get("date", "")
    status = doc.get("status", "")
    owner = doc.get("owner", "")
    parent = doc.get("parent", "")

    purpose_line = f'{purpose} ({abbr})' if abbr else purpose

    meta_lines = []
    if version:
        meta_lines.append(f"<strong>Version:</strong> {version}")
    if date:
        meta_lines.append(f"<strong>Date:</strong> {date}")
    if status:
        meta_lines.append(f"<strong>Status:</strong> {status}")
    if owner:
        meta_lines.append(f"<strong>Owner:</strong> {owner}")
    if parent:
        meta_lines.append(f"<strong>Parent:</strong> {parent}")
    meta_html = "<br>".join(meta_lines)

    return f"""
    <div class="cover-page">
        <div class="cover-title">{name}</div>
        <div class="cover-tagline">"{tagline}"</div>
        <div class="cover-purpose">{purpose_line}</div>
        <div class="cover-divider"></div>
        <div class="cover-meta">{meta_html}</div>
    </div>
    """


def _strip_cover_from_markdown(md_content: str) -> str:
    """Remove the title and metadata block from markdown since cover page handles it."""
    lines = md_content.strip().split("\n")
    skip_until_separator = False
    result_lines = []
    found_first_heading = False

    for line in lines:
        stripped = line.strip()
        if not found_first_heading and stripped.startswith("# "):
            found_first_heading = True
            skip_until_separator = True
            continue
        if skip_until_separator:
            if stripped == "---":
                skip_until_separator = False
                continue
            continue
        result_lines.append(line)

    return "\n".join(result_lines)


def _add_bookmark_anchors(html: str) -> str:
    """Auto-generate id attributes on heading tags for bookmark navigation."""
    def _make_id(tag: str, text: str) -> str:
        text = text.strip()
        m = re.match(r"Section\s+(\d+)", text, re.IGNORECASE)
        if m:
            return f"section-{m.group(1)}"
        m = re.match(r"Appendix\s+([A-Za-z])", text, re.IGNORECASE)
        if m:
            return f"appendix-{m.group(1).lower()}"
        m = re.match(r"(\d+(?:\.\d+)+)", text)
        if m:
            return "section-" + m.group(1).replace(".", "-")
        m = re.match(r"([A-Za-z])\.(\d+(?:\.\d+)*)", text)
        if m:
            return f"appendix-{m.group(1).lower()}-{m.group(2).replace('.', '-')}"
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug[:60]

    def _replace_heading(match):
        tag = match.group(1)
        attrs = match.group(2) or ""
        content = match.group(3)
        if 'id="' in attrs or "id='" in attrs:
            return match.group(0)
        anchor_id = _make_id(tag, content)
        return f"<{tag}{attrs} id=\"{anchor_id}\">{content}</{tag}>"

    return re.sub(
        r"<(h[1-6])([^>]*)>(.*?)</\1>",
        _replace_heading,
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _auto_link_toc(html: str) -> str:
    """Make TOC table entries into clickable anchor links."""
    def _link_toc_row(match):
        full = match.group(0)
        section_num = match.group(1).strip()
        title = match.group(2).strip()
        if not section_num or not title:
            return full
        if re.match(r"^\d+$", section_num):
            anchor = f"section-{section_num}"
        elif re.match(r"^[A-Za-z]$", section_num):
            anchor = f"appendix-{section_num.lower()}"
        else:
            return full
        if "<a " in title:
            return full
        return full.replace(
            f"<td>{match.group(2)}</td>",
            f'<td><a href="#{anchor}">{title}</a></td>',
        )

    return re.sub(
        r"<td>(\s*\w+\s*)</td>\s*<td>((?:(?!</td>).)+)</td>\s*<td>\s*\d+\s*</td>",
        _link_toc_row,
        html,
        flags=re.DOTALL,
    )


def _resolve_template_variables(content: str, config: dict) -> str:
    """Replace {{variable}} placeholders in content using company config.

    Supported variables (all drawn from company-config.json):
      {{company_name}}          - company.name
      {{company_name_upper}}    - company.name in UPPERCASE
      {{company_short_name}}    - company.short_name
      {{parent_company_name}}   - company.subsidiary_of (or company.name if parent)
      {{tagline}}               - company.tagline
      {{date}}                  - current date in MM/DD/YYYY
      {{formation_date}}        - legal.formation_date
      {{manager_name}}          - legal.manager_name
      {{registered_address}}    - legal.registered_address
      {{registered_agent}}      - legal.registered_agent
      {{state}}                 - legal.state
      {{capital_contribution}}  - legal.capital_contribution
      {{business_purpose}}      - legal.business_purpose
      {{address_line1}}         - contact.address_line1
      {{address_line2}}         - contact.address_line2
      {{phone}}                 - contact.phone
      {{email}}                 - contact.email
      {{website}}               - contact.website
    """
    from datetime import datetime

    company = config.get("company", {})
    legal = config.get("legal", {})
    contact = config.get("contact", {})

    parent_name = company.get("subsidiary_of") or company.get("name", "")

    variables = {
        "company_name": company.get("name", ""),
        "company_name_upper": company.get("name", "").upper(),
        "company_short_name": company.get("short_name", ""),
        "parent_company_name": parent_name,
        "tagline": company.get("tagline", ""),
        "date": datetime.now().strftime("%m/%d/%Y"),
        "formation_date": legal.get("formation_date", "___________"),
        "manager_name": legal.get("manager_name", "___________"),
        "registered_address": legal.get("registered_address", "___________"),
        "registered_agent": legal.get("registered_agent", "___________"),
        "state": legal.get("state", "___________"),
        "capital_contribution": legal.get("capital_contribution", "___________"),
        "business_purpose": legal.get("business_purpose", "___________"),
        "control_number": legal.get("control_number", "___________"),
        "ein": legal.get("ein", "___________"),
        "address_line1": contact.get("address_line1", ""),
        "address_line2": contact.get("address_line2", ""),
        "phone": contact.get("phone", ""),
        "email": contact.get("email", ""),
        "website": contact.get("website", ""),
    }

    for key, value in variables.items():
        # Use blank-line placeholder if value is empty
        if not value:
            value = "___________"
        content = content.replace("{{" + key + "}}", value)

    return content


def _markdown_to_branded_html(
    md_content: str,
    config: dict,
    logo_uri: str,
    doc_config: Optional[dict] = None,
) -> str:
    """Convert markdown content to branded HTML with header/footer."""
    # Resolve {{variable}} placeholders from company config
    md_content = _resolve_template_variables(md_content, config)

    css = _build_branded_css(config)
    header_html = _build_header_html(config, logo_uri)
    footer_html = _build_footer_html(config)

    cover_html = ""
    if doc_config:
        cover_html = _build_cover_page(doc_config, config["brand"])
        md_content = _strip_cover_from_markdown(md_content)

    # Strip YAML frontmatter
    if md_content.strip().startswith("---"):
        parts = md_content.split("---", 2)
        if len(parts) >= 3:
            md_content = parts[2]

    html_content = md_lib.markdown(
        md_content,
        extensions=["tables", "fenced_code", "toc", "nl2br"],
    )

    html_content = _add_bookmark_anchors(html_content)
    html_content = _auto_link_toc(html_content)

    # Wrap TOC in page-break div
    html_content = re.sub(
        r'(<h2[^>]*>Table of Contents</h2>.*?</table>)',
        r'<div class="toc-section">\1</div>',
        html_content,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>{css}</style>
</head>
<body>
    <div class="page-header">{header_html}</div>
    {cover_html}
    {html_content}
    <div class="page-footer-bar">{footer_html}</div>
</body>
</html>"""


def register() -> ToolModule:
    tools = [
        Tool(
            name="generate_branded_html",
            description="Convert markdown to branded HTML with Om Apex header/footer, cover page, auto-bookmarks, and linked TOC. Output is HTML for browser Print-to-PDF.",
            inputSchema={
                "type": "object",
                "properties": {
                    "md_content": {"type": "string", "description": "Markdown content to convert (provide this OR md_file_path)"},
                    "md_file_path": {"type": "string", "description": "Absolute path to a .md file to convert (provide this OR md_content)"},
                    "company": {"type": "string", "description": "Company name to use for branding (optional, auto-detected from file path if not provided)"},
                    "output_path": {"type": "string", "description": "Absolute path for the output HTML file (optional, defaults to .html next to .md file)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="generate_company_document",
            description=(
                "Generate a branded HTML document from a template for a specific company. "
                "Templates live in document-templates/ on the shared drive. "
                "All {{variables}} in the template are resolved from the company's config. "
                "Example: generate_company_document(template='Operating-Agreement-Template', company='Om Luxe Properties')"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "template": {
                        "type": "string",
                        "description": "Template name (without .md extension) from the document-templates/ folder, e.g. 'Operating-Agreement-Template'",
                    },
                    "company": {
                        "type": "string",
                        "description": "Company name, e.g. 'Om Luxe Properties', 'Om AI Solutions', 'Om Supply Chain', 'Om Apex Holdings'",
                    },
                    "output_folder": {
                        "type": "string",
                        "description": "Output folder relative to shared drive root (optional, defaults to 'business-plan/01 Legal')",
                    },
                },
                "required": ["template", "company"],
            },
        ),
        Tool(
            name="view_document_template",
            description="View the contents of a document template, showing all {{variables}} and their placement. Example: view_document_template(template='Operating-Agreement-Template')",
            inputSchema={
                "type": "object",
                "properties": {
                    "template": {
                        "type": "string",
                        "description": "Template name (without .md extension), e.g. 'Operating-Agreement-Template'",
                    },
                },
                "required": ["template"],
            },
        ),
        Tool(
            name="list_document_templates",
            description="List available document templates from the document-templates/ folder on the shared drive.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_brand_assets",
            description="Get the full brand assets for a company: colors, fonts, logo path, legal info, contact info. Example: get_brand_assets(company='Om Luxe Properties')",
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Company name, e.g. 'Om Apex Holdings', 'Om AI Solutions', 'Om Luxe Properties', 'Om Supply Chain'",
                    },
                },
                "required": ["company"],
            },
        ),
        Tool(
            name="list_company_configs",
            description="List available company-config.json files with branding and legal info summary for document generation.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="sync_templates_to_supabase",
            description="Sync document templates and company configs from local Google Drive to Supabase for remote access. Only works when local storage is available.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]

    async def handler(name: str, arguments: dict):
        if name == "generate_branded_html":
            md_content = arguments.get("md_content")
            md_file_path = arguments.get("md_file_path")
            company_name = arguments.get("company")
            output_path = arguments.get("output_path")

            if not md_content and not md_file_path:
                return [TextContent(type="text", text="Error: Provide either md_content or md_file_path")]

            # Load markdown from file if path given
            search_start = md_file_path or str(_get_shared_drive_root())
            if md_file_path:
                md_path = Path(md_file_path)
                if not md_path.exists():
                    return [TextContent(type="text", text=f"Error: File not found: {md_file_path}")]
                md_content = md_path.read_text(encoding="utf-8")
                if not output_path:
                    output_path = str(md_path.with_suffix(".html"))

            if not output_path:
                return [TextContent(type="text", text="Error: output_path is required when using md_content directly")]

            # Find company config
            if company_name:
                config = _find_company_config_by_name(company_name) or _default_config()
            else:
                config = _find_company_config(search_start)

            logo_uri = _resolve_logo_path(config, search_start)
            logo_path = Path(logo_uri)
            if logo_path.is_absolute() and logo_path.exists():
                logo_uri = logo_path.as_uri()

            doc_config = _find_document_config(search_start)

            try:
                html_output = _markdown_to_branded_html(md_content, config, logo_uri, doc_config)
            except Exception as e:
                return [TextContent(type="text", text=f"Error generating HTML: {e}")]

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(html_output, encoding="utf-8")

            return [TextContent(type="text", text=f"HTML generated successfully: {output_path}\n\nOpen in browser and use Print (Cmd+P) -> Save as PDF for final output.")]

        elif name == "generate_company_document":
            template_name = arguments.get("template", "")
            company_name = arguments.get("company", "")
            output_folder = arguments.get("output_folder", "business-plan/01 Legal")

            if not template_name or not company_name:
                return [TextContent(type="text", text="Error: Both 'template' and 'company' are required.")]

            md_content = None
            template_source = "local"

            # Try Supabase first if not using local storage
            if _use_supabase_for_templates():
                # Normalize template name to ID format
                template_id = template_name.lower().replace(" ", "-")
                if not template_id.endswith("-template"):
                    template_id = f"{template_id}-template"

                template = sb_get_template(template_id)
                if not template:
                    # Try without -template suffix
                    template = sb_get_template(template_name.lower().replace(" ", "-"))

                if template:
                    md_content = template["content"]
                    template_source = "supabase"
                else:
                    templates = sb_get_templates()
                    available = [t["name"] for t in templates]
                    return [TextContent(type="text", text=f"Error: Template not found: {template_name}\nAvailable in Supabase: {', '.join(available)}")]

            # Fall back to local storage
            if md_content is None:
                if not _is_local_storage():
                    return [TextContent(type="text", text="Error: Templates not available - no local storage and Supabase templates not found.")]

                root = _get_shared_drive_root()
                template_path = root / "document-templates" / f"{template_name}.md"
                if not template_path.exists():
                    # Try without assuming .md was stripped
                    template_path = root / "document-templates" / template_name
                    if not template_path.exists():
                        available = [f.stem for f in (root / "document-templates").glob("*.md")]
                        return [TextContent(type="text", text=f"Error: Template not found: {template_name}\nAvailable: {', '.join(available)}")]

                md_content = template_path.read_text(encoding="utf-8")

            # Load company config
            config = _find_company_config_by_name(company_name)
            if not config:
                return [TextContent(type="text", text=f"Error: No company-config.json found for '{company_name}'")]

            # Resolve logo (only meaningful for local storage)
            logo_uri = config.get("brand", {}).get("logo", "")
            if _is_local_storage():
                try:
                    root = _get_shared_drive_root()
                    logo_uri = _resolve_logo_path(config, str(root / "document-templates"))
                    logo_path = Path(logo_uri)
                    if logo_path.is_absolute() and logo_path.exists():
                        logo_uri = logo_path.as_uri()
                except RuntimeError:
                    pass

            # Build output filename: strip "-Template" suffix for final documents
            short = config["company"].get("short_name", company_name).replace(" ", "-")
            doc_name = re.sub(r"-?Template$", "", template_name)
            output_filename = f"{short}-{doc_name}.html"

            # For local storage, write to filesystem; for remote, return HTML content
            if _is_local_storage():
                root = _get_shared_drive_root()
                output_dir = root / output_folder
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / output_filename

                # Find optional document-config.json
                doc_config = _find_document_config(str(root / "document-templates"))

                try:
                    html_output = _markdown_to_branded_html(md_content, config, logo_uri, doc_config)
                except Exception as e:
                    return [TextContent(type="text", text=f"Error generating HTML: {e}")]

                output_path.write_text(html_output, encoding="utf-8")

                return [TextContent(type="text", text=(
                    f"Document generated successfully!\n\n"
                    f"Company: {config['company']['name']}\n"
                    f"Template: {template_name} (from {template_source})\n"
                    f"Output: {output_path}\n\n"
                    f"Open in browser and use Print (Cmd+P) → Save as PDF."
                ))]
            else:
                # Non-local: generate HTML and return it (can't write to filesystem)
                try:
                    html_output = _markdown_to_branded_html(md_content, config, logo_uri, None)
                except Exception as e:
                    return [TextContent(type="text", text=f"Error generating HTML: {e}")]

                return [TextContent(type="text", text=(
                    f"Document generated (template from {template_source})!\n\n"
                    f"Company: {config['company']['name']}\n"
                    f"Template: {template_name}\n"
                    f"Suggested filename: {output_filename}\n\n"
                    f"Note: Running in remote mode - cannot write to filesystem.\n"
                    f"HTML content returned below. Save it locally and open in browser for Print-to-PDF.\n\n"
                    f"---HTML START---\n{html_output}\n---HTML END---"
                ))]

        elif name == "view_document_template":
            template_name = arguments.get("template", "")
            if not template_name:
                return [TextContent(type="text", text="Error: 'template' is required.")]

            # Try Supabase first if not using local storage
            if _use_supabase_for_templates():
                # Normalize template name to ID format
                template_id = template_name.lower().replace(" ", "-")
                if not template_id.endswith("-template"):
                    template_id = f"{template_id}-template"

                template = sb_get_template(template_id)
                if not template:
                    # Try without -template suffix
                    template = sb_get_template(template_name.lower().replace(" ", "-"))

                if template:
                    content = template["content"]
                    variables = template.get("variables", []) or sorted(set(re.findall(r"\{\{(\w+)\}\}", content)))
                    return [TextContent(type="text", text=(
                        f"**Template:** {template['filename']}\n\n"
                        f"**Variables used ({len(variables)}):** {', '.join(variables)}\n\n"
                        f"---\n\n{content}"
                    ))]

                templates = sb_get_templates()
                available = [t["name"] for t in templates]
                return [TextContent(type="text", text=f"Error: Template not found: {template_name}\nAvailable: {', '.join(available)}")]

            # Fall back to local storage
            try:
                root = _get_shared_drive_root()
            except RuntimeError as e:
                return [TextContent(type="text", text=f"Error: {e}")]

            template_path = root / "document-templates" / f"{template_name}.md"
            if not template_path.exists():
                template_path = root / "document-templates" / template_name
                if not template_path.exists():
                    available = [f.stem for f in (root / "document-templates").glob("*.md")]
                    return [TextContent(type="text", text=f"Error: Template not found: {template_name}\nAvailable: {', '.join(available)}")]

            content = template_path.read_text(encoding="utf-8")

            # Extract all {{variables}} used
            variables = sorted(set(re.findall(r"\{\{(\w+)\}\}", content)))

            return [TextContent(type="text", text=(
                f"**Template:** {template_path.name}\n\n"
                f"**Variables used ({len(variables)}):** {', '.join(variables)}\n\n"
                f"---\n\n{content}"
            ))]

        elif name == "list_document_templates":
            # Try Supabase first if not using local storage
            if _use_supabase_for_templates():
                templates = sb_get_templates()
                if templates:
                    result = [{"name": t["name"], "filename": t["filename"], "id": t["id"]} for t in templates]
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                return [TextContent(type="text", text="No templates found in Supabase. Use sync_templates_to_supabase to upload templates.")]

            # Fall back to local storage
            try:
                root = _get_shared_drive_root()
            except RuntimeError as e:
                return [TextContent(type="text", text=f"Error: {e}. Templates not available without local storage or Supabase.")]

            templates_dir = root / "document-templates"
            if not templates_dir.exists():
                return [TextContent(type="text", text="No document-templates/ folder found on shared drive.")]

            templates = []
            for f in sorted(templates_dir.glob("*.md")):
                templates.append({
                    "name": f.stem,
                    "filename": f.name,
                    "path": str(f),
                })

            if not templates:
                return [TextContent(type="text", text="No .md templates found in document-templates/ folder.")]

            return [TextContent(type="text", text=json.dumps(templates, indent=2))]

        elif name == "get_brand_assets":
            company_name = arguments.get("company", "")
            if not company_name:
                return [TextContent(type="text", text="Error: 'company' is required.")]

            config = _find_company_config_by_name(company_name)
            if not config:
                return [TextContent(type="text", text=f"Error: No company-config.json found for '{company_name}'")]

            company = config.get("company", {})
            brand = config.get("brand", {})
            contact = config.get("contact", {})
            legal = config.get("legal", {})

            # Resolve logo path (only for local storage)
            logo_uri = brand.get("logo", "")
            if _is_local_storage():
                try:
                    logo_uri = _resolve_logo_path(config, str(_get_shared_drive_root()))
                    logo_path = Path(logo_uri)
                    if logo_path.is_absolute() and logo_path.exists():
                        logo_uri = logo_path.as_uri()
                except RuntimeError:
                    pass  # Non-local, keep original logo filename

            output = {
                "company": company,
                "brand": {
                    **brand,
                    "resolved_logo_uri": logo_uri,
                },
                "contact": contact,
                "legal": legal,
            }

            return [TextContent(type="text", text=json.dumps(output, indent=2))]

        elif name == "list_company_configs":
            # Try Supabase first if not using local storage
            if _use_supabase_for_configs():
                configs = sb_get_configs()
                if configs:
                    result = []
                    for c in configs:
                        data = c.get("config", {})
                        company = data.get("company", {})
                        brand = data.get("brand", {})
                        legal = data.get("legal", {})
                        result.append({
                            "id": c["id"],
                            "company_name": c["company_name"],
                            "short_name": c.get("short_name", ""),
                            "is_parent": company.get("is_parent", False),
                            "primary_color": brand.get("primary_color", ""),
                            "accent_color": brand.get("accent_color", ""),
                            "logo": brand.get("logo", ""),
                            "state": legal.get("state", ""),
                            "ein": legal.get("ein", ""),
                            "formation_date": legal.get("formation_date", ""),
                        })
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]
                return [TextContent(type="text", text="No company configs in Supabase. Use sync_templates_to_supabase to upload configs.")]

            # Fall back to local storage
            try:
                root = _get_shared_drive_root()
            except RuntimeError as e:
                return [TextContent(type="text", text=f"Error: {e}")]

            configs = []
            for subdir in COMPANY_CONFIG_PATHS:
                config_path = root / subdir / "company-config.json" if subdir else root / "company-config.json"
                if config_path.exists():
                    try:
                        data = json.loads(config_path.read_text(encoding="utf-8"))
                        company = data.get("company", {})
                        brand = data.get("brand", {})
                        legal = data.get("legal", {})
                        configs.append({
                            "path": str(config_path),
                            "company_name": company.get("name", "Unknown"),
                            "short_name": company.get("short_name", ""),
                            "is_parent": company.get("is_parent", False),
                            "primary_color": brand.get("primary_color", ""),
                            "accent_color": brand.get("accent_color", ""),
                            "logo": brand.get("logo", ""),
                            "state": legal.get("state", ""),
                            "ein": legal.get("ein", ""),
                            "formation_date": legal.get("formation_date", ""),
                        })
                    except Exception:
                        continue

            if not configs:
                return [TextContent(type="text", text="No company-config.json files found in known paths.")]

            return [TextContent(type="text", text=json.dumps(configs, indent=2))]

        elif name == "sync_templates_to_supabase":
            if not _is_local_storage():
                return [TextContent(type="text", text="Error: sync_templates_to_supabase requires local storage access.")]

            if not is_supabase_available():
                return [TextContent(type="text", text="Error: Supabase is not configured.")]

            root = _get_shared_drive_root()
            results = {"templates_synced": [], "configs_synced": [], "errors": []}

            # Sync document templates
            templates_dir = root / "document-templates"
            if templates_dir.exists():
                for f in templates_dir.glob("*.md"):
                    try:
                        content = f.read_text(encoding="utf-8")
                        variables = sorted(set(re.findall(r"\{\{(\w+)\}\}", content)))
                        template_id = f.stem.lower().replace(" ", "-")
                        template = {
                            "id": template_id,
                            "name": f.stem,
                            "filename": f.name,
                            "content": content,
                            "variables": variables,
                        }
                        sb_upsert_template(template)
                        results["templates_synced"].append(f.stem)
                    except Exception as e:
                        results["errors"].append(f"Template {f.name}: {e}")

            # Sync company configs
            for subdir in COMPANY_CONFIG_PATHS:
                config_path = root / subdir / "company-config.json" if subdir else root / "company-config.json"
                if config_path.exists():
                    try:
                        data = json.loads(config_path.read_text(encoding="utf-8"))
                        company_name = data.get("company", {}).get("name", "Unknown")
                        short_name = data.get("company", {}).get("short_name", "")
                        config_id = short_name.lower().replace(" ", "-") if short_name else company_name.lower().replace(" ", "-")
                        config_row = {
                            "id": config_id,
                            "company_name": company_name,
                            "short_name": short_name,
                            "config": data,
                        }
                        sb_upsert_config(config_row)
                        results["configs_synced"].append(company_name)
                    except Exception as e:
                        results["errors"].append(f"Config {config_path.name}: {e}")

            summary = f"Synced {len(results['templates_synced'])} templates and {len(results['configs_synced'])} configs to Supabase."
            if results["errors"]:
                summary += f"\n\nErrors ({len(results['errors'])}):\n" + "\n".join(results["errors"])

            return [TextContent(type="text", text=summary + "\n\n" + json.dumps(results, indent=2))]

        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )
