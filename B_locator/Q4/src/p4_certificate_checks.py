"""Independent geometry checks; run directly with Python."""
from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np

from p4_certificate import DirectionalCertificate, certify_channels, strict_layout
from p4_grid import triangular_lattice


def main():
    cert = DirectionalCertificate(step_m=80, n_dir=24)
    # All disk points belong to retained cells, including boundary cell centres
    # outside the circle.  Check dense boundary angles and cell indexing.
    side = cert.cell_side_m
    retained = {tuple(np.round(p, 7)) for p in cert.centers}
    for a in np.linspace(0, 2 * math.pi, 20001):
        p = 1800 * np.array([math.cos(a), math.sin(a)])
        i = np.minimum(np.floor((p + 1800) / side), round(3600 / side) - 1)
        center = -1800 + (i + 0.5) * side
        assert tuple(np.round(center, 7)) in retained

    # A returned mask must hold for each square corner and the centre/endpoints
    # of every certified angular interval, even outside the arena.
    rng = np.random.default_rng(7712)
    for _ in range(16):
        q = rng.uniform(-2400, 2400, 2)
        mask = cert.station_mask(q)
        ii, jj = np.nonzero(mask)
        if len(ii) > 200:
            take = rng.choice(len(ii), 200, replace=False)
            ii, jj = ii[take], jj[take]
        for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            p = cert.centers[ii] + np.array([dx, dy]) * side / 2
            vec = q - p
            assert np.all(np.hypot(vec[:, 0], vec[:, 1]) < 1000 + 1e-8)
            for offset in (-cert.angle_half_width, 0, cert.angle_half_width):
                aa = cert.angles[jj] + offset
                assert np.all(vec[:, 0] * np.cos(aa) + vec[:, 1] * np.sin(aa) > -1e-8)

    # Inward AND outward radial samples do not cover an arbitrary orientation.
    p = np.array([1000.0, 0.0])
    q = np.array([[950.0, 500.0], [1050.0, 500.0]])
    radial = (q - p) @ p
    assert min(radial) < 0 < max(radial)
    assert np.all((q - p) @ np.array([0.0, -1.0]) < 0)
    assert not cert.summarize(cert.mask_for_points(q)).complete

    # a/sqrt(3) is a nearest-vertex covering radius, not the farthest-vertex
    # distance.  The commonly stated a=1700 directed triangle guarantee fails.
    p = np.array([1.0, 1.0])
    vertices = np.array([[0, 0], [1700, 0], [850, 850 * math.sqrt(3)]])
    visible = ((vertices - p) @ np.array([1.0, 0.0])) >= 0
    assert not np.any(visible & (np.linalg.norm(vertices - p, axis=1) <= 1000))

    # A dense truncated lattice really certifies the whole continuous disk.
    dense = triangular_lattice(700, 2800)
    assert cert.summarize(cert.mask_for_points(dense)).complete

    # near/direction cannot be used as absence evidence, nor can a heard
    # pending channel be allowed to pass the completion check.
    log = [(x, y, 0.0, "no_signal") for x, y in dense]
    assert cert.summarize(cert.from_log(log)).complete
    assert not np.any(cert.from_log([(0, 0, 0, "near"), (20, 0, 0, "direction")]))
    rec = SimpleNamespace(cleared=False, meas_log=log + [(0, 0, 0, "near")])
    assert not certify_channels({1: rec}, certificate=cert)[1]["complete"]
    rec.cleared = True
    assert certify_channels({1: rec}, certificate=cert)[1]["complete"]
    assert cert.summarize(cert.empty()).excluded_fraction_lower_bound == 0
    assert cert.summarize(cert.mask_for_points(dense)).excluded_fraction_lower_bound == 1

    # Circular interval union must reject a single semicircle and accept the
    # certified 25-stop layout.  In particular empty interval placeholders
    # cannot artificially close a missing interval at 2*pi.
    assert not np.any(cert.all_orientation_cells([(0, 0)]))
    fine = DirectionalCertificate(step_m=20, n_dir=96)
    strict = strict_layout()
    assert fine.summarize(fine.mask_for_points(strict)).complete
    assert fine.continuous_complete(strict)
    assert not fine.continuous_complete(strict[:13])

    # All-angle certification also covers every cell corner for arbitrarily
    # fine heading samples, using the actual nearby stations.
    proved = cert.all_orientation_cells(dense)
    ids = rng.choice(np.flatnonzero(proved), 150, replace=False)
    headings = np.arange(721) * (2 * math.pi / 721)
    directions = np.column_stack((np.cos(headings), np.sin(headings)))
    stations = np.asarray(dense)
    for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        for i in ids:
            p = cert.centers[i] + np.array([dx, dy]) * side / 2
            delta = stations - p
            audible = (np.linalg.norm(delta, axis=1)[:, None] <= 1000) & (delta @ directions.T >= -1e-8)
            assert audible.any(axis=0).all()
    print("10 geometry/absence checks passed")


if __name__ == "__main__":
    main()
