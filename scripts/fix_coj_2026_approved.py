"""
Correct City of Johannesburg 2026/27 rates to the approved City Power schedule,
and put all CoJ TOU tariffs (both rate years) on the City Power TOU clock.

Source: City Power "Schedule of Approved Tariffs for FY26/27", dated
01 July 2026 (2026.27 Tariffs charges.pdf), sections 3 and 4, pages 5-8.
All values ex-VAT.

Why: v1.22.0 loaded a projection (2025/26 x 1.0863, the City's headline 8.63%
electricity figure). The approved LPU rates are 2025/26 x 1.0901 on every
line, and the Business/LPU embedded generator rate moved 90.05 -> 103.26 c/kWh.

Name mapping (established names kept, downstream lookups are by name):
  PDF "Industrial LV (TOU)" -> CoJ Industrial TOU LV
  PDF "Industrial MV (TOU)" -> CoJ Industrial TOU MV
  PDF "Industrial LV"       -> CoJ Large Consumer Demand LV
  PDF "Industrial MV"       -> CoJ Large Consumer Demand MV
  (not in PDF)              -> CoJ Industrial TOU HV, 2025/26 x 1.0901

Conventions (unchanged from the 2025/26 CoJ entries):
  * service_r_month = Service charge + Capacity charge (both R/month).
  * Energy carries the 6 c/kWh Network Surcharge (still 6c in 2026/27).
  * HD = winter (Jun-Aug), LD = summer.
  * Export = Business & LPU Embedded Generator rate, flat, no surcharge.

IDEMPOTENT: overwrites the 2026-07-01 CoJ tariffs with fixed values.
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tariff_engine" / "tariff_data.json"
PROVIDER = "City of Johannesburg"
BASE_EFFECTIVE = "2025-07-01"
EFFECTIVE = "2026-07-01"

NETWORK_SURCHARGE = 6.00   # c/kWh
EXPORT = 103.26            # c/kWh, Business & LPU Embedded Generators (<=1MW)
HV_ESCALATION = 1.0901     # realised approved LPU increase
TOU_SCHEDULE = "coj-2025"
TOU_TARIFFS = ("CoJ Industrial TOU LV", "CoJ Industrial TOU MV", "CoJ Industrial TOU HV")


def flat(v: float) -> dict:
    return {"HD": {"P": v, "S": v, "O": v}, "LD": {"P": v, "S": v, "O": v}}


def season(winter: float, summer: float) -> dict:
    return {
        "HD": {"P": winter, "S": winter, "O": winter},
        "LD": {"P": summer, "S": summer, "O": summer},
    }


def plus_surcharge(x: float) -> float:
    return round(x + NETWORK_SURCHARGE, 2)


# Industrial LV/MV (TOU) energy, page 6 (identical for LV and MV)
TOU_ENERGY = {
    "HD": {"P": plus_surcharge(766.24), "S": plus_surcharge(292.56), "O": plus_surcharge(200.44)},
    "LD": {"P": plus_surcharge(322.00), "S": plus_surcharge(242.42), "O": plus_surcharge(186.35)},
}

# HV: 2025/26 booklet service 39 368.03 + capacity 40 224.48, demand 367.79
HV_SERVICE = round(round(39368.03 * HV_ESCALATION, 2) + round(40224.48 * HV_ESCALATION, 2), 2)
HV_DEMAND = round(367.79 * HV_ESCALATION, 2)

TARIFFS = {
    "CoJ Industrial TOU LV": {
        "type": "municipal_tou",
        "energy_c_per_kwh": TOU_ENERGY,
        "export_c_per_kwh": flat(EXPORT),
        "service_r_month": round(2444.32 + 2185.32, 2),
        "capacity_r_kva_month": 0.0,
        "demand_r_kva_month": 461.28,
        "tou_schedule": TOU_SCHEDULE,
    },
    "CoJ Industrial TOU MV": {
        "type": "municipal_tou",
        "energy_c_per_kwh": TOU_ENERGY,
        "export_c_per_kwh": flat(EXPORT),
        "service_r_month": round(3360.96 + 9347.51, 2),
        "capacity_r_kva_month": 0.0,
        "demand_r_kva_month": 431.11,
        "tou_schedule": TOU_SCHEDULE,
    },
    "CoJ Industrial TOU HV": {
        "type": "municipal_tou",
        "energy_c_per_kwh": TOU_ENERGY,
        "export_c_per_kwh": flat(EXPORT),
        "service_r_month": HV_SERVICE,
        "capacity_r_kva_month": 0.0,
        "demand_r_kva_month": HV_DEMAND,
        "tou_schedule": TOU_SCHEDULE,
    },
    # PDF "Industrial LV", page 5
    "CoJ Large Consumer Demand LV": {
        "type": "municipal_flat",
        "energy_c_per_kwh": season(winter=plus_surcharge(333.79), summer=plus_surcharge(284.96)),
        "export_c_per_kwh": flat(EXPORT),
        "service_r_month": round(1527.71 + 2332.96, 2),
        "capacity_r_kva_month": 0.0,
        "demand_r_kva_month": 461.22,
    },
    # PDF "Industrial MV", page 5
    "CoJ Large Consumer Demand MV": {
        "type": "municipal_flat",
        "energy_c_per_kwh": season(winter=plus_surcharge(314.85), summer=plus_surcharge(266.01)),
        "export_c_per_kwh": flat(EXPORT),
        "service_r_month": round(1833.23 + 9899.66, 2),
        "capacity_r_kva_month": 0.0,
        "demand_r_kva_month": 431.11,
    },
}


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    versions = {v["effective"]: v for v in data["providers"][PROVIDER]["versions"]}
    for eff in (BASE_EFFECTIVE, EFFECTIVE):
        if eff not in versions:
            raise SystemExit(f"No {PROVIDER} {eff} block; aborting.")

    block = versions[EFFECTIVE]["tariffs"]
    if set(block) != set(TARIFFS):
        raise SystemExit(f"Unexpected 2026/27 tariff set {sorted(block)}; aborting.")
    for name, tariff in TARIFFS.items():
        block[name] = tariff

    # 2025/26: same City Power clock (booklet item 5.4.7). Rates untouched.
    base = versions[BASE_EFFECTIVE]["tariffs"]
    for name in TOU_TARIFFS:
        base[name]["tou_schedule"] = TOU_SCHEDULE

    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"CoJ {EFFECTIVE} corrected ({len(TARIFFS)} tariffs); "
          f"tou_schedule={TOU_SCHEDULE} on TOU tariffs in both years.\n")

    # ── CROSS-CHECKS against the PDF (surcharge-inclusive where applicable) ──
    t = block
    checks = [
        ("TOU LV HD P", t["CoJ Industrial TOU LV"]["energy_c_per_kwh"]["HD"]["P"], 772.24),
        ("TOU LV LD O", t["CoJ Industrial TOU LV"]["energy_c_per_kwh"]["LD"]["O"], 192.35),
        ("TOU LV fixed", t["CoJ Industrial TOU LV"]["service_r_month"], 4629.64),
        ("TOU MV fixed", t["CoJ Industrial TOU MV"]["service_r_month"], 12708.47),
        ("TOU HV fixed", t["CoJ Industrial TOU HV"]["service_r_month"], 86763.80),
        ("TOU HV demand", t["CoJ Industrial TOU HV"]["demand_r_kva_month"], 400.93),
        ("LCD LV winter", t["CoJ Large Consumer Demand LV"]["energy_c_per_kwh"]["HD"]["P"], 339.79),
        ("LCD LV fixed", t["CoJ Large Consumer Demand LV"]["service_r_month"], 3860.67),
        ("LCD MV summer", t["CoJ Large Consumer Demand MV"]["energy_c_per_kwh"]["LD"]["P"], 272.01),
        ("LCD MV fixed", t["CoJ Large Consumer Demand MV"]["service_r_month"], 11732.89),
        ("export", t["CoJ Large Consumer Demand MV"]["export_c_per_kwh"]["HD"]["P"], 103.26),
    ]
    all_ok = True
    for name, got, expected in checks:
        ok = abs(got - expected) < 0.005
        all_ok &= ok
        print(f"  {'OK  ' if ok else 'FAIL'}  {name}: {got}  (expected {expected})")
    print()
    print("All checks passed!" if all_ok else "SOME CHECKS FAILED -- review above.")


if __name__ == "__main__":
    main()
