#!/opt/anaconda3/bin/python
"""Deterministic generator for the Nord Dual-Theme Hopf Fibration GitHub Profile.

Reads manifest.toml and outputs:
- assets/banner-dark.svg, assets/banner-light.svg
- assets/sec-{bench,treatises,sketches}-{dark,light}.svg
- README.md
- preview.html
"""

from __future__ import annotations

import html
import re
import sys
import tomllib
from pathlib import Path

import numpy as np
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTCollection, TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from hopf_geometry import (  # noqa: E402
    build_hopf_torus_data,
    build_s2_inset_data,
    offset_polyline,
    points_to_closed_bezier,
    points_to_open_bezier,
)

ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

# Official 16-color Nord Palette
NORD = {
    "nord0": "#2E3440",
    "nord1": "#3B4252",
    "nord2": "#434C5E",
    "nord3": "#4C566A",
    "nord4": "#D8DEE9",
    "nord5": "#E5E9F0",
    "nord6": "#ECEFF4",
    "nord7": "#8FBCBB",
    "nord8": "#88C0D0",
    "nord9": "#81A1C1",
    "nord10": "#5E81AC",
    "nord11": "#BF616A",
    "nord12": "#D08770",
    "nord13": "#EBCB8B",
    "nord14": "#A3BE8C",
    "nord15": "#B48EAD",
}


class FontRegistry:
    """Loads macOS system fonts and converts text strings to pure SVG <path> data."""

    def __init__(self) -> None:
        ny_raw = TTFont("/System/Library/Fonts/NewYork.ttf")
        self.serif = instantiateVariableFont(ny_raw, {"opsz": 34.0, "wght": 520.0})

        ny_sm_raw = TTFont("/System/Library/Fonts/NewYork.ttf")
        self.serif_sm = instantiateVariableFont(ny_sm_raw, {"opsz": 16.0, "wght": 520.0})

        mono_raw = TTFont("/System/Library/Fonts/SFNSMono.ttf")
        self.mono = instantiateVariableFont(mono_raw, {"wght": 420.0})

        self.zh_sans = TTCollection("/System/Library/Fonts/Hiragino Sans GB.ttc").fonts[0]
        self.zh_serif = TTCollection("/System/Library/Fonts/Supplemental/Songti.ttc").fonts[6]

    def _font_for_char(self, ch: str, style: str) -> TTFont:
        is_cjk = ord(ch) > 0x2E00 and ch not in "→·—"
        if style == "serif":
            return self.zh_serif if is_cjk else self.serif
        if style == "serif_sm":
            return self.zh_serif if is_cjk else self.serif_sm
        if style == "zh_sans":
            return self.zh_sans if is_cjk else self.mono
        return self.zh_sans if is_cjk else self.mono

    def text_to_path(
        self,
        text: str,
        x: float,
        y_baseline: float,
        size_px: float,
        style: str = "serif",
        tracking: float = 0.0,
    ) -> tuple[str, float]:
        """Convert text to SVG path d-string at (x, y_baseline). Returns (d_str, end_x)."""
        cursor_x = x
        cmds: list[str] = []
        for ch in text:
            font = self._font_for_char(ch, style)
            upem = font["head"].unitsPerEm
            scale = size_px / upem
            cmap = font.getBestCmap()
            gname = cmap.get(ord(ch))
            if gname is None:
                gname = cmap.get(ord(" "), ".notdef")
            glyph_set = font.getGlyphSet()
            adv_width, _ = font["hmtx"].metrics.get(gname, (int(upem * 0.5), 0))

            svg_pen = SVGPathPen(glyph_set)
            t_pen = TransformPen(svg_pen, (scale, 0.0, 0.0, -scale, cursor_x, y_baseline))
            glyph_set[gname].draw(t_pen)
            cmd = svg_pen.getCommands()
            if cmd:
                # Round excessive floating-point precision from fontTools TransformPen
                cmd = re.sub(
                    r"-?\d+\.\d+",
                    lambda m: f"{float(m.group(0)):.2f}".rstrip("0").rstrip("."),
                    cmd,
                )
                cmds.append(cmd)
            cursor_x += adv_width * scale + tracking

        return " ".join(cmds), cursor_x


