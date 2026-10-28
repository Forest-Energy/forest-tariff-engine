"""
Add Sol Plaatje Local Municipality (Kimberley) 2026/27 rates (effective 2026-07-01).

Source: NERSA decision "Sol Plaatje Local Municipality: Tariff Applications for
the 2026/27 Financial Year", Table 6 Schedule of Tariffs, pages 24-31, the
APPROVED TARIFFS 2026/2027 column only (Request Desk REQ-60, PDF #89 and
screenshots #90-#92). Rates are ex VAT; the PDF gives R/kWh, stored here as
c/kWh (x100).

Mapping notes
-------------
* The PDF's tariff codes (EL1250 etc.) are mislabelled (EL1250 "STD" is the
  High Demand Peak row), so rows are mapped by the Season/Period columns only.
* No season months or TOU hours are published, so no `tou_schedule` is set:
  the TOU tariffs use the default Eskom clock (High Demand Jun-Aug).
* Winter/Summer tariffs (Public Benefit, Business Small Power) are stored as
  municipal_flat with HD = Winter and LD = Summer, like CoJ Large Consumer.
* Network Access (fixed, R/kVA/m) -> capacity_r_kva_month and Network Demand
  (measured, R/kVA/m) -> demand_r_kva_month, the same split as CoCT TOU.
* SSEG export credits are stored as export_c_per_kwh on the TOU tariffs (the
  PDF makes Small Consumer TOU compulsory for SSEG customers). They are not
  added as sseg_options, because that would make these tariffs Gen-Offset
  eligible, which Sol Plaatje does not publish. The SSEG support charge is
  approved at R0.0000/m and is left out.
* The engine has no block, per-Amp or reactive energy pricing. Those charges
  are kept in `other_charges` for display only; the engine ignores that key.
  - Block tariffs are priced at Block 1 (the lowest block), so modelled
    savings are conservative.
  - Per-Amp capacity charges (R/Amp/phase/month) are NOT put in
    capacity_r_kva_month, which the model multiplies by kVA.
  - Reactive energy (R/kvarh) is not modelled, as for CoJ.
* Basic charges are blank in the PDF and are stored as 0.

Idempotent: re-running replaces the provider in place.
"""
import json
from pathlib import Path

JSON_PATH = Path(__file__).resolve().parent.parent / "tariff_engine" / "tariff_data.json"

PROVIDER = "Sol Plaatje Local Municipality"
EFFECTIVE = "2026-07-01"


def c(r_per_kwh):
    """R/kWh -> c/kWh."""
    return round(r_per_kwh * 100, 4)


def tou(hd, ld):
    return {"HD": dict(zip("PSO", map(c, hd))), "LD": dict(zip("PSO", map(c, ld)))}


def flat(hd, ld=None):
    ld = hd if ld is None else ld
    return tou((hd, hd, hd), (ld, ld, ld))


def other(label, value, unit, note=None):
    row = {"label": label, "value": value, "unit": unit}
    if note:
        row["note"] = note
    return row


SSEG_EXPORT = tou((5.7268, 1.6039, 1.1458), (2.5109, 1.5122, 1.1458))
REACTIVE = other("Reactive energy charge (all seasons, Peak and Standard)", 0.2934, "R/kvarh",
                 "Not used in calculations")
NOT_PRICED = "Shown for reference, not used in calculations"
BLOCK1_NOTE = "Calculations use Block 1 for all kWh"


def tou_tariff(hd, ld, network_demand, network_access, reactive=False):
    t = {
        "type": "municipal_tou",
        "energy_c_per_kwh": tou(hd, ld),
        "export_c_per_kwh": SSEG_EXPORT,
        "service_r_month": 0,
        "capacity_r_kva_month": network_access,
        "demand_r_kva_month": network_demand,
        "other_charges": [
            other("Network Access charge", network_access, "R/kVA/month", "Shown above as Network capacity"),
            other("Network Demand charge", network_demand, "R/kVA/month", "Shown above as Demand charge"),
        ],
    }
    if reactive:
        t["other_charges"].append(REACTIVE)
    return t


def flat_tariff(hd, ld=None, service=0, other_charges=None, export=None):
    t = {
        "type": "municipal_flat",
        "energy_c_per_kwh": flat(hd, ld),
        "export_c_per_kwh": export,
        "service_r_month": service,
        "capacity_r_kva_month": 0,
        "demand_r_kva_month": 0,
    }
    if other_charges:
        t["other_charges"] = other_charges
    return t


