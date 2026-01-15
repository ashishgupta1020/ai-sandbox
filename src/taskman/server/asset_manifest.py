"""
Asset manifest utilities for cache-busting static files.

This module builds a mapping from original asset paths to hash-suffixed variants,
enabling long-term browser caching while ensuring updates are always fetched.
"""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Dict, Tuple

# Extensions that should be cache-busted with content hashes
ASSET_EXTENSIONS = {".css", ".js"}

# Cache-control header for hashed assets (immutable, long-lived)
ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"


def build_asset_manifest(ui_dir: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Build a mapping of original asset paths to hash-suffixed variants.

    Args:
        ui_dir: Root directory containing UI assets.

    Returns:
        A tuple of (manifest, reverse_map) where:
        - manifest maps original paths (e.g., "styles/base.css") to hashed paths
          (e.g., "styles/base.a1b2c3d4.css")
        - reverse_map is the inverse mapping for serving hashed requests
    """
    manifest: Dict[str, str] = {}
    reverse: Dict[str, str] = {}

    for path in ui_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in ASSET_EXTENSIONS:
            continue

        rel = PurePosixPath(path.relative_to(ui_dir))
        # Compute content hash for cache-busting
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
        hashed_name = f"{rel.stem}.{digest}{path.suffix}"
        hashed_rel = str(rel.with_name(hashed_name))
        original_rel = str(rel)

        manifest[original_rel] = hashed_rel
        reverse[hashed_rel] = original_rel

    return manifest, reverse


def rewrite_html_assets(html: str, manifest: Dict[str, str]) -> str:
    """
    Replace asset URLs in HTML with their hash-suffixed variants.

    Args:
        html: The HTML content to rewrite.
        manifest: Mapping from original paths to hashed paths.

    Returns:
        HTML with asset URLs replaced.
    """
    if not manifest:
        return html

    for original, hashed in manifest.items():
        html = html.replace(f"/{original}", f"/{hashed}")

    return html