def _render_banner_svg(mode: str, manifest: dict, fonts: FontRegistry) -> str:
    """Render banner-dark.svg or banner-light.svg (880 x 252)."""
    is_dark = mode == "dark"
    prof = manifest["profile"]

    canvas = NORD["nord0"] if is_dark else NORD["nord6"]
    elevated = NORD["nord1"] if is_dark else NORD["nord5"]
    hairline = NORD["nord2"] if is_dark else NORD["nord4"]
    title_ink = NORD["nord6"] if is_dark else NORD["nord0"]
    sub_ink = NORD["nord4"] if is_dark else NORD["nord2"]
    muted_ink = NORD["nord3"]

    ambient_colors = (
        [NORD["nord10"], NORD["nord9"]] if is_dark else [NORD["nord10"], NORD["nord3"]]
    )

    # 1. Hopf geometry & S^2 inset
    ambient_fibers, aurora_arcs, _ = build_hopf_torus_data(
        cx=640.0, cy=126.0, target_height=204.0, n_pts_ambient=32
    )
    s2 = build_s2_inset_data(cx=66.0, cy=182.0, radius=22.0)

    lines: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 252" width="880" height="252">',
        "<defs>",
    ]

    # Mineral Halo Wash gradients (pure Nord colors)
    if is_dark:
        lines.append(
            f'<radialGradient id="halo-wash-d" cx="50%" cy="50%" r="50%">'
            f'<stop offset="0%" stop-color="{NORD["nord10"]}" stop-opacity="0.10"/>'
            f'<stop offset="70%" stop-color="{NORD["nord10"]}" stop-opacity="0.04"/>'
            f'<stop offset="100%" stop-color="{NORD["nord10"]}" stop-opacity="0.0"/>'
            f"</radialGradient>"
        )
    else:
        lines.append(
            f'<radialGradient id="halo-wash-l1" cx="50%" cy="50%" r="50%">'
            f'<stop offset="0%" stop-color="{NORD["nord13"]}" stop-opacity="0.26"/>'
            f'<stop offset="68%" stop-color="{NORD["nord13"]}" stop-opacity="0.09"/>'
            f'<stop offset="100%" stop-color="{NORD["nord13"]}" stop-opacity="0.0"/>'
            f"</radialGradient>"
        )
        lines.append(
            f'<radialGradient id="halo-wash-l2" cx="50%" cy="50%" r="50%">'
            f'<stop offset="0%" stop-color="{NORD["nord14"]}" stop-opacity="0.20"/>'
            f'<stop offset="72%" stop-color="{NORD["nord14"]}" stop-opacity="0.06"/>'
            f'<stop offset="100%" stop-color="{NORD["nord14"]}" stop-opacity="0.0"/>'
            f"</radialGradient>"
        )

    lines.extend(
        [
            "</defs>",
            "<style>",
            "@keyframes frostBreath { 0%, 100% { opacity: 1; } 50% { opacity: 0.72; } }",
            ".ambient-foliation { animation: frostBreath 14s ease-in-out infinite; }",
            "</style>",
            # Ground & framing
            f'<rect x="0" y="0" width="880" height="252" rx="8" fill="{canvas}"/>',
            f'<rect x="0.5" y="0.5" width="879" height="251" rx="7.5" fill="none" stroke="{hairline}" stroke-width="1"/>',
            # Top & bottom architectural rulers (y=28, y=224; left/right margin 36px)
            f'<line x1="36" y1="28" x2="844" y2="28" stroke="{hairline}" stroke-width="0.9"/>',
            f'<line x1="36" y1="224" x2="844" y2="224" stroke="{hairline}" stroke-width="0.9"/>',
            f'<line x1="36" y1="25" x2="36" y2="31" stroke="{hairline}" stroke-width="0.9"/>',
            f'<line x1="844" y1="25" x2="844" y2="31" stroke="{hairline}" stroke-width="0.9"/>',
            f'<line x1="36" y1="221" x2="36" y2="227" stroke="{hairline}" stroke-width="0.9"/>',
            f'<line x1="844" y1="221" x2="844" y2="227" stroke="{hairline}" stroke-width="0.9"/>',
        ]
    )

    # Mineral Halo Wash under torus
    if is_dark:
        lines.append('<ellipse cx="640" cy="126" rx="168" ry="110" fill="url(#halo-wash-d)"/>')
    else:
        lines.append('<ellipse cx="618" cy="120" rx="158" ry="104" fill="url(#halo-wash-l1)"/>')
        lines.append('<ellipse cx="662" cy="134" rx="146" ry="96" fill="url(#halo-wash-l2)"/>')

    # Ambient Frost Foliation (40 fibers sorted far-to-near)
    lines.append('<g class="ambient-foliation">')
    for idx, fiber in enumerate(ambient_fibers):
        col = ambient_colors[idx % 2]
        d_path = points_to_closed_bezier(fiber.points, precision=1)
        lines.append(
            f'<path d="{d_path}" fill="none" stroke="{col}" stroke-width="0.9" stroke-opacity="0.28"/>'
        )
    lines.append("</g>")

    # 3 Linked Aurora Characteristic Fibers with Copperplate Crossing Halos
    lines.append('<g class="aurora-fibers">')
    for arc in aurora_arcs:
        # 1. Over-crossing 5.6px canvas-ground halo bridges
        for span in arc.halo_spans:
            h_path = points_to_open_bezier(span, precision=1)
            if not is_dark and arc.key == "B":
                # Cover both primary and parallel companion strand cleanly
                lines.append(
                    f'<path d="{h_path}" fill="none" stroke="{canvas}" stroke-width="6.4" stroke-linecap="round" stroke-linejoin="round"/>'
                )
                comp_span = offset_polyline(span, offset_px=2.3, closed=False)
                hc_path = points_to_open_bezier(comp_span, precision=1)
                lines.append(
                    f'<path d="{hc_path}" fill="none" stroke="{canvas}" stroke-width="4.4" stroke-linecap="round" stroke-linejoin="round"/>'
                )
            else:
                lines.append(
                    f'<path d="{h_path}" fill="none" stroke="{canvas}" stroke-width="5.6" stroke-linecap="round" stroke-linejoin="round"/>'
                )

        # 2. Colored stroke
        a_path = (
            points_to_closed_bezier(arc.points, precision=1)
            if arc.closed
            else points_to_open_bezier(arc.points, precision=1)
        )

        if arc.key == "A":
            lines.append(
                f'<path d="{a_path}" fill="none" stroke="{NORD["nord11"]}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
            )
        elif arc.key == "B":
            if is_dark:
                lines.append(
                    f'<path d="{a_path}" fill="none" stroke="{NORD["nord14"]}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
                )
            else:
                # Light mode: #5E81AC primary + #A3BE8C parallel companion
                lines.append(
                    f'<path d="{a_path}" fill="none" stroke="{NORD["nord10"]}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
                )
                comp_pts = offset_polyline(arc.points, offset_px=2.3, closed=arc.closed)
                c_path = (
                    points_to_closed_bezier(comp_pts, precision=1)
                    if arc.closed
                    else points_to_open_bezier(comp_pts, precision=1)
                )
                lines.append(
                    f'<path d="{c_path}" fill="none" stroke="{NORD["nord14"]}" stroke-width="1.15" stroke-linecap="round" stroke-linejoin="round"/>'
                )
        elif arc.key == "C":
            if is_dark:
                lines.append(
                    f'<path d="{a_path}" fill="none" stroke="{NORD["nord13"]}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
                )
            else:
                # Light mode: #D08770 terracotta + #2E3440 thin inner core
                lines.append(
                    f'<path d="{a_path}" fill="none" stroke="{NORD["nord12"]}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
                )
                lines.append(
                    f'<path d="{a_path}" fill="none" stroke="{NORD["nord0"]}" stroke-width="0.75" stroke-linecap="round" stroke-linejoin="round"/>'
                )
    lines.append("</g>")

    # Left-zone typography (x = 40..390), 100% vector <path>
    title_d, title_end_x = fonts.text_to_path(
        prof["handle"], x=40.0, y_baseline=88.0, size_px=37.0, style="serif", tracking=0.2
    )
    sub_d, _ = fonts.text_to_path(
        prof["subtitle_en"], x=title_end_x + 11.0, y_baseline=88.0, size_px=12.5, style="mono"
    )
    tag_d, _ = fonts.text_to_path(
        prof["tagline"], x=41.0, y_baseline=117.0, size_px=14.0, style="serif_sm", tracking=0.4
    )

    lines.append(f'<path d="{title_d}" fill="{title_ink}"/>')
    lines.append(f'<path d="{sub_d}" fill="{sub_ink}" fill-opacity="0.82"/>')
    lines.append(f'<path d="{tag_d}" fill="{sub_ink}"/>')
    lines.append(f'<line x1="41" y1="134" x2="88" y2="134" stroke="{hairline}" stroke-width="0.9"/>')

    # Bottom-left S^2 base space inset card (elevated surface)
    cx_s2, cy_s2, r_s2 = s2["cx"], s2["cy"], s2["radius"]
    lines.append(
        f'<rect x="38" y="154" width="186" height="56" rx="6" fill="{elevated}" stroke="{hairline}" stroke-width="0.85"/>'
    )
    lines.append(
        f'<circle cx="{cx_s2:.1f}" cy="{cy_s2:.1f}" r="{r_s2:.1f}" fill="{canvas}" stroke="{muted_ink}" stroke-width="0.85"/>'
    )

    # Wireframe arcs on S^2 split into back (d < 0) and front (d >= 0)
    wire_stroke = NORD["nord9"] if is_dark else NORD["nord3"]
    for w_pts, w_ds in s2["wire_curves"]:
        # Emit front and back polyline segments
        front_seg: list[np.ndarray] = []
        back_seg: list[np.ndarray] = []
        for i in range(len(w_pts)):
            if w_ds[i] >= 0:
                front_seg.append(w_pts[i])
                if len(back_seg) >= 2:
                    bp = "M " + " L ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in back_seg)
                    lines.append(f'<path d="{bp}" fill="none" stroke="{wire_stroke}" stroke-width="0.6" stroke-opacity="0.22"/>')
                back_seg = []
            else:
                back_seg.append(w_pts[i])
                if len(front_seg) >= 2:
                    fp = "M " + " L ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in front_seg)
                    lines.append(f'<path d="{fp}" fill="none" stroke="{wire_stroke}" stroke-width="0.65" stroke-opacity="0.48"/>')
                front_seg = []
        if len(back_seg) >= 2:
            bp = "M " + " L ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in back_seg)
            lines.append(f'<path d="{bp}" fill="none" stroke="{wire_stroke}" stroke-width="0.6" stroke-opacity="0.22"/>')
        if len(front_seg) >= 2:
            fp = "M " + " L ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in front_seg)
            lines.append(f'<path d="{fp}" fill="none" stroke="{wire_stroke}" stroke-width="0.65" stroke-opacity="0.48"/>')

    # Base curve gamma(s) on S^2
    g_pts, g_ds = s2["gamma_pts"], s2["gamma_depths"]
    g_color = NORD["nord8"] if is_dark else NORD["nord10"]
    n_g = len(g_pts)
    for is_front in (False, True):
        run: list[np.ndarray] = []
        for i in range(n_g + 1):
            pt = g_pts[i % n_g]
            d_val = g_ds[i % n_g]
            cond = (d_val >= 0) if is_front else (d_val < 0)
            if cond:
                run.append(pt)
            else:
                if len(run) >= 2:
                    gp = points_to_open_bezier(np.array(run), precision=1)
                    op = "0.90" if is_front else "0.28"
                    dash = "" if is_front else ' stroke-dasharray="2,1.8"'
                    lines.append(
                        f'<path d="{gp}" fill="none" stroke="{g_color}" stroke-width="1.15" stroke-opacity="{op}"{dash}/>'
                    )
                run = []
        if len(run) >= 2:
            gp = points_to_open_bezier(np.array(run), precision=1)
            op = "0.90" if is_front else "0.28"
            dash = "" if is_front else ' stroke-dasharray="2,1.8"'
            lines.append(
                f'<path d="{gp}" fill="none" stroke="{g_color}" stroke-width="1.15" stroke-opacity="{op}"{dash}/>'
            )

    # Tracer points s_A, s_B, s_C sorted by depth
    tracer_items = sorted(s2["tracers"].items(), key=lambda kv: kv[1][2])
    for key, (tx, ty, _) in tracer_items:
        if key == "A":
            fill_c = NORD["nord11"]
            lines.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="3.0" fill="{fill_c}" stroke="{canvas}" stroke-width="1.0"/>')
        elif key == "B":
            if is_dark:
                lines.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="3.0" fill="{NORD["nord14"]}" stroke="{canvas}" stroke-width="1.0"/>')
            else:
                lines.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="3.2" fill="{NORD["nord10"]}" stroke="{NORD["nord14"]}" stroke-width="1.1"/>')
        elif key == "C":
            if is_dark:
                lines.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="3.0" fill="{NORD["nord13"]}" stroke="{canvas}" stroke-width="1.0"/>')
            else:
                lines.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="3.1" fill="{NORD["nord12"]}" stroke="{canvas}" stroke-width="1.0"/>')
                lines.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="1.0" fill="{NORD["nord0"]}"/>')

    # Monospace math annotation S¹ → S³ → S²
    formula_d, _ = fonts.text_to_path(
        "S¹ → S³ → S²", x=100.0, y_baseline=186.0, size_px=12.5, style="mono"
    )
    lines.append(f'<path d="{formula_d}" fill="{sub_ink}"/>')

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _render_section_svg(section: dict, mode: str, fonts: FontRegistry) -> str:
    """Render narrow section divider plate (880 x 34) with 100% vector <path> text."""
    is_dark = mode == "dark"
    roman_ink = NORD["nord6"] if is_dark else NORD["nord0"]
    zh_ink = NORD["nord6"] if is_dark else NORD["nord0"]
    en_ink = NORD["nord4"] if is_dark else NORD["nord2"]
    rule_ink = NORD["nord2"] if is_dark else NORD["nord4"]

    lines: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 34" width="880" height="34">'
    ]

    # Aurora / Mineral marker dot or dual-semicircle badge at (10, 17), r=5
    bx, by, br = 10.0, 17.0, 5.0
    if is_dark:
        accent = section["accent_dark"]
        lines.append(f'<circle cx="{bx}" cy="{by}" r="{br}" fill="{accent}"/>')
    else:
        accent1 = section["accent_light"]
        accent2 = section.get("accent_light_secondary", "")
        if accent2:
            # Dual-semicircle badge (left half accent1, right half accent2)
            lines.append(
                f'<path d="M {bx},{by - br} A {br},{br} 0 0,0 {bx},{by + br} Z" fill="{accent1}"/>'
            )
            lines.append(
                f'<path d="M {bx},{by - br} A {br},{br} 0 0,1 {bx},{by + br} Z" fill="{accent2}"/>'
            )
        else:
            lines.append(f'<circle cx="{bx}" cy="{by}" r="{br}" fill="{accent1}"/>')

    # Roman numeral + middle dot + ZH title + EN title
    cur_x = 24.0
    roman_d, cur_x = fonts.text_to_path(
        section["roman"], x=cur_x, y_baseline=22.0, size_px=15.0, style="serif_sm"
    )
    dot1_d, cur_x = fonts.text_to_path(
        "·", x=cur_x + 6.0, y_baseline=22.0, size_px=13.0, style="mono"
    )
    zh_d, cur_x = fonts.text_to_path(
        section["title_zh"], x=cur_x + 6.0, y_baseline=22.0, size_px=14.5, style="serif_sm", tracking=0.3
    )
    en_d, cur_x = fonts.text_to_path(
        section["title_en"], x=cur_x + 12.0, y_baseline=22.0, size_px=12.0, style="mono"
    )

    lines.append(f'<path d="{roman_d}" fill="{roman_ink}"/>')
    lines.append(f'<path d="{dot1_d}" fill="{rule_ink}"/>')
    lines.append(f'<path d="{zh_d}" fill="{zh_ink}"/>')
    lines.append(f'<path d="{en_d}" fill="{en_ink}" fill-opacity="0.80"/>')

    # Copperplate right-extending hairline
    rule_start = cur_x + 14.0
    lines.append(
        f'<line x1="{rule_start:.1f}" y1="17" x2="876" y2="17" stroke="{rule_ink}" stroke-width="0.9"/>'
    )
    lines.append(
        f'<line x1="876" y1="14" x2="876" y2="20" stroke="{rule_ink}" stroke-width="0.9"/>'
    )

    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _render_readme(manifest: dict) -> str:
    """Render deterministic README.md from manifest.toml."""
    prof = manifest["profile"]
    sections = manifest["sections"]

    out: list[str] = [
        "<!-- Generated by scripts/build_profile.py from manifest.toml. Do not edit manually. -->",
        "",
        "<picture>",
        '  <source media="(prefers-color-scheme: dark)" srcset="./assets/banner-dark.svg">',
        '  <source media="(prefers-color-scheme: light)" srcset="./assets/banner-light.svg">',
        f'  <img alt="{prof["handle"]} — Hopf Fibration Archive Banner" src="./assets/banner-dark.svg" width="100%">',
        "</picture>",
        "",
        "<br>",
        "",
    ]

    for sec in sections:
        sid = sec["id"]
        alt_text = f'{sec["roman"]} · {sec["title_zh"]} {sec["title_en"]}'
        out.extend(
            [
                "<picture>",
                f'  <source media="(prefers-color-scheme: dark)" srcset="./assets/sec-{sid}-dark.svg">',
                f'  <source media="(prefers-color-scheme: light)" srcset="./assets/sec-{sid}-light.svg">',
                f'  <img alt="{alt_text}" src="./assets/sec-{sid}-dark.svg" width="100%">',
                "</picture>",
                "",
                "| 条目 | 介质与核心不变量 | 入口 |",
                "| :--- | :--- | :--- |",
            ]
        )
        for item in sec["items"]:
            name = item["name"]
            r_url = item["repo_url"]
            tag = item["tag"]
            summary = item["summary"]
            a_label = item.get("artifact_label", "").strip()
            a_url = item.get("artifact_url", "").strip()
            if a_label and a_url and a_url != r_url:
                entry = f"[{a_label}]({a_url}) · [源码]({r_url})"
            elif a_label and a_url:
                entry = f"[{a_label}]({a_url})"
            else:
                entry = f"[源码]({r_url})"
            out.append(f"| **[{name}]({r_url})** | `{tag}` — {summary} | {entry} |")
        out.append("")

    out.append(
        f'<sub>Colophon · 题头 Hopf 纤维丛投影与分栏铭牌由仓库内 <a href="./scripts/hopf_geometry.py"><code>scripts/hopf_geometry.py</code></a> 按 Nord 极夜/雪暴规范生成。</sub>'
    )
    out.append("")
    return "\n".join(out)


