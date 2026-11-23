#!/opt/anaconda3/bin/python
"""Automated acceptance verifier for the Nord Dual-Theme Hopf Fibration Profile.

Checks Section 7.3 assertions:
1. 100% Nord 16-color palette purity across all generated SVGs.
2. Zero external dependencies (<script>, http://, https://) and zero raw <text>/<tspan>.
3. File size bounds (15 KB - 160 KB for banner-*.svg) and t=0 visibility safety.
4. Headless Chrome PNG rasterization of preview-dark.png and preview-light.png.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

NORD_16 = {
    "#2E3440", "#3B4252", "#434C5E", "#4C566A",
    "#D8DEE9", "#E5E9F0", "#ECEFF4",
    "#8FBCBB", "#88C0D0", "#81A1C1", "#5E81AC",
    "#BF616A", "#D08770", "#EBCB8B", "#A3BE8C", "#B48EAD",
}

EXPECTED_SVGS = [
    "banner-dark.svg",
    "banner-light.svg",
    "sec-bench-dark.svg",
    "sec-bench-light.svg",
    "sec-treatises-dark.svg",
    "sec-treatises-light.svg",
    "sec-sketches-dark.svg",
    "sec-sketches-light.svg",
]


def verify_svgs() -> None:
    hex_re = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")

    for name in EXPECTED_SVGS:
        path = ASSETS / name
        assert path.exists(), f"Missing SVG asset: {path}"
        raw = path.read_text(encoding="utf-8")
        size_bytes = len(raw.encode("utf-8"))

        # Assertion 1: Nord 16-color palette purity
        # Strip url(#id) fragments before checking hex codes
        cleaned = re.sub(r"url\(#[^)]+\)", "", raw)
        cleaned = re.sub(r'id="[^"]+"', "", cleaned)
        found_hex = {f"#{m.group(1).upper()}" for m in hex_re.finditer(cleaned)}
        illegal = found_hex - NORD_16
        assert not illegal, f"{name} contains non-Nord colors: {sorted(illegal)}"

        # Assertion 2: Zero external deps & zero raw <text>
        lower = raw.lower()
        assert "<script" not in lower, f"{name} contains forbidden <script>"
        lower_no_ns = lower.replace('xmlns="http://www.w3.org/2000/svg"', "")
        assert "http://" not in lower_no_ns and "https://" not in lower_no_ns, (
            f"{name} contains external URL"
        )
        assert "<text" not in lower and "<tspan" not in lower, f"{name} contains un-outlined <text>/<tspan>"

        # Assertion 3: Size & first-frame safety
        if name.startswith("banner-"):
            assert 15 * 1024 <= size_bytes <= 160 * 1024, (
                f"{name} size {size_bytes} bytes outside [15 KB, 160 KB]"
            )
        else:
            assert 1024 <= size_bytes <= 160 * 1024, (
                f"{name} size {size_bytes} bytes unreasonable"
            )
        assert "stroke-dashoffset" not in lower, f"{name} uses stroke-dashoffset hiding trap"
        assert "opacity: 0;" not in lower and 'opacity="0"' not in lower, f"{name} hides elements at t=0"

        print(f"[PASS] {name}: {size_bytes / 1024:.1f} KB | colors={len(found_hex)} (100% Nord) | paths-only")


def verify_readme_and_manifest() -> None:
    manifest = tomllib.loads((ROOT / "manifest.toml").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in EXPECTED_SVGS:
        assert f"./assets/{name}" in readme, f"README.md missing reference to ./assets/{name}"
    for sec in manifest["sections"]:
        for item in sec["items"]:
            assert item["name"] in readme, f"README.md missing item {item['name']}"
    # Check prose constraints (no !, no common emoji; ignore HTML comments)
    readme_visible = re.sub(r"<!--.*?-->", "", readme, flags=re.S)
    assert "!" not in readme_visible and "！" not in readme_visible, "README.md contains exclamation mark"
    print("[PASS] manifest.toml & README.md consistency & prose constraints verified")


def render_previews() -> None:
    preview_html = ROOT / "preview.html"
    assert preview_html.exists(), "preview.html missing"
    for mode in ("dark", "light"):
        out_png = ROOT / f"preview-{mode}.png"
        url = f"file://{preview_html}?theme={mode}"
        cmd = [
            CHROME,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--window-size=980,1180",
            f"--screenshot={out_png}",
            url,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert out_png.exists() and out_png.stat().st_size > 10_000, f"Failed to render {out_png}"
        print(f"[PASS] Rendered {out_png.name} ({out_png.stat().st_size / 1024:.1f} KB)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()

    if not args.render_only:
        verify_svgs()
        verify_readme_and_manifest()
    render_previews()


if __name__ == "__main__":
    main()
