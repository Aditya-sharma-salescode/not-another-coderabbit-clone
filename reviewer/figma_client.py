"""Figma REST API v1 client — fetch design specs from node trees."""

from __future__ import annotations

import logging

import httpx

from reviewer import config

logger = logging.getLogger(__name__)

FIGMA_API = "https://api.figma.com/v1"


def _headers() -> dict[str, str]:
    return {"X-Figma-Token": config.FIGMA_ACCESS_TOKEN}


def get_file_node(file_key: str, node_id: str) -> dict | None:
    """
    Fetch a specific node from a Figma file.
    GET /v1/files/{file_key}/nodes?ids={node_id}
    """
    if not config.figma_enabled():
        logger.info("Figma not configured, skipping design fetch")
        return None

    url = f"{FIGMA_API}/files/{file_key}/nodes"
    params = {"ids": node_id} if node_id else {}

    try:
        with httpx.Client(timeout=20) as client:
            r = client.get(url, headers=_headers(), params=params)
            if r.status_code == 404:
                logger.warning("Figma file %s not found", file_key)
                return None
            r.raise_for_status()
            data = r.json()

            if node_id:
                nodes = data.get("nodes", {})
                node_data = nodes.get(node_id)
                if node_data:
                    return node_data.get("document")
            return data
    except Exception as e:
        logger.warning("Figma API error: %s", e)
        return None


def extract_design_specs(node: dict | None, depth: int = 0, max_depth: int = 8) -> dict:
    """
    Depth-first traversal of a Figma node tree to extract design specs.
    Returns layout, colors, and typography information.
    """
    specs: dict = {
        "layout": [],
        "colors": [],
        "typography": [],
        "components": [],
    }

    if node is None or depth > max_depth:
        return specs

    _extract_node_specs(node, specs, depth)

    # Recurse into children
    for child in node.get("children", []):
        child_specs = extract_design_specs(child, depth + 1, max_depth)
        specs["layout"].extend(child_specs["layout"])
        specs["colors"].extend(child_specs["colors"])
        specs["typography"].extend(child_specs["typography"])
        specs["components"].extend(child_specs["components"])

    return specs


def _extract_node_specs(node: dict, specs: dict, depth: int) -> None:
    """Extract specs from a single node."""
    name = node.get("name", "")
    node_type = node.get("type", "")

    # Layout info
    layout_info = _extract_layout(node)
    if layout_info:
        layout_info["name"] = name
        layout_info["type"] = node_type
        layout_info["depth"] = depth
        specs["layout"].append(layout_info)

    # Colors from fills
    fills = node.get("fills", [])
    for fill in fills:
        if fill.get("type") == "SOLID" and fill.get("visible", True):
            color = fill.get("color", {})
            hex_color = _rgba_to_hex(color)
            token = ""
            # Check for bound variables (design tokens)
            bound = fill.get("boundVariables", {}).get("color", {})
            if bound:
                token = bound.get("id", "")

            specs["colors"].append({
                "node": name,
                "hex": hex_color,
                "token": token,
                "opacity": fill.get("opacity", 1.0),
            })

    # Typography from style
    style = node.get("style", {})
    if style.get("fontFamily"):
        typo = {
            "node": name,
            "fontFamily": style.get("fontFamily", ""),
            "fontSize": style.get("fontSize", 0),
            "fontWeight": style.get("fontWeight", 400),
            "lineHeightPx": style.get("lineHeightPx", 0),
            "letterSpacing": style.get("letterSpacing", 0),
        }
        if style.get("fontSize") and style.get("lineHeightPx"):
            typo["heightRatio"] = round(style["lineHeightPx"] / style["fontSize"], 2)
        specs["typography"].append(typo)

    # Component instances
    if node_type == "INSTANCE":
        specs["components"].append({
            "name": name,
            "componentId": node.get("componentId", ""),
        })