def _render_preview_html(manifest: dict) -> str:
    """Render local dual-theme GitHub Profile simulator HTML for Chrome verification."""
    prof = manifest["profile"]
    sections = manifest["sections"]

    def build_panel(mode: str) -> str:
        blocks: list[str] = [
            f'<img class="banner" src="./assets/banner-{mode}.svg" alt="Banner ({mode})">',
        ]
        for sec in sections:
            sid = sec["id"]
            blocks.append(f'<img class="sec-plate" src="./assets/sec-{sid}-{mode}.svg" alt="{html.escape(sec["title_en"])}">')
            rows = []
            for item in sec["items"]:
                name = html.escape(item["name"])
                r_url = html.escape(item["repo_url"])
                tag = html.escape(item["tag"])
                summary = html.escape(item["summary"])
                a_label = item.get("artifact_label", "").strip()
                a_url = item.get("artifact_url", "").strip()
                if a_label and a_url and a_url != item["repo_url"]:
                    entry_html = f'<a href="{html.escape(a_url)}">{html.escape(a_label)}</a> · <a href="{r_url}">源码</a>'
                elif a_label and a_url:
                    entry_html = f'<a href="{html.escape(a_url)}">{html.escape(a_label)}</a>'
                else:
                    entry_html = f'<a href="{r_url}">源码</a>'
                rows.append(
                    f"<tr>"
                    f"<td><strong><a href=\"{r_url}\">{name}</a></strong></td>"
                    f"<td><code>{tag}</code> — {summary}</td>"
                    f"<td class=\"entry\">{entry_html}</td>"
                    f"</tr>"
                )
            blocks.append(
                "<table><thead><tr><th>条目</th><th>介质与核心不变量</th><th>入口</th></tr></thead>"
                f"<tbody>{''.join(rows)}</tbody></table>"
            )
        blocks.append(
            '<p class="colophon">Colophon · 题头 Hopf 纤维丛投影与分栏铭牌由仓库内 '
            '<a href="./scripts/hopf_geometry.py"><code>scripts/hopf_geometry.py</code></a> '
            "按 Nord 极夜/雪暴规范生成。</p>"
        )
        return "\n".join(blocks)

    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8">
