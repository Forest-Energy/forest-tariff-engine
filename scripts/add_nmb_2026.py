"""
Add Nelson Mandela Bay Metro 2026/27 rates (effective 2026-07-01).

Source: "Capturing of approved tariffs 4 August 2026", sheet "Eastern Cape",
section "NELSON MANDELA BAY METRO 10,9%" (rows 1496-1821), business tariffs
12, 14, 15, 16, 17 and 18. Rates are ex VAT; the sheet gives R/kWh, stored
here as c/kWh (x100). Export credits are negative in the sheet and stored
positive.

Mapping (existing tariff name -> sheet tariff), names kept so 2025/26 history
and downstream lookups keep working. HD = Winter (also Jun-Aug on the Eskom
clock), LD = Summer.

* NMB Medium Business Single Rate (T33/38)            -> 12. Single Rate (T33/T38), winter/summer
* NMB Medium Business Metered Demand (Scale 34/39)    -> 14. Metered Demand (34 & 39)
* NMB LV Medium Business TOU (Scale 32X/33Y/32Y)      -> 15. LV TOU (34X, 34Y, 34Z)
* NMB Large Business Metered Demand (Scale 35/30)     -> 16. Large Business (T35)
* NMB MV Large Business TOU (Scale 40X/40Y/40Z)       -> 17. HV TOU (40X, 40Y, 40Z)
* NMB Extra High Voltage TOU (Scale 40A)              -> 18. EHV TOU (50X, 50Y, 50Z)

Notes
-----
* The scale codes in the 2026/27 sheet differ from the tariff names (LV TOU is
  now 34X/34Y/34Z, EHV is now 50X/50Y/50Z). Names are unchanged; each mapping
  was confirmed by a consistent uplift on the 2025/26 rates.
* EHV: demand charge falls R19.83 -> R14.00/kVA and capacity R50.04 -> R45.00
  as published. EHV export credits (50Z) are new; the 2025/26 EHV had none.
* Not priced (no engine support, as for 2025/26): wheeling charges 34Y, 40Y and
  50Y, and all domestic, prepaid, small business and Net Billing 32X/33X tariffs.
* Sheet typos ignored: row 1648 shows 32Z winter standard export as +1.82; row
  1750 labels the 40X import as "34X"; row 1786 reads ">13 2000 Volts".

Idempotent: re-running replaces the 2026-07-01 version in place.
"""
import json
from pathlib import Path

JSON_PATH = Path(__file__).resolve().parent.parent / "tariff_engine" / "tariff_data.json"

PROVIDER = "Nelson Mandela Bay"
EFFECTIVE = "2026-07-01"


def c(r_per_kwh):
    """R/kWh -> c/kWh."""
    return round(r_per_kwh * 100, 4)


def tou(hd, ld):
    """hd, ld are (peak, standard, off-peak) in R/kWh."""
    return {"HD": dict(zip("PSO", map(c, hd))), "LD": dict(zip("PSO", map(c, ld)))}


def flat(winter, summer):
    return tou((winter,) * 3, (summer,) * 3)


def flat_tariff(winter, summer, service, demand=0):
    return {
        "type": "municipal_flat",
        "energy_c_per_kwh": flat(winter, summer),
        "export_c_per_kwh": None,
        "service_r_month": service,
        "capacity_r_kva_month": 0,
        "demand_r_kva_month": demand,
    }


def tou_tariff(hd, ld, service, demand, export_hd, export_ld, capacity=0):
    return {
        "type": "municipal_tou",
        "energy_c_per_kwh": tou(hd, ld),
        "export_c_per_kwh": tou(export_hd, export_ld),
        "service_r_month": service,
        "capacity_r_kva_month": capacity,
        "demand_r_kva_month": demand,
    }


TARIFFS = {
    # 12. Medium Business Single Rate (T33/T38)
    "NMB Medium Business Single Rate (T33/38)": flat_tariff(4.99, 3.69, 1948.09),
    # 14. Medium Business Metered Demand (34 & 39)
    "NMB Medium Business Metered Demand (Scale 34/39)": flat_tariff(4.00, 2.96, 1771.56, demand=248.83),
    # 15. Medium Business LV TOU (34X import, 34Z export)
    "NMB LV Medium Business TOU (Scale 32X/33Y/32Y)": tou_tariff(
        (8.45, 2.43, 1.76), (3.67, 2.30, 1.76), 1850.30, 205.79,
        export_hd=(5.07, 1.46, 1.06), export_ld=(2.20, 1.38, 1.05)),
    # 16. Large Business (T35)
    "NMB Large Business Metered Demand (Scale 35/30)": flat_tariff(3.83, 2.51, 7571.72, demand=197.99),
    # 17. Large Business HV TOU (40X import, 40Z export)
    "NMB MV Large Business TOU (Scale 40X/40Y/40Z)": tou_tariff(
        (7.38, 2.29, 1.44), (3.27, 2.13, 1.66), 7402.38, 170.29,
        export_hd=(4.43, 1.37, 0.86), export_ld=(1.37, 1.28, 1.00)),
    # 18. Large Business EHV TOU (50X import, 50Z export)
    "NMB Extra High Voltage TOU (Scale 40A)": tou_tariff(
        (7.47, 2.24, 1.43), (3.30, 2.12, 1.58), 20333.35, 14.00,
        export_hd=(4.48, 1.34, 0.86), export_ld=(1.98, 1.27, 0.95), capacity=45.00),
}


def main():
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    prov = data["providers"][PROVIDER]
    prov["versions"] = [v for v in prov["versions"] if v["effective"] != EFFECTIVE]
    prov["versions"].append({"effective": EFFECTIVE, "tariffs": TARIFFS})
    prov["versions"].sort(key=lambda v: v["effective"])

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"{PROVIDER}: {len(TARIFFS)} tariffs, effective {EFFECTIVE}")


if __name__ == "__main__":
    main()
