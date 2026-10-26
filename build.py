"""Build the static mission website into public/.

    python3 build.py

Every number on the site comes from analysis/*.py so the pages cannot drift
from the models. Charts are rendered client-side by web/charts.js from JSON
embedded in each page.
"""
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "analysis"))

import das_inputs        # noqa: E402
import link_budget       # noqa: E402
import mass_budget       # noqa: E402
import orbit             # noqa: E402
import orbit_lifetime    # noqa: E402
import power_budget      # noqa: E402

OUT = ROOT / "public"
MISSION = "DPI LTM CubeSat"

L = {  # external links
    "ltm": "https://www.amsat.org/amsat-linear-transponder-module/",
    "amsat_status": "https://www.amsat.org/amsat-project-status/",
    "amsat": "https://www.amsat.org/",
    "foxtelem": "https://www.amsat.org/foxtelem-software-for-windows-mac-linux/",
    "foxtelem_src": "https://github.com/ac2cz/FoxTelem",
    "fc": "https://github.com/dpiresearch/claude_flight_board/tree/main/hardware/FC_V5d_LTM_mods_20261010",
    "fc_repo": "https://github.com/dpiresearch/claude_flight_board",
    "fc_fw": "https://github.com/dpiresearch/claude_flight_board/tree/main/firmware",
    "battery": "https://github.com/proveskit/battery_board/tree/main/battery_pack_v2",
    "antenna": "https://github.com/proveskit/antenna-board/tree/main/antenna_top_cap_v2c",
    "solar": "https://github.com/proveskit/solar_boards/tree/main/XY_Faces_V2a",
    "proves": "https://github.com/proveskit",
    "proves_docs": "https://github.com/proveskit/Documentation",
    "proves_fc": "https://github.com/proveskit/flight_controller_board",
    "pysquared": "https://github.com/proveskit/pysquared",
    "proves_das": "https://github.com/proveskit/The-PROVES-Project-DAS",
    "das": "https://orbitaldebris.jsc.nasa.gov/mitigation/debris-assessment-software.html",
    "das_guide": "https://orbitaldebris.jsc.nasa.gov/library/das/DAS3.2_UsersGuide.pdf",
    "fcc_5yr": "https://docs.fcc.gov/public/attachments/FCC-22-74A1.pdf",
    "iaru": "https://www.iaru.org/reference/satellites/",
    "iaru_status": "https://iaru.amsat-uk.org/",
    "site_src": "https://github.com/dpiresearch/sat_mission_20261025",
}

NAV = [("index.html", "Mission"), ("spacecraft.html", "Spacecraft"), ("mockup.html", "3D mockup"),
       ("conops.html", "ConOps"), ("power.html", "Power budget"), ("link.html", "Link budget"),
       ("das.html", "Debris (DAS)"), ("resources.html", "Resources"), ("ask.html", "Ask AI")]


def chat_api_url():
    """Function URL of the chatbot Lambda, recorded by deploy/deploy_chat.sh."""
    if os.environ.get("CHAT_API"):
        return os.environ["CHAT_API"]
    st = ROOT / "deploy" / "chat_state.env"
    if st.exists():
        for line in st.read_text().splitlines():
            if line.startswith("CHAT_URL="):
                return line.split("=", 1)[1].strip()
    return ""


def esc(s):
    return html.escape(str(s))


def a(key, text=None):
    return f'<a href="{L[key]}">{esc(text or L[key])}</a>'


def page(fname, title, body, has_charts=False, head_extra=""):
    nav = "".join(f'<a href="{h}"{" class=\"active\"" if h == fname else ""}>{t}</a>' for h, t in NAV)
    script = '<script src="charts.js" defer></script>' if has_charts else ""
    api = chat_api_url()
    if api:
        script += f'<script>window.CHAT_API = {json.dumps(api)};</script><script src="chat.js" defer></script>'
    script += head_extra
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {MISSION}</title>
<meta name="description" content="{MISSION}: a 1U PROVES-based CubeSat flying the AMSAT Linear Transponder Module.">
<link rel="stylesheet" href="styles.css">
{script}
</head>
<body>
<header class="site"><div class="inner">
<a class="brand" href="index.html">🛰️ {MISSION}</a>
<nav>{nav}</nav>
</div></header>
<main>
{body}
</main>
<footer class="site"><div class="inner">
DPI Research · AMSAT · Arrow Technologies of Texas — a PROVES Kit 1U CubeSat carrying the AMSAT Linear Transponder Module.
Analyses are engineering estimates for planning; see each page for assumptions. Site source: {a("site_src")}.
</div></footer>
</body>
</html>
"""
    (OUT / fname).write_text(doc)


def table(headers, rows, num_cols=(), classes=None):
    th = "".join(f'<th class="num">{esc(h)}</th>' if i in num_cols else f"<th>{esc(h)}</th>"
                 for i, h in enumerate(headers))
    trs = []
    for ri, r in enumerate(rows):
        cls = f' class="{classes[ri]}"' if classes and classes[ri] else ""
        tds = "".join(f'<td class="num">{c}</td>' if i in num_cols else f"<td>{c}</td>"
                      for i, c in enumerate(r))
        trs.append(f"<tr{cls}>{tds}</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'


def stat(label, value, sub=""):
    return f'<div class="stat"><div class="label">{esc(label)}</div><div class="value">{value}</div><div class="sub">{sub}</div></div>'


_chart_id = [0]


def chart(kind, title, subtitle, spec, table_html=""):
    _chart_id[0] += 1
    cid = f"chart{_chart_id[0]}"
    data = json.dumps(spec, separators=(",", ":"))
    tbl = f"<details><summary>Show data table</summary>{table_html}</details>" if table_html else ""
    return (f'<figure class="chart" data-chart="{kind}" data-src="{cid}">'
            f'<figcaption><div class="title">{esc(title)}</div><div class="subtitle">{esc(subtitle)}</div></figcaption>'
            f'<script type="application/json" id="{cid}">{data}</script>{tbl}</figure>')


def badge(ok, text=None):
    if ok is True:
        return f'<span class="badge good">✓ {text or "Pass"}</span>'
    if ok is None:
        return f'<span class="badge warn">◐ {text or "TBC"}</span>'
    return f'<span class="badge bad">✗ {text or "Fail"}</span>'


# ======================================================================= pages
def build_index(ctx):
    pb, lb, lt = ctx["power"], ctx["link"], ctx["life"]
    life525 = next(r for r in lt["table"] if r["alt_km"] == 525)["cycle_tumble"]
    body = f"""
<section class="hero">
<div class="kicker">1U CubeSat · Amateur-radio linear transponder · Launch target Nov 2027</div>
<h1>Flying the AMSAT Linear Transponder Module on a PROVES Kit 1U</h1>
<p class="lede">{MISSION} puts AMSAT's flight-proven V/u <b>Linear Transponder Module (LTM-1)</b> on an open-source
<b>PROVES Kit</b> 1U bus, with a modified PROVES V5d flight controller that drives the LTM over CAN. When it's in orbit, amateur radio
operators around the world will be able to make SSB and CW contacts through a 30 kHz passband. The 1200 bps BPSK
telemetry beacon will be received by the global FoxTelem ground network.</p>
</section>

<div class="stats">
{stat("Form factor", "1U", f"{ctx['mass']['mev_kg']:.2f} kg MEV (limit 2.0 kg)")}
{stat("Payload", "AMSAT LTM", "V/u linear transponder, 30 kHz")}
{stat("Orbit (TBC)", f"{pb['alt_km']:.0f} km SSO", f"{orbit.sso_inclination_deg(pb['alt_km']):.1f}° · {pb['period_min']:.1f} min period")}
{stat("Launch", "Transporter-22", "SpaceX rideshare · Nov 2027 (target)")}
{stat("Orbit-avg power", f"{pb['gen_avg_w']:.2f} W", "EOL, tumbling, worst-case β = 0°")}
{stat("Orbital lifetime", f"~{life525:.0f} yr", "at 525 km; DAS-calibrated estimate")}
</div>

