"""Pure numerical geometry engine for Hopf fibration stereographic projection.

Implements Section 3.1 of the Nord Profile specification:
- Base curve gamma(s) on S^2: theta(s) = 0.44*pi + 0.14*pi*cos(3s), phi(s) = s
- Hopf fiber circles in S^3 subset C^2
- R^4 w_4-offset rotation (psi = 0.22) and stereographic projection to R^3
- Orthographic camera tilt (alpha = -58 deg around X, beta = 26 deg around Z)
- Smooth closed cubic Bezier paths for 40 ambient Frost fibers
- Exact 2D crossing detection, topological arc ordering, and Over/Under halo
  windows for the 3 linked Aurora characteristic fibers (s_A, s_B, s_C)
- Orthographic 44px-diameter S^2 wireframe sphere inset with gamma(s) and tracers
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np


# Characteristic fiber base parameters (pairwise linking number = 1)
S_CHARACTERISTIC: dict[str, float] = {
    "A": 0.18 * math.pi,
    "B": 0.85 * math.pi,
    "C": 1.52 * math.pi,
}


@dataclass(frozen=True)
class ProjectedFiber:
    """Projected 2D points and depth values for a closed Hopf fiber circle."""

    key: str
    s: float
    points: np.ndarray  # shape (N, 2) in screen coordinates
    depths: np.ndarray  # shape (N,) camera depth (larger = closer to viewer)
    mean_depth: float


@dataclass(frozen=True)
class AuroraArc:
    """A continuous sub-arc of an Aurora characteristic fiber in painter's order."""

    key: str
    points: np.ndarray        # shape (M, 2)
    halo_spans: list[np.ndarray]  # list of (K, 2) sub-polylines needing 5.6px halo
    closed: bool


