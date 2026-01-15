"""Tests for asset_manifest module."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from taskman.server.asset_manifest import (
    ASSET_CACHE_CONTROL,
    ASSET_EXTENSIONS,
    build_asset_manifest,
    rewrite_html_assets,
)


class TestBuildAssetManifest(unittest.TestCase):
    def test_empty_directory(self):
        """Empty directory returns empty manifests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest, reverse = build_asset_manifest(Path(tmpdir))
            self.assertEqual(manifest, {})
            self.assertEqual(reverse, {})

    def test_non_asset_files_ignored(self):
        """Files without supported extensions are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "readme.txt").write_text("text file")
            (p / "data.json").write_text("{}")
            (p / "image.png").write_bytes(b"\x89PNG")
            manifest, reverse = build_asset_manifest(p)
            self.assertEqual(manifest, {})
            self.assertEqual(reverse, {})

    def test_css_files_included(self):
        """CSS files are included with content hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            css_content = b"body { color: red; }"
            (p / "style.css").write_bytes(css_content)
            manifest, reverse = build_asset_manifest(p)

            # Verify manifest has the CSS file
            self.assertIn("style.css", manifest)
            hashed = manifest["style.css"]

            # Verify hash is correct
            expected_hash = hashlib.sha256(css_content).hexdigest()[:8]
            self.assertEqual(hashed, f"style.{expected_hash}.css")

            # Verify reverse mapping
            self.assertEqual(reverse[hashed], "style.css")

    def test_js_files_included(self):
        """JS files are included with content hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            js_content = b"console.log('hello');"
            (p / "app.js").write_bytes(js_content)
            manifest, reverse = build_asset_manifest(p)

            self.assertIn("app.js", manifest)
            hashed = manifest["app.js"]
            expected_hash = hashlib.sha256(js_content).hexdigest()[:8]
            self.assertEqual(hashed, f"app.{expected_hash}.js")
            self.assertEqual(reverse[hashed], "app.js")

    def test_nested_files(self):
        """Files in subdirectories use relative paths with forward slashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            styles_dir = p / "styles"
            styles_dir.mkdir()
            css_content = b".base { margin: 0; }"
            (styles_dir / "base.css").write_bytes(css_content)
            manifest, reverse = build_asset_manifest(p)

            self.assertIn("styles/base.css", manifest)
            hashed = manifest["styles/base.css"]
            expected_hash = hashlib.sha256(css_content).hexdigest()[:8]
            self.assertEqual(hashed, f"styles/base.{expected_hash}.css")
            self.assertEqual(reverse[hashed], "styles/base.css")

    def test_multiple_files(self):
        """Multiple asset files are all included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir)
            (p / "a.css").write_bytes(b"a")
            (p / "b.js").write_bytes(b"b")
            (p / "c.css").write_bytes(b"c")
            manifest, reverse = build_asset_manifest(p)

            self.assertEqual(len(manifest), 3)
            self.assertIn("a.css", manifest)
            self.assertIn("b.js", manifest)
            self.assertIn("c.css", manifest)
            self.assertEqual(len(reverse), 3)


class TestRewriteHtmlAssets(unittest.TestCase):
    def test_empty_manifest(self):
        """Empty manifest returns HTML unchanged."""
        html = '<link href="/styles/base.css">'
        result = rewrite_html_assets(html, {})
        self.assertEqual(result, html)

    def test_single_replacement(self):
        """Single asset URL is replaced."""
        html = '<link href="/styles/base.css">'
        manifest = {"styles/base.css": "styles/base.abc123.css"}
        result = rewrite_html_assets(html, manifest)
        self.assertEqual(result, '<link href="/styles/base.abc123.css">')

    def test_multiple_replacements(self):
        """Multiple asset URLs are replaced."""
        html = '''
        <link href="/styles/base.css">
        <script src="/app.js"></script>
        <link href="/styles/layout.css">
        '''
        manifest = {
            "styles/base.css": "styles/base.abc.css",
            "app.js": "app.def.js",
            "styles/layout.css": "styles/layout.ghi.css",
        }
        result = rewrite_html_assets(html, manifest)
        self.assertIn("/styles/base.abc.css", result)
        self.assertIn("/app.def.js", result)
        self.assertIn("/styles/layout.ghi.css", result)
        self.assertNotIn("/styles/base.css", result)
        self.assertNotIn("/app.js", result)
        self.assertNotIn("/styles/layout.css", result)

    def test_no_matching_urls(self):
        """HTML with no matching URLs is unchanged."""
        html = '<img src="/logo.png"><a href="/about.html">About</a>'
        manifest = {"styles/base.css": "styles/base.abc.css"}
        result = rewrite_html_assets(html, manifest)
        self.assertEqual(result, html)

    def test_substring_matches_are_replaced(self):
        """Substring matches are also replaced (simple string replace behavior)."""
        html = '<link href="/other/styles/base.css">'
        manifest = {"styles/base.css": "styles/base.abc.css"}
        result = rewrite_html_assets(html, manifest)
        # The implementation uses simple string replace, so "/styles/base.css" in the path is matched
        self.assertIn("styles/base.abc.css", result)


class TestConstants(unittest.TestCase):
    def test_asset_extensions(self):
        """Verify expected asset extensions are defined."""
        self.assertIn(".css", ASSET_EXTENSIONS)
        self.assertIn(".js", ASSET_EXTENSIONS)

    def test_cache_control_immutable(self):
        """Cache control header includes immutable directive."""
        self.assertIn("immutable", ASSET_CACHE_CONTROL)
        self.assertIn("max-age=", ASSET_CACHE_CONTROL)


if __name__ == "__main__":
    unittest.main()