<h2>Mission objectives</h2>
<ol>
<li><b>Demonstrate the AMSAT LTM on an open-source university bus.</b> The LTM's command, telemetry and transponder functions run on a PROVES Kit spacecraft instead of an AMSAT Fox bus.</li>
<li><b>Provide a public V/u linear transponder</b> (SSB/CW, 30 kHz passband) for the worldwide amateur-satellite community.</li>
<li><b>Return health and science telemetry</b> on a 1200 bps BPSK beacon decoded by {a("foxtelem", "FoxTelem")}, including host temperatures and bus data that the flight controller sends to the LTM over CAN.</li>
<li><b>Validate the FC V5d LTM interface board</b> (CAN, switched 5 V LTM supply, umbilical and telemetry lines) as a reusable path for other PROVES users who want to fly the LTM.</li>
</ol>

<h2>Explore the mission</h2>
<div class="grid">
<a class="card" href="spacecraft.html"><h3>Spacecraft →</h3><p>Subsystems, open-source hardware, mass budget and open design items.</p></a>
<a class="card" href="conops.html"><h3>Concept of operations →</h3><p>The mission from integration and launch through deployment, commissioning, transponder operations and reentry.</p></a>
<a class="card" href="power.html"><h3>Power budget →</h3><p>Solar generation, mode-by-mode loads, battery state of charge, and how much transponder time the bus can sustain.</p></a>
<a class="card" href="link.html"><h3>Link budget →</h3><p>Telemetry, transponder and command links for portable and fixed ground stations, plus Doppler.</p></a>
<a class="card" href="das.html"><h3>Debris assessment (DAS) →</h3><p>Orbital lifetime, NASA-STD-8719.14 compliance and the FCC 5-year rule, with a DAS project ready to open.</p></a>
<a class="card" href="resources.html"><h3>Resources →</h3><p>GitHub repositories, AMSAT pages, PROVES documentation and regulatory references.</p></a>
</div>

<h2>Partners</h2>
<div class="grid">
<div class="card"><h3>DPI Research</h3><p>Mission lead. Owns spacecraft integration, the LTM flight-controller interface and mission analysis.</p></div>
<div class="card"><h3>AMSAT</h3><p>Supplies the Linear Transponder Module, its flight software and ground tools, plus command-station support. {a("ltm", "LTM page")}</p></div>
<div class="card"><h3>Arrow Technologies of Texas</h3><p>Engineering support through design, integration and launch.</p></div>
<div class="card"><h3>PROVES Kit (Bronco Space, Cal Poly Pomona)</h3><p>Open-source 1U structure, battery, solar and antenna boards. {a("proves", "github.com/proveskit")}</p></div>
</div>

<h2>Timeline</h2>
<ul class="timeline">
<li><div class="when">2026</div><div class="what">MOU signed between DPI Research and AMSAT; FC V5d LTM interface design (Oct 2026).</div></li>
<li><div class="when">2026 – 2027</div><div class="what">Board layout and routing, FlatSat with the LTM, flight software, IARU coordination and FCC filing, environmental test.</div></li>
<li><div class="when">2027</div><div class="what">Final integration, AMSAT LTM acceptance testing, delivery to the dispenser provider.</div></li>
<li><div class="when">Nov 2027</div><div class="what">Launch on SpaceX Transporter-22 (target).</div></li>
<li><div class="when">Post-launch</div><div class="what">Commissioning, then transponder operations for the amateur community until reentry.</div></li>
</ul>
"""
    page("index.html", "Mission overview", body)


def build_spacecraft(ctx):
    mb = ctx["mass"]
    pb = ctx["power"]
    rows = [[esc(r["name"]), r["qty"], f"{r['unit_kg']*1000:.1f}", f"{r['total_kg']*1000:.1f}", esc(r["source"])]
            for r in mb["rows"]]
    rows.append(["<b>Current best estimate</b>", "", "", f"<b>{mb['cbe_kg']*1000:.0f}</b>", ""])
    rows.append([f"Contingency ({mb['contingency']*100:.0f} %)", "", "", f"{(mb['mev_kg']-mb['cbe_kg'])*1000:.0f}", ""])
    rows.append(["<b>Maximum expected value</b>", "", "", f"<b>{mb['mev_kg']*1000:.0f}</b>", f"CDS 1U limit {mb['limit_kg']*1000:.0f} g"])
    cls = [None] * len(mb["rows"]) + ["total", None, "total"]
    body = f"""
<section class="hero"><div class="kicker">Spacecraft</div>
<h1>A PROVES Kit 1U bus with an AMSAT LTM payload</h1>
<p class="lede">The spacecraft is built almost entirely from open-source PROVES Kit hardware. The one custom board is a
PROVES V5d flight controller with its on-board radios removed and replaced by an interface to the LTM.</p></section>

<h2>Subsystems</h2>
<div class="grid">
<div class="card"><h3>Payload: AMSAT LTM</h3>
<p>A V/u linear transponder (SSB/CW, 30 kHz passband) with a 1200 bps BPSK telemetry beacon and a command receiver.
It is a three-board PC-104 stack (transponder at the bottom, the ICR command receiver in the middle, and the LTI host interface on top), 92 × 90 × 33 mm, 130 g, running on 5–7 V.
It has flight heritage on HuskySat-1, Fox-1E and MESAT1.</p><p>{a("ltm", "amsat.org → LTM")}</p></div>
<div class="card"><h3>Flight controller: FC V5d LTM</h3>
<p>RP2350 running CircuitPython, with an LSM6DSO IMU, LIS2MDL magnetometer, RTC and SD NAND. The RFM98/E28 radios are replaced by an
MCP25625 CAN controller (1 Mbit/s) and a switched 5 V LTM supply that stays off at boot and is enabled after
antenna deployment. The board also carries umbilical sense, console and telemetry lines and a host temperature sensor.</p>
<p>{a("fc", "FC_V5d_LTM_mods_20261010")} · {a("fc_fw", "firmware / ltm1 driver")}</p></div>
<div class="card"><h3>EPS</h3>
<p>The EPS sits on the flight controller: an LT3652 2S solar charger (8.38 V float, 1 A), a TPS54226 3.3 V rail, the TPS54225 5 V
LTM rail, INA219 battery and solar monitors, per-face load switches, and TPS4H160 burn-wire and heater drivers.</p></div>
<div class="card"><h3>Battery pack v2</h3>
<p>Four 18650 Li-ion cells in 2S2P (NCR18650B class, about {pb['battery_bol_wh']:.0f} Wh at 7.2 V), with an R5460 2-cell protector,
back-to-back FETs and four TMP112 temperature sensors.</p><p>{a("battery", "battery_pack_v2")}</p></div>
<div class="card"><h3>Solar: XY Faces V2a</h3>
<p>Six KXOB101K08TF mono-Si cells per face in 2s3p, with Schottky-isolated strings. Each panel also carries a
MCP9808 temperature sensor, a VEML7700 light sensor and a DRV2605L-driven PCB magnetorquer coil.
About {pb['solar']['face_am0_w']:.1f} W per face at normal incidence (AM0, BOL).</p><p>{a("solar", "XY_Faces_V2a")}</p></div>
<div class="card"><h3>Antenna top cap v2c</h3>
<p>A +Z endcap with burn-wire-released tape-measure elements, a CSD17576 burn FET, a balun, an MMCX feed and
sun/temperature sensors.</p><p>{a("antenna", "antenna_top_cap_v2c")}</p></div>
<div class="card"><h3>Structure</h3>
<p>The PROVES 1U frame is made of 1.6 mm 5052 aluminium sheet with PA-12 feet, M2.5 self-clinching fasteners and normally-closed
deployment switches. It has been vibration-tested to 20 g RMS and thermally cycled.</p><p>{a("proves_docs", "PROVES documentation")}</p></div>
<div class="card"><h3>ADCS</h3>
<p>Passive and magnetic. B-dot detumble uses the face PCB coils and the torque rods/air coil from the PROVES build. No pointing is
required: the transponder and beacon work while the spacecraft tumbles, at the cost of the antenna-null allowance in the link budget.</p></div>
</div>

