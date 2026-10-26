"""Link budget for the LTM V/u linear transponder, telemetry beacon and command uplink.

RF figures from the public AMSAT LTM page (amsat.org/amsat-linear-transponder-module):
  - V/u: uplink 144 MHz band, downlink 432 MHz band, 30 kHz passband, SSB/CW
  - TX power 100 mW telemetry only, 450 mW telemetry + transponder
  - Telemetry 1200 bps BPSK (FoxTelem); command uplink 20K0F1D
Frequencies below are representative (Fox-1E plan) until IARU coordination is complete.
Ground-station gains are typical amateur figures, not vendor-verified.
"""
import math

from orbit import max_slant_range_km

ALT_KM = 525.0
K_DBW = -228.6             # Boltzmann, dBW/K/Hz

F_UP_MHZ = 145.875
F_DN_MHZ = 435.775

# spacecraft
SC_TX_TOTAL_W = 0.450
SC_TX_TLM_W = 0.100
SC_ANT_GAIN_DBI = -3.0     # tumbling monopole/dipole, average-with-nulls allowance
SC_LINE_LOSS_DB = 1.0
SC_RX_TSYS_K = 700.0       # Earth-facing VHF antenna (~290 K + man-made noise) + LNA
TP_USERS = 5               # simultaneous SSB users sharing transponder PEP

# propagation
POL_LOSS_DB = 3.0          # linear spacecraft vs circular ground (or polarization fade)
ATMOS_LOSS_DB = 0.5        # atmosphere + ionospheric scintillation at V/UHF

STATIONS = {
    "Portable (handheld Yagi)": {
        "up_w": 5.0, "up_gain": 5.0, "dn_gain": 7.5, "line_up": 0.5, "line_dn": 0.5,
        "tsys_dn": 450.0,   # no preamp, suburban noise
    },
    "Fixed (crossed Yagis + LNA)": {
        "up_w": 50.0, "up_gain": 12.0, "dn_gain": 15.0, "line_up": 1.5, "line_dn": 0.3,
        "tsys_dn": 250.0,
    },
    "AMSAT command station": {
        "up_w": 100.0, "up_gain": 14.0, "dn_gain": 16.0, "line_up": 1.5, "line_dn": 0.3,
        "tsys_dn": 200.0,
    },
}

SIGNALS = {
    "SSB voice (2.4 kHz)": {"bw_hz": 2400, "req_db": 10.0, "kind": "cn"},
    "CW (500 Hz)": {"bw_hz": 500, "req_db": 6.0, "kind": "cn"},
    "Telemetry BPSK 1200 bps": {"rate": 1200, "req_db": 9.6 + 1.5, "kind": "ebn0"},
    "Command FSK (20 kHz)": {"rate": 9600, "req_db": 13.0 + 2.0, "kind": "ebn0"},
}


def db(x):
    return 10 * math.log10(x)


def fspl_db(range_km, f_mhz):
    return 32.45 + 20 * math.log10(range_km) + 20 * math.log10(f_mhz)


def downlink(station, signal, el_deg, tx_w):
    st = STATIONS[station]
    r = max_slant_range_km(ALT_KM, el_deg)
    eirp = db(tx_w) - SC_LINE_LOSS_DB + SC_ANT_GAIN_DBI
    L = fspl_db(r, F_DN_MHZ)
    c = eirp - L - POL_LOSS_DB - ATMOS_LOSS_DB + st["dn_gain"] - st["line_dn"]
    gt = st["dn_gain"] - st["line_dn"] - db(st["tsys_dn"])
    c_n0 = c - K_DBW - db(st["tsys_dn"])
    return _margin(signal, c_n0), {"range_km": r, "eirp_dbw": eirp, "fspl_db": L,
                                   "c_dbw": c, "gt_dbk": gt, "c_n0": c_n0}


