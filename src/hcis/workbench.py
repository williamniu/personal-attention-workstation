"""Personal career workspace. Research and human progress stay outside ATS recomputation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from openpyxl import load_workbook

from hcis.repositories import LocalDataStore

PREFIX = "workbench_"
TRACKS = {
    "FULL_TIME": "全职工作",
    "COFOUNDER": "联创 / 创业",
    "AI_PARTNERSHIP": "企业 AI 合作",
    "HISTORY": "历史线索 · 路径待核",
}
STATUSES = {
    "VERIFY": "待核验",
    "PREPARE": "准备材料 / 沟通",
    "CONTACTED": "已联系 · 待回应",
    "INTERVIEW": "面试 / 深入交流",
    "NEGOTIATING": "条件 / 权限谈判",
    "OFFER": "收到书面条件",
    "JOINED": "已入职 / 合作落地",
    "WATCH": "持续观察",
    "PAUSED": "暂缓",
    "CLOSED": "已关闭",
}
BOARD_GROUPS = {
    "评估核验": {"VERIFY", "WATCH"},
    "准备行动": {"PREPARE"},
    "沟通推进": {"CONTACTED", "INTERVIEW", "NEGOTIATING"},
    "条件与落地": {"OFFER", "JOINED"},
    "暂缓归档": {"PAUSED", "CLOSED"},
}
PRIORITIES = ("优先", "条件优先", "普通", "观察")
SHEETS = {
    "候选总览": ("candidates", ("候选 ID", "公司 / 主体", "审查结论")),
    "证据与审查": ("evidence", ("候选 ID", "证据类型", "来源 URL")),
    "关系历史": ("relationships", ("记录 ID", "联系人", "历史接触状态")),
}
RELATION_LABELS = {
    "previous_first10_reported_processed_in_receipt_summary_individual_delivery_not_verified":
        "历史批次称已处理 · 逐人投递未核",
    "not_in_final63_receipt_do_not_infer_sent": "不在最终回执 · 不推断已发送",
    "已发送 · 已核实": "历史已发送 · 已核实",
    "去重跳过": "历史去重跳过",
    "pending": "历史邀请 · 当时待接受",
    "dm": "历史私信",
    "blocked": "历史受限",
    "hold": "历史暂缓",
}


def now() -> str:
    return datetime.now(UTC).isoformat()


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def safe_url(value: object) -> str | None:
    raw = text(value)
    if any(ord(character) < 32 for character in raw) or "\\" in raw:
        return None
    try:
        parsed = urlsplit(raw)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username:
            return None
    except ValueError:
        return None
    return raw


def urls(value: object) -> list[str]:
    found = re.findall(r"https?://[^\s<>\"']+", text(value))
    return list(dict.fromkeys(url for item in found if (url := safe_url(item.rstrip(").,，；")))))


def canonical_profile(value: object) -> str | None:
    raw = safe_url(value)
    if not raw:
        return None
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower().removeprefix("www.")
    return urlunsplit(("https", host, parts.path.rstrip("/").lower(), "", ""))


def _serial(value: object) -> object:
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _sheet_rows(sheet: Any, required: tuple[str, ...]) -> list[dict[str, object]]:
    header_row = 0
    headers: list[str] = []
    for row in sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 20)):
        values = [text(cell.value) for cell in row]
        if all(name in values for name in required):
            header_row, headers = row[0].row, values
            break
    if not header_row:
        raise ValueError(f"{sheet.title} 缺少必需表头：{', '.join(required)}")
    result = []
    for row in sheet.iter_rows(min_row=header_row + 1):
        if not any(cell.value is not None for cell in row):
            continue
        item = {header: _serial(cell.value) for header, cell in zip(headers, row, strict=True)
                if header}
        item["_sheet_row"] = row[0].row
        item["_cell_links"] = {headers[index]: cell.hyperlink.target
                               for index, cell in enumerate(row)
                               if cell.hyperlink and headers[index]}
        result.append(item)
    return result


def _tracks(path: str) -> list[str]:
    if "联创讨论" in path:
        return ["COFOUNDER"]
    if "成熟企业" in path:
        return ["AI_PARTNERSHIP"]
    if "既有全职或合作" in path:
        return ["FULL_TIME", "AI_PARTNERSHIP"]
    if "历史岗位或关系" in path:
        return ["HISTORY"]
    return ["FULL_TIME"]


def _priority(verdict: str, name: str) -> str:
    if name in {"Labelbox", "Atlas Cloud"} or "优先核岗" in verdict:
        return "优先"
    if "条件优先" in verdict:
        return "条件优先"
    if "历史候选" in verdict or any(t in verdict for t in ("观察", "不匹配", "暂缓", "恢复")):
        return "观察"
    return "普通"


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", text(value).casefold())


def _company_links(company: object, candidates: list[dict[str, object]]) -> list[str]:
    # A company name collision is unresolved until a human supplies identity evidence.
    if _key(company) in {"braintrust", "atlas"}:
        return []
    return [str(row["id"]) for row in candidates if _key(row["company"]) == _key(company)]


def import_workbook(
    store: LocalDataStore, path: Path, *, library_file_id: str = ""
) -> dict[str, object]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    existing = store.get(PREFIX + "imports", digest)
    if existing:
        return {**existing, "reused": True}
    workbook = load_workbook(path, data_only=True)
    try:
        parsed = {collection: _sheet_rows(workbook[sheet], required)
                  for sheet, (collection, required) in SHEETS.items()}
        heading = " ".join(text(cell.value) for row in workbook["候选总览"].iter_rows(max_row=4)
                           for cell in row)
        snapshot_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", heading)
    except KeyError as error:
        raise ValueError("工作簿须包含候选总览、证据与审查、关系历史三个表。") from error
    finally:
        workbook.close()
    candidates = []
    for row in parsed["candidates"]:
        identifier = text(row.get("候选 ID"))
        if not identifier or not text(row.get("公司 / 主体")):
            raise ValueError("候选 ID 和主体名不能为空。")
        verdict, company = text(row.get("审查结论")), text(row.get("公司 / 主体"))
        candidates.append({
            "id": identifier, "company": company,
            "verdict": verdict, "origin": row.get("记录来源"),
            "tracks": _tracks(text(row.get("机会路径"))), "path": row.get("机会路径"),
            "signal": row.get("岗位 / 邀请证据"), "fit": row.get("与你的匹配"),
            "objections": row.get("主要反证 / 门槛"), "next_action": row.get("下一步只读核查"),
            "source_date": row.get("证据日期"), "domain": row.get("主体域名"),
            "priority": _priority(verdict, company),
            "status": "WATCH" if _priority(verdict, company) == "观察" else "VERIFY",
            "import_id": digest, "raw": row,
        })
    identifiers = [str(row["id"]) for row in candidates]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("候选 ID 重复；未导入。")
    for candidate in candidates:
        old = store.get(PREFIX + "candidates", str(candidate["id"]))
        if old and _key(old.get("company")) != _key(candidate.get("company")):
            old_domain = text(old.get("domain")).lower().removeprefix("www.")
            new_domain = text(candidate.get("domain")).lower().removeprefix("www.")
            if not old_domain or old_domain != new_domain:
                raise ValueError(f"候选 ID {candidate['id']} 的主体发生变化，请先核查身份映射。")
    evidence = []
    for row in parsed["evidence"]:
        identifier = text(row.get("候选 ID"))
        # Workbook-wide adversarial findings are retained even without a candidate ID.
        evidence.append({
            "id": f"{digest[:16]}:E{row['_sheet_row']}", "candidate_id": identifier,
            "company": row.get("公司 / 主体"), "kind": row.get("证据类型"),
            "detail": row.get("事实 / 限制 / 待核"), "source_date": row.get("证据日期"),
            "urls": urls(row.get("来源 URL")), "source_text": row.get("来源 URL"),
            "import_id": digest, "raw": row,
        })
    relationships = []
    for row in parsed["relationships"]:
        identifier = text(row.get("记录 ID"))
        if not identifier:
            raise ValueError("历史关系记录 ID 不能为空。")
        relationships.append({
            "id": identifier, "name": row.get("联系人"), "company": row.get("公司 / 原记录"),
            "role": row.get("角色"), "profile_url": safe_url(row.get("身份主页")),
            "canonical_profile": canonical_profile(row.get("身份主页")),
            "historical_status": row.get("历史接触状态"),
            "historical_date": row.get("历史证据时间 UTC"),
            "latest_reply": row.get("最新回复"), "limitations": row.get("冲突 / 限制"),
            "source_file_id": row.get("历史文件 ID"), "next_action": row.get("核查动作"),
            "candidate_ids": _company_links(row.get("公司 / 原记录"), candidates),
            "import_id": digest, "raw": row,
        })
    if len({row["id"] for row in relationships}) != len(relationships):
        raise ValueError("历史关系记录 ID 重复；未导入。")
    for relationship in relationships:
        old = store.get(PREFIX + "relationships", str(relationship["id"]))
        if not old:
            continue
        old_profile, new_profile = old.get("canonical_profile"), relationship.get("canonical_profile")
        same_identity = (old_profile == new_profile) if old_profile and new_profile else (
            _key(old.get("name")) == _key(relationship.get("name"))
            and _key(old.get("company")) == _key(relationship.get("company")))
        if not same_identity:
            raise ValueError(f"历史记录 ID {relationship['id']} 的身份发生变化，不能继承回执或人工状态。")
    if not snapshot_dates:
        snapshot_dates = [str(row["source_date"])[:10] for row in candidates
                          if re.match(r"^\d{4}-\d{2}-\d{2}", str(row.get("source_date") or ""))]
    receipt: dict[str, object] = {
        "id": digest, "sha256": digest, "file_name": path.name,
        "library_file_id": library_file_id, "imported_at": now(),
        "counts": {key: len(value) for key, value in parsed.items()},
        "source_snapshot": max(snapshot_dates) if snapshot_dates else None, "reused": False,
    }
    with store.transaction():
        for collection, rows in (("candidates", candidates), ("evidence", evidence),
                                 ("relationships", relationships)):
            # Keep old source versions; active IDs point at the latest imported source only.
            for row in rows:
                store.upsert(PREFIX + "source_versions", f"{digest}:{collection}:{row['id']}",
                             {"id": f"{digest}:{collection}:{row['id']}", "record": row},
                             "WORKBENCH_SOURCE_VERSION_IMPORTED")
                store.upsert(PREFIX + collection, str(row["id"]), row,
                             "WORKBENCH_RESEARCH_IMPORTED")
        store.append(PREFIX + "imports", receipt, "WORKBENCH_WORKBOOK_IMPORTED")
    return receipt


def merge_state(store: LocalDataStore, kind: str) -> list[dict[str, object]]:
    states = {str(row["id"]): row for row in store.list(PREFIX + kind + "_states")}
    return [{**row, **{key: value for key, value in states.get(str(row["id"]), {}).items()
                       if key not in {"id", "recorded_at"}},
             "updated_at": states.get(str(row["id"]), {}).get("recorded_at")}
            for row in store.list(PREFIX + kind)]


def candidates(store: LocalDataStore) -> list[dict[str, object]]:
    rows = merge_state(store, "candidates")
    return sorted(rows, key=lambda row: (PRIORITIES.index(str(row.get("priority", "普通"))),
                                         str(row.get("company", ""))))


def save_candidate(store: LocalDataStore, identifier: str, values: dict[str, object]) -> None:
    if not store.get(PREFIX + "candidates", identifier):
        raise ValueError("机会不存在。")
    if values.get("status") not in STATUSES or values.get("priority") not in PRIORITIES:
        raise ValueError("无效进展或优先级。")
    tracks = values.get("tracks")
    if not isinstance(tracks, list) or not tracks or any(track not in TRACKS for track in tracks):
        raise ValueError("请至少选择一条机会路径。")
    for field in ("due_date",):
        if values.get(field):
            date.fromisoformat(str(values[field]))
    current = store.get(PREFIX + "candidates_states", identifier) or {}
    allowed = {"status", "priority", "tracks", "favorite", "notes", "next_action", "due_date",
               "country", "cash_terms", "equity_terms", "authority_terms", "partner_scope"}
    payload = {**current, **{key: value for key, value in values.items() if key in allowed},
               "id": identifier}
    if all(current.get(key) == payload.get(key) for key in payload if key != "recorded_at"):
        return
    with store.transaction():
        store.upsert(PREFIX + "candidates_states", identifier, payload,
                     "WORKBENCH_PROGRESS_SAVED")
        store.append(PREFIX + "events", {
            "id": str(uuid4()), "candidate_id": identifier, "kind": "PROGRESS",
            "title": f"进展更新：{STATUSES[str(values['status'])]}",
            "previous_status": current.get("status"), "changes": values, "at": now(),
        }, "WORKBENCH_PROGRESS_EVENT")


def add_candidate(store: LocalDataStore, values: dict[str, object]) -> str:
    company = text(values.get("company"))
    if not company:
        raise ValueError("请填写公司 / 项目名称。")
    tracks = values.get("tracks")
    if not isinstance(tracks, list) or not tracks or any(track not in TRACKS for track in tracks):
        raise ValueError("请至少选择一条机会路径。")
    identifier = "M-" + uuid4().hex[:12]
    raw_url = text(values.get("source_url"))
    if raw_url and not safe_url(raw_url):
        raise ValueError("来源必须是有效的 http(s) 链接。")
    store.upsert(PREFIX + "candidates", identifier, {
        "id": identifier, "company": company, "tracks": tracks,
        "verdict": "手动新增 · 待核验", "origin": "个人录入", "source_date": now(),
        "signal": text(values.get("signal")), "fit": "待补充",
        "objections": "业务基础与参与条件待核实。", "priority": "普通", "status": "VERIFY",
        "next_action": text(values.get("next_action")), "source_url": raw_url,
    }, "WORKBENCH_OPPORTUNITY_ADDED")
    return identifier


def promote_legacy_opportunity(store: LocalDataStore, opportunity_id: str) -> str:
    row = store.get("opportunities", opportunity_id)
    if not row or row.get("candidate_id") != "william":
        raise ValueError("只能加入 William 的现有线索。")
    identifier = "HCIS:" + opportunity_id
    if store.get(PREFIX + "candidates", identifier):
        return identifier
    links = _company_links(row.get("company_name"), candidates(store))
    current_job = row.get("lead_type") == "CURRENT_JOB"
    store.upsert(PREFIX + "candidates", identifier, {
        "id": identifier, "company": row.get("company_name"), "tracks": ["FULL_TIME"],
        "verdict": "旧雷达岗位 · 当前条件待复核" if current_job else "历史雇主线索 · 非在招证明",
        "origin": "HCIS 岗位雷达", "signal": row.get("title"),
        "fit": "待按当前目标重新映射；旧分数不作为本看板优先级。",
        "objections": "岗位存续、资历、入职条件与当前来源证据需重新核查。",
        "status": "VERIFY", "priority": "普通", "next_action": "复核官方职位与本人经历。",
        "source_date": row.get("last_seen_at"),
        "source_url": row.get("official_apply_url") or row.get("apply_url"),
        "legacy_job_id": row.get("job_id"), "legacy_opportunity_id": opportunity_id,
        "parent_candidate_id": links[0] if len(links) == 1 else None, "raw": row,
    }, "WORKBENCH_RADAR_ITEM_ADDED")
    return identifier


def save_relationship(store: LocalDataStore, identifier: str, values: dict[str, object]) -> None:
    if not store.get(PREFIX + "relationships", identifier):
        raise ValueError("关系记录不存在。")
    allowed = {"current_stage", "latest_reply", "notes", "next_action", "candidate_ids"}
    current = store.get(PREFIX + "relationships_states", identifier) or {}
    store.upsert(PREFIX + "relationships_states", identifier,
                 {**current, **{k: v for k, v in values.items() if k in allowed}, "id": identifier},
                 "WORKBENCH_RELATIONSHIP_REVIEWED")


def save_task(store: LocalDataStore, values: dict[str, object]) -> str:
    title = text(values.get("title"))
    if not title:
        raise ValueError("任务标题不能为空。")
    if values.get("status") not in {"OPEN", "DONE", "CANCELLED"}:
        raise ValueError("无效任务状态。")
    if values.get("due_date"):
        date.fromisoformat(str(values["due_date"]))
    identifier = text(values.get("id")) or "task-" + uuid4().hex[:12]
    current = store.get(PREFIX + "tasks", identifier) or {}
    payload = {**current, **values, "id": identifier,
               "completed_at": (current.get("completed_at") or now())
               if values["status"] == "DONE" else None}
    store.upsert(PREFIX + "tasks", identifier, payload, "WORKBENCH_TASK_SAVED")
    return identifier


def seed_context(store: LocalDataStore, context: dict[str, object]) -> None:
    for kind in ("channels", "assets", "facts", "tasks", "candidates_states", "relationships_states"):
        rows = context.get(kind, [])
        if not isinstance(rows, list):
            raise ValueError(f"{kind} 必须是记录列表。")
        for row in rows:
            if not isinstance(row, dict) or not row.get("id"):
                raise ValueError(f"{kind} 必须有稳定 ID。")
            if not store.get(PREFIX + kind, str(row["id"])):
                store.upsert(PREFIX + kind, str(row["id"]), row, "WORKBENCH_CONTEXT_SEEDED")


def brief(store: LocalDataStore) -> dict[str, object]:
    rows = candidates(store)
    counts = Counter(str(row.get("status", "VERIFY")) for row in rows)
    tasks = store.list(PREFIX + "tasks")
    stage = "机会核验与材料准备"
    if counts["JOINED"]:
        stage = "已落地机会管理与其他路径评估"
    elif counts["OFFER"] or counts["NEGOTIATING"]:
        stage = "评估条件与合作权限"
    elif counts["INTERVIEW"] or counts["CONTACTED"]:
        stage = "沟通与面试推进"
    imports = sorted(store.list(PREFIX + "imports"), key=lambda row: str(row.get("imported_at")))
    relationships = store.list(PREFIX + "relationships")
    return {
        "stage": stage, "candidates": len(rows), "status_counts": dict(counts),
        "priority": sum(row.get("priority") in {"优先", "条件优先"}
                        and row.get("status") not in {"PAUSED", "CLOSED"} for row in rows),
        "active_conversations": sum(counts[key] for key in ("CONTACTED", "INTERVIEW", "NEGOTIATING")),
        "written_terms": counts["OFFER"], "landed": counts["JOINED"],
        "open_tasks": sum(row.get("status") == "OPEN" for row in tasks),
        "completed_tasks": sum(row.get("status") == "DONE" for row in tasks),
        "historical_relationship_records": len(relationships),
        "historical_contact_statuses": dict(Counter(str(row.get("historical_status"))
                                                    for row in relationships)),
        "last_import": imports[-1] if imports else None,
    }


def export_workspace(store: LocalDataStore) -> bytes:
    collections = ("candidates", "evidence", "relationships", "candidates_states",
                   "relationships_states", "tasks", "facts", "channels", "assets", "events", "imports",
                   "source_versions", "scan_sources", "scan_entries", "scan_jobs", "scan_imports",
                   "scan_profiles", "scan_runs", "scan_briefs", "scan_news")
    result = {"schema_version": 1, "exported_at": now(),
              "collections": {key: store.list(PREFIX + key) for key in collections}}
    return json.dumps(result, ensure_ascii=False, indent=2).encode()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import reviewed research into the personal workbench.")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--home", type=Path, default=Path.cwd())
    parser.add_argument("--library-file-id", default="")
    parser.add_argument("--context", type=Path)
    args = parser.parse_args()
    from hcis.settings import Settings

    store = LocalDataStore(Settings(home=args.home).database_path)
    result = import_workbook(store, args.workbook, library_file_id=args.library_file_id)
    if args.context:
        seed_context(store, json.loads(args.context.read_text()))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
