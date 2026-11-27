"""
Add the eThekwini Industrial Net Billing ancillary network charge to
eThekwini Industrial TOU as structured data, both rate years.

The charge is R/kVA/month on the installed inverter/generator size, set by
supply voltage, and applies when the customer is on the Industrial Net Billing
tariff (exports to the grid). Net Billing is only offered with ITOU.

Source (ex VAT): eThekwini final 2026/2027 tariff tables, printed p228,
"Ancilliary Network Access Charge", current (2025/26) and proposed (2026/27).
No 275 kV value is published.

Replaces the display-only `other_charges` entries added in 1.33.0.
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tariff_engine" / "tariff_data.json"

PROVIDER = "eThekwini"
TARIFF = "eThekwini Industrial TOU"
CHARGE = {
    "2025-07-01": {"400V": 47.80, "6.6kV": 27.95, "11kV": 22.50, "33kV": 6.37, "132kV": 4.88},
    "2026-07-01": {"400V": 52.11, "6.6kV": 30.47, "11kV": 24.86, "33kV": 7.03, "132kV": 5.39},
}


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    versions = {v["effective"]: v for v in data["providers"][PROVIDER]["versions"]}
    for eff, table in CHARGE.items():
        if eff not in versions or TARIFF not in versions[eff]["tariffs"]:
            raise SystemExit(f"{TARIFF} not found in {eff}; aborting.")
        t = versions[eff]["tariffs"][TARIFF]
        t["export_network_charge_r_kva_month"] = dict(table)
        others = [o for o in t.get("other_charges", [])
                  if not o["label"].startswith("Net billing ancillary network charge")]
        if others:
            t["other_charges"] = others
        else:
            t.pop("other_charges", None)
        print(f"{eff}: {TARIFF} export network charge set")
    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
