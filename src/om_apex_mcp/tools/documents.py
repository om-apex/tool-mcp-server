"""Document generation tools: generate_branded_html, list_company_configs.

Approach (TECH-038, TECH-039, TECH-040):
  Generate multi-page HTML where each logical page section has branded header/footer.
  The HTML is opened in a browser and printed to PDF (Cmd+P -> Save as PDF).
"""

import json
import re
from pathlib import Path
from typing import Optional

import markdown as md_lib

from mcp.types import Tool, TextContent

from . import ToolModule
from .helpers import SHARED_DRIVE_ROOT

READING = ["list_company_configs"]
WRITING = ["generate_branded_html"]

# Known company config locations relative to shared drive root
COMPANY_CONFIG_PATHS = [
    "om-ai",
    "om-luxe",
    "om-scm",
    "",  # root = Om Apex Holdings
]


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
    """Find company-config.json by company name from known paths."""
    for subdir in COMPANY_CONFIG_PATHS:
        config_path = SHARED_DRIVE_ROOT / subdir / "company-config.json" if subdir else SHARED_DRIVE_ROOT / "company-config.json"
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
            "primary_color": "#1E4D7C",
            "accent_color": "#C9A227",
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
    """Resolve the logo path from brand-assets/ or by walking up directories."""
    logo_filename = config["brand"]["logo"]
    logo_dir = config["brand"].get("logo_dir", "brand-assets")
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

    return f"""<table class="hdr-table">
      <tr>
        <td class="hdr-left-cell">
          <img src="{logo_uri}" alt="" style="height:48px;width:auto;">
          <span style="font-family:{brand['heading_font']};font-weight:600;font-size:16px;color:{brand['primary_color']};letter-spacing:1px;line-height:1.2;">{company['display_name_line1']}<br>{company['display_name_line2']}</span>
        </td>
        <td class="hdr-right-cell">
          <table>
            <tr><td style="vertical-align:top;padding:0;"><svg width="10" height="10" viewBox="0 0 24 24"><path fill="#EA4335" d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z"/></svg></td><td style="vertical-align:top;padding:0 0 0 4px;font-size:8px;color:{brand['secondary_text_color']};line-height:1.2;">{contact['address_line1']}<br>{contact['address_line2']}</td></tr>
            <tr><td colspan="2" style="padding:1px 0;"><hr style="border:none;border-top:1px solid #D0D0D0;margin:0;"></td></tr>
            <tr><td style="vertical-align:middle;padding:0;font-size:10px;color:{brand['secondary_text_color']};">&#x260E;</td><td style="vertical-align:middle;padding:0 0 0 4px;font-size:8px;color:{brand['secondary_text_color']};">{contact['phone']}</td></tr>
          </table>
        </td>
      </tr>
    </table>"""


def _build_footer_html(config: dict) -> str:
    company = config["company"]
    footer_left = _build_footer_left(config)

    return f"""<div class="ftr-left">{footer_left}</div>
    <div class="ftr-center">{company['tagline']}</div>"""


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
            height: 69px;
            padding: 0 60px;
            background: #fff;
        }}
        .page-footer-bar {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 6px 60px 10px 60px;
            border-top: 2px solid {brand["accent_color"]};
            background: #fff;
            font-size: 7px;
            color: {brand["secondary_text_color"]};
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
        border-bottom: 2px solid {brand["accent_color"]};
        padding-bottom: 8px;
        margin-bottom: 20px;
    }}
    .hdr-table {{
        width: 100%;
        border-collapse: collapse;
        height: 100%;
    }}
    .hdr-table td {{
        border: none;
        background: transparent;
        vertical-align: middle;
        padding: 0;
    }}
    .hdr-left-cell {{
        text-align: left;
        white-space: nowrap;
    }}
    .hdr-left-cell img {{
        vertical-align: middle;
    }}
    .hdr-left-cell span {{
        vertical-align: middle;
        padding-left: 10px;
    }}
    .hdr-right-cell {{
        text-align: right;
    }}
    .hdr-right-cell table {{
        float: right;
        border-collapse: collapse;
    }}
    .hdr-right-cell table td {{
        border: none;
        background: transparent;
        padding: 0;
    }}

    /* ── Footer bar ── */
    .page-footer-bar {{
        border-top: 2px solid {brand["accent_color"]};
        padding-top: 6px;
        margin-top: 30px;
    }}
    .ftr-left {{
        font-size: 7px;
        line-height: 1.1;
        color: {brand["secondary_text_color"]};
        display: inline;
    }}
    .ftr-center {{
        font-style: italic;
        font-size: 11px;
        color: {brand["secondary_text_color"]};
        display: inline;
        float: right;
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


def _markdown_to_branded_html(
    md_content: str,
    config: dict,
    logo_uri: str,
    doc_config: Optional[dict] = None,
) -> str:
    """Convert markdown content to branded HTML with header/footer."""
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
            name="list_company_configs",
            description="List available company-config.json files with branding summary for document generation.",
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
            search_start = md_file_path or str(SHARED_DRIVE_ROOT)
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

        elif name == "list_company_configs":
            configs = []
            for subdir in COMPANY_CONFIG_PATHS:
                config_path = SHARED_DRIVE_ROOT / subdir / "company-config.json" if subdir else SHARED_DRIVE_ROOT / "company-config.json"
                if config_path.exists():
                    try:
                        data = json.loads(config_path.read_text(encoding="utf-8"))
                        company = data.get("company", {})
                        brand = data.get("brand", {})
                        configs.append({
                            "path": str(config_path),
                            "company_name": company.get("name", "Unknown"),
                            "short_name": company.get("short_name", ""),
                            "is_parent": company.get("is_parent", False),
                            "primary_color": brand.get("primary_color", ""),
                            "accent_color": brand.get("accent_color", ""),
                            "logo": brand.get("logo", ""),
                        })
                    except Exception:
                        continue

            if not configs:
                return [TextContent(type="text", text="No company-config.json files found in known paths.")]

            return [TextContent(type="text", text=json.dumps(configs, indent=2))]

        return None

    return ToolModule(
        tools=tools,
        handler=handler,
        reading_tools=READING,
        writing_tools=WRITING,
    )
