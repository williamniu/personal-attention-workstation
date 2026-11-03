from __future__ import annotations

import json
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
from streamlit.testing.v1 import AppTest

from hcis.repositories import LocalDataStore
from hcis.settings import Settings
from hcis.workbench import (
    PREFIX, add_candidate, brief, candidates, export_workspace, import_workbook,
    merge_state, promote_legacy_opportunity, safe_url, save_candidate, save_task, seed_context,
)


def workbook(path: Path) -> Path:
    w = Workbook()
    w.remove(w.active)
    sheets = {
        "候选总览": [
            ["候选 ID", "公司 / 主体", "审查结论", "记录来源", "机会路径", "岗位 / 邀请证据", "与你的匹配", "主要反证 / 门槛", "下一步只读核查", "证据日期", "主体域名"],
            ["C001", "Cresta", "优先核岗", "研究", "有薪全职（联创未核实）", "AI Engineer, GTM", "Agent / GTM", "年限未知不是应届岗", "映射实际经历", "2026-10-31", "cresta.com"],
            ["C016", "Labelbox", "历史关系：现状待核", "历史", "既有全职或合作线索", "FDRS 内推意向", "FDE", "内推是否提交未知", "核对具体岗位", "2026-10-31", "labelbox.com"],
            ["C018", "Aonflow", "商业验证待核", "历史", "联创讨论（非已接受）", "联创邀请", "产品工程", "客户、现金与权限未知", "核查商业和权限", "2026-10-31", "aonflow.com"],
        ],
        "证据与审查": [
            ["候选 ID", "公司 / 主体", "证据类型", "事实 / 限制 / 待核", "证据日期", "来源 URL"],
            ["C001", "Cresta", "岗位", "完整官方 JD", "2026-10-31", "https://example.com/job"],
            ["C001", "Cresta", "反方", "无年限不等于应届岗", "2026-10-31", "https://example.com/job"],
            ["C016", "Labelbox", "Labelbox referrer unnamed", "历史时点未知", "2026-10-30", "https://example.com/referral"],
        ],
        "关系历史": [
            ["记录 ID", "联系人", "公司 / 原记录", "角色", "身份主页", "历史接触状态", "历史证据时间 UTC", "最新回复", "冲突 / 限制", "历史文件 ID", "核查动作"],
            ["N059", "Lei Cao", "Labelbox", "FDRS", "https://www.linkedin.com/in/lei-c/", "已发送 · 已核实", "2026-10-20", "未知", "愿意内推不等于内部已提交", "original-receipt", "核对现状"],
            ["N072", "Walter", "Atlas / Patrick", "CTO", "https://www.linkedin.com/in/walter", "not_in_final63_receipt_do_not_infer_sent", "2026-10-20", "未知", "不是 Atlas Cloud", "original-network", "核查身份"],
            ["N074", "Jack", "Braintrust", "Engineer", "https://www.linkedin.com/in/jack", "已发送 · 已核实", "2026-10-20", "未知", "排名替换不能继承状态", "final-receipt", "核查身份"],
        ],
    }
    for title, rows in sheets.items():
        sheet = w.create_sheet(title)
        sheet.append(["研究快照"])
        sheet.append([])
        for row in rows:
            sheet.append(row)
    w.save(path)
    return path


def seeded(tmp_path: Path) -> LocalDataStore:
    store = LocalDataStore(Settings(home=tmp_path).database_path)
    import_workbook(store, workbook(tmp_path / "source.xlsx"))
    seed_context(store, {
        "facts": [{"id": "labelbox-confirmed", "candidate_id": "C016", "title": "曹磊 / Lei Cao 已确认", "detail": "用户确认愿意内推；尚未确认内部提交。", "source": "用户本线程确认", "source_date": "2026-10-31"}],
        "channels": [{"id": "yc", "category": "岗位", "name": "YC", "url": "https://www.ycombinator.com/jobs", "purpose": "发现团队"}],
        "assets": [{"id": "context", "kind": "历史对话", "title": "历史上下文", "source_date": "2026-10-30", "url": "https://chatgpt.com/c/example"}],
    })
    save_task(store, {"id": "task-one", "title": "核对岗位证据", "candidate_id": "C001", "status": "OPEN"})
    return store


def test_import_replay_preserves_history_human_progress_and_existing_hcis(tmp_path: Path) -> None:
    store = LocalDataStore(Settings(home=tmp_path).database_path)
    legacy = {"id": "william:old", "candidate_id": "william", "favorite": True, "notes": "原备注"}
    store.upsert("opportunity_states", legacy["id"], legacy, "BASELINE")
    original = store.list("opportunity_states")
    path = workbook(tmp_path / "source.xlsx")
    receipt = import_workbook(store, path)
    assert receipt["counts"] == {"candidates": 3, "evidence": 3, "relationships": 3}
    save_candidate(store, "C001", {"status": "INTERVIEW", "priority": "优先", "tracks": ["FULL_TIME"], "notes": "真实人工进展"})
    assert import_workbook(store, path)["reused"] is True
    assert next(row for row in candidates(store) if row["id"] == "C001")["notes"] == "真实人工进展"
    assert store.list("opportunity_states") == original
    assert len(store.list(PREFIX + "imports")) == 1
    relations = {row["id"]: row for row in store.list(PREFIX + "relationships")}
    assert relations["N059"]["candidate_ids"] == ["C016"]
    assert relations["N072"]["candidate_ids"] == []
    assert relations["N074"]["candidate_ids"] == []
    assert relations["N072"]["historical_status"] != relations["N074"]["historical_status"]
    assert len(store.list(PREFIX + "relationships")) == 3


