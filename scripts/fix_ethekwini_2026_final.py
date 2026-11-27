"""
Correct eThekwini 2026/27 to the final schedule and add Commercial TOU (CTOU).

The 2026/27 version was loaded in June 2026 from the draft tables (+10.5%). The
final schedule is about +9%. Primary source (all ex VAT): eThekwini final
2026/2027 tariff tables ("eth-final-2026-2027-tariff-tables.pdf"), printed
pages 224 (Scale 1), 225 (ITOU present/proposed, Current Commercial TOU),
226 (Proposed Commercial TOU) and 228 (Industrial Net Billing). Where it
differs from "tariff-rates-2026-2027.pdf" (Scale 1 flat 403.65, CTOU 1-cent
rounding, ancillary charge at 132/33/11 kV), the final tables are used.

Changes:
  - eThekwini Industrial TOU 2026/27: energy, network demand, network access and
    service charge to the final schedule. Export = Industrial Net Billing feed-in
    rates (as in 2025/26). Net Billing ancillary network charge (R/kVA of
    inverter size, by voltage) kept in other_charges for display only.
    voltage_surcharge_pct / default_voltage are left as they are.
  - eThekwini Business Scale 1 2026/27: was holding the draft CTOU rates. Now
    the Scale 1 tariff: high season 415.47, low season 400.89 c/kWh (no TOU),
    R528.16/month.
  - New tariff "eThekwini Commercial TOU" (CTOU, NMD 100 kVA and below), both
    years, so the CTOU rates stay available under their own name.
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tariff_engine" / "tariff_data.json"

PROVIDER = "eThekwini"
ITOU = "eThekwini Industrial TOU"
SCALE1 = "eThekwini Business Scale 1"
CTOU = "eThekwini Commercial TOU"


def tou(hp, hs, ho, lp, ls, lo):
    return {"HD": {"P": hp, "S": hs, "O": ho}, "LD": {"P": lp, "S": ls, "O": lo}}


ITOU_2026 = {
    "energy_c_per_kwh": tou(667.89, 187.31, 133.91, 293.04, 176.64, 133.91),
    "export_c_per_kwh": tou(640.77, 160.19, 106.79, 265.92, 149.52, 106.79),
    "service_r_month": 8079.99,
    "capacity_r_kva_month": 60.81,   # Network Access Charge
    "demand_r_kva_month": 176.51,    # Network Demand Charge
}

ANCILLARY_2026 = [
    {
        "label": f"Net billing ancillary network charge, {v}",
        "value": r,
        "unit": "R/kVA/month",
        "note": "On inverter/generator size, only if on Industrial Net Billing. Not used in calculations",
    }
    for v, r in (("400V", 52.11), ("6.6kV", 30.47), ("11kV", 24.86), ("33kV", 7.03), ("132kV", 5.39))
]

SCALE1_2026 = {
    "type": "municipal_flat",
    "energy_c_per_kwh": tou(415.47, 415.47, 415.47, 400.89, 400.89, 400.89),
    "export_c_per_kwh": None,
    "service_r_month": 528.16,
    "capacity_r_kva_month": 0,
    "demand_r_kva_month": 0,
}

CTOU_RATES = {
    "2025-07-01": {
        "type": "municipal_tou",
        "energy_c_per_kwh": tou(642.15, 321.30, 156.52, 316.82, 254.87, 148.26),
        "export_c_per_kwh": None,
        "service_r_month": 680.02,
        "capacity_r_kva_month": 0,
        "demand_r_kva_month": 137.04,
    },
    "2026-07-01": {
        "type": "municipal_tou",
        "energy_c_per_kwh": tou(699.95, 350.22, 170.61, 345.34, 277.81, 161.61),
        "export_c_per_kwh": None,
        "service_r_month": 741.23,
        "capacity_r_kva_month": 0,
        "demand_r_kva_month": 149.38,
    },
}

ORDER = (SCALE1, CTOU, ITOU)


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    versions = {v["effective"]: v for v in data["providers"][PROVIDER]["versions"]}
    for eff in ("2025-07-01", "2026-07-01"):
        if eff not in versions:
            raise SystemExit(f"No {PROVIDER} version block for {eff}; aborting.")
        for name in (SCALE1, ITOU):
            if name not in versions[eff]["tariffs"]:
                raise SystemExit(f"{name} not found in {eff}; aborting.")

    new = versions["2026-07-01"]["tariffs"]
    itou = new[ITOU]
    if "voltage_surcharge_pct" not in itou:
        raise SystemExit("Run add_ethekwini_voltage_surcharge.py first; aborting.")
    itou.update(ITOU_2026)
    itou["other_charges"] = ANCILLARY_2026
    new[SCALE1] = SCALE1_2026
    print(f"2026-07-01: {ITOU} and {SCALE1} set to the final schedule")

    for eff, entry in CTOU_RATES.items():
        tariffs = versions[eff]["tariffs"]
        tariffs[CTOU] = entry
        versions[eff]["tariffs"] = {n: tariffs[n] for n in ORDER} | {
            n: t for n, t in tariffs.items() if n not in ORDER
        }
        print(f"{eff}: {CTOU} set")

    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
