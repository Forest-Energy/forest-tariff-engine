"""
Point the Stellenbosch 2026/27 tariffs back at the "stellenbosch-2025" TOU schedule.

v1.21.0 moved the 2026/27 block to the Eskom clock based on the proposed
electricity annexure (ANNEXURE-ELECTRICITY-PROPOSED-TARIFFS-2026-27A, p9). The
confirmed final schedule is WC024 Appendix 3 "Final Tariff Proposals 2026-2027"
(May 2026), whose section 13 "Time of use periods" (p10) is band-for-band the
2025/26 Stellenbosch clock: winter peak 06-09 and 17-19, summer peak 07-10 and
18-20, Saturday standard 07-12 and 18-20 all year, Sunday off-peak all day.
Rates are not changed (they already match the final appendix).
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tariff_engine" / "tariff_data.json"

EFFECTIVE = "2026-07-01"
SCHEDULE = "stellenbosch-2025"
TARIFFS = [
    "Stellenbosch TOU LV",
    "Stellenbosch TOU MV",
    "Stellenbosch Large Power LV >80A (IND1)",
]


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    versions = {v["effective"]: v for v in data["providers"]["Stellenbosch"]["versions"]}
    if EFFECTIVE not in versions:
        raise SystemExit(f"No Stellenbosch version block for {EFFECTIVE}; aborting.")
    block = versions[EFFECTIVE]["tariffs"]
    for name in TARIFFS:
        if name not in block:
            raise SystemExit(f"{name} not found in {EFFECTIVE}; aborting.")
        block[name]["tou_schedule"] = SCHEDULE
        print(f"{EFFECTIVE}: set tou_schedule={SCHEDULE} on {name}")
    PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