def _extract_layout(node: dict) -> dict | None:
    """Extract layout properties from a Figma node."""
    layout: dict = {}

    # Dimensions
    bbox = node.get("absoluteBoundingBox", {})
    if bbox:
        layout["width"] = bbox.get("width", 0)
        layout["height"] = bbox.get("height", 0)

    # Auto-layout properties
    layout_mode = node.get("layoutMode")
    if layout_mode:
        layout["layoutMode"] = layout_mode  # HORIZONTAL or VERTICAL
        layout["itemSpacing"] = node.get("itemSpacing", 0)
        layout["primaryAxisAlignItems"] = node.get("primaryAxisAlignItems", "")
        layout["counterAxisAlignItems"] = node.get("counterAxisAlignItems", "")

    # Padding
    padding_top = node.get("paddingTop", 0)
    padding_right = node.get("paddingRight", 0)
    padding_bottom = node.get("paddingBottom", 0)
    padding_left = node.get("paddingLeft", 0)
    if any([padding_top, padding_right, padding_bottom, padding_left]):
        layout["padding"] = {
            "top": padding_top,
            "right": padding_right,
            "bottom": padding_bottom,
            "left": padding_left,
        }

    # Corner radius
    corner_radius = node.get("cornerRadius", 0)
    if corner_radius:
        layout["cornerRadius"] = corner_radius

    return layout if layout else None


def _rgba_to_hex(color: dict) -> str:
    """Convert Figma RGBA (0-1 float) to hex string."""
    r = round(color.get("r", 0) * 255)
    g = round(color.get("g", 0) * 255)
    b = round(color.get("b", 0) * 255)
    return f"#{r:02X}{g:02X}{b:02X}"


def format_design_specs_for_prompt(specs: dict) -> str:
    """Format extracted design specs into a readable section for the AI prompt."""
    if not any(specs.values()):
        return "No design specs extracted."

    sections = []

    if specs["layout"]:
        sections.append("### Layout")
        for item in specs["layout"][:20]:  # Cap at 20
            name = item.get("name", "?")
            parts = [f"**{name}** ({item.get('type', '')})"]
            if "width" in item:
                parts.append(f"  Size: {item['width']}×{item['height']}")
            if "layoutMode" in item:
                parts.append(f"  Layout: {item['layoutMode']}, gap={item.get('itemSpacing', 0)}")
            if "padding" in item:
                p = item["padding"]
                parts.append(f"  Padding: T={p['top']} R={p['right']} B={p['bottom']} L={p['left']}")
            if "cornerRadius" in item:
                parts.append(f"  Corner radius: {item['cornerRadius']}")
            sections.append("\n".join(parts))

    if specs["colors"]:
        sections.append("### Colors")
        seen = set()
        for c in specs["colors"]:
            key = c["hex"]
            if key not in seen:
                seen.add(key)
                token_str = f" (token: {c['token']})" if c["token"] else ""
                sections.append(f"- {c['hex']}{token_str} — used on: {c['node']}")

    if specs["typography"]:
        sections.append("### Typography")
        for t in specs["typography"][:10]:
            height_str = f", height={t.get('heightRatio', '')}" if t.get("heightRatio") else ""
            sections.append(
                f"- **{t['node']}**: {t['fontFamily']} {t['fontSize']}px "
                f"w{t['fontWeight']}{height_str}"
            )

    # Figma → Flutter mapping table
    sections.append("""### Figma → Flutter Mapping
| Figma | Flutter |
|-------|---------|
| paddingTop/Right/Bottom/Left | `EdgeInsets.fromLTRB(l, t, r, b)` |
| itemSpacing (VERTICAL) | `SizedBox(height: gap)` |
| itemSpacing (HORIZONTAL) | `SizedBox(width: gap)` |
| fill.color {r,g,b,a} | `Color(0xFF{hex})` |
| style.fontSize | `TextStyle(fontSize: n)` |
| style.fontWeight 700 | `FontWeight.bold` |
| lineHeightPx / fontSize | `TextStyle(height: ratio)` |
| cornerRadius | `BorderRadius.circular(r)` |""")

    return "\n\n".join(sections)
