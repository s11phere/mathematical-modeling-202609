"""Offline static-layout exploration, using only certified geometry."""
from __future__ import annotations

import json
import math
import time

import numpy as np

from p4_certificate import DirectionalCertificate, ring_layout
from p4_grid import tour_len, triangular_lattice


def prune_layout(cert, points):
    points = list(points)
    masks = np.asarray([cert.station_mask(p) for p in points])
    counts = masks.sum(axis=0)
    if np.any(counts == 0):
        return points
    keep = list(range(len(points)))
    while True:
        choices = []
        base_len = tour_len([points[i] for i in keep])[0]
        for i in keep:
            if i == 0 or np.any(masks[i] & (counts == 1)):
                continue
            length = tour_len([points[j] for j in keep if j != i])[0]
            choices.append((length - base_len, i))
        if not choices:
            break
        _, i = min(choices)
        counts -= masks[i]
        keep.remove(i)
    return [points[i] for i in keep]


def main():
    start = time.perf_counter()
    cert = DirectionalCertificate(step_m=40, n_dir=48)
    rows = []
    for a in (850, 900):
        for r in (1925, 1950, 1975, 2000):
            points = triangular_lattice(a, 1800) + ring_layout(((r, 12),), False)
            if cert.summarize(cert.mask_for_points(points)).complete:
                points = prune_layout(cert, points)
                length, order = tour_len(points)
                rows.append({"n": len(points), "length_m": length, "a": a, "r": r,
                             "points": points, "order": order})
    for a, ni in ((850, 8), (900, 8), (1000, 8), (900, 9), (1000, 9), (1000, 10)):
        for r in (1900, 1950, 2000):
            for no in (12, 14, 16, 18):
                for off in (0, 90 / no, 180 / no):
                    points = ring_layout(((a, ni, 0), (r, no, off)))
                    if cert.summarize(cert.mask_for_points(points)).complete:
                        points = prune_layout(cert, points)
                        length, order = tour_len(points)
                        rows.append({"n": len(points), "length_m": length, "rings": (a, ni, r, no, off),
                                     "points": points, "order": order})
    rows.sort(key=lambda row: row["length_m"])
    print(json.dumps({"seconds": time.perf_counter() - start, "best": rows[:8]}, indent=2))


if __name__ == "__main__":
    main()
