"""
tests/test_tariff_engine.py
===========================
Standalone test suite for the forest-tariff-engine package.

Covers:
  - TOU period classification (Section 1)
  - 8760-hour TOU array construction (Section 2)
  - Tariff rate lookup via JSON (Section 3)
  - Fixed-charge formula sanity check (Section 4)

Run with: pytest -v
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from tariff_engine import (
    get_tou_period,
    build_hourly_tou,
    get_tariff_rates,
    list_tariffs,
    list_tou_schedules,
)


# ============================================================================
# Section 1 - TOU period mapping
# ============================================================================

class TestTOUPeriod:
    """Spot-check get_tou_period() against the Eskom TOU schedule."""

    # High Demand (Jun-Aug) weekday
    def test_hd_weekday_peak_morning(self):
        assert get_tou_period(7, 7, 1, False) == ("HI", 1)

    def test_hd_weekday_peak_evening(self):
        assert get_tou_period(7, 18, 2, False) == ("HI", 1)

    def test_hd_weekday_peak_boundary_start(self):
        assert get_tou_period(7, 6, 3, False) == ("HI", 1)

    def test_hd_weekday_peak_boundary_end(self):
        assert get_tou_period(7, 8, 3, False) == ("HI", 2)

    def test_hd_weekday_standard_day(self):
        assert get_tou_period(7, 10, 3, False) == ("HI", 2)

    def test_hd_weekday_standard_evening(self):
        assert get_tou_period(7, 20, 4, False) == ("HI", 2)

    def test_hd_weekday_off_peak_midnight(self):
        assert get_tou_period(7, 0, 5, False) == ("HI", 3)

    def test_hd_weekday_off_peak_early(self):
        assert get_tou_period(7, 3, 5, False) == ("HI", 3)

    def test_hd_weekday_off_peak_late(self):
        assert get_tou_period(7, 22, 5, False) == ("HI", 3)

    # Low Demand weekday
    def test_ld_weekday_peak_morning(self):
        assert get_tou_period(3, 8, 1, False) == ("LO", 1)

    def test_ld_weekday_peak_boundary_start(self):
        assert get_tou_period(3, 7, 1, False) == ("LO", 1)

    def test_ld_weekday_peak_boundary_end(self):
        assert get_tou_period(3, 9, 1, False) == ("LO", 2)

    def test_ld_weekday_peak_evening(self):
        assert get_tou_period(3, 19, 2, False) == ("LO", 1)

    def test_ld_weekday_peak_evening_boundary(self):
        assert get_tou_period(3, 21, 2, False) == ("LO", 2)

    def test_ld_weekday_standard_midday(self):
        assert get_tou_period(3, 12, 3, False) == ("LO", 2)

    def test_ld_weekday_standard_hour6(self):
        assert get_tou_period(3, 6, 5, False) == ("LO", 2)

    def test_ld_weekday_off_peak(self):
        assert get_tou_period(3, 4, 5, False) == ("LO", 3)

    def test_ld_weekday_off_peak_night(self):
        assert get_tou_period(3, 23, 5, False) == ("LO", 3)

    # Saturday
    def test_saturday_standard_morning(self):
        assert get_tou_period(4, 9, 6, False) == ("LO", 2)

    def test_saturday_summer_evening_standard(self):
        # Summer (Low Demand) weekend Standard window is 18:00-20:00.
        assert get_tou_period(4, 17, 6, False) == ("LO", 3)   # 17:00 now off-peak
        assert get_tou_period(4, 18, 6, False) == ("LO", 2)   # 18:00 standard
        assert get_tou_period(4, 19, 6, False) == ("LO", 2)   # 19:00 standard
        assert get_tou_period(4, 20, 6, False) == ("LO", 3)   # 20:00 off-peak

    def test_saturday_off_peak_afternoon(self):
        assert get_tou_period(4, 14, 6, False) == ("LO", 3)

    def test_saturday_off_peak_midnight(self):
        assert get_tou_period(4, 0, 6, False) == ("LO", 3)

    def test_saturday_in_hi_season(self):
        assert get_tou_period(7, 9, 6, False) == ("HI", 2)

    # Sunday (summer Standard window 18:00-20:00)
    def test_sunday_summer_17_off_peak(self):
        assert get_tou_period(4, 17, 7, False) == ("LO", 3)

    def test_sunday_standard_18(self):
        assert get_tou_period(4, 18, 7, False) == ("LO", 2)

    def test_sunday_standard_boundary_end(self):
        assert get_tou_period(4, 19, 7, False) == ("LO", 2)

    def test_sunday_summer_20_off_peak(self):
        assert get_tou_period(4, 20, 7, False) == ("LO", 3)

    # Winter (High Demand) weekend Standard window stays 17:00-19:00.
    def test_weekend_winter_standard_17_19(self):
        assert get_tou_period(7, 17, 6, False) == ("HI", 2)   # Sat 17:00 standard
        assert get_tou_period(7, 19, 6, False) == ("HI", 3)   # Sat 19:00 off-peak
        assert get_tou_period(7, 17, 7, False) == ("HI", 2)   # Sun 17:00 standard
        assert get_tou_period(7, 19, 7, False) == ("HI", 3)   # Sun 19:00 off-peak

    def test_sunday_off_peak_morning(self):
        assert get_tou_period(4, 10, 7, False) == ("LO", 3)

    # Holidays: Excel does NOT treat holidays specially.
    def test_holiday_weekday_treated_as_saturday(self):
        assert get_tou_period(4, 9, 5, True) == ("LO", 2)

    def test_holiday_standard_evening(self):
        assert get_tou_period(4, 17, 5, True) == ("LO", 2)

    def test_holiday_off_peak(self):
        assert get_tou_period(4, 14, 5, True) == ("LO", 2)

    # Seasons
    def test_hi_season_months(self):
        for m in (6, 7, 8):
            s, _ = get_tou_period(m, 12, 1, False)
            assert s == "HI", f"Month {m} should be HI"

    def test_lo_season_months(self):
        for m in (1, 2, 3, 4, 5, 9, 10, 11, 12):
            s, _ = get_tou_period(m, 12, 1, False)
            assert s == "LO", f"Month {m} should be LO"


# ============================================================================
# Section 1b - Named TOU schedules (registry)
# ============================================================================

class TestTOUSchedules:
    """The schedule registry, the default, and the Stellenbosch 2025/26 clock."""

    def test_eskom_is_default(self):
        # Omitting schedule must equal explicitly asking for eskom.
        for m, h, wd in [(7, 7, 1), (3, 18, 1), (4, 9, 6), (7, 18, 7)]:
            assert get_tou_period(m, h, wd, False) == get_tou_period(m, h, wd, False, "eskom")

    def test_registry_lists_known_schedules(self):
        names = list_tou_schedules()
        assert "eskom" in names
        assert "stellenbosch-2025" in names

    def test_unknown_schedule_raises(self):
        with pytest.raises(KeyError):
            get_tou_period(7, 7, 1, False, "does-not-exist")

    # Stellenbosch differs from Eskom on weekday peak bands and Sundays.
    def test_stellenbosch_differs_from_eskom(self):
        # Winter weekday 08:00: Eskom peak ends at 08:00 (Standard), Stellenbosch
        # peak runs to 09:00 (Peak).
        assert get_tou_period(7, 8, 1, False, "eskom") == ("HI", 2)
        assert get_tou_period(7, 8, 1, False, "stellenbosch-2025") == ("HI", 1)
        # Sunday 18:00: Eskom is Standard, Stellenbosch is Off-Peak all Sunday.
        assert get_tou_period(4, 18, 7, False, "eskom") == ("LO", 2)
        assert get_tou_period(4, 18, 7, False, "stellenbosch-2025") == ("LO", 3)

    def test_stellenbosch_winter_weekday(self):
        S = "stellenbosch-2025"
        assert get_tou_period(7, 6, 1, False, S) == ("HI", 1)   # peak start
        assert get_tou_period(7, 9, 1, False, S) == ("HI", 2)   # peak ends 09:00
        assert get_tou_period(7, 17, 1, False, S) == ("HI", 1)  # evening peak
        assert get_tou_period(7, 19, 1, False, S) == ("HI", 2)  # peak ends 19:00
        assert get_tou_period(7, 0, 1, False, S) == ("HI", 3)   # off-peak

    def test_stellenbosch_summer_weekday(self):
        S = "stellenbosch-2025"
        assert get_tou_period(3, 7, 1, False, S) == ("LO", 1)   # peak start
        assert get_tou_period(3, 6, 1, False, S) == ("LO", 2)   # 06:00 standard
        assert get_tou_period(3, 10, 1, False, S) == ("LO", 2)  # peak ends 10:00
        assert get_tou_period(3, 18, 1, False, S) == ("LO", 1)  # evening peak
        assert get_tou_period(3, 20, 1, False, S) == ("LO", 2)  # peak ends 20:00

    def test_stellenbosch_saturday_and_sunday(self):
        S = "stellenbosch-2025"
        assert get_tou_period(3, 7, 6, False, S) == ("LO", 2)   # Sat standard
        assert get_tou_period(3, 12, 6, False, S) == ("LO", 3)  # Sat off-peak gap
        assert get_tou_period(3, 18, 6, False, S) == ("LO", 2)  # Sat evening standard
        assert get_tou_period(3, 12, 7, False, S) == ("LO", 3)  # Sunday all off-peak
        assert get_tou_period(7, 18, 7, False, S) == ("HI", 3)  # Sunday off-peak

    def test_stellenbosch_no_weekday_peak_outside_bands(self):
        # No peak at 12:00 on a Stellenbosch weekday in either season.
        assert get_tou_period(7, 12, 1, False, "stellenbosch-2025")[1] != 1
        assert get_tou_period(3, 12, 1, False, "stellenbosch-2025")[1] != 1

    def test_tariff_carries_schedule(self):
        # The final 2026/27 Stellenbosch schedule keeps the Stellenbosch clock.
        for name in ("Stellenbosch TOU LV", "Stellenbosch TOU MV", "Stellenbosch Large Power LV >80A (IND1)"):
            assert get_tariff_rates(name).tou_schedule == "stellenbosch-2025"
        assert get_tariff_rates("Eskom Miniflex").tou_schedule == "eskom"

    def test_stellenbosch_historical_schedule(self):
        # The 2025/26 rate year must keep the stellenbosch-2025 clock.
        import datetime as dt
        from tariff_engine.rates import _load_tariff_json_for_date, _resolve_tariff_rates
        data = _load_tariff_json_for_date("Stellenbosch TOU LV", dt.date(2026, 3, 1))
        rates = _resolve_tariff_rates("Stellenbosch TOU LV", data)
        assert rates.tou_schedule == "stellenbosch-2025"

    # City Power clock: same bands in both seasons, differs from Eskom.
    def test_coj_weekday(self):
        S = "coj-2025"
        for m, season in [(7, "HI"), (3, "LO")]:
            assert get_tou_period(m, 6, 1, False, S) == (season, 2)   # 06:00 standard
            assert get_tou_period(m, 7, 1, False, S) == (season, 1)   # peak 07-10
            assert get_tou_period(m, 9, 1, False, S) == (season, 1)
            assert get_tou_period(m, 10, 1, False, S) == (season, 2)
            assert get_tou_period(m, 18, 1, False, S) == (season, 1)  # peak 18-20
            assert get_tou_period(m, 20, 1, False, S) == (season, 2)
            assert get_tou_period(m, 22, 1, False, S) == (season, 3)  # off-peak 22-06
        # Winter 06:00 is peak on Eskom, standard on City Power.
        assert get_tou_period(7, 6, 1, False, "eskom") == ("HI", 1)

    def test_coj_weekend(self):
        S = "coj-2025"
        assert get_tou_period(7, 7, 6, False, S) == ("HI", 2)   # Sat standard 07-12
        assert get_tou_period(7, 12, 6, False, S) == ("HI", 3)
        assert get_tou_period(3, 18, 6, False, S) == ("LO", 2)  # Sat standard 18-20
        assert get_tou_period(3, 17, 7, False, S) == ("LO", 2)  # Sun standard 17-19
        assert get_tou_period(3, 19, 7, False, S) == ("LO", 3)

    def test_coj_tou_tariffs_carry_schedule_both_years(self):
        import datetime as dt
        from tariff_engine.rates import _load_tariff_json_for_date, _resolve_tariff_rates
        for name in ("CoJ Industrial TOU LV", "CoJ Industrial TOU MV", "CoJ Industrial TOU HV"):
            assert get_tariff_rates(name).tou_schedule == "coj-2025"
            data = _load_tariff_json_for_date(name, dt.date(2026, 3, 1))
            assert _resolve_tariff_rates(name, data).tou_schedule == "coj-2025"

    # City of Cape Town: Eskom's Low Demand clock used in both seasons.
    def test_coct_same_clock_both_seasons(self):
        S = "coct-2025"
        for wd in (1, 6, 7):
            for h in range(24):
                assert get_tou_period(7, h, wd, False, S)[1] == get_tou_period(3, h, wd, False, S)[1]
                assert get_tou_period(3, h, wd, False, S)[1] == get_tou_period(3, h, wd, False, "eskom")[1]

    def test_coct_winter_differs_from_eskom(self):
        S = "coct-2025"
        assert get_tou_period(7, 6, 1, False, S) == ("HI", 2)    # Eskom winter: peak
        assert get_tou_period(7, 8, 1, False, S) == ("HI", 1)    # Eskom winter: standard
        assert get_tou_period(7, 17, 1, False, S) == ("HI", 2)   # Eskom winter: peak
        assert get_tou_period(7, 20, 1, False, S) == ("HI", 1)   # Eskom winter: standard
        assert get_tou_period(7, 17, 7, False, S) == ("HI", 3)   # Sunday 17:00 off-peak
        assert get_tou_period(7, 19, 6, False, S) == ("HI", 2)   # Saturday 19:00 standard

    def test_coct_tou_tariffs_carry_schedule_both_years(self):
        import datetime as dt
        from tariff_engine.rates import _load_tariff_json_for_date, _resolve_tariff_rates
        for name in ("CoCT LV TOU", "CoCT MV TOU", "CoCT HV TOU"):
            assert get_tariff_rates(name).tou_schedule == "coct-2025"
            data = _load_tariff_json_for_date(name, dt.date(2026, 3, 1))
            assert _resolve_tariff_rates(name, data).tou_schedule == "coct-2025"
        assert get_tariff_rates("CoCT Small Power Users 1").tou_schedule == "eskom"

    def test_coj_2026_approved_rates(self):
        # City Power approved schedule FY26/27, energy incl. 6 c/kWh surcharge.
        lv = get_tariff_rates("CoJ Industrial TOU LV")
        assert lv.hd_peak == pytest.approx(7.7224)
        assert lv.ld_off_peak == pytest.approx(1.9235)
        assert lv.export_hd_peak == pytest.approx(1.0326)
        assert lv.demand_charge_kva == pytest.approx(461.28)
        assert lv.service_charge_pa == pytest.approx(4629.64 * 12)
        flat_lv = get_tariff_rates("CoJ Large Consumer Demand LV")
        assert flat_lv.hd_peak == pytest.approx(3.3979)
        assert flat_lv.ld_off_peak == pytest.approx(2.9096)


# Nelson Mandela Bay 2026/27, approved tariffs sheet (Eastern Cape, rows 1496-1821), R/kWh and R/kVA/m.
# name: (HD P/S/O, LD P/S/O, service R/m, demand R/kVA/m, capacity R/kVA/m, export HD, export LD)
NMB_2026 = {
    "NMB Medium Business Single Rate (T33/38)": ((4.99,) * 3, (3.69,) * 3, 1948.09, 0, 0, None, None),
    "NMB Medium Business Metered Demand (Scale 34/39)": ((4.00,) * 3, (2.96,) * 3, 1771.56, 248.83, 0, None, None),
    "NMB LV Medium Business TOU (Scale 32X/33Y/32Y)": (
        (8.45, 2.43, 1.76), (3.67, 2.30, 1.76), 1850.30, 205.79, 0, (5.07, 1.46, 1.06), (2.20, 1.38, 1.05)),
    "NMB Large Business Metered Demand (Scale 35/30)": ((3.83,) * 3, (2.51,) * 3, 7571.72, 197.99, 0, None, None),
    "NMB MV Large Business TOU (Scale 40X/40Y/40Z)": (
        (7.38, 2.29, 1.44), (3.27, 2.13, 1.66), 7402.38, 170.29, 0, (4.43, 1.37, 0.86), (1.37, 1.28, 1.00)),
    "NMB Extra High Voltage TOU (Scale 40A)": (
        (7.47, 2.24, 1.43), (3.30, 2.12, 1.58), 20333.35, 14.00, 45.00, (4.48, 1.34, 0.86), (1.98, 1.27, 0.95)),
}


class TestNelsonMandelaBay2026:
    @pytest.mark.parametrize("name", sorted(NMB_2026))
    def test_2026_rates(self, name):
        hd, ld, service, demand, capacity, exp_hd, exp_ld = NMB_2026[name]
        r = get_tariff_rates(name)
        assert (r.hd_peak, r.hd_standard, r.hd_off_peak) == pytest.approx(hd, abs=1e-6)
        assert (r.ld_peak, r.ld_standard, r.ld_off_peak) == pytest.approx(ld, abs=1e-6)
        assert r.service_charge_pa == pytest.approx(service * 12, abs=0.01)
        assert r.demand_charge_kva == pytest.approx(demand)
        assert r.capacity_charge_kva == pytest.approx(capacity)
        if exp_hd is None:
            assert r.export_hd_peak is None
        else:
            assert (r.export_hd_peak, r.export_hd_standard, r.export_hd_off_peak) == pytest.approx(exp_hd, abs=1e-6)
            assert (r.export_ld_peak, r.export_ld_standard, r.export_ld_off_peak) == pytest.approx(exp_ld, abs=1e-6)

    def test_versions_and_history(self):
        import datetime as dt
        from tariff_engine.rates import _get_raw_tariff_data, _load_tariff_json_for_date, _resolve_tariff_rates
        prov = _get_raw_tariff_data()["providers"]["Nelson Mandela Bay"]
        assert [v["effective"] for v in prov["versions"]] == ["2025-07-01", "2026-07-01"]
        # 2025/26 must still price at the old rates.
        name = "NMB Medium Business Single Rate (T33/38)"
        old = _resolve_tariff_rates(name, _load_tariff_json_for_date(name, dt.date(2026, 3, 1)))
        assert old.hd_peak == pytest.approx(4.4514)
        assert old.service_charge_pa == pytest.approx(1739.37 * 12, abs=0.01)


# Sol Plaatje 2026/27, NERSA decision Table 6 pp24-31, approved column (R/kWh, R/kVA/m).
SOL_PLAATJE_TOU = {
    "Sol Plaatje Bulk Consumer TOU LV <200 kVA": ((7.8961, 2.9463, 2.1472), (3.2234, 2.3935, 1.9742), 219.1237, 80.5896),
    "Sol Plaatje Bulk Consumer TOU LV 200-500 kVA": ((7.9506, 2.9803, 2.2833), (3.2172, 2.4629, 2.0488), 172.7022, 80.5896),
    "Sol Plaatje Bulk Consumer TOU MV": ((7.9276, 2.9081, 2.2547), (3.1328, 2.4267, 1.9732), 148.3419, 76.6900),
    "Sol Plaatje TOU NPO/NGO/Schools LV <200 kVA": ((7.1673, 2.8759, 1.9995), (3.0721, 2.3565, 1.8399), 206.9077, 98.4060),
    "Sol Plaatje TOU NPO/NGO/Schools LV 200-500 kVA": ((7.2154, 2.9222, 2.0282), (3.1494, 2.4069, 1.8803), 206.9077, 98.4060),
    "Sol Plaatje TOU NPO/NGO/Schools MV": ((7.2348, 2.9750, 2.0986), (3.2269, 2.4573, 1.9326), 160.4861, 75.9969),
    "Sol Plaatje Small Consumer TOU <70 kVA": ((9.7509, 2.9537, 1.6039), (3.1809, 2.1891, 1.3883), 0, 0),
}

SOL_PLAATJE_FLAT = {
    # name: (winter/HD, summer/LD, service R/month)
    "Sol Plaatje Business Small Power": (3.3619, 3.1323, 0),
    "Sol Plaatje Public Benefit and Schools": (3.4732, 3.2533, 0),
    "Sol Plaatje Domestic Kimlite 20A": (2.9628, 2.9628, 0),
    "Sol Plaatje Domestic Kimlite >20A": (2.7642, 2.7642, 0),
    "Sol Plaatje Domestic Kim Power Indigent Prepaid 20A": (2.7777, 2.7777, 0),
    "Sol Plaatje Streetlights": (0.8576, 0.8576, 106.1506),
}


class TestSolPlaatje2026:
    @pytest.mark.parametrize("name", sorted(SOL_PLAATJE_TOU))
    def test_tou_rates(self, name):
        hd, ld, demand, capacity = SOL_PLAATJE_TOU[name]
        r = get_tariff_rates(name)
        assert (r.hd_peak, r.hd_standard, r.hd_off_peak) == pytest.approx(hd, abs=1e-6)
        assert (r.ld_peak, r.ld_standard, r.ld_off_peak) == pytest.approx(ld, abs=1e-6)
        assert r.demand_charge_kva == pytest.approx(demand)
        assert r.capacity_charge_kva == pytest.approx(capacity)
        assert r.service_charge_pa == 0
        assert r.tou_schedule == "eskom"
        # SSEG export credits
        assert (r.export_hd_peak, r.export_hd_standard, r.export_hd_off_peak) == pytest.approx((5.7268, 1.6039, 1.1458), abs=1e-6)
        assert (r.export_ld_peak, r.export_ld_standard, r.export_ld_off_peak) == pytest.approx((2.5109, 1.5122, 1.1458), abs=1e-6)

    @pytest.mark.parametrize("name", sorted(SOL_PLAATJE_FLAT))
    def test_flat_rates(self, name):
        winter, summer, service = SOL_PLAATJE_FLAT[name]
        r = get_tariff_rates(name)
        assert (r.hd_peak, r.hd_standard, r.hd_off_peak) == pytest.approx((winter,) * 3, abs=1e-6)
        assert (r.ld_peak, r.ld_standard, r.ld_off_peak) == pytest.approx((summer,) * 3, abs=1e-6)
        assert r.service_charge_pa == pytest.approx(service * 12, abs=0.01)
        # Per-Amp capacity charges must never be priced per kVA.
        assert r.capacity_charge_kva == 0
        assert r.demand_charge_kva == 0
        assert r.export_hd_peak is None

    def test_all_tariffs_listed(self):
        names = set(list_tariffs())
        assert set(SOL_PLAATJE_TOU) | set(SOL_PLAATJE_FLAT) <= names
        assert "Sol Plaatje Availability Charge" not in names


# JB Marks 2026/27 Tariff D, Schedule of Tariffs pp12-15, bold values (R/kWh, R/kVA/m, R/m).
# name: (HD P/S/O, LD P/S/O, demand, NAC, fixed Normal Read)
JBM_LV, JBM_MV = "JB Marks Tariff D LV (230/400 V)", "JB Marks Tariff D MV (>400 V to 11 kV)"
JB_MARKS_D = {
    JBM_LV: ((9.2701, 3.5110, 2.0629), (3.7472, 2.4328, 1.7952), 149.04, 97.73, 868.15),
    JBM_MV: ((8.7965, 3.3682, 1.9442), (3.5235, 2.2202, 1.7179), 146.48, 93.33, 869.77),
}


class TestJBMarks2026:
    def test_listed_with_one_version(self):  # AC1
        from tariff_engine.rates import _get_raw_tariff_data
        assert set(JB_MARKS_D) <= set(list_tariffs())
        prov = _get_raw_tariff_data()["providers"]["JB Marks Local Municipality"]
        assert [v["effective"] for v in prov["versions"]] == ["2026-07-01"]

    @pytest.mark.parametrize("name", sorted(JB_MARKS_D))
    def test_all_rates(self, name):
        hd, ld, demand, nac, fixed = JB_MARKS_D[name]
        r = get_tariff_rates(name)
        assert (r.hd_peak, r.hd_standard, r.hd_off_peak) == pytest.approx(hd, abs=1e-6)
        assert (r.ld_peak, r.ld_standard, r.ld_off_peak) == pytest.approx(ld, abs=1e-6)
        assert (r.demand_charge_kva, r.capacity_charge_kva) == pytest.approx((demand, nac))
        assert r.service_charge_pa == pytest.approx(fixed * 12, abs=0.01)
        assert r.export_hd_peak is None and r.tou_schedule == "jbmarks-2026"

    def test_lv_low_demand(self):  # AC2
        import datetime as dt
        from tariff_engine import get_tariff_rates_for_date
        assert get_tou_period(9, 12, 1, False, "jbmarks-2026")[0] == "LO"
        for r in (get_tariff_rates_for_date(JBM_LV, dt.date(2026, 9, 1)), get_tariff_rates(JBM_LV)):
            assert (r.ld_peak, r.ld_standard, r.ld_off_peak) == pytest.approx((3.7472, 2.4328, 1.7952))
            assert r.demand_charge_kva == pytest.approx(149.04)

    def test_mv_high_demand(self):  # AC3
        import datetime as dt
        from tariff_engine import get_tariff_rates_for_date
        assert get_tou_period(7, 12, 1, False, "jbmarks-2026")[0] == "HI"
        r = get_tariff_rates_for_date(JBM_MV, dt.date(2026, 7, 15))
        assert (r.hd_peak, r.hd_standard, r.hd_off_peak) == pytest.approx((8.7965, 3.3682, 1.9442))
        assert r.capacity_charge_kva == pytest.approx(93.33)

    def test_tou_schedule(self):  # AC4 (06:30 is the 06:00 hour)
        S = "jbmarks-2026"
        assert S in list_tou_schedules()
        cases = {(3, 8, 1): ("LO", 1), (7, 8, 1): ("HI", 1), (3, 6, 1): ("LO", 2), (7, 6, 1): ("HI", 1),
                 (7, 9, 1): ("HI", 2), (7, 17, 1): ("HI", 1), (7, 19, 1): ("HI", 2), (7, 22, 1): ("HI", 3),
                 (3, 10, 1): ("LO", 2), (3, 18, 1): ("LO", 1), (3, 20, 1): ("LO", 2), (3, 22, 1): ("LO", 3),
                 (7, 7, 6): ("HI", 2), (3, 12, 6): ("LO", 3), (7, 18, 6): ("HI", 2), (3, 20, 6): ("LO", 3)}
        for (m, h, wd), want in cases.items():
            assert get_tou_period(m, h, wd, False, S) == want
            assert get_tou_period(m, h, wd, True, S) == want  # holiday = the day it falls on
        assert all(get_tou_period(m, h, 7, False, S)[1] == 3 for m in (3, 7) for h in range(24))


# Newcastle Notice CS 9/2026 pp5-6, Scales 3/4/5, R/kWh and R/kVA/m.
# name: (HD P/S/O, LD P/S/O, basic metered R/m, network demand, network capacity)
NEWCASTLE = {
    "2025/26": {
        "Newcastle Scale 3 Small Business LV": ((2.7303,) * 3, (2.7303,) * 3, 1167.64, 0, 0),
        "Newcastle Scale 3T Small Business LV TOU": ((5.2028, 2.2185, 1.0770), (3.0133, 1.9175, 0.9936), 1167.64, 0, 0),
        "Newcastle Scale 4S Medium Business LV": ((1.4803,) * 3, (1.4803,) * 3, 2511.53, 261.78, 227.04),
        "Newcastle Scale 4T Medium Business TOU Demand": ((5.8313, 2.9573, 1.6680), (4.9335, 2.2192, 1.3813), 2511.53, 82.22, 61.48),
        "Newcastle Scale 5S Large Business MV": ((1.4803,) * 3, (1.4803,) * 3, 4932.93, 237.92, 210.97),
        "Newcastle Scale 5T Large Business MV TOU": ((5.1130, 2.1794, 1.0590), (2.9609, 1.8842, 0.9777), 4932.93, 81.71, 62.01),
    },
    "2026/27": {
        "Newcastle Scale 3 Small Business LV": ((2.9760,) * 3, (2.9760,) * 3, 1272.73, 0, 0),
        "Newcastle Scale 3T Small Business LV TOU": ((5.6711, 2.4182, 1.1739), (3.2845, 2.0901, 1.0830), 1272.73, 0, 0),
        "Newcastle Scale 4S Medium Business LV": ((1.6135,) * 3, (1.6135,) * 3, 2737.57, 285.34, 247.47),
        "Newcastle Scale 4T Medium Business TOU Demand": ((6.3561, 3.2235, 1.8181), (5.3775, 2.4189, 1.5056), 2737.57, 89.62, 67.01),
        "Newcastle Scale 5S Large Business MV": ((1.6135,) * 3, (1.6135,) * 3, 5376.89, 259.33, 229.96),
        "Newcastle Scale 5T Large Business MV TOU": ((5.5732, 2.3755, 1.1543), (3.2274, 2.0538, 1.0657), 5376.89, 89.06, 67.59),
    },
}
NEWCASTLE_DATES = {
    "2025/26": [(2025, 7, 1), (2026, 6, 30)],
    "2026/27": [(2026, 7, 1), (2027, 3, 1)],
}
NEWCASTLE_CASES = [
    (year, date, name)
    for year, dates in NEWCASTLE_DATES.items()
    for date in dates
    for name in sorted(NEWCASTLE[year])
]


def _newcastle_version(effective):
    from tariff_engine.rates import _get_raw_tariff_data
    prov = _get_raw_tariff_data()["providers"]["Newcastle"]
    return next(v for v in prov["versions"] if v["effective"] == effective)


class TestNewcastle2026:
    @pytest.mark.parametrize("year,date,name", NEWCASTLE_CASES)
    def test_rates_for_date(self, year, date, name):
        # AC1-AC6 (2026/27) and AC7 (2025/26 for any date before 1 July 2026).
        import datetime as dt
        from tariff_engine import get_tariff_rates_for_date
        hd, ld, basic, demand, capacity = NEWCASTLE[year][name]
        r = get_tariff_rates_for_date(name, dt.date(*date))
        assert (r.hd_peak, r.hd_standard, r.hd_off_peak) == pytest.approx(hd, abs=1e-6)
        assert (r.ld_peak, r.ld_standard, r.ld_off_peak) == pytest.approx(ld, abs=1e-6)
        assert r.service_charge_pa == pytest.approx(basic * 12, abs=0.01)
        assert r.demand_charge_kva == pytest.approx(demand)
        assert r.capacity_charge_kva == pytest.approx(capacity)
        assert r.tou_schedule == "eskom"
        assert r.export_hd_peak is None

    @pytest.mark.parametrize("name", sorted(NEWCASTLE["2026/27"]))
    def test_latest_is_2026(self, name):
        hd, ld, basic, demand, capacity = NEWCASTLE["2026/27"][name]
        r = get_tariff_rates(name)
        assert (r.hd_peak, r.hd_standard, r.hd_off_peak) == pytest.approx(hd, abs=1e-6)
        assert (r.ld_peak, r.ld_standard, r.ld_off_peak) == pytest.approx(ld, abs=1e-6)
        assert r.service_charge_pa == pytest.approx(basic * 12, abs=0.01)

    @pytest.mark.parametrize("effective,vacant", [("2025-07-01", 1164.76), ("2026-07-01", 1269.59)])
    def test_vacant_stand_basic_charge(self, effective, vacant):
        # Vacant-stand basic charge is display-only on the Standard tariffs, never a tariff.
        tariffs = _newcastle_version(effective)["tariffs"]
        for name in ("Newcastle Scale 3 Small Business LV", "Newcastle Scale 4S Medium Business LV",
                     "Newcastle Scale 5S Large Business MV"):
            (row,) = tariffs[name]["other_charges"]
            assert (row["label"], row["value"], row["unit"]) == ("Basic charge, vacant stand", vacant, "R/month")

    def test_versions_and_names(self):
        from tariff_engine.rates import _get_raw_tariff_data
        prov = _get_raw_tariff_data()["providers"]["Newcastle"]
        assert [v["effective"] for v in prov["versions"]] == ["2025-07-01", "2026-07-01"]
        for v in prov["versions"]:
            assert set(v["tariffs"]) == set(NEWCASTLE["2026/27"])
        listed = {n for n in list_tariffs() if n.startswith("Newcastle")}
        assert listed == set(NEWCASTLE["2026/27"])

    @pytest.mark.parametrize("year,date,name", NEWCASTLE_CASES)
    def test_positive_and_tou_not_flat(self, year, date, name):
        # AC8: every Scale 3/4/5 tariff has a positive energy rate (no zero-rate entries),
        # and every TOU tariff has distinct rates across seasons and periods.
        import datetime as dt
        from tariff_engine import get_tariff_rates_for_date
        r = get_tariff_rates_for_date(name, dt.date(*date))
        cells = (r.hd_peak, r.hd_standard, r.hd_off_peak, r.ld_peak, r.ld_standard, r.ld_off_peak)
        assert min(cells) > 0
        raw = _newcastle_version("2025-07-01" if year == "2025/26" else "2026-07-01")["tariffs"][name]
        if raw["type"] == "municipal_tou":
            assert len(set(cells)) == 6


def test_every_tariff_has_a_positive_energy_rate():
    # The Solar Dashboard smoke test prices every listed tariff and refuses a non-positive rate,
    # so a charge-only entry (for example a no-supply availability charge) must not be a tariff.
    bad = []
    for name in list_tariffs():
        r = get_tariff_rates(name)
        if min(r.hd_peak, r.hd_standard, r.hd_off_peak, r.ld_peak, r.ld_standard, r.ld_off_peak) <= 0:
            bad.append(name)
    assert not bad, bad

    def test_other_charges_for_display(self):
        from tariff_engine.rates import _get_raw_tariff_data
        prov = _get_raw_tariff_data()["providers"]["Sol Plaatje Local Municipality"]
        assert [v["effective"] for v in prov["versions"]] == ["2026-07-01"]
        tariffs = prov["versions"][0]["tariffs"]
        bulk = {o["label"]: o for o in tariffs["Sol Plaatje Bulk Consumer TOU LV <200 kVA"]["other_charges"]}
        assert bulk["Reactive energy charge (all seasons, Peak and Standard)"]["value"] == 0.2934
        kimlite = [o["value"] for o in tariffs["Sol Plaatje Domestic Kimlite 20A"]["other_charges"]]
        assert kimlite == [2.9628, 3.7465]
        small = tariffs["Sol Plaatje Small Consumer TOU <70 kVA"]["other_charges"][0]
        assert (small["value"], small["unit"]) == (4.5098, "R/Amp/phase/month")


# ============================================================================
# Section 2 - build_hourly_tou
# ============================================================================

class TestBuildHourlyTOU:
    """Verify 8760-array construction and TOU distribution."""

    @pytest.fixture(scope="class")
    def tou(self):
        return build_hourly_tou(2021)

    def test_length(self, tou):
        assert len(tou["months"]) == 8760
        assert len(tou["tou_periods"]) == 8760
        assert len(tou["seasons"]) == 8760

    def test_months_range(self, tou):
        assert tou["months"].min() == 1
        assert tou["months"].max() == 12

    def test_hours_range(self, tou):
        assert tou["hours"].min() == 0
        assert tou["hours"].max() == 23

    def test_weekdays_range(self, tou):
        assert tou["weekdays"].min() >= 1
        assert tou["weekdays"].max() <= 7

    def test_tou_periods_valid(self, tou):
        assert set(np.unique(tou["tou_periods"])) <= {1, 2, 3}

    def test_seasons_valid(self, tou):
        assert set(np.unique(tou["seasons"])) <= {"HI", "LO"}

    def test_hi_season_hours(self, tou):
        hi_count = np.sum(tou["seasons"] == "HI")
        assert hi_count == 2208, f"Expected 2208 HI hours, got {hi_count}"

    def test_lo_season_hours(self, tou):
        lo_count = np.sum(tou["seasons"] == "LO")
        assert lo_count == 6552, f"Expected 6552 LO hours, got {lo_count}"

    def test_no_peak_on_weekends(self, tou):
        is_weekend = (tou["weekdays"] == 6) | (tou["weekdays"] == 7)
        weekend_peak = np.sum((tou["tou_periods"] == 1) & is_weekend & ~tou["is_holiday"])
        assert weekend_peak == 0

    def test_public_holidays_2021(self, tou):
        holiday_count = int(np.sum(tou["is_holiday"]))
        assert holiday_count >= 240

    def test_january_1_hour_0_is_holiday(self, tou):
        assert tou["is_holiday"][0] == True

    def test_christmas_is_holiday(self, tou):
        import datetime as dt
        start = dt.datetime(2021, 1, 1)
        target = dt.datetime(2021, 12, 25, 0)
        i = int((target - start).total_seconds() // 3600)
        assert tou["is_holiday"][i] == True


# ============================================================================
# Section 3 - Tariff rates (2026/27 Eskom Miniflex >900km <500V)
# ============================================================================

class TestTariffRates:
    """Verify TOU rates match 2026/27 Eskom tariff values (effective 2026-04-01)."""

    def test_miniflex_hd_peak(self):
        t = get_tariff_rates("Eskom Miniflex")
        assert math.isclose(t.hd_peak, 8.2946, rel_tol=1e-4)

    def test_miniflex_hd_standard(self):
        t = get_tariff_rates("Eskom Miniflex")
        assert math.isclose(t.hd_standard, 2.5836, rel_tol=1e-4)

    def test_miniflex_hd_off_peak(self):
        t = get_tariff_rates("Eskom Miniflex")
        assert math.isclose(t.hd_off_peak, 1.6261, rel_tol=1e-4)

    def test_miniflex_ld_peak(self):
        t = get_tariff_rates("Eskom Miniflex")
        assert math.isclose(t.ld_peak, 3.8402, rel_tol=1e-3)

    def test_miniflex_ld_standard(self):
        t = get_tariff_rates("Eskom Miniflex")
        assert math.isclose(t.ld_standard, 2.4567, rel_tol=1e-4)

    def test_miniflex_ld_off_peak(self):
        t = get_tariff_rates("Eskom Miniflex")
        assert math.isclose(t.ld_off_peak, 1.6261, rel_tol=1e-4)

    def test_miniflex_service_charge(self):
        t = get_tariff_rates("Eskom Miniflex")
        assert math.isclose(t.service_charge_pa, 5453.10, rel_tol=1e-4)

    def test_miniflex_capacity_charge(self):
        t = get_tariff_rates("Eskom Miniflex")
        assert math.isclose(t.capacity_charge_kva, 59.87, rel_tol=1e-4)

    def test_miniflex_export_hd_peak(self):
        t = get_tariff_rates("Eskom Miniflex")
        assert t.export_hd_peak is not None
        assert math.isclose(t.export_hd_peak, 7.2984, rel_tol=1e-3)

    def test_rate_method_hi_peak(self):
        t = get_tariff_rates("Eskom Miniflex")
        assert math.isclose(t.rate("HI", 1), 8.2946, rel_tol=1e-4)

    def test_rate_method_lo_standard(self):
        t = get_tariff_rates("Eskom Miniflex")
        assert math.isclose(t.rate("LO", 2), 2.4567, rel_tol=1e-4)

    def test_unknown_tariff_raises(self):
        with pytest.raises(KeyError, match="Unknown tariff"):
            get_tariff_rates("Nonexistent Tariff XYZ")

    def test_list_tariffs_contains_miniflex(self):
        tariffs = list_tariffs()
        assert "Eskom Miniflex" in tariffs

    def test_list_tariffs_contains_expected_providers(self):
        tariffs = list_tariffs()
        expected = [
            "Eskom Megaflex", "Eskom Ruraflex",
            "CoCT LV TOU", "CoCT MV TOU",
            "eThekwini Industrial TOU", "NMB LV Medium Business TOU (Scale 32X/33Y/32Y)",
            "Tshwane LV TOU", "Stellenbosch TOU LV",
        ]
        for t in expected:
            assert t in tariffs, f"Missing tariff: {t}"


# ============================================================================
# Section 4 - Fixed-charge formula sanity check
# ============================================================================

class TestFixedChargeFormula:
    """
    The fixed-charge formula (service + capacity x kva x 12 + demand x kva x 12)
    lives in solar_calculation_engine.compute_fixed_charges, but the inputs come
    from this package. Verify the inputs produce the expected R/year totals.
    """

    def test_miniflex_nmd_3000(self):
        t = get_tariff_rates("Eskom Miniflex")
        annual = t.service_charge_pa + t.capacity_charge_kva * 3000 * 12 + t.demand_charge_kva * 3000 * 12
        expected = 5453.10 + 59.87 * 3000 * 12
        assert math.isclose(annual, expected, rel_tol=1e-5)

    def test_miniflex_nmd_3000_exact(self):
        t = get_tariff_rates("Eskom Miniflex")
        annual = t.service_charge_pa + t.capacity_charge_kva * 3000 * 12 + t.demand_charge_kva * 3000 * 12
        assert math.isclose(annual, 2_160_773.10, rel_tol=1e-5)

    def test_zero_nmd(self):
        t = get_tariff_rates("Eskom Miniflex")
        annual = t.service_charge_pa + t.capacity_charge_kva * 0 * 12 + t.demand_charge_kva * 0 * 12
        assert math.isclose(annual, t.service_charge_pa, rel_tol=1e-5)


# ============================================================================
# Section 5 - Capacity charge split (generation + network)
# ============================================================================

class TestCapacitySplit:
    """The capacity charge is exposed split into generation + network, and the
    two must always sum back to the combined capacity_charge_kva."""

    def test_miniflex_2026_split(self):
        t = get_tariff_rates("Eskom Miniflex")  # current date -> 2026/27, >900km <500V
        assert math.isclose(t.generation_capacity_charge_kva, 5.29, rel_tol=1e-4)
        assert math.isclose(t.network_capacity_charge_kva, 54.58, rel_tol=1e-4)

    def test_ruraflex_2026_split(self):
        t = get_tariff_rates("Eskom Ruraflex")
        assert math.isclose(t.generation_capacity_charge_kva, 5.07, rel_tol=1e-4)
        assert math.isclose(t.network_capacity_charge_kva, 56.95, rel_tol=1e-4)

    @pytest.mark.parametrize("name", ["Eskom Miniflex", "Eskom Ruraflex"])
    def test_split_sums_to_combined(self, name):
        t = get_tariff_rates(name)
        assert math.isclose(
            t.generation_capacity_charge_kva + t.network_capacity_charge_kva,
            t.capacity_charge_kva,
            rel_tol=1e-6,
        )

    def test_unsplit_tariff_falls_back_to_network(self):
        # A tariff without a generation/network split: generation is 0 and the
        # whole capacity charge is reported as network.
        t = get_tariff_rates("Eskom Megaflex")
        assert t.generation_capacity_charge_kva == 0.0
        assert math.isclose(t.network_capacity_charge_kva, t.capacity_charge_kva, rel_tol=1e-9)


# ============================================================================
# Section 6 - Eskom 2025/26 Gen-Offset (export) rates
# ============================================================================

class TestEskom2025Export:
    """2025/26 Gen-Offset export rates (Booklet 2025/26 p45, >900km <500V)."""

    def test_miniflex_2025_export_present(self):
        import datetime as dt
        from tariff_engine.history import get_tariff_rates_for_date
        t = get_tariff_rates_for_date("Eskom Miniflex", dt.date(2025, 6, 1))
        assert t.export_hd_peak is not None
        assert math.isclose(t.export_hd_peak, 6.7106, rel_tol=1e-4)
        assert math.isclose(t.export_ld_off_peak, 1.1185, rel_tol=1e-4)

    def test_ruraflex_2025_export_present(self):
        import datetime as dt
        from tariff_engine.history import get_tariff_rates_for_date
        t = get_tariff_rates_for_date("Eskom Ruraflex", dt.date(2025, 6, 1))
        assert t.export_hd_peak is not None
        assert math.isclose(t.export_hd_peak, 6.7766, rel_tol=1e-4)
        assert math.isclose(t.export_ld_off_peak, 1.1294, rel_tol=1e-4)


# ============================================================================
# Section 6 - Service + admin charge by NMD bracket (Eskom)
# ============================================================================

class TestServiceChargeByNmd:
    """Eskom service + admin charges step up by customer category (NMD bracket).
    Municipal tariffs are flat and must ignore nmd_kva entirely."""

    def test_default_no_nmd_is_smallest_bracket(self):
        # Backward compatibility: no nmd -> <=100 kVA service, as before.
        t = get_tariff_rates("Eskom Ruraflex")
        assert math.isclose(t.service_charge_pa, 9190.70, rel_tol=1e-4)  # 25.18 * 365

    def test_ruraflex_1000kva_bracket(self):
        t = get_tariff_rates("Eskom Ruraflex", nmd_kva=1000)
        assert math.isclose(t.service_charge_pa, 215.91 * 365, rel_tol=1e-4)  # 78807.15
        assert math.isclose(t.admin_charge_pa, 21.07 * 365, rel_tol=1e-4)     # 7690.55

    def test_miniflex_mid_bracket(self):
        t = get_tariff_rates("Eskom Miniflex", nmd_kva=300)
        assert math.isclose(t.service_charge_pa, 69.91 * 365, rel_tol=1e-4)
        assert math.isclose(t.admin_charge_pa, 13.49 * 365, rel_tol=1e-4)

    def test_bracket_boundary_inclusive(self):
        # 100 kVA falls in the <=100 bracket; just above moves up.
        at = get_tariff_rates("Eskom Miniflex", nmd_kva=100)
        above = get_tariff_rates("Eskom Miniflex", nmd_kva=100.01)
        assert math.isclose(at.service_charge_pa, 14.94 * 365, rel_tol=1e-4)
        assert math.isclose(above.service_charge_pa, 69.91 * 365, rel_tol=1e-4)

    def test_key_customer(self):
        t = get_tariff_rates("Eskom Ruraflex", key_customer=True)
        assert math.isclose(t.service_charge_pa, 1216.44 * 365, rel_tol=1e-4)

    def test_2025_26_bracket_via_date(self):
        from tariff_engine import get_tariff_rates_for_date
        import datetime as _dt
        t = get_tariff_rates_for_date("Eskom Ruraflex", _dt.date(2025, 6, 1), nmd_kva=1000)
        assert math.isclose(t.service_charge_pa, 198.52 * 365, rel_tol=1e-4)
        assert math.isclose(t.admin_charge_pa, 19.37 * 365, rel_tol=1e-4)

    def test_municipal_ignores_nmd(self):
        # Municipal service charge is flat; nmd_kva must not change it, admin stays 0.
        flat = get_tariff_rates("CoCT LV TOU")
        scaled = get_tariff_rates("CoCT LV TOU", nmd_kva=5000)
        assert math.isclose(flat.service_charge_pa, scaled.service_charge_pa, rel_tol=1e-9)
        assert scaled.admin_charge_pa == 0.0


# ============================================================================
# Section 5 - eThekwini Industrial TOU voltage surcharge
# ============================================================================

class TestEThekwiniVoltageSurcharge:
    """ITOU voltage surcharge: a % on all charges except the service charge.
    Source: eThekwini tariff-rates-2026-2027.pdf p11, final tariff tables p228."""

    NAME = "eThekwini Industrial TOU"
    PDF_TABLE = {"400V": 22.5, "6.6kV": 12.75, "11kV": 10.5,
                 "33kV": 3.0, "132kV": 2.25, "275kV": 0.0}

    @staticmethod
    def _raw(effective):
        from tariff_engine.rates import _get_raw_tariff_data
        prov = _get_raw_tariff_data()["providers"]["eThekwini"]
        ver = next(v for v in prov["versions"] if v["effective"] == effective)
        return ver["tariffs"]["eThekwini Industrial TOU"]

    @staticmethod
    def _import(t):
        return (t.hd_peak, t.hd_standard, t.hd_off_peak, t.ld_peak, t.ld_standard, t.ld_off_peak)

    @pytest.mark.parametrize("effective", ["2025-07-01", "2026-07-01"])
    def test_table_matches_pdf_both_years(self, effective):
        raw = self._raw(effective)
        assert raw["voltage_surcharge_pct"] == self.PDF_TABLE
        assert raw["default_voltage"] == "400V"

    @pytest.mark.parametrize("voltage", list(PDF_TABLE))
    def test_charges_scaled_service_not(self, voltage):
        raw = self._raw("2026-07-01")
        m = 1 + self.PDF_TABLE[voltage] / 100
        t = get_tariff_rates(self.NAME, voltage=voltage)
        e = raw["energy_c_per_kwh"]
        expected = [e[s][p] * m / 100 for s in ("HD", "LD") for p in ("P", "S", "O")]
        assert all(math.isclose(a, b, rel_tol=1e-9) for a, b in zip(self._import(t), expected))
        assert math.isclose(t.demand_charge_kva, raw["demand_r_kva_month"] * m, rel_tol=1e-9)
        assert math.isclose(t.capacity_charge_kva, raw["capacity_r_kva_month"] * m, rel_tol=1e-9)
        assert math.isclose(t.network_capacity_charge_kva, t.capacity_charge_kva, rel_tol=1e-9)
        assert math.isclose(t.service_charge_pa, raw["service_r_month"] * 12, rel_tol=1e-9)
        assert (t.supply_voltage, t.voltage_surcharge_pct) == (voltage, self.PDF_TABLE[voltage])

    def test_275kv_is_unsurcharged(self):
        raw = self._raw("2026-07-01")["energy_c_per_kwh"]
        t = get_tariff_rates(self.NAME, voltage="275kV")
        assert math.isclose(t.hd_peak, raw["HD"]["P"] / 100, rel_tol=1e-12)

    @pytest.mark.parametrize("voltage", [None, "<500V", "11 kV"])
    def test_missing_or_unknown_voltage_uses_400v(self, voltage):
        t = get_tariff_rates(self.NAME, voltage=voltage)
        lv = get_tariff_rates(self.NAME, voltage="400V")
        assert (t.supply_voltage, t.voltage_surcharge_pct) == ("400V", 22.5)
        assert self._import(t) == self._import(lv)

    def test_2025_by_date_and_export_not_surcharged(self):
        import datetime as _dt
        from tariff_engine import get_tariff_rates_for_date
        raw = self._raw("2025-07-01")
        t = get_tariff_rates_for_date(self.NAME, _dt.date(2025, 8, 1), voltage="11kV")
        assert math.isclose(t.hd_peak, raw["energy_c_per_kwh"]["HD"]["P"] * 1.105 / 100, rel_tol=1e-9)
        assert math.isclose(t.demand_charge_kva, raw["demand_r_kva_month"] * 1.105, rel_tol=1e-9)
        # Export (net billing) credit is not a cost: no surcharge.
        assert math.isclose(t.export_hd_peak, raw["export_c_per_kwh"]["HD"]["P"] / 100, rel_tol=1e-12)

    def test_other_tariffs_unaffected(self):
        biz = get_tariff_rates("eThekwini Business Scale 1", voltage="400V")
        assert (biz.supply_voltage, biz.voltage_surcharge_pct) == (None, 0.0)
        assert biz.hd_peak == get_tariff_rates("eThekwini Business Scale 1").hd_peak
        mini = get_tariff_rates("Eskom Miniflex")
        assert (mini.supply_voltage, mini.voltage_surcharge_pct) == ("<500V", 0.0)

    def test_list_supply_voltages(self):
        from tariff_engine import list_supply_voltages
        assert list_supply_voltages(self.NAME) == list(self.PDF_TABLE)
        assert list_supply_voltages("Eskom Miniflex")[0] == "<500V"
        assert list_supply_voltages("eThekwini Business Scale 1") == []
        with pytest.raises(KeyError):
            list_supply_voltages("No Such Tariff")


class TestEThekwini2026Final:
    """2026/27 on the final tariff tables (printed pp224-226, 228).
    Checked at 275kV so the ITOU surcharge is 0%."""

    @staticmethod
    def _cells(t):
        return [round(x * 100, 2) for x in
                (t.hd_peak, t.hd_standard, t.hd_off_peak, t.ld_peak, t.ld_standard, t.ld_off_peak)]

    def test_itou_2026(self):
        t = get_tariff_rates("eThekwini Industrial TOU", voltage="275kV")
        assert self._cells(t) == [667.89, 187.31, 133.91, 293.04, 176.64, 133.91]
        assert (t.demand_charge_kva, t.capacity_charge_kva) == (176.51, 60.81)
        assert math.isclose(t.service_charge_pa, 8079.99 * 12, rel_tol=1e-9)

    def test_itou_2026_net_billing_export_not_surcharged(self):
        for v in ("275kV", "400V"):
            t = get_tariff_rates("eThekwini Industrial TOU", voltage=v)
            exp = [round(x * 100, 2) for x in (t.export_hd_peak, t.export_hd_standard, t.export_hd_off_peak,
                                               t.export_ld_peak, t.export_ld_standard, t.export_ld_off_peak)]
            assert exp == [640.77, 160.19, 106.79, 265.92, 149.52, 106.79]

    def test_scale1_2026_is_seasonal(self):
        t = get_tariff_rates("eThekwini Business Scale 1")
        assert self._cells(t) == [415.47] * 3 + [400.89] * 3
        assert (t.demand_charge_kva, t.capacity_charge_kva) == (0, 0)
        assert math.isclose(t.service_charge_pa, 528.16 * 12, rel_tol=1e-9)

    @pytest.mark.parametrize("date, cells, service, demand", [
        ((2025, 8, 1), [642.15, 321.30, 156.52, 316.82, 254.87, 148.26], 680.02, 137.04),
        ((2026, 8, 1), [699.95, 350.22, 170.61, 345.34, 277.81, 161.61], 741.23, 149.38),
    ])
    def test_commercial_tou_both_years(self, date, cells, service, demand):
        import datetime as _dt
        from tariff_engine import get_tariff_rates_for_date
        t = get_tariff_rates_for_date("eThekwini Commercial TOU", _dt.date(*date))
        assert self._cells(t) == cells
        assert t.demand_charge_kva == demand
        assert math.isclose(t.service_charge_pa, service * 12, rel_tol=1e-9)
        assert (t.supply_voltage, t.voltage_surcharge_pct) == (None, 0.0)

    def test_2025_scale1_and_itou_unchanged(self):
        import datetime as _dt
        from tariff_engine import get_tariff_rates_for_date
        s1 = get_tariff_rates_for_date("eThekwini Business Scale 1", _dt.date(2025, 8, 1))
        assert self._cells(s1) == [370.32] * 6
        it = get_tariff_rates_for_date("eThekwini Industrial TOU", _dt.date(2025, 8, 1), voltage="275kV")
        assert self._cells(it) == [616.88, 172.88, 123.54, 270.56, 163.02, 123.54]
        assert it.demand_charge_kva == 207.35
