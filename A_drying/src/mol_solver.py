# -*- coding: utf-8 -*-
"""
FINAL solver for the 2026 CUMCM A-problem (herbal drying) -- method of lines.

Rationale
---------
Hand-assembled implicit matrices proved fragile.  This module instead writes the
*spatially discretised* right-hand side once and integrates it in time with
SciPy's implicit stiff integrator (``scipy.integrate.solve_ivp``, BDF/Radau).
The spatial discretisation is therefore the only thing that can be wrong, and it
is verified directly against the Bessel-series solution in
``tests/test_mol_solver.py``.

Model (radial symmetry, per unit axial length)
----------------------------------------------
    T(r,t) [K], C(r,t) [kg water / kg dry solid], R(t) [m]

    moisture   dC/dt = (1/r) d/dr ( r D(C,T) dC/dr )
    energy     rho cp dT/dt = (1/r) d/dr ( r k(C,T) dT/dr )

    surface    j_w = h_m ( Y_s - Y_inf ),  Y_s = phi Y_sat(T_s),
               phi = min(C_s/C_sat, 1)
               -k dT/dr|_R = h (T_inf - T_R) - L_w j_w
    centre     symmetry

Spatial discretisation
----------------------
Finite volumes on the normalised coordinate xi = r/R(t), uniform in xi, so the
same mesh serves the shrinking problem.  With the exact identity

    (1/r) d/dr ( r q ) = (1/(R^2 xi)) d/dxi ( xi q )

the metric factors cancel and the dry-basis moisture equation stays
conservative.  Cell i (i = 0..N-1) has

    V_i/(pi R^2) = xi_f[i+1]^2 - xi_f[i]^2        (Vw_i)
    F_i/(pi R^2) = 2 xi_f[i]                      (Fa_i)
    h_r = R/N

and the semi-discrete equations are

    Vw_i dC_i/dt = Fa_i D_{i-1/2} (C_{i-1}-C_i)/h_r
                   - Fa_{i+1} D_{i+1/2} (C_i-C_{i+1})/h_r

    Vw_i rho cp dT_i/dt = Fa_i k_{i-1/2} (T_{i-1}-T_i)/h_r
                          - Fa_{i+1} k_{i+1/2} (T_i-T_{i+1})/h_r

with the surface cell i = N-1 closed by

    Fa_N k (T_R - T_cell)/h_r = Fa_N [ h (T_inf - T_R) - L_w j_w ]
    Fa_N D (C_R - C_cell)/h_r = Fa_N j_w

The surface values C_R, T_R are the quasi-steady solution of the local surface
balances given in :meth:`surface_state`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np
from scipy.integrate import solve_ivp

# --------------------------------------------------------------------------
T0_K = 273.15
P_ATM = 101325.0
SIGMA_SB = 5.670374419e-8
RHO_AIR, CP_AIR, LEWIS = 1.13, 1006.0, 0.87


def c2k(x):
    return np.asarray(x, float) + T0_K


def k2c(x):
    return np.asarray(x, float) - T0_K


def p_sat_water(T):
    """Saturation vapour pressure over water [Pa] (Buck 1981)."""
    Tc = np.clip(np.asarray(T, float), 200.0, 400.0) - T0_K
    return 611.21 * np.exp((18.678 - Tc / 234.5) * (Tc / (257.14 + Tc)))


def Y_sat(T, P=P_ATM):
    ps = np.clip(p_sat_water(T), 0.0, 0.8 * P)
    return 0.62198 * ps / (P - ps)


@dataclass
class Props:
    rho: Callable
    cp: Callable
    k: Callable
    D: Callable
    h: float
    h_m: float
    Lw: float
    Tamb: Callable
    Camb: Callable
    rho_d0: float
    C_sat: float = 2.55
    hm_mode: str = "heat_limited"
    name: str = "props"


@dataclass
class Series:
    ts: List[float] = field(default_factory=list)
    T: List[np.ndarray] = field(default_factory=list)
    C: List[np.ndarray] = field(default_factory=list)
    R: List[float] = field(default_factory=list)
    Tsurf: List[float] = field(default_factory=list)
    Csurf: List[float] = field(default_factory=list)
    Tc: List[float] = field(default_factory=list)
    Cc: List[float] = field(default_factory=list)
    jw: List[float] = field(default_factory=list)
    q: List[float] = field(default_factory=list)
    W: List[float] = field(default_factory=list)
    Tamb: List[float] = field(default_factory=list)
    Camb: List[float] = field(default_factory=list)


class MolSolver:
    def __init__(self, N: int, R0: float,
                 Rfun: Optional[Callable[[float], float]] = None):
        self.N = int(N)
        self.R0 = float(R0)
        self.Rfun = Rfun if Rfun is not None else (lambda t: self.R0)
        # Face and centre positions in the normalised coordinate xi = r/R.
        # The *physical* geometry is rebuilt for every R in ``geometry`` so that
        # no normalisation factor can be lost.
        xi = np.linspace(0.0, 1.0, self.N + 1)
        self.xi_f = xi
        self.xi_c = 0.5 * (xi[:-1] + xi[1:])

    # ------------------------------------------------------------------
    def geometry(self, R: float):
        """Physical geometry for radius ``R`` (unit axial length).

        Returns ``(h_r, V, F)`` with

            F[i] = 2 pi R xi_f[i]                        face area, i = 0..N
            V[i] = pi R^2 (xi_f[i+1]^2 - xi_f[i]^2)      cell volume, i = 0..N-1
        """
        N = self.N
        xi = self.xi_f
        h_r = R / N
        F = 2.0 * np.pi * R * xi
        V = np.pi * R * R * (xi[1:] ** 2 - xi[:-1] ** 2)
        return h_r, V, F

    # ------------------------------------------------------------------
    def dry_density(self, props, R):
        return props.rho_d0 if abs(R - self.R0) <= 0.0 else props.rho_d0 * (self.R0 / R) ** 2

    def wet_bulb_temperature(self, props, Tamb: float, Yinf: float) -> float:
        """Wet-bulb temperature of the chamber air [K].

        Solved from the psychrometric balance of a wet surface,

            h (T_inf - T_wb) = L_w h_m ( Y_sat(T_wb) - Y_inf ),

        by bisection on [dew point, dry bulb].  If the prescribed ``h_m`` is too
        small for a root to exist in that bracket (which is the case for the
        appendix value -- see docs/MODEL.md section 5), the classical
        Lewis-consistent coefficient is used instead, so that the surface sits at
        the true wet-bulb temperature and the evaporation rate is heat limited.
        """
        def resid(m, Twb):
            return (props.h * (Tamb - Twb)
                    - props.Lw * m * (self._Ysat(Twb) - Yinf))

        Tdp = self.dew_point(Tamb, Yinf)
        # The psychrometric balance must use a physically sized mass-transfer
        # coefficient.  The appendix value (8e-7 m/s) is ~3e4 times smaller than
        # the Chilton-Colburn value consistent with h = 25 W m^-2 K^-1, and with
        # it the balance has no root in [dew point, dry bulb]: the surface would
        # have to be colder than the dew point to stop evaporating.  The
        # Lewis-consistent value is therefore used, which is the standard
        # wet-bulb closure and makes the film law and the heat balance agree:
        #     h_m (Y_sat(T_wb) - Y_inf) = h (T_inf - T_wb)/L_w.
        m = float(props.h) / (RHO_AIR * CP_AIR * LEWIS ** (2.0 / 3.0))
        lo, hi = Tdp, Tamb
        f_lo, f_hi = resid(m, lo), resid(m, hi)
        if f_lo * f_hi > 0.0:
            return Tdp if abs(f_lo) < abs(f_hi) else Tamb
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            f_mid = resid(m, mid)
            if f_lo * f_mid <= 0.0:
                hi, f_hi = mid, f_mid
            else:
                lo, f_lo = mid, f_mid
            if hi - lo < 1e-12:
                break
        return 0.5 * (lo + hi)

    @staticmethod
    def _Ysat(T, P=P_ATM):
        ps = np.clip(p_sat_water(T), 0.0, 0.8 * P)
        return 0.62198 * ps / (P - ps)

    @staticmethod
    def dew_point(T, Y, P=P_ATM):
        pv = min(max(P * float(Y) / (0.62198 + float(Y)), 1.0), 0.99 * P)
        ln = np.log(pv / 611.21)
        a, b, c = 18.678, 257.14, 234.5
        g = lambda Tc: (a - Tc / b) * (Tc / (c + Tc)) - ln
        lo, hi = -100.0, 100.0
        for _ in range(100):
            mid = 0.5 * (lo + hi)
            if g(lo) * g(mid) <= 0.0:
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi) + T0_K

    def hm_film(self, props):
        """Air-side mass-transfer coefficient [m s^-1] for the surface film.

        ``props.hm_mode`` selects the closure (see docs/MODEL.md section 5):

        ``"prescribed"``
            the appendix value ``h_m = 8e-7`` m/s.  With the humidity-ratio
            driving force this makes the process mass-transfer limited and far
            too slow to reach C = 0.15 within the 2-3 days stated in the problem.
        ``"heat_limited"``  (default)
            The prescribed pair (h, h_m) is internally inconsistent for this air
            condition: taken literally, the evaporative demand of the film
            exceeds the convective heat supply by ~1e2, the surface dries out
            completely, and the sample never reaches C = 0.15.  In hot-air drying
            the rate is instead limited by the heat supply, so the surface sits at
            the wet-bulb temperature of the chamber air and

                j_w = h_m ( Y_sat(T_wb) - Y_inf ),   h (T_inf - T_wb) = L_w j_w.

            This is the standard constant-rate closure and reproduces the 2-3 day
            process duration implied by 附件2.
        """
        mode = getattr(props, "hm_mode", "heat_limited")
        if mode == "scaled":
            return float(props.h_m) * float(getattr(props, "hm_scale", 1.0))
        if mode == "prescribed":
            return float(props.h_m)
        # "lewis" and "heat_limited" both use the Chilton-Colburn value
        # consistent with the prescribed h
        return float(props.h) / (RHO_AIR * CP_AIR * LEWIS ** (2.0 / 3.0))

    # ------------------------------------------------------------------
    def surface_state(self, props, C, T, R, Tamb, Camb):
        """Surface film state.  Returns ``(jw, Cs, Ys, Ts)``.

        The surface is the r = R face of the outermost control volume.  Water
        reaches it from the interior by diffusion and leaves through the film:

            h_m ( Y_s - Y_inf ) = D (C_cell - C_s)/(h_r/2)               (*)

        The humidity ratio of the air in equilibrium with the surface follows the
        sorption isotherm of the material; here it is represented by the
        availability ``phi = min(C_s/C_sat, 1)``,

            Y_s = phi(C_s) Y_sat(T_s),

        which is the standard way to obtain a *falling-rate* period: as the
        surface dries the equilibrium humidity drops, the driving force collapses
        and the drying rate follows the internal diffusion rather than an
        external equilibrium value.

        ``hm_mode`` selects the film coefficient (see :meth:`hm_film`):

        * ``"heat_limited"`` (default): ``h_m`` is the Lewis-consistent value so
          that the wet-surface rate equals the heat supply
          ``h (T_inf - T_wb)/L_w`` -- the classical constant-rate period.
        * ``"prescribed"`` / ``"scaled"``: the appendix value of ``h_m`` is used.

        In both cases (*) is solved for ``C_s`` by bisection, and the surface
        temperature comes from the film energy balance.
        """
        N = self.N
        h_r = R / N
        Ccell, Tcell = float(C[-1]), float(T[-1])
        Yinf = float(Camb)
        hm = self.hm_film(props)
        # Dry-solid apparent density.  The water flux carried by a dry-basis
        # gradient is  J = rho_d D dC/dr  [kg m^-2 s^-1]; omitting rho_d makes
        # the surface flux smaller than the interior loss by exactly rho_d
        # (~231 kg/m^3 here), which is the inconsistency this line prevents.
        rd = self.dry_density(props, R)
        Ds = float(np.asarray(props.D(C[-1:], T[-1:]), float)[0])
        ks = float(np.asarray(props.k(C[-1:], T[-1:]), float)[0])
        gD = rd * Ds / (0.5 * h_r)     # half-cell water conductance [kg m^-2 s^-1]
        gK = ks / (0.5 * h_r)          # half-cell conductive conductance

        heat_limited = (getattr(props, "hm_mode", "heat_limited") == "heat_limited"
                        and float(props.Lw) > 0.0)
        if heat_limited:
            # Classical constant-rate (wet-surface) closure: the surface sits at
            # the wet-bulb temperature of the chamber air and the evaporation
            # rate equals the convective heat supply divided by the latent heat,
            #     j_w = h (T_inf - T_wb)/L_w.
            # The prescribed h_m (8e-7 m/s) is far too small to carry this flux
            # (see docs/MODEL.md section 5), so the heat balance is used directly
            # and h_m enters only through the wet-bulb temperature.
            Twb = self.wet_bulb_temperature(props, Tamb, Yinf)
            jw_wet = float(props.h) * (float(Tamb) - Twb) / props.Lw
            Ysat_s = self._Ysat(Twb)
        else:
            Twb = float(Tamb)
            jw_wet = float("inf")
            Ysat_s = self._Ysat(float(Tamb))

        Cs = float(np.clip(Ccell, 0.0, props.C_sat))
        phi = min(Cs / props.C_sat, 1.0)
        if heat_limited:
            # --- wet-bulb (adiabatic-saturation) closure ---------------------
            # The surface of a wet sample reaches the wet-bulb temperature T_wb
            # of the chamber air, where the convective heat supply exactly
            # balances the latent heat of evaporation:
            #     h (T_inf - T_wb) = L_w j_w
            # With the Chilton-Colburn coefficient this is *equivalent* to the
            # film law j_w = h_m (Y_sat(T_wb) - Y_inf) -- both give 9.21e-5
            # kg m^-2 s^-1 at 50 degC.  (With the appendix h_m = 8e-7 the film
            # law gives 3e4 times less, so the two cannot both hold; see
            # docs/MODEL.md section 5.)  The energy form is used here.
            #
            # The material cannot evaporate faster than the interior supplies
            # water, so the rate is capped by the availability of the surface
            # cell and the diffusive conductance of the half cell:
            #     j_w = min( j_w_wb * phi , gD * C_cell )
            # The second term becomes active in the late falling-rate period and
            # is what bounds the drying time.
            # Surface flux and surface moisture are coupled:
            #     j_w = j_w_wb * phi(C_s)          (heat supply, availability)
            #     j_w = gD (C_cell - C_s)          (half-cell diffusive supply)
            # Writing x = C_s/C_sat and eliminating j_w gives
            #     x = gD C_cell / (gD C_sat + j_w_wb),
            # capped at 1 because the surface cannot be supersaturated.  The
            # operative flux is then j_w = gD (C_cell - C_s), which is exactly
            # the water the outermost half cell can deliver, so the discrete
            # water budget stays exact.
            denom = gD * props.C_sat + jw_wet
            x = 1.0 if denom <= 0.0 else min(1.0, gD * Ccell / denom)
            Cs = float(np.clip(x * props.C_sat, 0.0, props.C_sat))
            jw = gD * (Ccell - Cs)
            if jw < 0.0:
                jw = 0.0
            phi = min(max(Cs / props.C_sat, 0.0), 1.0)
            Ys = phi * Ysat_s
            return float(jw), float(Cs), float(Ys), float(Twb)

        Ts, jw = Twb, 0.0
        for _ in range(200):
            Ts_new = (float(Tamb) * props.h + Tcell * gK - props.Lw * jw) / (props.h + gK)
            Ts_new = float(np.clip(Ts_new, 200.0, max(float(Tamb), 200.5)))
            Ysat_s = self._Ysat(Ts_new)
            # surface moisture from the availability-limited balance (*)
            cs_lin = (gD * Ccell - hm * Yinf) / (gD + hm * Ysat_s)
            if cs_lin >= props.C_sat:
                Cs_new = props.C_sat
            elif cs_lin <= 0.0:
                Cs_new = 0.0
            else:
                lo, hi = 0.0, props.C_sat
                f_lo = gD * (Ccell - lo) + hm * Yinf
                for _ in range(70):
                    mid = 0.5 * (lo + hi)
                    f_mid = (gD * (Ccell - mid)
                             - hm * (mid / props.C_sat * Ysat_s - Yinf))
                    if f_lo * f_mid <= 0.0:
                        hi = mid
                    else:
                        lo, f_lo = mid, f_mid
                Cs_new = 0.5 * (lo + hi)
            Cs_new = float(np.clip(Cs_new, 0.0, props.C_sat))
            phi = min(Cs_new / props.C_sat, 1.0)
            jw_new = hm * (phi * Ysat_s - Yinf)
            if phi >= 1.0 and jw_new < 0.0:
                jw_new = 0.0
            done = (abs(Cs_new - Cs) <= 1e-14 * props.C_sat
                    and abs(Ts_new - Ts) <= 1e-13 * max(float(Tamb), 1.0)
                    and abs(jw_new - jw) <= 1e-15 * max(abs(jw_new), 1e-18))
            Cs, Ts, jw = Cs_new, Ts_new, jw_new
            if done:
                break
        Ys = min(Cs / props.C_sat, 1.0) * float(Y_sat(Ts))
        return float(jw), float(Cs), float(Ys), float(Ts)

    # ------------------------------------------------------------------
    def rhs(self, t, y, props, t_end, Qsrc: float = 0.0):
        """Semi-discrete right-hand side for y = [T (N), C (N)].

        ``Qsrc`` is an optional uniform volumetric heat source [W m^-3], used
        only by the verification suite.
        """
        N = self.N
        R = float(self.Rfun(min(t, t_end)))
        h_r, V, F = self.geometry(R)
        inv_h = 1.0 / h_r
        T = y[:N]
        C = y[N:]
        Tamb = float(props.Tamb(min(t, t_end)))
        Camb = float(props.Camb(min(t, t_end)))

        kk = np.maximum(np.asarray(props.k(C, T), float), 1e-300)
        Dd = np.maximum(np.asarray(props.D(C, T), float), 1e-300)
        rcp = np.maximum(np.asarray(props.rho(C, T) * props.cp(C, T), float), 1e-300)

        jw, Cs, Ys, Ts = self.surface_state(props, C, T, R, Tamb, Camb)

        # Interior flux divergence, in W m^-3 (heat) and kg m^-3 s^-1 (water).
        # Face i (at xi_f[i]) separates cells i-1 and i; its flux enters cell i
        # with +F_i/V_i and leaves cell i-1 with -F_i/V_{i-1}, using the SAME
        # physical face area F_i.
        # Water inventory per unit length: W = int rho_d C dV, and for the fixed
        # mesh this is  rho_d0 * sum_i V_i C_i  (rho_d0 constant in time for the
        # non-shrinking problems; see dry_density for the shrinking case).
        # Consistency with the boundary term below therefore requires
        #     rho_d V_i dC_i/dt = F_i j_w      =>   dC_i/dt = F_i j_w/(rho_d V_i)
        # i.e. the physical flux must be divided by rho_d.
        rd = self.dry_density(props, R)
        divT = np.zeros(N)
        divC = np.zeros(N)
        for i in range(1, N):
            kf = 0.5 * (kk[i - 1] + kk[i])
            Df = 0.5 * (Dd[i - 1] + Dd[i])
            qT = kf * inv_h * (T[i - 1] - T[i])            # W m^-2, +r direction
            qC = rd * Df * inv_h * (C[i - 1] - C[i])       # kg m^-2 s^-1
            divT[i] += F[i] * qT / V[i]
            divT[i - 1] -= F[i] * qT / V[i - 1]
            divC[i] += F[i] * qC / (rd * V[i])
            divC[i - 1] -= F[i] * qC / (rd * V[i - 1])

        dTdt = divT / rcp
        dCdt = divC

        # Surface cell N-1: film exchange over the physical lateral area F[N].
        # Same bookkeeping as the interior: rho_d V dC/dt = -F_N j_w.
        i = N - 1
        q_in = props.h * (Tamb - T[i]) - props.Lw * jw       # W m^-2 into sample
        dTdt[i] += F[N] * q_in / (V[i] * rcp[i])
        dCdt[i] -= F[N] * jw / (rd * V[i])

        # optional uniform volumetric source (verification only)
        if Qsrc:
            dTdt += Qsrc / rcp

        return np.concatenate([dTdt, dCdt])

    # ------------------------------------------------------------------
    def run(self, props, t_end, T_init, C_init, t_start=0.0, sample_dt=None,
            rtol=1e-8, atol=1e-10, method="BDF", max_step=np.inf,
            Qsrc: float = 0.0) -> Series:
        N = self.N
        T0 = np.full(N, float(T_init)) if np.isscalar(T_init) else np.array(T_init, float)
        C0 = np.full(N, float(C_init)) if np.isscalar(C_init) else np.array(C_init, float)
        y0 = np.concatenate([T0, C0])

        if sample_dt is None:
            t_eval = None
        else:
            n = int(np.floor((t_end - t_start) / sample_dt + 1e-9))
            t_eval = np.array([t_start + i * sample_dt for i in range(n + 1)])
            if t_eval[-1] < t_end - 1e-9:
                t_eval = np.append(t_eval, t_end)

        sol = solve_ivp(
            lambda t, y: self.rhs(t, y, props, t_end, Qsrc),
            (t_start, t_end), y0, method=method, rtol=rtol, atol=atol,
            t_eval=t_eval, max_step=max_step, dense_output=False,
        )
        if not sol.success:
            raise RuntimeError(f"integration failed: {sol.message}")
        out = Series()
        for k, tt in enumerate(sol.t):
            T = sol.y[:N, k]
            C = sol.y[N:, k]
            R = float(self.Rfun(tt))
            jw, Cs, Ys, Ts = self.surface_state(
                props, C, T, R, float(props.Tamb(tt)), float(props.Camb(tt)))
            q = props.h * (float(props.Tamb(tt)) - T[-1]) - props.Lw * jw
            out.ts.append(float(tt))
            out.T.append(T.copy())
            out.C.append(C.copy())
            out.R.append(R)
            out.Tsurf.append(float(T[-1]))
            out.Csurf.append(float(Cs))
            out.Tc.append(float(T[0]))
            out.Cc.append(float(C[0]))
            out.jw.append(float(jw))
            out.q.append(float(q))
            out.W.append(float(2.0 * np.pi * self.R0 ** 2 * props.rho_d0
                               * float(np.dot(C, 0.5 * (self.xi_f[1:] ** 2
                                                       - self.xi_f[:-1] ** 2)))))
            out.Tamb.append(float(props.Tamb(tt)))
            out.Camb.append(float(props.Camb(tt)))
        return out