def _camera_project(
    X: np.ndarray,
    Y: np.ndarray,
    Z: np.ndarray,
    alpha_deg: float = -58.0,
    beta_deg: float = 26.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Apply R_z(beta) then R_x(alpha) and return (u, v_screen_up, depth)."""
    a = math.radians(alpha_deg)
    b = math.radians(beta_deg)
    cb, sb = math.cos(b), math.sin(b)
    ca, sa = math.cos(a), math.sin(a)

    x1 = X * cb - Y * sb
    y1 = X * sb + Y * cb
    z1 = Z

    u = x1
    # Negate screen Y so +Z points upward in SVG coordinates
    v = -(y1 * ca - z1 * sa)
    d = y1 * sa + z1 * ca
    return u, v, d


def hopf_fiber_raw(
    s: float,
    n_pts: int = 160,
    psi: float = 0.22,
    alpha_deg: float = -58.0,
    beta_deg: float = 26.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute unscaled (u, v, depth) for a single Hopf fiber at base parameter s."""
    theta = 0.44 * math.pi + 0.14 * math.pi * math.cos(3.0 * s)
    phi = s
    t = np.linspace(0.0, 2.0 * math.pi, n_pts, endpoint=False)

    ct = math.cos(theta / 2.0)
    st = math.sin(theta / 2.0)

    x1 = ct * np.cos(t)
    x2 = ct * np.sin(t)
    x3 = st * np.cos(t + phi)
    x4 = st * np.sin(t + phi)

    # Slight R^4 rotation involving w_4 (x3, x4 plane) by offset angle psi = 0.22
    cp, sp = math.cos(psi), math.sin(psi)
    x3_rot = x3 * cp - x4 * sp
    x4_rot = x3 * sp + x4 * cp

    denom = 1.18 - x4_rot
    X = x1 / denom
    Y = x2 / denom
    Z = x3_rot / denom

    return _camera_project(X, Y, Z, alpha_deg=alpha_deg, beta_deg=beta_deg)


def points_to_closed_bezier(pts: np.ndarray, precision: int = 1) -> str:
    """Convert a closed cyclic Nx2 polyline into a smooth SVG cubic Bezier path."""
    n = len(pts)
    fmt = f"{{:.{precision}f}}"
    parts = [f"M {fmt.format(pts[0, 0])},{fmt.format(pts[0, 1])}"]
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        c1 = p1 + (p2 - p0) / 6.0
        c2 = p2 - (p3 - p1) / 6.0
        parts.append(
            f"C {fmt.format(c1[0])},{fmt.format(c1[1])} "
            f"{fmt.format(c2[0])},{fmt.format(c2[1])} "
            f"{fmt.format(p2[0])},{fmt.format(p2[1])}"
        )
    parts.append("Z")
    return " ".join(parts)


def points_to_open_bezier(pts: np.ndarray, precision: int = 1) -> str:
    """Convert an open Mx2 polyline into a smooth SVG cubic Bezier path."""
    n = len(pts)
    if n < 2:
        return ""
    fmt = f"{{:.{precision}f}}"
    if n == 2:
        return (
            f"M {fmt.format(pts[0, 0])},{fmt.format(pts[0, 1])} "
            f"L {fmt.format(pts[1, 0])},{fmt.format(pts[1, 1])}"
        )
    parts = [f"M {fmt.format(pts[0, 0])},{fmt.format(pts[0, 1])}"]
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[0] - (pts[1] - pts[0])
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[-1] + (pts[-1] - pts[-2])
        c1 = p1 + (p2 - p0) / 6.0
        c2 = p2 - (p3 - p1) / 6.0
        parts.append(
            f"C {fmt.format(c1[0])},{fmt.format(c1[1])} "
            f"{fmt.format(c2[0])},{fmt.format(c2[1])} "
            f"{fmt.format(p2[0])},{fmt.format(p2[1])}"
        )
    return " ".join(parts)


def offset_polyline(pts: np.ndarray, offset_px: float, closed: bool = False) -> np.ndarray:
    """Compute a parallel companion polyline shifted along the 2D unit left-normal."""
    n = len(pts)
    tangents = np.zeros_like(pts)
    if closed:
        for i in range(n):
            tangents[i] = pts[(i + 1) % n] - pts[(i - 1) % n]
    else:
        tangents[0] = pts[1] - pts[0]
        tangents[-1] = pts[-1] - pts[-2]
        if n > 2:
            tangents[1:-1] = pts[2:] - pts[:-2]

    norms = np.linalg.norm(tangents, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-6)
    t_unit = tangents / norms
    normals = np.stack([-t_unit[:, 1], t_unit[:, 0]], axis=1)
    return pts + offset_px * normals


def _segments_intersect(
    p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, p4: np.ndarray
) -> tuple[bool, float, float]:
    """Return (intersects, t_on_12, u_on_34) for 2D segments p1-p2 and p3-p4."""
    d1 = p2 - p1
    d2 = p4 - p3
    denom = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(denom) < 1e-9:
        return False, 0.0, 0.0
    dp = p3 - p1
    t = (dp[0] * d2[1] - dp[1] * d2[0]) / denom
    u = (dp[0] * d1[1] - dp[1] * d1[0]) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return True, float(t), float(u)
    return False, 0.0, 0.0


def build_hopf_torus_data(
    cx: float = 640.0,
    cy: float = 126.0,
    target_height: float = 204.0,
    n_ambient: int = 40,
    n_pts_ambient: int = 48,
    n_pts_aurora: int = 160,
) -> tuple[list[ProjectedFiber], list[AuroraArc], dict[str, float]]:
    """Generate ambient Frost fibers (far-to-near) and Aurora arcs with crossing halos.

    Returns:
        ambient_fibers: sorted list of ProjectedFiber (far to near)
        aurora_arcs: depth-ordered list of AuroraArc with over-crossing halo spans
        bounds: dict with xmin, xmax, ymin, ymax of the projected torus
    """
    raw_ambient: list[tuple[str, float, np.ndarray, np.ndarray, np.ndarray]] = []
    for k in range(n_ambient):
        s = 2.0 * math.pi * k / n_ambient
        u, v, d = hopf_fiber_raw(s, n_pts=n_pts_ambient)
        raw_ambient.append((f"F{k}", s, u, v, d))

    raw_aurora: dict[str, tuple[float, np.ndarray, np.ndarray, np.ndarray]] = {}
    for key, s in S_CHARACTERISTIC.items():
        u, v, d = hopf_fiber_raw(s, n_pts=n_pts_aurora)
        raw_aurora[key] = (s, u, v, d)

    all_u = np.concatenate(
        [r[2] for r in raw_ambient] + [r[1] for r in raw_aurora.values()]
    )
    all_v = np.concatenate(
        [r[3] for r in raw_ambient] + [r[2] for r in raw_aurora.values()]
    )

    u_min, u_max = float(all_u.min()), float(all_u.max())
    v_min, v_max = float(all_v.min()), float(all_v.max())
    u_mid = 0.5 * (u_min + u_max)
    v_mid = 0.5 * (v_min + v_max)
    scale = target_height / (v_max - v_min)

    def to_screen(u: np.ndarray, v: np.ndarray) -> np.ndarray:
        return np.stack([cx + (u - u_mid) * scale, cy + (v - v_mid) * scale], axis=1)

    ambient_fibers: list[ProjectedFiber] = []
    for key, s, u, v, d in raw_ambient:
        pts = to_screen(u, v)
        ambient_fibers.append(
            ProjectedFiber(key=key, s=s, points=pts, depths=d, mean_depth=float(d.mean()))
        )
    ambient_fibers.sort(key=lambda f: f.mean_depth)

    # Project Aurora curves
    aurora_pts: dict[str, np.ndarray] = {}
    aurora_depths: dict[str, np.ndarray] = {}
    for key, (s, u, v, d) in raw_aurora.items():
        aurora_pts[key] = to_screen(u, v)
        aurora_depths[key] = d

    # Detect all 2D crossings among the 3 Aurora curves
    keys = ["A", "B", "C"]
    # crossings_under[key] = sorted list of segment indices where `key` passes UNDER
    under_splits: dict[str, list[int]] = {k: [] for k in keys}
    # over_windows[key] = list of (center_idx, half_win) where `key` passes OVER
    over_crossings: dict[str, list[int]] = {k: [] for k in keys}

    # Precompute segment bounding boxes for fast pairwise check
    segs: list[tuple[str, int, np.ndarray, np.ndarray, float]] = []
    for k in keys:
        pts = aurora_pts[k]
        ds = aurora_depths[k]
        n = len(pts)
        for i in range(n):
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            d_mid = 0.5 * (ds[i] + ds[(i + 1) % n])
            segs.append((k, i, p1, p2, float(d_mid)))

    # Record directional crossing constraints for arc sorting
    raw_crossings: list[tuple[str, int, str, int]] = []  # (over_k, over_i, under_k, under_i)
    n_segs = len(segs)
    for idx1 in range(n_segs):
        k1, i1, p1, p2, d1 = segs[idx1]
        min1x, max1x = min(p1[0], p2[0]), max(p1[0], p2[0])
        min1y, max1y = min(p1[1], p2[1]), max(p1[1], p2[1])
        for idx2 in range(idx1 + 1, n_segs):
            k2, i2, p3, p4, d2 = segs[idx2]
            if k1 == k2:
                diff = abs(i1 - i2)
                if diff <= 6 or diff >= n_pts_aurora - 6:
                    continue
            if max1x < min(p3[0], p4[0]) or min1x > max(p3[0], p4[0]):
                continue
            if max1y < min(p3[1], p4[1]) or min1y > max(p3[1], p4[1]):
                continue
            hit, t_val, u_val = _segments_intersect(p1, p2, p3, p4)
            if not hit:
                continue
            # Interpolate exact depth at intersection point
            ds1 = aurora_depths[k1]
            ds2 = aurora_depths[k2]
            z1 = (1.0 - t_val) * ds1[i1] + t_val * ds1[(i1 + 1) % n_pts_aurora]
            z2 = (1.0 - u_val) * ds2[i2] + u_val * ds2[(i2 + 1) % n_pts_aurora]
            if z1 >= z2:
                raw_crossings.append((k1, i1, k2, i2))
                over_crossings[k1].append(i1)
                under_splits[k2].append(i2)
            else:
                raw_crossings.append((k2, i2, k1, i1))
                over_crossings[k2].append(i2)
                under_splits[k1].append(i1)

    # Build clean continuous arcs split at under-crossings (deduplicating nearby splits)
    arc_records: list[dict] = []
    for k in keys:
        pts = aurora_pts[k]
        ds = aurora_depths[k]
        n = len(pts)
        raw_splits = sorted(set(under_splits[k]))
        # Merge adjacent split indices within 3 segments
        splits: list[int] = []
        for sp in raw_splits:
            if not splits or sp - splits[-1] > 3:
                splits.append(sp)
        if len(splits) > 1 and (n - splits[-1] + splits[0]) <= 3:
            splits.pop()

        if not splits:
            # Closed loop with no under-crossings
            arc_records.append(
                {
                    "key": k,
                    "indices": list(range(n)),
                    "closed": True,
                    "pts": pts,
                    "mean_depth": float(ds.mean()),
                    "over_indices": sorted(set(over_crossings[k])),
                }
            )
        else:
            m = len(splits)
            for s_idx in range(m):
                start = splits[s_idx]
                end = splits[(s_idx + 1) % m]
                if end > start:
                    idxs = list(range(start, end + 1))
                else:
                    idxs = list(range(start, n)) + list(range(0, end + 1))
                arc_pts = pts[idxs]
                arc_ds = ds[idxs]
                idx_set = set(idxs[:-1])
                local_overs = [oi for oi in over_crossings[k] if oi in idx_set]
                arc_records.append(
                    {
                        "key": k,
                        "indices": idxs,
                        "closed": False,
                        "pts": arc_pts,
                        "mean_depth": float(arc_ds.mean()),
                        "over_indices": sorted(set(local_overs)),
                    }
                )

    # Topological sort of arcs using crossing constraints (under_arc -> over_arc)
    num_arcs = len(arc_records)
    edges: dict[int, set[int]] = {i: set() for i in range(num_arcs)}
    indeg: dict[int, int] = {i: 0 for i in range(num_arcs)}

    def find_arc_containing(key: str, seg_idx: int) -> int:
        # Match the arc that actually draws segment (seg_idx -> seg_idx+1)
        for a_i, rec in enumerate(arc_records):
            if rec["key"] != key:
                continue
            idxs = rec["indices"]
            if rec["closed"]:
                return a_i
            if seg_idx in idxs[:-1]:
                return a_i
        return -1

    for ok, oi, uk, ui in raw_crossings:
        over_a = find_arc_containing(ok, oi)
        under_a = find_arc_containing(uk, ui)
        if over_a != -1 and under_a != -1 and over_a != under_a:
            if over_a not in edges[under_a]:
                edges[under_a].add(over_a)
                indeg[over_a] += 1

    # Kahn's algorithm prioritizing deeper arcs first
    ordered_indices: list[int] = []
    ready = sorted([i for i in range(num_arcs) if indeg[i] == 0], key=lambda i: arc_records[i]["mean_depth"])
    visited: set[int] = set()
    while ready:
        curr = ready.pop(0)
        ordered_indices.append(curr)
        visited.add(curr)
        for nxt in edges[curr]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
                ready.sort(key=lambda i: arc_records[i]["mean_depth"])

    # Fallback in case of any topological cycle: append remaining sorted by depth
    if len(ordered_indices) < num_arcs:
        rem = sorted(
            [i for i in range(num_arcs) if i not in visited],
            key=lambda i: arc_records[i]["mean_depth"],
        )
        ordered_indices.extend(rem)

    # Extract concise halo sub-polylines (+/- 4 segments around each over-crossing)
    aurora_arcs: list[AuroraArc] = []
    half_win = 4
    for a_i in ordered_indices:
        rec = arc_records[a_i]
        k = rec["key"]
        full_pts = aurora_pts[k]
        n = len(full_pts)
        idxs = rec["indices"]
        pos_map = {seg_i: p for p, seg_i in enumerate(idxs)}

        # Merge overlapping halo intervals in local arc coordinates
        intervals: list[tuple[int, int]] = []
        for oi in rec["over_indices"]:
            if oi not in pos_map:
                continue
            c = pos_map[oi]
            lo = max(0, c - half_win)
            hi = min(len(idxs) - 1, c + half_win + 1)
            intervals.append((lo, hi))

        intervals.sort()
        merged: list[tuple[int, int]] = []
        for lo, hi in intervals:
            if not merged or lo > merged[-1][1] + 1:
                merged.append((lo, hi))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))

        halo_spans: list[np.ndarray] = []
        for lo, hi in merged:
            span_idxs = idxs[lo : hi + 1]
            if len(span_idxs) >= 2:
                halo_spans.append(full_pts[span_idxs])

        # For closed loop, ensure full wrap; for open arc, keep endpoints
        pts_out = rec["pts"]
        aurora_arcs.append(
            AuroraArc(
                key=k,
                points=pts_out,
                halo_spans=halo_spans,
                closed=rec["closed"],
            )
        )

    bounds = {
        "xmin": float(cx + (u_min - u_mid) * scale),
        "xmax": float(cx + (u_max - u_mid) * scale),
        "ymin": float(cy + (v_min - v_mid) * scale),
        "ymax": float(cy + (v_max - v_mid) * scale),
    }
    return ambient_fibers, aurora_arcs, bounds


