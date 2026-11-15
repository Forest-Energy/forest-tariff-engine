"""
Add JB Marks Local Municipality (Potchefstroom) Tariff D 2026/27 (effective 2026-07-01).

Source: JB Marks Schedule of Tariffs for the Supply of Electricity 2026/27, VAT
excl., pp12-15, bold 2026/27 values only (Request Desk REQ-89, PDF #123). Still
awaiting NERSA approval. One entry per voltage band (engine has one set of
charges per name). D.3 energy is printed in R/kWh, stored as c/kWh. Demand ->
demand_r_kva_month; NAC -> capacity_r_kva_month; fixed charge = Normal Read, AMR
kept in other_charges for display. TOU clock: tou "jbmarks-2026" (Note 4, p15).
Idempotent: re-running replaces the provider in place.
"""
import json
from pathlib import Path

JSON_PATH = Path(__file__).resolve().parent.parent / "tariff_engine" / "tariff_data.json"
AMR = {"label": "Fixed charge, Automated Meter Reading (AMR)", "value": 4083.54, "unit": "R/month",
       "note": "Shown for reference; calculations use the Normal Read fixed charge"}


def tariff_d(hd, ld, fixed, demand, nac):
    c = lambda r: round(r * 100, 4)  # R/kWh -> c/kWh
    return {"type": "municipal_tou", "tou_schedule": "jbmarks-2026",
            "energy_c_per_kwh": {"HD": dict(zip("PSO", map(c, hd))), "LD": dict(zip("PSO", map(c, ld)))},
            "export_c_per_kwh": None, "service_r_month": fixed,
            "capacity_r_kva_month": nac, "demand_r_kva_month": demand, "other_charges": [AMR]}


TARIFFS = {
    "JB Marks Tariff D LV (230/400 V)": tariff_d(
        (9.2701, 3.5110, 2.0629), (3.7472, 2.4328, 1.7952), 868.15, 149.04, 97.73),
    "JB Marks Tariff D MV (>400 V to 11 kV)": tariff_d(
        (8.7965, 3.3682, 1.9442), (3.5235, 2.2202, 1.7179), 869.77, 146.48, 93.33),
}

if __name__ == "__main__":
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    data["providers"]["JB Marks Local Municipality"] = {
        "escalation_month": 7, "escalation_day": 1,
        "versions": [{"effective": "2026-07-01", "tariffs": TARIFFS}]}
    JSON_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"JB Marks Local Municipality: {len(TARIFFS)} tariffs")