def uplink(station, signal, el_deg):
    st = STATIONS[station]
    r = max_slant_range_km(ALT_KM, el_deg)
    eirp = db(st["up_w"]) - st["line_up"] + st["up_gain"]
    L = fspl_db(r, F_UP_MHZ)
    c = eirp - L - POL_LOSS_DB - ATMOS_LOSS_DB + SC_ANT_GAIN_DBI - SC_LINE_LOSS_DB
    c_n0 = c - K_DBW - db(SC_RX_TSYS_K)
    return _margin(signal, c_n0), {"range_km": r, "eirp_dbw": eirp, "fspl_db": L,
                                   "c_dbw": c, "c_n0": c_n0}


def _margin(signal, c_n0):
    s = SIGNALS[signal]
    if s["kind"] == "cn":
        snr = c_n0 - db(s["bw_hz"])
    else:
        snr = c_n0 - db(s["rate"])
    return snr - s["req_db"]


def per_user_tp_w():
    return (SC_TX_TOTAL_W - SC_TX_TLM_W) / TP_USERS


def end_to_end_ssb(station, el_deg):
    """Bent-pipe SSB: combine uplink and downlink C/N0 (linear transponder)."""
    _, up = uplink(station, "SSB voice (2.4 kHz)", el_deg)
    _, dn = downlink(station, "SSB voice (2.4 kHz)", el_deg, per_user_tp_w())
    c_n0 = -db(10 ** (-up["c_n0"] / 10) + 10 ** (-dn["c_n0"] / 10))
    return _margin("SSB voice (2.4 kHz)", c_n0)


def doppler_khz(f_mhz):
    re = 6378.137
    v = math.sqrt(398600.4418 / (re + ALT_KM)) * 1e3 * re / (re + ALT_KM)  # radial velocity at horizon
    return f_mhz * 1e6 * v / 3e8 / 1e3


def detailed_tables(el_deg=10.0):
    """Line-item tables at the design elevation."""
    tables = []
    for title, station, signal, direction, txw in [
        ("Telemetry downlink (BPSK 1200)", "Portable (handheld Yagi)", "Telemetry BPSK 1200 bps", "dn", SC_TX_TLM_W),
        ("Transponder downlink, per user (SSB)", "Portable (handheld Yagi)", "SSB voice (2.4 kHz)", "dn", per_user_tp_w()),
        ("User uplink to transponder (SSB)", "Portable (handheld Yagi)", "SSB voice (2.4 kHz)", "up", None),
        ("Command uplink (FSK)", "AMSAT command station", "Command FSK (20 kHz)", "up", None),
    ]:
        st = STATIONS[station]
        sig = SIGNALS[signal]
        if direction == "dn":
            m, d = downlink(station, signal, el_deg, txw)
            rows = [
                ("Frequency", f"{F_DN_MHZ:.3f}", "MHz"),
                ("Spacecraft TX power", f"{db(txw):.1f}", f"dBW ({txw*1000:.0f} mW)"),
                ("Spacecraft line loss", f"-{SC_LINE_LOSS_DB:.1f}", "dB"),
                ("Spacecraft antenna gain", f"{SC_ANT_GAIN_DBI:.1f}", "dBi"),
                ("EIRP", f"{d['eirp_dbw']:.1f}", "dBW"),
                ("Slant range", f"{d['range_km']:.0f}", "km"),
                ("Free-space path loss", f"-{d['fspl_db']:.1f}", "dB"),
                ("Polarization loss", f"-{POL_LOSS_DB:.1f}", "dB"),
                ("Atmos./ionosphere", f"-{ATMOS_LOSS_DB:.1f}", "dB"),
                ("Ground antenna gain", f"{st['dn_gain']:.1f}", "dBi"),
                ("Ground line loss", f"-{st['line_dn']:.1f}", "dB"),
                ("Ground system noise temp", f"{db(st['tsys_dn']):.1f}", f"dBK ({st['tsys_dn']:.0f} K)"),
                ("G/T", f"{d['gt_dbk']:.1f}", "dB/K"),
                ("C/N0", f"{d['c_n0']:.1f}", "dB-Hz"),
            ]
        else:
            m, d = uplink(station, signal, el_deg)
            rows = [
                ("Frequency", f"{F_UP_MHZ:.3f}", "MHz"),
                ("Ground TX power", f"{db(st['up_w']):.1f}", f"dBW ({st['up_w']:.0f} W)"),
                ("Ground line loss", f"-{st['line_up']:.1f}", "dB"),
                ("Ground antenna gain", f"{st['up_gain']:.1f}", "dBi"),
                ("EIRP", f"{d['eirp_dbw']:.1f}", "dBW"),
                ("Slant range", f"{d['range_km']:.0f}", "km"),
                ("Free-space path loss", f"-{d['fspl_db']:.1f}", "dB"),
                ("Polarization loss", f"-{POL_LOSS_DB:.1f}", "dB"),
                ("Atmos./ionosphere", f"-{ATMOS_LOSS_DB:.1f}", "dB"),
                ("Spacecraft antenna gain", f"{SC_ANT_GAIN_DBI:.1f}", "dBi"),
                ("Spacecraft line loss", f"-{SC_LINE_LOSS_DB:.1f}", "dB"),
                ("Spacecraft system noise temp", f"{db(SC_RX_TSYS_K):.1f}", f"dBK ({SC_RX_TSYS_K:.0f} K)"),
                ("C/N0", f"{d['c_n0']:.1f}", "dB-Hz"),
            ]
        if sig["kind"] == "cn":
            rows.append(("Noise bandwidth", f"{db(sig['bw_hz']):.1f}", f"dB-Hz ({sig['bw_hz']} Hz)"))
            rows.append(("Required C/N", f"{sig['req_db']:.1f}", "dB"))
        else:
            rows.append(("Data rate", f"{db(sig['rate']):.1f}", f"dB-Hz ({sig['rate']} bps)"))
            rows.append(("Required Eb/N0 (incl. impl. loss)", f"{sig['req_db']:.1f}", "dB"))
        tables.append({"title": title, "station": station, "rows": rows, "margin_db": m})
    return tables


