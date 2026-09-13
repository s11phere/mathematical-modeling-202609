"""Adaptive continuous directional layout certificate and candidate layouts.

Every refined square is certified by the same exact angular-interval union
and strict spatial margin as DirectionalCertificate. Refinement changes the
proof's resolution; it does not replace the continuous square by samples.
"""
from __future__ import annotations
import math
import numpy as np
from p4_certificate import DirectionalCertificate, ring_layout


def adaptive_complete(points, initial_step_m=40., min_step_m=.625, *, detail=False):
    cert=DirectionalCertificate(initial_step_m,48)
    counts=[]
    while True:
        covered=cert.all_orientation_cells(points)
        left=cert.centers[~covered]
        counts.append((cert.cell_side_m,len(cert.centers),len(left)))
        if not len(left):
            return (True,counts) if detail else True
        # Find an actual unsupported interior point before refining large
        # blind regions. This is only an early rejection, never acceptance.
        centers,rho=cert.centers,cert.rho
        cert.centers=left[np.sum(left*left,axis=1)<cert.arena_radius_m**2]
        cert.rho=0.
        point_gap=not np.all(cert.all_orientation_cells(points))
        cert.centers,cert.rho=centers,rho
        if point_gap:
            return (False,counts) if detail else False
        if cert.cell_side_m/2 < min_step_m-1e-12:
            return (False,counts) if detail else False
        side=cert.cell_side_m/2
        offsets=np.array([[-1.,-1.],[-1.,1.],[1.,-1.],[1.,1.]])*side/2
        centers=(left[:,None,:]+offsets[None,:,:]).reshape(-1,2)
        closest=np.maximum(np.abs(centers)-side/2,0)
        cert.centers=centers[np.sum(closest*closest,axis=1)<=cert.arena_radius_m**2]
        cert.cell_side_m=side
        cert.rho=side/math.sqrt(2)


def compact_layout():
    """22 points; 17.70 km static open tour; certified by 5 m refinement."""
    return ring_layout(((980.,7,0.),(1856.,14,0.)))


def compact21_layout():
    """21 points; 17.91 km tour; certificate refines to 2.5 m."""
    return ring_layout(((998.,8,0.),(1867.,12,15.)))


if __name__=='__main__':
    from p4_grid import tour_len
    p=compact_layout()
    print(adaptive_complete(p,detail=True))
    print(tour_len(p)[0])