def build_s2_inset_data(
    cx: float = 64.0,
    cy: float = 186.0,
    radius: float = 22.0,
    alpha_deg: float = -58.0,
    beta_deg: float = 26.0,
) -> dict:
    """Compute orthographic S^2 wireframe sphere, base curve gamma(s), and tracers.

    Radius 22.0 yields exact 44px diameter per Section 3.2.
    """
    def project_s2(theta: np.ndarray, phi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        X = np.sin(theta) * np.cos(phi)
        Y = np.sin(theta) * np.sin(phi)
        Z = np.cos(theta)
        u, v, d = _camera_project(X, Y, Z, alpha_deg=alpha_deg, beta_deg=beta_deg)
        pts = np.stack([cx + u * radius, cy + v * radius], axis=1)
        return pts, d

    # Wireframe meridians and equator
    wire_curves: list[tuple[np.ndarray, np.ndarray]] = []
    ts = np.linspace(0.0, 2.0 * math.pi, 96, endpoint=True)
    # Equator: theta = pi/2
    wire_curves.append(project_s2(np.full_like(ts, math.pi / 2.0), ts))
    # Two orthogonal meridians: phi = 0 and phi = pi/2
    thetas_mer = np.linspace(0.0, math.pi, 48, endpoint=True)
    for phi_val in (0.0, math.pi, math.pi / 2.0, 1.5 * math.pi):
        wire_curves.append(project_s2(thetas_mer, np.full_like(thetas_mer, phi_val)))

    # Base curve gamma(s) on S^2
    s_grid = np.linspace(0.0, 2.0 * math.pi, 144, endpoint=False)
    th_grid = 0.44 * math.pi + 0.14 * math.pi * np.cos(3.0 * s_grid)
    gamma_pts, gamma_depths = project_s2(th_grid, s_grid)

    # Characteristic tracer points s_A, s_B, s_C
    tracers: dict[str, tuple[float, float, float]] = {}
    for key, s_val in S_CHARACTERISTIC.items():
        th_val = 0.44 * math.pi + 0.14 * math.pi * math.cos(3.0 * s_val)
        p_arr, d_arr = project_s2(np.array([th_val]), np.array([s_val]))
        tracers[key] = (float(p_arr[0, 0]), float(p_arr[0, 1]), float(d_arr[0]))

    return {
        "cx": cx,
        "cy": cy,
        "radius": radius,
        "wire_curves": wire_curves,
        "gamma_pts": gamma_pts,
        "gamma_depths": gamma_depths,
        "tracers": tracers,
    }


if __name__ == "__main__":
    amb, arcs, b = build_hopf_torus_data()
    print(f"Ambient fibers: {len(amb)}, Aurora arcs: {len(arcs)}, bounds: {b}")
    for idx, arc in enumerate(arcs):
        print(f"  Arc {idx}: fiber={arc.key}, pts={len(arc.points)}, halos={len(arc.halo_spans)}, closed={arc.closed}")