def budget():
    els = list(range(5, 91, 5))
    curves = {}
    for station in ("Portable (handheld Yagi)", "Fixed (crossed Yagis + LNA)"):
        curves[f"Telemetry - {station}"] = [[e, round(downlink(station, "Telemetry BPSK 1200 bps", e, SC_TX_TLM_W)[0], 2)] for e in els]
        curves[f"SSB end-to-end - {station}"] = [[e, round(end_to_end_ssb(station, e), 2)] for e in els]
    return {
        "alt_km": ALT_KM, "f_up": F_UP_MHZ, "f_dn": F_DN_MHZ,
        "tables": detailed_tables(10.0), "curves": curves,
        "per_user_mw": per_user_tp_w() * 1000, "users": TP_USERS,
        "doppler_up_khz": doppler_khz(F_UP_MHZ), "doppler_dn_khz": doppler_khz(F_DN_MHZ),
        "stations": STATIONS, "e2e_portable_10": end_to_end_ssb("Portable (handheld Yagi)", 10),
        "e2e_fixed_10": end_to_end_ssb("Fixed (crossed Yagis + LNA)", 10),
    }


if __name__ == "__main__":
    b = budget()
    for t in b["tables"]:
        print(f"{t['title']:42s} [{t['station']}] margin @10deg: {t['margin_db']:.1f} dB")
    print(f"SSB end-to-end @10deg: portable {b['e2e_portable_10']:.1f} dB, fixed {b['e2e_fixed_10']:.1f} dB")
    print(f"Doppler: up +/-{b['doppler_up_khz']:.1f} kHz, down +/-{b['doppler_dn_khz']:.1f} kHz")
    for k, v in b["curves"].items():
        print(f"  {k}: 5deg {v[0][1]} dB, 30deg {v[5][1]} dB, 90deg {v[-1][1]} dB")