<h2>System block diagram</h2>
<div class="table-wrap" style="padding:1rem"><pre class="mono" style="margin:0;line-height:1.35">
 Solar faces x5 ──(2s3p, Schottky OR)──► LT3652 charger ──► 2S2P 18650 pack (6.0–8.4 V, VBUSP)
                                                                │
          ┌──────────────────────── FC V5d LTM ─────────────────┼─────────────────────────┐
          │  TPS54226 ─► +3V3 ─► RP2350, IMU, mag, RTC, SD, MCP23017, sensors            │
          │  TPS54225 ─► LTM_VSYS 5 V  (EN = MCP23017 GPB6, forced on by USB umbilical)  │
          │  MCP25625 ─► CAN 1 Mbit/s ─────────────┐                                      │
          │  TPS4H160 ─► burn wire, heater          │   I2C (LTM master) ─► MAX31725      │
          └────────────────────────────────────────┼──────────────────────────────────────┘
                                                   ▼  J30 harness
                                   AMSAT LTM-1 (LTI · ICR · Transponder)
                                    │ 2 m RX (uplink)      │ 70 cm TX (downlink)
                                    ▼                      ▼
                          V-band element (TBD)      Antenna top cap v2c
</pre></div>

<h2>Mass budget</h2>
<p>This budget is derived from the PROVES Atlas DAS component list ({a("proves_das", "The-PROVES-Project-DAS")}),
with the PROVES payload board and camera replaced by the LTM and its harness.</p>
{table(["Component", "Qty", "Unit (g)", "Total (g)", "Source"], rows, num_cols=(1, 2, 3), classes=cls)}

<h2>Open design items</h2>
<div class="callout warn">
<p><b>1. V-band (2 m) receive antenna.</b> The antenna top cap's tape elements are about 0.18 m long, which is a 70 cm quarter-wave.
The LTM's uplink is in the 144 MHz band and needs its own element (about 0.5 m quarter-wave) or a diplexed dual-band arrangement.
The link budget assumes a dedicated V-band monopole.</p>
<p><b>2. Charger operating point.</b> The LT3652 input-regulation threshold (about 8.44 V) and startup headroom need to be checked
on the bench against the 2S panel's V<sub>mp</sub> and V<sub>oc</sub> at hot and cold temperatures. The power budget carries a 10 % operating-point loss for this.</p>
<p><b>3. FC V5d LTM layout.</b> Parts are placed but not routed (87 ratsnest connections). The J30–LTM harness has not been designed yet.</p>
<p><b>4. LTM interface details.</b> CAN termination, the host temperature-sensor address and health-message encoding all need to be confirmed with AMSAT.
The interface follows AMSAT's partner documentation, which is not reproduced on this site.</p>
<p><b>5. Part-number reconciliation.</b> The solar cell part (KXOB101K08TF vs SM101K07TF) and the battery protector variant differ between
README, schematic and footprint in the source repositories.</p>
</div>
"""
    page("spacecraft.html", "Spacecraft", body)


def build_conops(ctx):
    pb, lb = ctx["power"], ctx["link"]
    alt = pb["alt_km"]
    passes = orbit.pass_duration_min(alt, 10)
    fp = orbit.footprint_radius_km(alt, 0)
    tp_min_day = pb["max_tp_duty_beta0"] * 1440
    life = next(r for r in ctx["life"]["table"] if r["alt_km"] == 525)["cycle_tumble"]
    phases = [
        ("0 · Integration & test", "Pre-launch",
         "FlatSat with the LTM on the bench, powered from the USB umbilical (which forces LTM_VSYS on). AMSAT's LTM acceptance "
         "test procedure is run, followed by flight-software qualification of the ltm1 CAN driver and environmental tests "
         "(random vibration, thermal vacuum and thermal cycling). The spacecraft is delivered with its RBF pin and with the deployment switches holding it powered off."),
        ("1 · Launch", "L-0",
         "Integrated in a 1U slot of a rideshare dispenser on SpaceX Transporter-22. Deployment switches and inhibits keep the "
         "battery disconnected, so there is no RF and no power during ascent."),
        ("2 · Deployment & quiet period", "T+0 → T+30 min",
         "The deployment switches close and the RP2350 boots. It logs the boot count, starts the RTC and keeps the LTM rail OFF "
         "(R125 pull-down). No deployables fire and no RF is transmitted for 30 minutes. Magnetic B-dot detumble starts using the face coils."),
        ("3 · Antenna deployment", "T+30 min",
         "The burn wire is fired through the TPS4H160 DEPLOY channel (about 1–2 A for a few seconds). The deployment flag is set in "
         "non-volatile memory. If the first burn fails, the software retries on later orbits with a sunlit-battery check."),
        ("4 · LTM power-on & first beacon", "T+45 min",
         "Flight software enables LTM_VSYS through MCP23017 GPB6, which is allowed only once antennas are deployed. The LTM boots in "
         "safe mode and starts its 1200 bps BPSK telemetry beacon. The FC begins sending health data (temperatures, UTC) over CAN."),
        ("5 · Commissioning", "Week 1 – 4",
         "The AMSAT command station checks LTM and bus health. FoxTelem stations worldwide upload frames to the AMSAT "
         "telemetry server. Team members verify the power and thermal trends against this site's budgets, then run short scheduled transponder tests."),
        ("6 · Nominal operations", "Month 1 → EOL",
         f"The beacon runs continuously. The transponder is power-limited to about {pb['max_tp_duty_beta0']*100:.0f}–"
         f"{pb['max_tp_duty_vs_beta'][9][1]:.0f} % duty (about {tp_min_day:.0f} min/day at β = 0°). It is scheduled over "
         "high-demand regions (North America, Europe, Japan) and weekend events, with a battery-gated fallback "
         "(ON above 80 % state of charge, OFF below 70 %)."),
        ("7 · Safe mode", "Any time",
         "Triggered by low state of charge, a watchdog reset, an over- or under-temperature condition or a ground command. The LTM drops to safe mode "
         "(40 mA), the FC slows its clock, and the battery heater is thermostatic. Recovery is by ground command once the battery has charged."),
        ("8 · End of mission & disposal", f"~{life:.0f} yr at {alt:.0f} km",
         "On ground command the LTM transmitter is permanently disabled (FCC requires the ability to cease emissions). "
         "The spacecraft decays passively, and DAS shows every component demises on reentry."),
    ]
    tl = "".join(f'<li><div class="when">{esc(n)} <span class="badge good" style="margin-left:.4rem">{esc(t)}</span></div>'
                 f'<div class="what">{esc(d)}</div></li>' for n, t, d in phases)
    modes = pb["modes"]
    mode_cards = "".join(f'<div class="mode"><b>{esc(k)}</b><span>{v["total_w"]:.2f} W orbit-avg load</span></div>'
                         for k, v in modes.items())
    body = f"""
