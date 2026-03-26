"""Lightweight HTML fetching and text cleaning utilities."""

from __future__ import annotations

import logging
import re

import requests

LOGGER = logging.getLogger(__name__)


def fetch_clean_text(url: str) -> str:
    """Fetch a URL and strip it down to basic readable text."""
    if not url:
        return ""

    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        html = response.text
        html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("HTML fetch failed for %s: %s", url, exc)
        return ""