<title>{html.escape(prof["handle"])} (@{html.escape(prof["github_user"])}) — Nord Dual-Theme Preview</title>
<style>
  :root {{
    --gh-bg: #0d1117;
    --gh-card: #0d1117;
    --gh-border: #30363d;
    --gh-text: #e6edf3;
    --gh-muted: #8b949e;
    --gh-link: #88C0D0;
    --gh-code-bg: rgba(110, 118, 129, 0.25);
    --gh-row-alt: #161b22;
  }}
  html[data-theme="light"] {{
    --gh-bg: #ffffff;
    --gh-card: #ffffff;
    --gh-border: #d0d7de;
    --gh-text: #1f2328;
    --gh-muted: #656d76;
    --gh-link: #5E81AC;
    --gh-code-bg: rgba(175, 184, 193, 0.22);
    --gh-row-alt: #f6f8fa;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 28px 20px 44px;
    background: var(--gh-bg);
    color: var(--gh-text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
    font-size: 14px;
    line-height: 1.55;
  }}
  .toolbar {{
    max-width: 896px;
    margin: 0 auto 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
    color: var(--gh-muted);
  }}
  .toolbar button {{
    background: transparent;
    color: var(--gh-text);
    border: 1px solid var(--gh-border);
    border-radius: 6px;
    padding: 4px 10px;
    cursor: pointer;
    font-size: 12px;
  }}
  .readme-box {{
    max-width: 896px;
    margin: 0 auto;
    padding: 24px 28px;
    background: var(--gh-card);
    border: 1px solid var(--gh-border);
    border-radius: 6px;
  }}
  img.banner {{
    display: block;
    width: 100%;
    height: auto;
    margin-bottom: 18px;
  }}
  img.sec-plate {{
    display: block;
    width: 100%;
    height: auto;
    margin: 18px 0 8px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 10px;
    font-size: 13.5px;
  }}
  th, td {{
    border: 1px solid var(--gh-border);
    padding: 7px 12px;
    text-align: left;
    vertical-align: top;
  }}
  th {{
    font-weight: 600;
  }}
  tbody tr:nth-child(2n) {{
    background: var(--gh-row-alt);
  }}
  td.entry {{
    white-space: nowrap;
  }}
  a {{
    color: var(--gh-link);
    text-decoration: none;
  }}
  a:hover {{
    text-decoration: underline;
  }}
  code {{
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    padding: 2px 5px;
    border-radius: 4px;
    background: var(--gh-code-bg);
  }}
  .colophon {{
    margin: 18px 0 0;
    font-size: 12px;
    color: var(--gh-muted);
  }}
  .panel {{ display: none; }}
  html[data-theme="dark"] .panel-dark {{ display: block; }}
  html[data-theme="light"] .panel-light {{ display: block; }}
</style>
</head>
<body>
  <div class="toolbar">
    <span>{html.escape(prof["github_user"])} / README.md — Local Profile Simulator</span>
    <div>
      <button onclick="setTheme('dark')">Dark (Nord Polar Night)</button>
      <button onclick="setTheme('light')">Light (Nord Snow Storm)</button>
    </div>
  </div>
  <main class="readme-box">
    <div class="panel panel-dark">{build_panel("dark")}</div>
    <div class="panel panel-light">{build_panel("light")}</div>
  </main>
  <script>
    function setTheme(t) {{
      document.documentElement.setAttribute('data-theme', t);
    }}
    const params = new URLSearchParams(window.location.search);
    const t = params.get('theme');
    if (t === 'light' || t === 'dark') setTheme(t);
  </script>
</body>
</html>
"""


def main() -> None:
    manifest = tomllib.loads((ROOT / "manifest.toml").read_text(encoding="utf-8"))
    fonts = FontRegistry()

    for mode in ("dark", "light"):
        banner_svg = _render_banner_svg(mode, manifest, fonts)
        out_banner = ASSETS / f"banner-{mode}.svg"
        out_banner.write_text(banner_svg, encoding="utf-8")
        print(f"Wrote {out_banner.relative_to(ROOT)} ({len(banner_svg.encode('utf-8'))} bytes)")

        for sec in manifest["sections"]:
            sec_svg = _render_section_svg(sec, mode, fonts)
            out_sec = ASSETS / f"sec-{sec['id']}-{mode}.svg"
            out_sec.write_text(sec_svg, encoding="utf-8")
            print(f"Wrote {out_sec.relative_to(ROOT)} ({len(sec_svg.encode('utf-8'))} bytes)")

    readme_md = _render_readme(manifest)
    (ROOT / "README.md").write_text(readme_md, encoding="utf-8")
    print("Wrote README.md")

    preview_html = _render_preview_html(manifest)
    (ROOT / "preview.html").write_text(preview_html, encoding="utf-8")
    print("Wrote preview.html")


if __name__ == "__main__":
    main()
