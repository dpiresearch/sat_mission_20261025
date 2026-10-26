"""Shared orbit geometry helpers (circular orbits)."""
import math

MU = 3.986004418e14
RE = 6378.137e3


def period_s(alt_km):
    a = RE + alt_km * 1e3
    return 2 * math.pi * math.sqrt(a ** 3 / MU)


def eclipse_fraction(alt_km, beta_deg):
    """Cylindrical-shadow eclipse fraction of a circular orbit."""
    r = RE + alt_km * 1e3
    beta = math.radians(beta_deg)
    beta_star = math.asin(RE / r)
    if abs(beta) >= beta_star:
        return 0.0
    h = alt_km * 1e3
    return math.acos(math.sqrt(h * h + 2 * RE * h) / (r * math.cos(beta))) / math.pi


def sso_inclination_deg(alt_km):
    """Sun-synchronous inclination from J2 precession."""
    j2 = 1.08263e-3
    a = RE + alt_km * 1e3
    n = math.sqrt(MU / a ** 3)
    omega_dot = 2 * math.pi / (365.2422 * 86400)
    cosi = -omega_dot / (1.5 * n * j2 * (RE / a) ** 2)
    return math.degrees(math.acos(cosi))


def max_slant_range_km(alt_km, el_deg):
    r = RE / 1e3 + alt_km
    re = RE / 1e3
    el = math.radians(el_deg)
    return math.sqrt(r * r - (re * math.cos(el)) ** 2) - re * math.sin(el)


def pass_duration_min(alt_km, min_el_deg=0.0):
    """Maximum (overhead) pass duration above min elevation."""
    re = RE / 1e3
    r = re + alt_km
    el = math.radians(min_el_deg)
    # Earth central angle to horizon at elevation el
    lam = math.acos(re * math.cos(el) / r) - el
    return 2 * lam / (2 * math.pi) * period_s(alt_km) / 60


def footprint_radius_km(alt_km, min_el_deg=0.0):
    re = RE / 1e3
    r = re + alt_km
    el = math.radians(min_el_deg)
    lam = math.acos(re * math.cos(el) / r) - el
    return re * lam
