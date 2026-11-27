"""
Add the eThekwini Industrial TOU (ITOU) voltage surcharge to both rate years.

The surcharge is a percentage "levied on the sum of all costs with the exception
of the service charge", set by supply voltage. Same table in 2025/26 and 2026/27:

    275 kV 0.00% | 132 kV 2.25% | 33 kV 3.00% | 11 kV 10.50% | 6.6 kV 12.75% | 400 V 22.50%

Sources:
  - eThekwini "tariff-rates-2026-2027.pdf", Industrial Time of Use (ITOU), p11
    (Network Charge table + "Voltage Surcharge" note).
  - eThekwini final 2026/2027 tariff tables, Bulk Tariffs, p228: the same table in
    both the present (2025/26) and proposed (2026/27) columns.

Rates are not changed. The engine applies the surcharge in rates.py when the
tariff is resolved; default_voltage (400V) applies when no voltage is passed.
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tariff_engine" / "tariff_data.json"

PROVIDER = "eThekwini"
EFFECTIVE = ("2025-07-01", "2026-07-01")
TARIFF = "eThekwini Industrial TOU"
SURCHARGE_PCT = {
    "400V": 22.5,
    "6.6kV": 12.75,
    "11kV": 10.5,
    "33kV": 3.0,
    "132kV": 2.25,
    "275kV": 0.0,
}
DEFAULT_VOLTAGE = "400V"


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    versions = {v["effective"]: v for v in data["providers"][PROVIDER]["versions"]}
    for eff in EFFECTIVE:
        if eff not in versions:
            raise SystemExit(f"No {PROVIDER} version block for {eff}; aborting.")
        block = versions[eff]["tariffs"]
        if TARIFF not in block:
            raise SystemExit(f"{TARIFF} not found in {eff}; aborting.")
        block[TARIFF]["voltage_surcharge_pct"] = dict(SURCHARGE_PCT)
        block[TARIFF]["default_voltage"] = DEFAULT_VOLTAGE
        print(f"{eff}: {TARIFF} voltage surcharge set, default {DEFAULT_VOLTAGE}")
    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
