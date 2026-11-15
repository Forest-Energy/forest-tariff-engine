"""
Correct Newcastle Scale 3, 4 and 5 tariffs (2025/26) and add 2026/27 (effective 2026-07-01).

Source: Newcastle Municipality Notice No. CS 9/2026 dated 19 March 2026, Council
resolution CM 27 (9% increase from 1 July 2026), "PROPOSED ELECTRICITY SUPPLY
TARIFF STRUCTURE: 01 JULY 2026", pages 5 (Scale 3) and 6 (Scales 4 and 5).
Columns used: "2025/2026 Approved Tariff" for the 2025-07-01 version and
"2026/2027 Proposed Tariff" for the 2026-07-01 version (Request Desk REQ-76,
PDF #107). The 2026/27 column is the council-approved draft for submission to
NERSA, not a NERSA approval. Rates are ex VAT and published in c/kWh.

Mapping notes
-------------
* Standard tariffs are municipal_flat with one energy rate in all six cells.
  TOU tariffs are municipal_tou with High season as HD and Low season as LD.
* "Network demand charge" -> demand_r_kva_month and "Network capacity charge"
  -> capacity_r_kva_month (R/kVA/month), the CoCT / Sol Plaatje split.
* The basic charge per point of supply (metered) -> service_r_month. The
  schedule publishes one basic charge per scale, so the Standard and TOU tariffs
  on a scale both carry it.
* The vacant-stand basic charge has no supply and no energy rate, so it is not
  a tariff. It is kept for display in `other_charges` on the Standard tariffs;
  the engine ignores that key.
* The stray "0.00" in the 2026/27 column under Scale 3 TOU is not a rate and
  is not loaded.
* All TOU sections say "in accordance with Eskom's specified time schedule",
  so no `tou_schedule` key is set (default Eskom clock).
* Scale 5 notes that are not modelled: no demand charge in off-peak (night
  save); off-peak 22:00-06:00 weekdays plus Saturdays, Sundays and holidays.
* Tariff names are unchanged. "Newcastle Scale 3T Small Business LV TOU" and
  "Newcastle Scale 5S Large Business MV" were missing and are added.
* Scales 1, 2, 6 and 7 are out of scope and not in the engine.

Idempotent: re-running replaces the Newcastle provider in place.
"""
import json
from pathlib import Path

JSON_PATH = Path(__file__).resolve().parent.parent / "tariff_engine" / "tariff_data.json"

PROVIDER = "Newcastle"

S3 = "Newcastle Scale 3 Small Business LV"
S3T = "Newcastle Scale 3T Small Business LV TOU"
S4S = "Newcastle Scale 4S Medium Business LV"
S4T = "Newcastle Scale 4T Medium Business TOU Demand"
S5S = "Newcastle Scale 5S Large Business MV"
S5T = "Newcastle Scale 5T Large Business MV TOU"

# Per year: {name: (energy, basic metered R/m, network demand R/kVA/m, network capacity R/kVA/m)}
# energy is one c/kWh value (Standard) or ((HD P, S, O), (LD P, S, O)) (TOU).
RATES = {
    "2025-07-01": {
        "vacant": 1164.76,
        S3: (273.03, 1167.64, 0, 0),
        S3T: (((520.28, 221.85, 107.70), (301.33, 191.75, 99.36)), 1167.64, 0, 0),
        S4S: (148.03, 2511.53, 261.78, 227.04),
        S4T: (((583.13, 295.73, 166.80), (493.35, 221.92, 138.13)), 2511.53, 82.22, 61.48),
        S5S: (148.03, 4932.93, 237.92, 210.97),
        S5T: (((511.30, 217.94, 105.90), (296.09, 188.42, 97.77)), 4932.93, 81.71, 62.01),
    },
    "2026-07-01": {
        "vacant": 1269.59,
        S3: (297.60, 1272.73, 0, 0),
        S3T: (((567.11, 241.82, 117.39), (328.45, 209.01, 108.30)), 1272.73, 0, 0),
        S4S: (161.35, 2737.57, 285.34, 247.47),
        S4T: (((635.61, 322.35, 181.81), (537.75, 241.89, 150.56)), 2737.57, 89.62, 67.01),
        S5S: (161.35, 5376.89, 259.33, 229.96),
        S5T: (((557.32, 237.55, 115.43), (322.74, 205.38, 106.57)), 5376.89, 89.06, 67.59),
    },
}

ORDER = [S3, S3T, S4S, S4T, S5S, S5T]


def tariff(energy, basic, demand, capacity, vacant):
    tou = isinstance(energy, tuple)
    hd, ld = energy if tou else ((energy,) * 3, (energy,) * 3)
    t = {
        "type": "municipal_tou" if tou else "municipal_flat",
        "energy_c_per_kwh": {"HD": dict(zip("PSO", hd)), "LD": dict(zip("PSO", ld))},
        "export_c_per_kwh": None,
        "service_r_month": basic,
        "capacity_r_kva_month": capacity,
        "demand_r_kva_month": demand,
    }
    if not tou:
        t["other_charges"] = [{
            "label": "Basic charge, vacant stand",
            "value": vacant,
            "unit": "R/month",
            "note": "Charged on a vacant stand with no supply; not used in calculations",
        }]
    return t


def main():
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    versions = []
    for effective, rates in RATES.items():
        tariffs = {name: tariff(*rates[name], rates["vacant"]) for name in ORDER}
        versions.append({"effective": effective, "tariffs": tariffs})

    data["providers"][PROVIDER] = {
        "escalation_month": 7,
        "escalation_day": 1,
        "versions": versions,
    }

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"{PROVIDER}: {len(ORDER)} tariffs x {len(versions)} versions")


if __name__ == "__main__":
    main()
