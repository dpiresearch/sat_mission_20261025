"""Mass budget, derived from the PROVES Atlas DAS reentry component list
(github.com/proveskit/The-PROVES-Project-DAS, Atlas/reentry.csv) with the
PROVES payload PCB and camera replaced by the AMSAT LTM.

Each row: (component, parent, qty, unit mass kg, material, DAS body type, dims m, source)
dims follow DAS conventions: Box (w, l, h), Flat Plate (w, l), Cylinder (d, l).
"""

COMPONENTS = [
    ("Primary structure (PROVES 1U frame)", 1, 0.092, "Aluminum 5052", "Box", (0.10, 0.1135, 0.10), "Atlas DAS"),
    ("Flight controller (FC V5d LTM)", 1, 0.0446, "Fiberglass", "Flat Plate", (0.09, 0.09), "Atlas DAS"),
    ("Battery pack board (battery_pack_v2)", 1, 0.0446, "Fiberglass", "Flat Plate", (0.09, 0.09), "Atlas DAS"),
    ("Li-ion 18650 cells (2S2P)", 4, 0.046, "Steel AISI 316", "Cylinder", (0.018, 0.065), "Atlas DAS / NCR18650B"),
    ("AMSAT LTM (3-board PC-104 stack)", 1, 0.130, "Fiberglass", "Box", (0.092, 0.090, 0.033), "amsat.org LTM page"),
    ("LTM harness (J30 to H1/H2)", 1, 0.010, "Copper Alloy", "Box", (0.02, 0.05, 0.005), "estimate"),
    ("Solar panels (XY_Faces_V2a / Z)", 5, 0.0025, "Fiberglass", "Flat Plate", (0.07, 0.09), "Atlas DAS"),
    ("Solar cells (KXOB101K08TF)", 30, 0.0033, "Fiberglass", "Flat Plate", (0.018, 0.042), "Atlas DAS"),
    ("Antenna top cap (v2c)", 1, 0.0427, "Fiberglass", "Flat Plate", (0.10, 0.10), "Atlas DAS"),
    ("Tape-measure antenna elements", 2, 0.0001, "Steel AISI 316", "Flat Plate", (0.0127, 0.1778), "Atlas DAS"),
    ("Card brackets", 6, 0.0044, "Aluminum 5052", "Flat Plate", (0.02, 0.088), "Atlas DAS"),
    ("L-brackets", 4, 0.0024, "Aluminum 5052", "Flat Plate", (0.018, 0.035), "Atlas DAS"),
    ("Feet (PA-12)", 8, 0.0021, "Polyamide", "Box", (0.014, 0.031, 0.007), "Atlas DAS"),
    ("M2.5 fasteners", 44, 0.0003, "Steel AISI 316", "Cylinder", (0.00238, 0.01), "Atlas DAS"),
    ("M2.5 bolts + locknuts", 16, 0.001, "Steel AISI 316", "Cylinder", (0.004, 0.01), "Atlas DAS"),
    ("Wire harnessing", 1, 0.17, "Copper Alloy", "Box", (0.028, 0.028, 0.028), "Atlas DAS"),
    ("Torque rod cores", 1, 0.0810, "Iron", "Cylinder", (0.0127, 0.07), "Atlas DAS (2 rods combined)"),
    ("Torque rod windings", 2, 0.004, "Copper Alloy", "Cylinder", (0.005, 0.07), "Atlas DAS"),
    ("Magnetorquer air coil", 1, 0.20, "Copper Alloy", "Box", (0.02, 0.0695, 0.016), "Atlas DAS"),
]

CONTINGENCY = 0.05     # 5 % on a design with flight-heritage parts
CDS_LIMIT_1U = 2.00    # kg, CubeSat Design Specification rev 14.1


def budget():
    rows = []
    for name, qty, unit, mat, body, dims, src in COMPONENTS:
        rows.append({"name": name, "qty": qty, "unit_kg": unit, "total_kg": qty * unit,
                     "material": mat, "body": body, "dims_m": dims, "source": src})
    cbe = sum(r["total_kg"] for r in rows)
    return {"rows": rows, "cbe_kg": cbe, "contingency": CONTINGENCY,
            "mev_kg": cbe * (1 + CONTINGENCY), "limit_kg": CDS_LIMIT_1U}


if __name__ == "__main__":
    b = budget()
    for r in b["rows"]:
        print(f"{r['name']:42s} {r['qty']:3d} x {r['unit_kg']*1000:6.1f} g = {r['total_kg']*1000:6.1f} g")
    print(f"CBE {b['cbe_kg']:.3f} kg, MEV {b['mev_kg']:.3f} kg (limit {b['limit_kg']} kg)")