TARIFFS = {
    # Bulk Consumer TOU (pages 28-30)
    "Sol Plaatje Bulk Consumer TOU LV <200 kVA": tou_tariff(
        (7.8961, 2.9463, 2.1472), (3.2234, 2.3935, 1.9742), 219.1237, 80.5896, reactive=True),
    "Sol Plaatje Bulk Consumer TOU LV 200-500 kVA": tou_tariff(
        (7.9506, 2.9803, 2.2833), (3.2172, 2.4629, 2.0488), 172.7022, 80.5896, reactive=True),
    "Sol Plaatje Bulk Consumer TOU MV": tou_tariff(
        (7.9276, 2.9081, 2.2547), (3.1328, 2.4267, 1.9732), 148.3419, 76.6900, reactive=True),
    # TOU NPO/NGO/Schools (the PDF prints the same ND/NA for <200 and 200-500 kVA)
    "Sol Plaatje TOU NPO/NGO/Schools LV <200 kVA": tou_tariff(
        (7.1673, 2.8759, 1.9995), (3.0721, 2.3565, 1.8399), 206.9077, 98.4060),
    "Sol Plaatje TOU NPO/NGO/Schools LV 200-500 kVA": tou_tariff(
        (7.2154, 2.9222, 2.0282), (3.1494, 2.4069, 1.8803), 206.9077, 98.4060),
    "Sol Plaatje TOU NPO/NGO/Schools MV": tou_tariff(
        (7.2348, 2.9750, 2.0986), (3.2269, 2.4573, 1.9326), 160.4861, 75.9969),
    # Small Consumer TOU <70 kVA, domestic and commercial (compulsory for SSEG customers)
    "Sol Plaatje Small Consumer TOU <70 kVA": {
        "type": "municipal_tou",
        "energy_c_per_kwh": tou((9.7509, 2.9537, 1.6039), (3.1809, 2.1891, 1.3883)),
        "export_c_per_kwh": SSEG_EXPORT,
        "service_r_month": 0,
        "capacity_r_kva_month": 0,
        "demand_r_kva_month": 0,
        "other_charges": [other("Capacity charge", 4.5098, "R/Amp/phase/month", NOT_PRICED)],
    },
    # Seasonal, non-TOU: HD = Winter, LD = Summer
    "Sol Plaatje Business Small Power": flat_tariff(3.3619, 3.1323, other_charges=[
        other("Capacity charge", 4.5098, "R/Amp/phase/month", NOT_PRICED),
        other("Block 1 (0-1200 kWh) and Block 2 (>1200 kWh)", 3.3619, "R/kWh", "Winter; same rate in both blocks"),
        other("Block 1 (0-1200 kWh) and Block 2 (>1200 kWh)", 3.1323, "R/kWh", "Summer; same rate in both blocks"),
    ]),
    "Sol Plaatje Public Benefit and Schools": flat_tariff(3.4732, 3.2533, other_charges=[
        other("Capacity charge", 5.2437, "R/Amp/phase/month", NOT_PRICED),
    ]),
    # Domestic block tariffs, priced at Block 1
    "Sol Plaatje Domestic Kimlite 20A": flat_tariff(2.9628, other_charges=[
        other("Block 1 (0-350 kWh)", 2.9628, "R/kWh", BLOCK1_NOTE),
        other("Block 2 (>350 kWh)", 3.7465, "R/kWh", NOT_PRICED),
    ]),
    "Sol Plaatje Domestic Kimlite >20A": flat_tariff(2.7642, other_charges=[
        other("Capacity charge", 4.5099, "R/Amp/phase/month", NOT_PRICED),
        other("Block 1 (0-350 kWh)", 2.7642, "R/kWh", BLOCK1_NOTE),
        other("Block 2 (>350 kWh)", 3.1302, "R/kWh", NOT_PRICED),
    ]),
    "Sol Plaatje Domestic Kim Power Indigent Prepaid 20A": flat_tariff(2.7777, other_charges=[
        other("Block 1 (0-50 kWh)", 2.7777, "R/kWh", BLOCK1_NOTE),
        other("Block 2 (51-350 kWh)", 2.7777, "R/kWh", NOT_PRICED),
        other("Block 3 (>350 kWh)", 3.8757, "R/kWh", NOT_PRICED),
    ]),
    # Reference tariffs
    "Sol Plaatje Streetlights": flat_tariff(0.8576, service=106.1506, other_charges=[
        other("Basic charge", 106.1506, "R/light/month", "Shown above as the service charge for one light"),
    ]),
    "Sol Plaatje Availability Charge": flat_tariff(0, service=574.6239, other_charges=[
        other("Availability charge (no supply)", 574.6239, "R/month"),
    ]),
}


def main():
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    data["providers"][PROVIDER] = {
        "escalation_month": 7,
        "escalation_day": 1,
        "versions": [{"effective": EFFECTIVE, "tariffs": TARIFFS}],
    }

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"{PROVIDER}: {len(TARIFFS)} tariffs, effective {EFFECTIVE}")


if __name__ == "__main__":
    main()
