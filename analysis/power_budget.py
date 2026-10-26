"""Power budget for the 1U LTM CubeSat.

Sources (see NOTES.md for full list):
  * Solar: proveskit/solar_boards XY_Faces_V2a - 6x KXOB101K08TF per face, 2s3p.
  * EPS: FC V5d - LT3652 2S charger (float 8.38 V, 1 A), TPS54226 3.3 V, TPS54225 5 V LTM_VSYS.
  * Battery: proveskit/battery_board battery_pack_v2 - 4x 18650 in 2S2P.
  * LTM: amsat.org/amsat-linear-transponder-module (public): 5-7 V in, 40 mA safe,
    310 mA telemetry (~11 % duty), 300-650 mA transponder.
Values marked "DS" are datasheet-typical and need bench confirmation.
"""
import math

from orbit import eclipse_fraction, period_s

# ---------------------------------------------------------------- orbit
ALT_KM = 525.0          # baseline Transporter-class SSO altitude (TBC)
BETA_WORST = 0.0        # deg, longest eclipse

# ---------------------------------------------------------------- solar
CELL_PMP_AM15_W = 0.20  # DS, KXOB101K08TF class mono-Si, AM1.5 1000 W/m^2 (verify)
AM0_FACTOR = 1366 / 1000
CELLS_PER_FACE = 6
FACES_WITH_CELLS = 5    # +/-X, +/-Y, -Z; +Z is the antenna top cap
TUMBLE_FACE_EQ = FACES_WITH_CELLS / 4.0   # mean |cos| of a face under random tumble = 1/4
SOLAR_LOSSES = {
    "Cell temperature (+50 C, -0.45 %/C)": 0.89,
    "LT3652 input regulation (8.44 V) vs 2S Vmp": 0.90,
    "Blocking Schottky (CDBA240LL)": 0.96,
    "Cover / EVA encapsulant": 0.97,
    "Radiation & UV degradation (EOL, 2 yr)": 0.96,
    "LT3652 charger efficiency": 0.85,
}

# ---------------------------------------------------------------- battery
CELL_AH = 3.35          # DS, NCR18650B typ
CELL_V = 3.6
SERIES, PARALLEL = 2, 2
BATT_EOL_FACTOR = 0.80
MAX_DOD = 0.30          # design limit for cycle life

# ---------------------------------------------------------------- regulators
EFF_3V3 = 0.85          # TPS54226 Eco-mode at ~50 mA (DS)
EFF_5V_LIGHT = 0.72     # TPS54225 forced-CCM at ~40 mA (DS)
EFF_5V_HEAVY = 0.89     # TPS54225 at 0.3-0.65 A (DS)

# ---------------------------------------------------------------- loads
# (name, rail, current A, note) - 3.3 V loads in amps on the 3.3 V rail.
FC_LOADS = [
    ("RP2350 MCU (150 MHz active)", 0.030, "DS"),
    ("Flash / PSRAM / SD NAND (avg)", 0.003, "DS"),
    ("IMU LSM6DSO + mag LIS2MDL", 0.0008, "DS"),
    ("MCP23017 GPIO expander", 0.001, "DS"),
    ("INA219 x2 power monitors", 0.002, "DS"),
    ("I2C muxes / buffers / watchdog / RTC", 0.003, "DS"),
    ("Face sensors x5 (MCP9808, VEML7700, TCA4311A)", 0.0035, "DS"),
    ("Antenna-cap + battery sensors (TMP112, VEML6031)", 0.001, "DS"),
]
CAN_LOAD = ("MCP25625 CAN controller (LTM on)", 0.005, "DS")
MTQ_W = 0.30            # detumble: face coils via DRV2605L, avg battery-side power (estimate)
HEATER_W = 1.0          # battery heater element on FC "Heater Output" (estimate)
HEATER_DUTY = 0.10      # cold-case thermostat duty, orbit average

LTM_V = 5.0
LTM_MODES = {           # amsat.org LTM public figures, at LTM_VSYS
    "off": 0.0,
    "safe": 0.040,
    "beacon": 0.040 * 0.89 + 0.310 * 0.11,   # 310 mA at ~11 % TX duty, 40 mA otherwise
    "transponder": 0.475,                   # mid of 300-650 mA (load-dependent)
    "transponder_max": 0.650,
}


def battery_wh():
    bol = SERIES * CELL_V * PARALLEL * CELL_AH
    return bol, bol * BATT_EOL_FACTOR


def solar():
    face_am0 = CELLS_PER_FACE * CELL_PMP_AM15_W * AM0_FACTOR
    sunlit_raw = face_am0 * TUMBLE_FACE_EQ
    eta = math.prod(SOLAR_LOSSES.values())
    return {"face_am0_w": face_am0, "sunlit_raw_w": sunlit_raw, "eta": eta,
            "sunlit_net_w": sunlit_raw * eta}


def ltm_batt_w(mode):
    i = LTM_MODES[mode]
    if i == 0:
        return 0.0
    eff = EFF_5V_LIGHT if i < 0.1 else EFF_5V_HEAVY
    return LTM_V * i / eff


def fc_batt_w(ltm_on, mcu_scale=1.0):
    i = sum(c for _, c, _ in FC_LOADS) - FC_LOADS[0][1] * (1 - mcu_scale)
    if ltm_on:
        i += CAN_LOAD[1]
    return 3.3 * i / EFF_3V3


