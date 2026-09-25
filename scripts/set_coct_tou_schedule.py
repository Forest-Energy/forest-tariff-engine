"""
Point the City of Cape Town TOU tariffs (both rate years) at the "coct-2025" schedule.

CoCT uses one TOU clock all year from 2025/26 (Eskom's Low Demand clock); only
the prices change in winter. Sources: Electricity Consumptive Tariffs 2025/26 p4
("Changes for 2025/26!"), Annexure 6 2026/27 p3, and the July 2026
"Understanding Residential Electricity Tariffs" guideline p4. The schedule itself
is defined in tariff_engine/tou.py. Rates are not changed. SPU1 is flat and left
on the default schedule.
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tariff_engine" / "tariff_data.json"

PROVIDER = "City of Cape Town"
EFFECTIVE = ("2025-07-01", "2026-07-01")
SCHEDULE = "coct-2025"
TARIFFS = ("CoCT LV TOU", "CoCT MV TOU", "CoCT HV TOU")


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    versions = {v["effective"]: v for v in data["providers"][PROVIDER]["versions"]}
    for eff in EFFECTIVE:
        if eff not in versions:
            raise SystemExit(f"No {PROVIDER} version block for {eff}; aborting.")
        block = versions[eff]["tariffs"]
        for name in TARIFFS:
            if name not in block:
                raise SystemExit(f"{name} not found in {eff}; aborting.")
            block[name]["tou_schedule"] = SCHEDULE
            print(f"{eff}: set tou_schedule={SCHEDULE} on {name}")
    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