<section class="hero"><div class="kicker">Concept of operations</div>
<h1>From the dispenser to a public linear transponder</h1>
<p class="lede">The spacecraft tumbles freely and needs no pointing. Operations come down to managing energy: the beacon runs all the time,
and the transponder is scheduled for when and where operators want it.</p></section>

<div class="stats">
{stat("Orbit (TBC)", f"{alt:.0f} km SSO", f"{orbit.sso_inclination_deg(alt):.1f}° incl · {pb['period_min']:.1f} min")}
{stat("Longest pass ≥10°", f"{passes:.0f} min", f"footprint radius {fp:.0f} km at 0°")}
{stat("Eclipse (β=0°)", f"{pb['eclipse_min']:.0f} min", "per orbit, worst case")}
{stat("Transponder time", f"~{tp_min_day:.0f} min/day", "power-limited, β = 0° worst case")}
</div>

<h2>Mission phases</h2>
<ul class="timeline">{tl}</ul>

<h2>Operating modes</h2>
<div class="modes">{mode_cards}</div>
<p>Mode transitions are owned by the FC flight software. The LTM's own mode is requested over CAN, and AMSAT ground commands to the LTM
can override it. See the <a href="power.html">power budget</a> for line-item loads.</p>

<h2>Ground segment</h2>
<div class="grid">
<div class="card"><h3>AMSAT command station(s)</h3><p>High-gain stations uplink commands to the LTM command receiver (20 kHz FSK). This link has
more than {ctx['link']['tables'][3]['margin_db']:.0f} dB margin at 10° elevation.</p></div>
<div class="card"><h3>FoxTelem network</h3><p>Volunteer stations decode the 1200 bps BPSK beacon with {a("foxtelem", "FoxTelem")} and forward
frames to AMSAT's server, so coverage is global rather than limited to a single team ground station.</p></div>
<div class="card"><h3>Amateur users</h3><p>Users work SSB and CW through the 30 kHz V/u passband. Uplink Doppler is ±{lb['doppler_up_khz']:.1f} kHz and downlink
±{lb['doppler_dn_khz']:.1f} kHz, so full-duplex Doppler tracking (for example with SatPC32 or Gpredict) is recommended.</p></div>
<div class="card"><h3>Mission team</h3><p>Reviews telemetry trends, plans transponder schedules and coordinates with AMSAT operations.</p></div>
</div>

<h2>Licensing & coordination</h2>
<ul>
<li>IARU amateur-satellite frequency coordination ({a("iaru", "iaru.org")}, {a("iaru_status", "status")}).</li>
<li>FCC Part 97 amateur space station notification, with an Orbital Debris Assessment Report built from <a href="das.html">DAS</a>.</li>
<li>The launch-provider ICD and dispenser compliance (CubeSat Design Specification rev 14.1).</li>
</ul>
"""
    page("conops.html", "Concept of operations", body)


def build_power(ctx):
    pb = ctx["power"]
    s = pb["solar"]
    md = pb["modes"]
    names = list(md.keys())
    comp = ["FC + sensors", "LTM", "Magnetorquers", "Heater"]
    bar_spec = {"categories": names, "unit": "W", "dp": 2,
                "series": [{"name": c, "slot": i, "values": [round(md[n]["items"][c], 3) for n in names]}
                           for i, c in enumerate(comp)],
                "stacked": True, "left": 190, "xlabel": "Battery-side power (W)",
                "vrefs": [{"x": round(pb["gen_avg_w"], 3), "label": f"Generation {pb['gen_avg_w']:.2f} W"}]}
    gen_line = round(pb["gen_avg_w"], 3)
    # stacked would be better but keep grouped; add generation as text
    def balance(n):
        d = pb["gen_avg_w"] - md[n]["total_w"]
        return badge(True, f"+{d:.2f} W") if d >= 0 else badge(False, f"{d:.2f} W deficit")
    mode_rows = [[esc(n)] + [f"{md[n]['items'][c]:.3f}" for c in comp] + [f"<b>{md[n]['total_w']:.3f}</b>", balance(n)]
                 for n in names]
    loss_rows = [[esc(k), f"{v:.2f}"] for k, v in pb["losses"].items()] + [["<b>Combined</b>", f"<b>{s['eta']:.3f}</b>"]]
    fc_rows = [[esc(n), f"{c*1000:.1f}", f"{c*3.3*1000:.1f}", src] for n, c, src in pb["fc_loads"]]
    ltm_rows = [[esc(k), f"{v*1000:.0f}", f"{v*5*1000:.0f}"] for k, v in pb["ltm_modes_a"].items() if v > 0]

    beta_spec = {"series": [{"name": "Orbit-average generation", "points": [[b, g] for b, g, _ in pb["gen_vs_beta"]], "area": True,
                             "endLabel": f"{pb['gen_vs_beta'][-1][1]:.2f} W"}],
                 "refs": [{"y": round(md["Beacon (telemetry only)"]["total_w"], 3), "label": "Beacon-mode load"}],
                 "xlabel": "Beta angle (deg)", "ylabel": "W", "yunit": "W", "ydp": 2, "xdp": 0, "ymin": 0, "xmin": 0, "xmax": 90}
    duty_spec = {"series": [{"name": "Max sustained transponder duty", "points": pb["max_tp_duty_vs_beta"],
                             "endLabel": f"{pb['max_tp_duty_vs_beta'][-1][1]:.0f} %"}],
                 "xlabel": "Beta angle (deg)", "ylabel": "% of time", "yunit": "%", "ydp": 1, "xdp": 0, "ymin": 0, "xmin": 0, "xmax": 90}

    def soc_series(sim, name, slot):
        return {"name": name, "slot": slot, "points": [[h[0], h[1]] for h in sim["history"]],
                "endLabel": f"β={sim['beta']}°"}
    soc_spec = {"series": [soc_series(pb["soc_beta0"], "SoC, β = 0°", 0), soc_series(pb["soc_beta45"], "SoC, β = 45°", 1)],
                "refs": [{"y": 80, "label": "TP on > 80 %"}, {"y": 70, "label": "TP off < 70 %"}],
                "xlabel": "Hours", "ylabel": "State of charge (%)", "yunit": "%", "ydp": 1, "xdp": 1, "ymin": 60, "ymax": 85}

    body = f"""
<section class="hero"><div class="kicker">Power budget</div>
<h1>The beacon can run continuously; the transponder needs scheduling</h1>
<p class="lede">The spacecraft is a tumbling 1U with body-mounted silicon cells on five faces, so energy is the limiting
resource. The 48 Wh battery is large compared with any single eclipse. What limits operations is the orbit-average
energy balance.</p></section>

<div class="stats">
{stat("Orbit-avg generation", f"{pb['gen_avg_w']:.2f} W", "EOL, tumbling, β = 0°")}
{stat("Beacon-mode load", f"{md['Beacon (telemetry only)']['total_w']:.2f} W", badge(md['Beacon (telemetry only)']['total_w'] < pb['gen_avg_w'], 'Positive balance'))}
{stat("Transponder load", f"{md['Transponder (typical load)']['total_w']:.2f} W", f"{md['Transponder (max load)']['total_w']:.2f} W at max LTM current")}
{stat("Max transponder duty", f"{pb['max_tp_duty_beta0']*100:.1f} %", f"β = 0° · {pb['max_tp_duty_vs_beta'][9][1]:.1f} % at β = 45°")}
{stat("Battery", f"{pb['battery_eol_wh']:.1f} Wh", f"EOL (80 % of {pb['battery_bol_wh']:.1f} Wh BOL)")}
{stat("Eclipse DoD", f"{pb['eclipse_dod_tp_max']*100:.1f} %", f"transponder at max load; limit {pb['max_dod']*100:.0f} %")}
</div>