def modes():
    """Orbit-average battery-side power per operating mode."""
    m = {}
    m["Detumble (LEOP)"] = {"FC + sensors": fc_batt_w(False), "Magnetorquers": MTQ_W,
                            "LTM": 0.0, "Heater": 0.0}
    m["Safe"] = {"FC + sensors": fc_batt_w(True, mcu_scale=0.4), "Magnetorquers": 0.0,
                 "LTM": ltm_batt_w("safe"), "Heater": HEATER_W * HEATER_DUTY}
    m["Beacon (telemetry only)"] = {"FC + sensors": fc_batt_w(True), "Magnetorquers": 0.0,
                                    "LTM": ltm_batt_w("beacon"), "Heater": 0.0}
    m["Transponder (typical load)"] = {"FC + sensors": fc_batt_w(True), "Magnetorquers": 0.0,
                                       "LTM": ltm_batt_w("transponder"), "Heater": 0.0}
    m["Transponder (max load)"] = {"FC + sensors": fc_batt_w(True), "Magnetorquers": 0.0,
                                   "LTM": ltm_batt_w("transponder_max"), "Heater": 0.0}
    return {k: {"items": v, "total_w": sum(v.values())} for k, v in m.items()}


def generation_vs_beta(alt_km=ALT_KM):
    s = solar()
    out = []
    for beta in range(0, 91, 5):
        f = eclipse_fraction(alt_km, beta)
        out.append([beta, round(s["sunlit_net_w"] * (1 - f), 3), round(f, 3)])
    return out


def max_transponder_duty(gen_avg, md):
    base = md["Beacon (telemetry only)"]["total_w"]
    tp = md["Transponder (typical load)"]["total_w"]
    return max(0.0, min(1.0, (gen_avg - base) / (tp - base)))


def simulate_soc(days=3.0, beta=BETA_WORST, on_soc=0.80, off_soc=0.70, dt_s=30.0):
    """SoC under a battery-gated policy: transponder ON above on_soc, beacon below off_soc."""
    _, cap_eol = battery_wh()
    s = solar()
    md = modes()
    p_beacon = md["Beacon (telemetry only)"]["total_w"]
    p_tp = md["Transponder (typical load)"]["total_w"]
    T = period_s(ALT_KM)
    f_ecl = eclipse_fraction(ALT_KM, beta)
    soc, tp_on, t = 0.75, False, 0.0
    hist, tp_time = [], 0.0
    while t <= days * 86400:
        phase = (t % T) / T
        sunlit = phase >= f_ecl              # eclipse at the start of each orbit
        gen = s["sunlit_net_w"] if sunlit else 0.0
        if tp_on and soc < off_soc:
            tp_on = False
        elif not tp_on and soc > on_soc:
            tp_on = True
        load = p_tp if tp_on else p_beacon
        soc = min(1.0, soc + (gen - load) * dt_s / 3600 / cap_eol)
        tp_time += dt_s if tp_on else 0
        if int(t) % 600 == 0:
            hist.append([round(t / 3600, 3), round(soc * 100, 2), 1 if tp_on else 0])
        t += dt_s
    return {"history": hist, "transponder_duty": tp_time / (days * 86400),
            "min_soc": min(h[1] for h in hist), "beta": beta}


def budget():
    s = solar()
    md = modes()
    T = period_s(ALT_KM)
    f0 = eclipse_fraction(ALT_KM, BETA_WORST)
    gen_avg = s["sunlit_net_w"] * (1 - f0)
    bol, eol = battery_wh()
    tp_max = md["Transponder (max load)"]["total_w"]
    ecl_wh = tp_max * f0 * T / 3600
    return {
        "alt_km": ALT_KM, "period_min": T / 60, "eclipse_frac": f0,
        "eclipse_min": f0 * T / 60, "solar": s, "losses": SOLAR_LOSSES,
        "gen_avg_w": gen_avg, "modes": md,
        "fc_loads": FC_LOADS + [CAN_LOAD], "ltm_modes_a": LTM_MODES,
        "battery_bol_wh": bol, "battery_eol_wh": eol,
        "eclipse_dod_tp_max": ecl_wh / eol, "max_dod": MAX_DOD,
        "max_tp_duty_beta0": max_transponder_duty(gen_avg, md),
        "gen_vs_beta": generation_vs_beta(),
        "max_tp_duty_vs_beta": [[b, round(max_transponder_duty(g, md) * 100, 1)]
                                for b, g, _ in generation_vs_beta()],
        "soc_beta0": simulate_soc(beta=0),
        "soc_beta45": simulate_soc(beta=45),
        "heater": (HEATER_W, HEATER_DUTY), "mtq_w": MTQ_W,
        "regulators": {"3V3": EFF_3V3, "5V_light": EFF_5V_LIGHT, "5V_heavy": EFF_5V_HEAVY},
    }


if __name__ == "__main__":
    b = budget()
    print(f"Orbit {b['alt_km']} km, period {b['period_min']:.1f} min, eclipse {b['eclipse_min']:.1f} min")
    print(f"Face AM0 {b['solar']['face_am0_w']:.2f} W, sunlit raw {b['solar']['sunlit_raw_w']:.2f} W, "
          f"eta {b['solar']['eta']:.3f}, sunlit net {b['solar']['sunlit_net_w']:.2f} W, OA {b['gen_avg_w']:.2f} W")
    for k, v in b["modes"].items():
        print(f"  {k:28s} {v['total_w']:.3f} W  " + ", ".join(f"{n}={w:.3f}" for n, w in v["items"].items()))
    print(f"Battery {b['battery_bol_wh']:.1f} Wh BOL / {b['battery_eol_wh']:.1f} Wh EOL; "
          f"eclipse DoD (TP max) {b['eclipse_dod_tp_max']*100:.1f} %")
    print(f"Max sustained transponder duty @beta0: {b['max_tp_duty_beta0']*100:.1f} %")
    for k in ("soc_beta0", "soc_beta45"):
        s = b[k]
        print(f"  {k}: gated TP duty {s['transponder_duty']*100:.1f} %, min SoC {s['min_soc']:.1f} %")
