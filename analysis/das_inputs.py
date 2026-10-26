"""Generate a NASA DAS 3.2.x project folder for the LTM CubeSat.

Files follow the layout of github.com/proveskit/The-PROVES-Project-DAS (Atlas),
so the folder can be opened directly in DAS ("Open Project") and Requirements
4.3, 4.5, 4.6 and 4.7 re-run there. Our own lifetime model only cross-checks DAS.
"""
import sys
from pathlib import Path

from mass_budget import budget as mass_budget

MISSION = "DPI LTM CubeSat"
LAUNCH_YEAR = 2027.87      # Transporter-22, Nov 2027 (TBC)
PERIGEE = APOGEE = 525     # km, TBC by launch provider
INCL = 97.5                # deg, SSO at 525 km
MEAN_AREA_M2 = 0.0170      # mean tumbling cross-section (Atlas DAS project basis)


def write_project(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mb = mass_budget()
    mass = round(mb["mev_kg"], 3)
    am = MEAN_AREA_M2 / mass

    (out / "das.prj").write_text("\n".join([
        "A321_ARGPERIGEE=0", f"S142_INCLINATION={INCL}", "S31131_OL=", "S142_MA=0",
        "S31131_AM_EDIT=", "S31131_STARTYEAR=", f"A321_INCLINATION={INCL}", "S31131_AM_LIST=",
        f"LaunchYear={LAUNCH_YEAR}", f"A321_PERIGEE={PERIGEE}", f"MissionName={MISSION}",
        "S142_ARGPERI=0", f"S142_PERIGEE={PERIGEE}", f"A321_AM={am:.6f}", "S142_RAAN=0",
        "A321_RAAN=0", f"S142_AM={am:.6f}", f"S142_STARTDATE={LAUNCH_YEAR}", "S142_DURATION=2",
        f"S142_APOGEE={APOGEE}", f"A321_YEAR={LAUNCH_YEAR}", ""]))

    (out / "payloads.csv").write_text(
        "Payloads\n"
        "Payload Name,Mission Duration (yrs),Operational Perigee (km),Operational Apogee(km),"
        "Operational Inclination(deg),RAAN (deg),Argument Of Perigee (deg),Mean Anomaly (deg),"
        "Post Mission Disposal Maneuver (y/n),Disposal Perigee (km),Disposal Apogee (km),"
        "Disposal Inclination (deg),Disposal RAAN (deg),Disposal Argument Of Perigee (deg),"
        "Disposal Mean Anomaly (deg),Initial Mass (kg),Final Mass (kg),Final Area To Mass (m^2/kg),"
        "Station Keeping (y/n),Long Term Reentry (y/n)\n"
        f"{MISSION},2,{PERIGEE},{APOGEE},{INCL},,,,n,,,,,,,{mass},{mass},{am:.5f},n,y\n")

    lines = ["Reentry Data",
             "Row Num,Name,Parent,Qty,Material,Body Type,Thermal Mass,Diameter/Width,Length,Height,"
             "Status,Risk,Demise Alt,Total DCA,KE",
             f"1,{MISSION},0,1,Aluminum 5052,Box,{mass},0.108,0.1135,0.108,,,,,"]
    for i, r in enumerate(mb["rows"], start=2):
        d = list(r["dims_m"]) + [""] * (3 - len(r["dims_m"]))
        lines.append(f"{i},{r['name']},1,{r['qty']},{r['material']},{r['body']},{r['unit_kg']},"
                     f"{d[0]},{d[1]},{d[2]},,,,,")
    (out / "reentry.csv").write_text("\n".join(lines) + "\n")

    # empty tables DAS expects to exist
    (out / "debris.csv").write_text(
        "Mission Debris\nDebris Name,Release Year,Quantity Of Each Element,Area To Mass (km),"
        "Perigee Altitude (km),Apogee Altitude (km),Inclination (deg),RAAN (deg),"
        "Argument Of Perigee (deg),Mean Anomaly (deg)\n")
    (out / "rocketbodies.csv").write_text(
        "Rocket Bodies\nRocket Body Name,Perigee (km),Apogee (km),Inclination (deg),RAAN (deg),"
        "Argument Of Perigee (deg),Mean Anomaly (deg),Final Mass (kg),"
        "Final Area To Mass (m^2/kg),Long-Term Reentry (y/n)\n")
    (out / "matprop.csv").write_text("")
    (out / "xsectional.csv").write_text(
        "Science and Engineering - Calculate Cross Sectional Area\n"
        "Component Shape,Point 1 U (LU),Point 1 V (LU),Point 1 W (LU),Point 2 U (LU),"
        "Point 2 V (LU),Point 2 W (LU),Point 3 U (LU),Point 3 V (LU),Point 3 W (LU),"
        "Radius 1 (LU),Radius 2 (LU)\n")
    (out / "req52data.csv").write_text(
        "Requirement 4.5-2 Critical Surface Data\n"
        "Payload,Orientation,Critical Surface,Critical Surface Density (g/cm^2),Surface Area (m^2),"
        "Unit Vector X,Unit Vector Y,Unit Vector Z,Pressurized (y/n),Outer Wall,"
        "Outer Wall Density (g/cm^2),Outer Wall Separation (cm)\n")
    return {"mass_kg": mass, "am": am, "files": sorted(p.name for p in out.iterdir())}


if __name__ == "__main__":
    print(write_project(sys.argv[1] if len(sys.argv) > 1 else "das_project"))