<h2>1. Solar generation</h2>
<p>Each face carries {power_budget.CELLS_PER_FACE} cells at about {power_budget.CELL_PMP_AM15_W:.2f} W (AM1.5), giving
<b>{s['face_am0_w']:.2f} W per face at AM0</b>. The cells are on five faces (±X, ±Y, −Z); +Z is the antenna cap. For a randomly
tumbling cube each face averages |cos θ| = ¼, so the mean sunlit input is {power_budget.TUMBLE_FACE_EQ:.2f} face-equivalents =
<b>{s['sunlit_raw_w']:.2f} W</b> before losses.</p>
{table(["Loss factor", "Multiplier"], loss_rows, num_cols=(1,))}
<p>The net sunlit power into the battery is <b>{s['sunlit_net_w']:.2f} W</b>. At {pb['alt_km']:.0f} km the orbit period is {pb['period_min']:.1f} min,
and the worst-case eclipse (β = 0°) is {pb['eclipse_min']:.1f} min ({pb['eclipse_frac']*100:.0f} %), giving an orbit-average of <b>{pb['gen_avg_w']:.2f} W</b>.</p>
{chart("line", "Orbit-average generation vs beta angle", f"{pb['alt_km']:.0f} km circular orbit, tumbling, EOL. Above about 68° the orbit is in full sun.", beta_spec,
       table(["β (deg)", "Generation (W)", "Eclipse fraction"], [[b, f"{g:.3f}", f"{f:.3f}"] for b, g, f in pb["gen_vs_beta"]], num_cols=(0, 1, 2)))}

<h2>2. Loads by operating mode</h2>
{chart("bar", "Orbit-average load by mode and subsystem", f"Battery-side watts, including regulator efficiency. Orbit-average generation is {gen_line:.2f} W.", bar_spec)}
{table(["Mode"] + comp + ["Total (W)", "Continuous-use balance"], mode_rows, num_cols=(1, 2, 3, 4, 5))}

<h3>Flight controller 3.3 V loads (datasheet-typical)</h3>
{table(["Load", "mA @ 3.3 V", "mW", "Source"], fc_rows, num_cols=(1, 2))}
<p>The 3.3 V rail comes from the TPS54226 at {pb['regulators']['3V3']*100:.0f} % efficiency (Eco-mode). The magnetorquers add an estimated
{pb['mtq_w']:.2f} W during detumble only. The battery heater ({pb['heater'][0]:.1f} W element) is budgeted at {pb['heater'][1]*100:.0f} % duty in safe and cold cases.</p>

<h3>LTM supply current (public AMSAT figures, 5 V LTM_VSYS)</h3>
{table(["LTM mode", "mA", "mW at LTM"], ltm_rows, num_cols=(1, 2))}
<p>The beacon figure is a 310 mA transmit current at about 11 % duty over a 40 mA baseline. Transponder current is 300–650 mA depending
on uplink loading. The TPS54225 rail is modelled at {pb['regulators']['5V_light']*100:.0f} % efficiency at light load and
{pb['regulators']['5V_heavy']*100:.0f} % at heavy load (forced-CCM part).</p>

<h2>3. How much transponder time?</h2>
{chart("line", "Maximum sustainable transponder duty vs beta angle", "Fraction of time the transponder can be on, with the beacon on the rest of the time, at zero net energy per orbit", duty_spec,
       table(["β (deg)", "Max duty (%)"], pb["max_tp_duty_vs_beta"], num_cols=(0, 1)))}
{chart("line", "Battery state of charge under a battery-gated transponder policy", f"Transponder ON above 80 %, back to beacon below 70 %. Achieved duty: {pb['soc_beta0']['transponder_duty']*100:.1f} % at β = 0°, {pb['soc_beta45']['transponder_duty']*100:.1f} % at β = 45°.", soc_spec)}

<div class="callout">
<p><b>Result.</b> At worst case the transponder can run about <b>{pb['max_tp_duty_beta0']*1440:.0f} minutes per day</b>.
That's enough for roughly {pb['max_tp_duty_beta0']*1440/10:.0f} ten-minute passes over high-demand regions. Commanded or battery-gated scheduling is
required. Ways to increase transponder time:</p>
<ul>
<li>Triple-junction cells (about 29 % vs about 22 % for Si) would add about 30 %.</li>
<li>Higher-β orbits (dawn-dusk SSO) give up to {pb['max_tp_duty_vs_beta'][-1][1]:.0f} % duty.</li>
<li>Cells on the +Z cap.</li>
<li>Reducing LTM output power at low uplink load.</li>
</ul>
</div>

<h2>Assumptions to verify</h2>
<ul>
<li>The cell P<sub>mp</sub> of the KXOB101K08TF (datasheet) and a measured face I-V curve under AM0-equivalent light.</li>
<li>The LT3652 operating point with a 2S face (see <a href="spacecraft.html">open items</a>).</li>
<li>LTM current in each mode, measured on the FlatSat through the FC's TLM3 (LTM_VSYS) channel and INA219.</li>
<li>The orbit and LTAN from the Transporter-22 manifest, which set the β-angle history.</li>
</ul>
<p>Model source: <code>analysis/power_budget.py</code>.</p>
"""
    page("power.html", "Power budget", body, has_charts=True)


def build_link(ctx):
    lb = ctx["link"]
    tables = ""
    for t in lb["tables"]:
        rows = [[esc(n), v, esc(u)] for n, v, u in t["rows"]]
        ok = t["margin_db"] >= 3
        rows.append(["<b>Link margin</b>", f"<b>{t['margin_db']:.1f}</b>",
                     "dB " + badge(ok if t["margin_db"] >= 0 else False,
                                   "≥ 3 dB" if ok else ("marginal" if t["margin_db"] >= 0 else "below threshold"))])
        tables += f"<h3>{esc(t['title'])} — {esc(t['station'])}, 10° elevation</h3>"
        tables += table(["Parameter", "Value", "Unit"], rows, num_cols=(1,), classes=[None] * (len(rows) - 1) + ["total"])
    names = list(lb["curves"].keys())
    spec = {"series": [{"name": n, "slot": i, "points": lb["curves"][n], "endLabel": f"{lb['curves'][n][-1][1]:.0f} dB"} for i, n in enumerate(names)],
            "refs": [{"y": 3, "label": "3 dB design margin"}, {"y": 0, "label": "threshold"}],
            "xlabel": "Elevation (deg)", "ylabel": "Margin (dB)", "yunit": "dB", "ydp": 1, "xdp": 0, "ymin": -8, "xmin": 0, "xmax": 90,
            "height": 360}
    curve_rows = [[e] + [f"{lb['curves'][n][i][1]:.1f}" for n in names] for i, (e, _) in enumerate(lb["curves"][names[0]])]
    st_rows = [[esc(n), f"{s['up_w']:.0f}", f"{s['up_gain']:.1f}", f"{s['dn_gain']:.1f}", f"{s['tsys_dn']:.0f}"]
               for n, s in lb["stations"].items()]
    body = f"""
<section class="hero"><div class="kicker">Link budget</div>
<h1>V/u transponder, telemetry beacon and command links</h1>
<p class="lede">The links are computed for a {lb['alt_km']:.0f} km orbit with a tumbling spacecraft and linear antennas. A fixed station
closes every link with margin. A portable Yagi station works best above about 30° elevation, which matches the
experience on earlier 1U linear-transponder missions.</p></section>

<div class="stats">
{stat("Uplink (2 m)", f"{lb['f_up']:.3f} MHz", "representative, pending IARU")}
{stat("Downlink (70 cm)", f"{lb['f_dn']:.3f} MHz", "representative, pending IARU")}
{stat("Per-user downlink", f"{lb['per_user_mw']:.0f} mW", f"350 mW transponder share ÷ {lb['users']} users")}
{stat("SSB end-to-end @10°", f"{lb['e2e_fixed_10']:+.1f} dB", f"fixed station · portable {lb['e2e_portable_10']:+.1f} dB")}
{stat("Doppler (max)", f"±{lb['doppler_dn_khz']:.1f} kHz", f"downlink · uplink ±{lb['doppler_up_khz']:.1f} kHz")}
</div>

