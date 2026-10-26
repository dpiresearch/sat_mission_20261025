"""Orbital lifetime estimate for the 1U LTM-1 CubeSat (DAS-style cross check).

This is NOT NASA DAS. It is a simple circular-orbit decay integrator used to
size the problem before running DAS 3.x (Requirement 4.6 / FCC 5-year rule).

    da/dt = -sqrt(mu * a) * rho(h, t) * Cd * A / m

Density comes from a piecewise-exponential table at solar minimum and
solar maximum (approximate MSIS-class values). For the time-varying case the
log-density is blended between the two using a sinusoidal 11-year solar cycle
anchored on the Solar Cycle 25 maximum (~2025.0) and the next minimum (~2030.5).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

MU = 3.986004418e14       # m^3/s^2
RE = 6378.137e3           # m
DAY = 86400.0

ALT_KM = np.array([200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700])
RHO_MIN = np.array([2.5e-10, 6.0e-11, 1.7e-11, 5.4e-12, 1.9e-12, 7.0e-13,
                    2.7e-13, 1.1e-13, 4.8e-14, 2.2e-14, 1.1e-14])   # F10.7 ~ 70
RHO_MAX = np.array([3.6e-10, 1.3e-10, 5.2e-11, 2.3e-11, 1.1e-11, 5.5e-12,
                    2.8e-12, 1.5e-12, 8.0e-13, 4.4e-13, 2.5e-13])   # F10.7 ~ 220

# Single density scale factor calibrated against the PROVES DAS 3.x runs
# (Atlas, Electra, Maia: 413 x 422 km, 51.64 deg). See calibrate() below.
DAS_CAL = 1.0

# Reference DAS 3.x results from github.com/proveskit/The-PROVES-Project-DAS
# (alt_km, DAS area-to-mass m^2/kg, start year, DAS lifetime yr, label)
DAS_REFS = [
    (417.5, 0.009686, 2026.333, 0.660, "Atlas (A/M 0.00969)"),
    (417.5, 0.014677, 2026.333, 0.422, "Atlas (A/M 0.01468)"),
    (417.5, 0.014692, 2026.748, 0.501, "Maia"),
    (417.5, 0.022401, 2026.333, 0.271, "Electra"),
]

CYCLE_YEARS = 11.0
CYCLE25_MAX = 2025.0      # decimal year


def solar_weight(year):
    """0 at solar minimum, 1 at solar maximum."""
    phase = 2 * math.pi * (year - CYCLE25_MAX) / CYCLE_YEARS
    return 0.5 * (1 + math.cos(phase))


def density(h_km, w):
    """Log-linear interpolation in altitude, log-blend between min and max."""
    h = min(max(h_km, ALT_KM[0]), ALT_KM[-1])
    lmin = np.interp(h, ALT_KM, np.log(RHO_MIN))
    lmax = np.interp(h, ALT_KM, np.log(RHO_MAX))
    rho = DAS_CAL * math.exp(lmin + w * (lmax - lmin))
    if h_km < ALT_KM[0]:  # extrapolate below 200 km with ~37 km scale height
        rho *= math.exp((ALT_KM[0] - h_km) / 37.0)
    return rho


def lifetime_years(h0_km, mass_kg, area_m2, cd=2.2, start_year=2027.9,
                   solar="cycle", reentry_km=120.0, max_years=100.0):
    """Return (years_to_reentry, history[(years, alt_km)])."""
    a = RE + h0_km * 1e3
    bc = cd * area_m2 / mass_kg
    t = 0.0
    hist = [(0.0, h0_km)]
    while True:
        h = (a - RE) / 1e3
        if h <= reentry_km:
            hist.append((t / (365.25 * DAY), h))
            return t / (365.25 * DAY), hist
        if t > max_years * 365.25 * DAY:
            return float("inf"), hist
        year = start_year + t / (365.25 * DAY)
        w = {"min": 0.0, "max": 1.0, "cycle": None}[solar]
        if w is None:
            w = solar_weight(year)
        dadt = -math.sqrt(MU * a) * density(h, w) * bc
        # adaptive step: never let altitude drop more than 0.5 km per step
        dt = min(DAY, 500.0 / max(-dadt, 1e-12))
        a += dadt * dt
        t += dt
        if len(hist) == 0 or t / (365.25 * DAY) - hist[-1][0] > 0.05:
            hist.append((t / (365.25 * DAY), (a - RE) / 1e3))


def lifetime_das_am(h0_km, am_das, start_year, **kw):
    """Lifetime using a DAS-style area-to-mass ratio (DAS applies Cd = 2.2 internally)."""
    return lifetime_years(h0_km, 1.0, am_das, cd=2.2, start_year=start_year, **kw)[0]


def calibrate():
    """Fit DAS_CAL so the geometric-mean model/DAS lifetime ratio is 1."""
    global DAS_CAL
    DAS_CAL = 1.0
    for _ in range(4):  # lifetime ~ 1/rho, so a few fixed-point steps converge
        logs = [math.log(lifetime_das_am(h, am, y) / ref) for h, am, y, ref, _ in DAS_REFS]
        DAS_CAL *= math.exp(sum(logs) / len(logs))
    return [(lbl, ref, lifetime_das_am(h, am, y)) for h, am, y, ref, lbl in DAS_REFS]


def main(out_path):
    validation = calibrate()
    print(f"DAS calibration factor on density: {DAS_CAL:.3f}")
    for lbl, ref, mod in validation:
        print(f"  {lbl:22s} DAS {ref:.3f} yr  model {mod:.3f} yr")

    # Mass / area assumptions (see NOTES.md). Area follows the PROVES Atlas DAS
    # project (A/M 0.014677 at 1.16 kg -> 0.0170 m^2 mean tumbling area).
    mass = 1.261           # kg, MEV from analysis/mass_budget.py
    a_tumble = 0.0170      # m^2, mean tumbling cross-section (DAS-style)
    a_min = 0.0118         # m^2, face-on minimum (~0.10 x 0.1135 m + antenna)
    a_max = 0.0200         # m^2, near corner-on

    results = {"assumptions": {
        "mass_kg": mass, "area_tumble_m2": a_tumble, "area_min_m2": a_min,
        "area_max_m2": a_max, "cd": 2.2, "start_year": 2027.9,
        "reentry_km": 120.0, "das_cal": DAS_CAL,
        "model": "piecewise exponential, solar-cycle blended, calibrated to PROVES DAS runs"},
        "validation": [{"case": l, "das_yr": r, "model_yr": round(m, 3)} for l, r, m in validation],
        "table": [], "profiles": {}}

    for h0 in range(400, 601, 25):
        row = {"alt_km": h0}
        row["cycle_tumble"] = lifetime_years(h0, mass, a_tumble)[0]
        row["cycle_min_area"] = lifetime_years(h0, mass, a_min)[0]
        row["cycle_max_area"] = lifetime_years(h0, mass, a_max)[0]
        row["solarmax_tumble"] = lifetime_years(h0, mass, a_tumble, solar="max")[0]
        row["solarmin_tumble"] = lifetime_years(h0, mass, a_tumble, solar="min")[0]
        results["table"].append(row)

    for h0 in (450, 500, 525, 550, 600):
        _, hist = lifetime_years(h0, mass, a_tumble)
        results["profiles"][str(h0)] = [[round(t, 3), round(h, 1)] for t, h in hist]

    Path(out_path).write_text(json.dumps(results, indent=1,
                                         default=lambda x: None if x == float("inf") else x))
    print(f"{'alt':>5} {'cycle':>8} {'cyc,Amin':>9} {'solmax':>8} {'solmin':>8}  (years)")
    for r in results["table"]:
        f = lambda v: f"{v:8.1f}" if v != float("inf") else "    >60"
        print(f"{r['alt_km']:>5} {f(r['cycle_tumble'])} {f(r['cycle_min_area']):>9} "
              f"{f(r['solarmax_tumble'])} {f(r['solarmin_tumble'])}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "orbit_lifetime.json")
