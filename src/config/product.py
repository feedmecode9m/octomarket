"""OctoMarket product identity — single source for branding."""

from typing import Any, Dict

PRODUCT_NAME = "OctoMarket"
VERSION = "0.1.0"
TAGLINE = "Practice. Analyze. Execute. Improve."
POSITIONING = "AI-powered trading practice terminal"

MODULE_LABELS = {
    "terminal": "OctoMarket Terminal",
    "mentor": "OctoMarket Mentor",
    "lab": "OctoMarket Lab",
    "replay": "OctoMarket Replay",
    "academy": "OctoMarket Academy",
    "journal": "OctoMarket Journal",
    "home": "OctoMarket",
}

NAV_ITEMS = [
    {"id": "terminal", "path": "/terminal", "label": "Terminal", "desc": "TradingView-style execution", "icon": "fa-terminal"},
    {"id": "mentor", "path": "/mentor", "label": "Mentor", "desc": "AI trading coach", "icon": "fa-user-graduate"},
    {"id": "lab", "path": "/strategy-lab", "label": "Lab", "desc": "Strategy testing", "icon": "fa-flask"},
    {"id": "replay", "path": "/replay", "label": "Replay", "desc": "Market simulation", "icon": "fa-chart-line"},
    {"id": "academy", "path": "/academy", "label": "Academy", "desc": "Lessons and challenges", "icon": "fa-graduation-cap"},
    {"id": "journal", "path": "/journal", "label": "Journal", "desc": "Trade reviews", "icon": "fa-book"},
]


def get_product() -> Dict[str, Any]:
    return {
        "name": PRODUCT_NAME,
        "version": VERSION,
        "tagline": TAGLINE,
        "positioning": POSITIONING,
        "labels": MODULE_LABELS,
        "nav": NAV_ITEMS,
    }


def get_product_context() -> Dict[str, Any]:
    """Template context dict."""
    p = get_product()
    return {
        "product": p,
        "product_name": p["name"],
        "product_version": p["version"],
        "product_tagline": p["tagline"],
        "product_positioning": p["positioning"],
        "module_labels": p["labels"],
        "nav_items": p["nav"],
    }