<h2>Margin vs elevation</h2>
{chart("line", "Link margin vs elevation", "Telemetry (BPSK 1200) downlink and end-to-end SSB through the transponder (uplink and downlink combined)", spec,
       table(["Elevation (deg)"] + names, curve_rows, num_cols=tuple(range(len(names) + 1))))}

<h2>Line-item budgets</h2>
{tables}

<h2>Ground station classes</h2>
{table(["Station", "Uplink (W)", "2 m gain (dBi)", "70 cm gain (dBi)", "Downlink Tsys (K)"], st_rows, num_cols=(1, 2, 3, 4))}

<h2>Assumptions</h2>
<ul>
<li><b>Spacecraft RF</b> ({a("ltm", "AMSAT LTM")}): 100 mW telemetry only, 450 mW telemetry plus transponder. The transponder's
350 mW is shared among {lb['users']} simultaneous SSB users.</li>
<li><b>Spacecraft antennas:</b> −3 dBi effective for a tumbling monopole or dipole (an allowance for pattern nulls) and 1 dB line loss.
The 2 m element is TBD (see <a href="spacecraft.html">open items</a>).</li>
<li><b>Spacecraft receive noise:</b> {link_budget.SC_RX_TSYS_K:.0f} K for an Earth-facing VHF antenna (about 290 K Earth plus man-made noise) and the LNA.</li>
<li><b>Propagation:</b> 3 dB polarization loss (linear spacecraft vs circular ground, or Faraday fading) and 0.5 dB atmospheric and ionospheric loss.</li>
<li><b>Required SNR:</b> 10 dB in 2.4 kHz for SSB, 6 dB in 500 Hz for CW. BPSK needs E<sub>b</sub>/N<sub>0</sub> of 9.6 dB (uncoded 10⁻⁵) plus 1.5 dB implementation loss.
This is conservative; FoxTelem's FEC improves on it.</li>
<li><b>Ground gains</b> are typical amateur values (handheld 2 m / 70 cm Yagi, crossed Yagis with LNA) and have not been checked against vendor data.</li>
</ul>
<p>Model source: <code>analysis/link_budget.py</code>.</p>
"""
    page("link.html", "Link budget", body, has_charts=True)


def build_das(ctx):
    lt = ctx["life"]
    das = ctx["das"]
    mb = ctx["mass"]
    rows, classes = [], []
    for r in lt["table"]:
        fcc = r["cycle_tumble"] <= 5
        rows.append([r["alt_km"], f"{r['cycle_tumble']:.1f}", f"{r['solarmax_tumble']:.1f}", f"{r['solarmin_tumble']:.1f}",
                     f"{r['cycle_min_area']:.1f}", badge(fcc, "≤ 5 yr") if fcc else badge(False, "> 5 yr"),
                     badge(r["cycle_tumble"] <= 25, "≤ 25 yr") if r["cycle_tumble"] <= 25 else badge(False, "> 25 yr")])
    val_rows = [[esc(v["case"]), f"{v['das_yr']:.3f}", f"{v['model_yr']:.3f}", f"{(v['model_yr']/v['das_yr']-1)*100:+.1f} %"]
                for v in lt["validation"]]
    prof = lt["profiles"]
    spec = {"series": [{"name": f"{k} km start", "slot": i, "points": v[::2] + [v[-1]], "endLabel": f"{k} km"} for i, (k, v) in enumerate(prof.items())],
            "vrefs": [{"x": 5, "label": "FCC 5-yr"}],
            "xlabel": "Years after Nov 2027", "ylabel": "Altitude (km)", "yunit": "km", "ydp": 0, "xdp": 1, "ymin": 100, "xmin": 0,
            "height": 340}
    life_spec = {"series": [
        {"name": "Solar-cycle baseline", "slot": 0, "points": [[r["alt_km"], r["cycle_tumble"]] for r in lt["table"]]},
        {"name": "Face-on (min area)", "slot": 1, "points": [[r["alt_km"], r["cycle_min_area"]] for r in lt["table"]]},
        {"name": "Solar max bound", "slot": 2, "points": [[r["alt_km"], r["solarmax_tumble"]] for r in lt["table"]]}],
        "refs": [{"y": 5, "label": "FCC 5-year rule"}],
        "xlabel": "Deployment altitude (km)", "ylabel": "Years to reentry", "yunit": "yr", "ydp": 1, "xdp": 0, "ymin": 0, "ymax": 20, "xmin": 400, "xmax": 600}
    l525 = next(r for r in lt["table"] if r["alt_km"] == 525)
    l475 = next(r for r in lt["table"] if r["alt_km"] == 475)
    reqs = [
        ("4.3-1 / 4.3-2", "Debris released during normal operations", badge(True, "Compliant"),
         "No planned debris release. The antenna elements stay attached, and the burn-wire line remains captive."),
        ("4.4-1 … 4.4-4", "Accidental explosions / intentional breakup", badge(True, "By analysis"),
         "Not evaluated by DAS. The Li-ion cells have a protection IC, back-to-back FETs and a temperature-gated charger. There are no pressure vessels and no propulsion."),
        ("4.5-1", "Collision with large objects (< 0.001)", badge(True, "Compliant (est.)"),
         f"PROVES Atlas DAS result: 5.6 × 10⁻⁹ for 0.66 yr at 417 km. Scaled to {l525['cycle_tumble']:.0f} yr at 525 km with "
         "higher flux, it remains below 10⁻⁶, orders of magnitude under the limit. Re-run in DAS."),
        ("4.5-2", "Small-debris damage preventing disposal", badge(True, "Compliant"),
         "Passive disposal (atmospheric decay) does not depend on a working spacecraft."),
        ("4.6-1", "Disposal within 25 years (NASA-STD-8719.14)", badge(True, "Compliant"),
         f"About {l525['cycle_tumble']:.0f} yr at 525 km and at most {lt['table'][-1]['cycle_tumble']:.0f} yr even at 600 km."),
        ("FCC 22-74", "Disposal within 5 years of end of mission", badge(None, "Altitude-dependent"),
         f"Met for deployment at or below about 475 km ({l475['cycle_tumble']:.1f} yr). Not met at 525 km ({l525['cycle_tumble']:.1f} yr) without a drag device or a lower drop-off."),
        ("4.7-1", "Reentry human casualty risk (< 1:10,000)", badge(True, "Compliant"),
         "PROVES Atlas DAS: every component, including the steel 18650 cans and iron torque rods, demises (68–78 km) with zero casualty area. "
         "The LTM adds only fiberglass PCBs and small parts. Re-run with the component list below."),
    ]
    req_rows = [[f"<b>{esc(a_)}</b>", esc(b_), c_, esc(d_)] for a_, b_, c_, d_ in reqs]
    comp_rows = [[esc(r["name"]), r["qty"], esc(r["material"]), esc(r["body"]), f"{r['unit_kg']:.4f}",
                  " × ".join(f"{d:.4g}" for d in r["dims_m"])] for r in mb["rows"]]
    body = f"""
<section class="hero"><div class="kicker">Orbital debris assessment · NASA DAS</div>
<h1>Debris Assessment Software (DAS) analysis</h1>
<p class="lede">NASA's {a("das", "Debris Assessment Software")} (DAS 3.2.7) checks a mission against NASA-STD-8719.14, and its results go into the
Orbital Debris Assessment Report that accompanies the FCC filing. This page gives our pre-DAS analysis, calibrated against real
DAS runs for PROVES 1U satellites, and includes a ready-made DAS project for this spacecraft.</p></section>

