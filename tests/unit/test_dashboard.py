from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from hcis.dashboard.tables import UNKNOWN, display_rows, filter_rows, local_time, sort_rows
from hcis.repositories import LocalDataStore
from hcis.settings import Settings

APP = Path(__file__).parents[2] / "src/hcis/dashboard/app.py"


def test_source_dates_do_not_borrow_another_channels_freshness() -> None:
    row = {
        "company_name": "Example AI", "platform_sources": ["careers", "myvisajobs"],
        "last_seen_at": "2026-09-10T12:00:00Z",
        "source_captured_at": {
            "careers": "2026-09-10T12:00:00Z", "myvisajobs": "2026-08-31T13:00:00Z",
        },
        "chinese_environment": "YES", "employee_count_min": 100,
        "chinese_workforce_percent": 50,
    }
    displayed = display_rows([row], "myvisajobs")[0]
    assert displayed["captured_at"] == "2026-08-31 09:00:00"
    assert displayed["captured_careers"] == "2026-09-10 08:00:00"
    assert displayed["company_size"] == UNKNOWN
    assert displayed["employee_count_min"] is None
    assert displayed["chinese_workforce_percent"] is None
    assert displayed["chinese_workforce_level"] == UNKNOWN
    assert displayed["chinese_environment"] == "YES"
    row.pop("source_captured_at")
    assert display_rows([row], "myvisajobs")[0]["captured_at"] == UNKNOWN
    row["platform_sources"] = ["careers"]
    assert display_rows([row], "careers")[0]["captured_at"] == "2026-09-10 08:00:00"


def test_all_columns_can_sort_and_filter_and_unknowns_stay_last() -> None:
    rows = [{"employee_count_min": 20, "company": "Alpha"},
            {"employee_count_min": None, "company": UNKNOWN},
            {"employee_count_min": 100, "company": "Beta"}]
    assert [row["employee_count_min"] for row in sort_rows(rows, "employee_count_min", True)] == [
        100, 20, None,
    ]
    assert [row["employee_count_min"] for row in sort_rows(rows, "employee_count_min", False)] == [
        20, 100, None,
    ]
    assert filter_rows(rows, "employee_count_min", "≥", "50") == [rows[2]]
    assert filter_rows(rows, "employee_count_min", "等于", "100.0") == [rows[2]]
    assert filter_rows(rows, "company", "包含", "ALP") == [rows[0]]
    assert filter_rows(rows, "company", "未知") == [rows[1]]
    assert len(filter_rows(rows, "employee_count_min", "已知")) == 2
    dated = [{"captured_at": "2026-09-10 23:59:59"}, {"captured_at": "2026-09-11 00:00:00"}]
    assert filter_rows(dated, "captured_at", "≤", "2026-09-10") == dated[:1]
    assert local_time("2026-09-10") == "2026-09-10"
    sizes = [{"company_size": "51–200 人", "employee_count_min": 51},
             {"company_size": "1001–5000 人", "employee_count_min": 1001}]
    assert sort_rows(sizes, "company_size", True) == list(reversed(sizes))


def test_dashboard_loads_all_rows_filters_full_set_and_preserves_edit_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalDataStore(Settings(home=tmp_path).database_path)
    records = [(f"william:job-{index}", {
        "id": f"william:job-{index}", "job_id": f"job-{index}", "candidate_id": "william",
        "company_name": f"Company {index}", "title": "AI Engineer", "score": index,
        "platform_sources": ["careers"], "favorite": False, "manual_status": "NEW",
        "notes": "", "first_seen_at": "2026-09-10T12:00:00Z",
    }) for index in range(1805)]
    store.bulk_upsert("opportunities", records, "TEST")
    monkeypatch.setattr("hcis.api.app.data_store", lambda: store)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    assert len(app.dataframe[-1].value) == 1805
    app.session_state["channel-william"] = "官方 Careers"
    app.run()
    assert not app.exception
    assert len(app.dataframe[-1].value) == 1805
    # AppTest does not serialize interactive tab changes; exercise widget reruns in the default tab.
    app.session_state["channel-william"] = "全部结果 / All results"
    app.run()
    app.multiselect(key="filters-william-all").select("company").run()
    app.text_input(key="value-william-all-company").set_value("Company 1804").run()
    assert len(app.dataframe[-1].value) == 1
    assert app.dataframe[-1].value.iloc[0]["job_id"] == "job-1804"
    app.text_input(key="value-william-all-company").set_value("").run()
    app.toggle(key="editing").set_value(True).run()
    extra = {**records[0][1], "id": "william:extra", "job_id": "extra"}
    store.upsert("opportunities", "william:extra", extra, "TEST")
    app.run()
    assert not app.exception
    assert len(app.dataframe[-1].value) == 1805
    app.toggle(key="editing").set_value(False).run()
    assert len(app.dataframe[-1].value) == 1806
    assert store.list("opportunity_states") == []