def test_new_workbook_cannot_reassign_an_existing_id_to_another_entity(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    path = tmp_path / "source.xlsx"
    w = load_workbook(path)
    w["候选总览"]["B4"] = "Different Legal Entity"
    w["候选总览"]["K4"] = "different.example"
    w.save(path)
    before = store.list(PREFIX + "candidates")
    with pytest.raises(ValueError, match="主体发生变化"):
        import_workbook(store, path)
    assert store.list(PREFIX + "candidates") == before


def test_new_source_version_keeps_manual_edits_and_retains_original_evidence(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    save_candidate(store, "C001", {"status": "PREPARE", "priority": "优先", "tracks": ["FULL_TIME"], "next_action": "我的下一步"})
    path = tmp_path / "source.xlsx"
    w = load_workbook(path)
    w["候选总览"]["I4"] = "更新后的研究建议"
    w["候选总览"]["A1"] = "核验快照 2026-11-02"
    w.save(path)
    assert import_workbook(store, path)["source_snapshot"] == "2026-11-02"
    current = next(row for row in candidates(store) if row["id"] == "C001")
    assert current["next_action"] == "我的下一步"
    assert current["raw"]["下一步只读核查"] == "更新后的研究建议"
    assert len(store.list(PREFIX + "evidence")) == 6


def test_relationship_rank_reassignment_cannot_inherit_another_persons_status(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    path = tmp_path / "source.xlsx"
    w = load_workbook(path)
    w["关系历史"]["B4"] = "Different Person"
    w["关系历史"]["E4"] = "https://www.linkedin.com/in/different-person"
    w.save(path)
    before = store.list(PREFIX + "relationships")
    with pytest.raises(ValueError, match="身份发生变化"):
        import_workbook(store, path)
    assert store.list(PREFIX + "relationships") == before


def test_tracks_tasks_and_legacy_promotion_do_not_invent_qualification(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    by_id = {row["id"]: row for row in candidates(store)}
    assert by_id["C001"]["tracks"] == ["FULL_TIME"]
    assert by_id["C018"]["tracks"] == ["COFOUNDER"]
    assert brief(store)["written_terms"] == 0
    assert brief(store)["open_tasks"] == 1
    save_task(store, {"id": "task-one", "title": "核对岗位证据", "status": "DONE"})
    assert brief(store)["completed_tasks"] == 1
    store.upsert("opportunities", "william:history", {"id": "william:history", "job_id": "history", "candidate_id": "william", "company_name": "Cresta", "lead_type": "H1B_ROLE_HISTORY", "score": 99, "title": "Old LCA"}, "BASELINE")
    identifier = promote_legacy_opportunity(store, "william:history")
    row = store.get(PREFIX + "candidates", identifier)
    assert row and row["verdict"] == "历史雇主线索 · 非在招证明"
    assert row["priority"] == "普通" and row["parent_candidate_id"] == "C001"
    assert promote_legacy_opportunity(store, "william:history") == identifier
    assert len(candidates(store)) == 4
    assert json.loads(export_workspace(store))["collections"]["relationships"][0]["raw"]


def test_untrusted_urls_and_invalid_progress_fail_before_writing(tmp_path: Path) -> None:
    store = seeded(tmp_path)
    for url in ["javascript:alert(1)", "https://user:secret@example.com", "https://[invalid", "https://example.com\n/unsafe"]:
        assert safe_url(url) is None
    with pytest.raises(ValueError):
        add_candidate(store, {"company": "New", "tracks": ["FULL_TIME"], "source_url": "javascript:alert(1)"})
    with pytest.raises(ValueError):
        save_candidate(store, "C001", {"status": "AUTOSUBMIT", "priority": "优先", "tracks": ["FULL_TIME"]})
    assert store.list(PREFIX + "candidates_states") == []


def test_interactive_workspace_navigates_saves_and_completes_tasks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = seeded(tmp_path)
    monkeypatch.setattr("hcis.api.app.data_store", lambda: store)
    monkeypatch.setattr("hcis.dashboard.workbench.get_settings", lambda: Settings(home=tmp_path))
    app = AppTest.from_file(str(Path(__file__).parents[2] / "src/hcis/dashboard/app.py"), default_timeout=20).run()
    assert not app.exception
    app.button(key="brief-open-C016").click().run()
    assert not app.exception
    assert app.radio(key="career-navigation").value == "机会看板"
    assert app.button(key="board-open-FULL_TIME-C016")
    assert app.button(key="board-open-AI_PARTNERSHIP-C016")
    assert app.selectbox(key="wb-detail-selector").value == "C016"
    current = next(widget for widget in app.selectbox if widget.label == "当前进展")
    current.set_value("PREPARE")
    notes = next(widget for widget in app.text_area if widget.label == "个人备注 / 决策理由")
    notes.set_value("已核对岗位，需要曹磊确认提交状态")
    next(button for button in app.button if button.label == "保存进展与下一步").click().run()
    assert not app.exception
    assert next(row for row in candidates(store) if row["id"] == "C016")["status"] == "PREPARE"
    for page in ("关系与联系", "渠道与资料", "数据与备份", "岗位雷达", "行动清单"):
        app.radio(key="career-navigation").set_value(page).run()
        assert not app.exception, page
    app.button(key="task-done-task-one").click().run()
    assert brief(store)["completed_tasks"] == 1
    assert merge_state(store, "relationships")[0]["historical_status"] == "已发送 · 已核实"