<div class="stats">
{stat("Lifetime @ 525 km", f"{l525['cycle_tumble']:.1f} yr", f"range {l525['solarmax_tumble']:.1f}–{l525['solarmin_tumble']:.1f} yr (solar max–min)")}
{stat("Area-to-mass", f"{das['am']:.4f}", "m²/kg (DAS input)")}
{stat("Mass (MEV)", f"{das['mass_kg']:.2f} kg", "from mass budget")}
{stat("FCC 5-year", "≤ ~475 km", "max deployment altitude, bare 1U")}
{stat("Casualty risk", "0", "all components demise (Atlas DAS)")}
</div>

<div class="callout warn">
<p><b>Key finding.</b> A bare 1U at the Transporter-class altitude of 525 km takes about {l525['cycle_tumble']:.0f} years to reenter. That meets NASA's 25-year
requirement but <b>not the FCC 5-year rule</b> (FCC 22-74, applying to satellites launched after 29 Sep 2024). Options:</p>
<ul>
<li>A drop-off at or below about 475 km, for example from the rideshare's orbital transfer vehicle.</li>
<li>A small deployable drag sail. Doubling the area roughly halves the lifetime.</li>
<li>An FCC waiver argument.</li>
</ul>
<p>This drives a launch-provider requirement and should be resolved before the ODAR is filed.</p>
</div>

<h2>Orbital lifetime vs deployment altitude</h2>
{chart("line", "Years to reentry vs deployment altitude", "1.26 kg, 0.017 m² mean tumbling area, launch Nov 2027, solar-cycle-varying atmosphere", life_spec)}
{table(["Altitude (km)", "Baseline (yr)", "Solar max (yr)", "Solar min (yr)", "Face-on area (yr)", "FCC 5-yr", "NASA 25-yr"], rows,
       num_cols=(0, 1, 2, 3, 4))}
{chart("line", "Altitude decay profiles", "Solar-cycle baseline. Decay slows through the ~2030 solar minimum and speeds up toward the Cycle 26 maximum.", spec)}

<h2>NASA-STD-8719.14 requirements</h2>
{table(["Requirement", "Description", "Status", "Basis"], req_rows)}

<h2>Model and calibration against DAS</h2>
<p>The model integrates circular-orbit decay, da/dt = −√(μa)·ρ·C<sub>D</sub>A/m, with C<sub>D</sub> = 2.2 (as in DAS) and a piecewise-exponential
atmosphere blended between solar minimum and maximum on an 11-year cycle (Cycle 25 maximum about 2025.0). A single density scale factor
(<b>{lt['assumptions']['das_cal']:.3f}</b>) was fitted so the model reproduces DAS 3.x lifetimes for the PROVES 1U satellites in
{a("proves_das", "The-PROVES-Project-DAS")}:</p>
{table(["DAS reference case (413 × 422 km, 51.6°)", "DAS (yr)", "Model (yr)", "Error"], val_rows, num_cols=(1, 2, 3))}
<p>The calibration points are all near 417 km and near solar maximum, so values at 500–600 km through the coming solar minimum are
extrapolations. The DAS run itself is the authoritative result.</p>

<h2>DAS project for this mission</h2>
<p>The site build generates a DAS project folder in the same format as the PROVES DAS repository. Download it, open it in DAS 3.2.7
("Open Project"), and run Requirements 4.3–4.7.</p>
<ul>
{"".join(f'<li><a href="das_project/{f}"><code>{f}</code></a></li>' for f in das["files"])}
</ul>
<p>Orbit inputs: {das_inputs.PERIGEE} × {das_inputs.APOGEE} km, {das_inputs.INCL}°, launch {das_inputs.LAUNCH_YEAR}. A/M = {das['am']:.5f} m²/kg.
<b>Update these once the launch provider confirms the deployment orbit.</b></p>
<h3>Reentry component list (Requirement 4.7-1 input)</h3>
{table(["Component", "Qty", "Material", "Body", "Unit mass (kg)", "Dims (m)"], comp_rows, num_cols=(1, 4))}

<h2>References</h2>
<ul>
<li>{a("das", "NASA ODPO – Debris Assessment Software")} · {a("das_guide", "DAS 3.2 User's Guide (PDF)")}</li>
<li>{a("proves_das", "PROVES Project DAS inputs (Atlas, Electra, Maia, Taygeta)")}</li>
<li>{a("fcc_5yr", "FCC 22-74 Second Report & Order — 5-year post-mission disposal rule")}</li>
</ul>
<p>Model source: <code>analysis/orbit_lifetime.py</code>, <code>analysis/das_inputs.py</code>.</p>
"""
    page("das.html", "Debris assessment (DAS)", body, has_charts=True)


def build_resources(ctx):
    groups = [
        ("Spacecraft hardware (GitHub)", [
            ("fc", "FC V5d LTM flight controller — KiCad design (Oct 2026 mods)"),
            ("fc_repo", "claude_flight_board — full repo (hardware, firmware, tools)"),
            ("fc_fw", "FC firmware — CircuitPython board definition and ltm1 CAN driver"),
            ("battery", "PROVES battery pack v2 (2S2P 18650)"),
            ("solar", "PROVES XY Faces V2a solar panels"),
            ("antenna", "PROVES antenna top cap v2c"),
            ("proves_fc", "PROVES flight controller board (upstream V5d)"),
            ("pysquared", "PROVES pysquared flight software"),
            ("proves", "PROVES Kit organisation"),
            ("proves_docs", "PROVES Kit documentation (structure, EPS, solar)"),
        ]),
        ("AMSAT", [
            ("ltm", "AMSAT Linear Transponder Module"),
            ("amsat_status", "AMSAT project status (Fox-Plus, GOLF)"),
            ("foxtelem", "FoxTelem telemetry decoder"),
            ("foxtelem_src", "FoxTelem source code"),
            ("amsat", "AMSAT home"),
        ]),
        ("Orbital debris & regulatory", [
            ("das", "NASA Debris Assessment Software"),
            ("das_guide", "DAS 3.2 User's Guide"),
            ("proves_das", "PROVES DAS project inputs"),
            ("fcc_5yr", "FCC 22-74 — 5-year deorbit rule"),
            ("iaru", "IARU satellite frequency coordination"),
            ("iaru_status", "IARU coordination status"),
        ]),
        ("This mission", [("site_src", "Website and analysis source")]),
    ]
    body = """<section class="hero"><div class="kicker">Resources</div><h1>Links, repositories & references</h1>
<p class="lede">The design is open source wherever possible. AMSAT LTM interface documentation is supplied to partners and is not reproduced here.</p></section>"""
    for title, items in groups:
        body += f"<h2>{esc(title)}</h2><div class='grid'>"
        for k, t in items:
            body += f'<a class="card" href="{L[k]}"><h3>{esc(t)}</h3><p class="mono" style="word-break:break-all">{esc(L[k].replace("https://", ""))}</p></a>'
        body += "</div>"
    body += """<h2>Analysis code</h2>
<ul>
<li><code>analysis/power_budget.py</code>: solar generation, mode loads, state-of-charge simulation</li>
<li><code>analysis/link_budget.py</code>: downlink, uplink and end-to-end transponder margins, Doppler</li>
<li><code>analysis/orbit_lifetime.py</code>: DAS-calibrated decay model</li>
<li><code>analysis/mass_budget.py</code>, <code>analysis/das_inputs.py</code>: mass budget and DAS project generator</li>
<li><code>build.py</code>: generates this site</li>
</ul>"""
    page("resources.html", "Resources", body)


def build_mockup(ctx):
    pb = ctx["power"]
    keys = [
        ("#b9bec6", "PROVES 1U structure", "aluminium rails and frame, 100 × 100 × 113.5 mm"),
        ("#18213d", "Solar faces", f"5 faces × 6 Si cells, about {pb['solar']['face_am0_w']:.1f} W each at normal incidence"),
        ("#1b1d22", "PROVES boards", "battery pack, flight controller, antenna top cap"),
        ("#1d6b3a", "AMSAT LTM-1 stack", "transponder (bottom), ICR (middle), LTI (top); 92 × 90 × 33 mm, 130 g"),
        ("#2e7dd1", "18650 cells", "2S2P, about 48 Wh"),
        ("#e0e3e8", "70 cm dipole", "2 × 178 mm tape-measure elements on the top cap (downlink)"),
        ("#eb6834", "Proposed 2 m element", "about 490 mm quarter-wave for the 144 MHz uplink (design TBD)"),
        ("#2a78d6", "Coax: TX", "transponder 432 MHz output to the top cap"),
    ]
    key_html = "".join(f'<li><span class="sw" style="background:{c}"></span><span><b>{esc(n)}</b> {esc(d)}</span></li>' for c, n, d in keys)
    importmap = '<script type="importmap">{"imports":{"three":"./vendor/three.module.min.js"}}</script><script type="module" src="mockup.js"></script>'
    body = f"""
<section class="hero"><div class="kicker">3D mockup</div>
<h1>Inside the DPI LTM CubeSat</h1>
<p class="lede">An interactive engineering mockup of the 1U spacecraft. Drag to orbit, scroll to zoom, and hover over any part for details.
Use <b>Explode</b> to pull the stack apart and <b>Hide panels</b> to see the AMSAT LTM-1 board stack inside.</p></section>

<div class="mockup-wrap">
  <div id="mockup" role="img" aria-label="3D model of a 1U CubeSat with solar panels, deployed tape antennas and an internal three-board AMSAT LTM stack"></div>
  <div id="mockup-labels"></div>
  <div id="mockup-tip"></div>
  <div class="mockup-bar">
    <button id="mk-explode" aria-pressed="false">Explode</button>
    <button id="mk-panels" aria-pressed="false">Hide panels</button>
    <button id="mk-antennas" aria-pressed="false">Stow antennas</button>
    <button id="mk-labels" aria-pressed="false">Hide labels</button>
    <button id="mk-spin" aria-pressed="false">Pause spin</button>
    <span class="sep"></span>
    <button data-view="iso">Iso</button><button data-view="side">Side</button><button data-view="top">Top</button><button data-view="inside">Inside</button>
  </div>
</div>
<noscript><p>The 3D mockup needs JavaScript and WebGL.</p></noscript>

<h2>Key</h2>
<ul class="key-list">{key_html}</ul>

<h2>How the LTM-1 sits in the bus</h2>
<ul>
<li><b>The stack, bottom to top:</b> 18650 battery pack (lowest, to keep the centre of mass low), then the FC V5d LTM flight controller, then the
AMSAT LTM-1. The LTM's three boards stack through a PC-104 connector: <b>transponder</b> at the bottom, then the <b>ICR</b> command receiver,
then the <b>LTI</b> host interface on top. That puts the RF board's coax leads close to the +Z antenna cap.</li>
<li><b>Interfaces:</b> the J30 harness (grey) carries the switched 5 V LTM_VSYS supply, CAN at 1 Mbit/s, I2C, umbilical sense and telemetry lines between the FC and the LTI.
The LTI's USB Mini-B umbilical faces a side panel for ground access.</li>
<li><b>Antennas:</b> the PROVES top cap's 2 × 178 mm tape elements form the 70 cm (432 MHz) downlink dipole. The orange 2 m element is a
<b>proposed</b> addition for the 144 MHz uplink, an open design item (see <a href="spacecraft.html">Spacecraft → open items</a>).</li>
<li><b>Fidelity:</b> board outlines, the stack order and the envelope follow AMSAT's public LTM description and the PROVES CAD dimensions.
Component placement on each board is illustrative, not the flight layout.</li>
</ul>
"""
    page("mockup.html", "3D mockup", body, head_extra=importmap)


def build_ask(ctx):
    api = chat_api_url()
    note = "" if api else '<div class="callout warn"><p>The assistant backend is not deployed yet.</p></div>'
    body = f"""
<section class="hero"><div class="kicker">Ask AI</div>
<h1>Mission assistant</h1>
<p class="lede">Ask about the spacecraft, the AMSAT LTM, the power and link budgets, operations or debris compliance. For anything not
covered on this site, the assistant researches primary sources (amsat.org, the GitHub repositories, NASA, FCC, IARU) and Wikipedia,
then lists the sources it used.</p></section>
{note}
<div id="chat-page"></div>
<p class="chat-foot" style="padding:0.6rem 0">Powered by Claude Opus 5.5 on Amazon Bedrock. Answers are AI-generated and can be wrong, so check
important numbers against the analysis pages. Conversations are kept in your browser tab only. Usage is rate-limited.</p>
"""
    page("ask.html", "Ask AI", body)


def _main_text(html_doc):
    m = re.search(r"<main>(.*)</main>", html_doc, re.S)
    s = m.group(1) if m else html_doc
    s = re.sub(r'(?s)<script type="application/json"[^>]*>.*?</script>', " ", s)
    s = re.sub(r"(?s)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r'<a [^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", s)
    s = re.sub(r"(?i)</t[dh]>", " | ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6]|table|section|ul|ol|pre|summary|figcaption)>", "\n", s)
    s = re.sub(r"(?i)<h[1-6][^>]*>", "\n## ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def build_knowledge(ctx):
    """Plain-text knowledge base for the chatbot, generated from the built pages."""
    parts = [f"# {MISSION} — site knowledge base\nGenerated by build.py from the published pages. Site: https://joansat.org/\n"]
    for fname, title in NAV:
        if fname == "ask.html":
            continue
        parts.append(f"\n\n=== PAGE: {title} ({fname}) ===\n" + _main_text((OUT / fname).read_text()))
    lt = ctx["life"]
    parts.append("\n\n=== DATA: orbital lifetime table (years) ===\n" + "\n".join(
        f"{r['alt_km']} km: baseline {r['cycle_tumble']:.1f}, solar max {r['solarmax_tumble']:.1f}, solar min {r['solarmin_tumble']:.1f}"
        for r in lt["table"]))
    out = ROOT / "chat" / "knowledge.md"
    out.write_text("".join(parts))
    return out


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    for f in ("styles.css", "charts.js", "chat.js", "mockup.js"):
        shutil.copy(ROOT / "web" / f, OUT / f)
    shutil.copytree(ROOT / "web" / "vendor", OUT / "vendor")

    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        orbit_lifetime.main(str(OUT / "data" / "orbit_lifetime.json"))
    ctx = {
        "life": json.loads((OUT / "data" / "orbit_lifetime.json").read_text()),
        "mass": mass_budget.budget(),
        "power": power_budget.budget(),
        "link": link_budget.budget(),
        "das": das_inputs.write_project(OUT / "das_project"),
    }
    for k in ("power", "link"):
        (OUT / "data" / f"{k}_budget.json").write_text(json.dumps(ctx[k], indent=1, default=str))

    build_index(ctx)
    build_spacecraft(ctx)
    build_conops(ctx)
    build_power(ctx)
    build_link(ctx)
    build_das(ctx)
    build_resources(ctx)
    build_mockup(ctx)
    build_ask(ctx)
    build_knowledge(ctx)
    (OUT / "error.html").write_text((OUT / "index.html").read_text())
    print("built:", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
