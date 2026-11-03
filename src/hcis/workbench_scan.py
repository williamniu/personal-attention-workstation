"""Collect evidence, prepare a review packet, and publish a bounded daily career brief.

Recall rules prepare inputs. The scheduled Codex chat supplies the semantic review;
an unreviewed shortlist is never presented as accepted personalized recommendations.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

import httpx
import yaml  # type: ignore[import-untyped]
from bs4 import BeautifulSoup

from hcis.repositories import LocalDataStore
from hcis.settings import Settings
from hcis.sources.discovery import (
    PublicWeb,
    Row,
    domain,
    fetch_directory,
    identify_jobs,
    job_url,
    public_url,
    read_board,
    read_employer,
    stable_hash,
)
from hcis.workbench import PREFIX, candidates

SCAN = "workbench_scan_"
DIRECTIONS = {
    "Agent / Applied AI": (
        "agentic",
        "ai agent",
        "agents",
        "llm",
        "applied ai",
        "大模型",
        "智能体",
    ),
    "RL / 研究 / 评估": (
        "reinforcement",
        "post-training",
        "post training",
        "research",
        "scientist",
        "evaluation",
        "alignment",
        "rlhf",
        "强化学习",
        "评估",
        "研究",
    ),
    "产品 / 设计工程": (
        "design engineer",
        "product engineer",
        "full stack",
        "full-stack",
        "fullstack",
        "figma",
        "prototype",
        "产品工程",
        "设计工程",
        "用户体验",
    ),
    "FDE / 客户落地": (
        "forward deployed",
        "field engineer",
        "solutions engineer",
        "implementation",
        "customer engineer",
        "developer relations",
        "devrel",
        "企业落地",
    ),
    "GTM / 业务系统": (
        "gtm",
        "go-to-market",
        "growth engineer",
        "business systems",
        "revenue systems",
    ),
    "ML / 软件工程": (
        "machine learning",
        "software engineer",
        "python",
        "pytorch",
        "typescript",
        "react",
        "机器学习",
        "开发",
        "工程师",
    ),
}
PROJECTS = {
    "agent-controls": (
        "NodeWitness",
        ["Agent / Applied AI", "RL / 研究 / 评估"],
        "治理与可审计工作流；历史材料支持，当前生产可靠性另核",
    ),
    "enterprise-delivery": (
        "Data Center Site-Sourcing",
        ["FDE / 客户落地", "Agent / Applied AI"],
        "端到端企业工作流与证据处理；业务数字和缺失 runtime 不作已验证能力",
    ),
    "gtm-systems": (
        "Atlas Daily Lead Agent",
        ["GTM / 业务系统", "Agent / Applied AI"],
        "GTM 原型与线索处理；precision / 转化和 mock 回退问题仍须说明",
    ),
    "product-data": (
        "Atlas Operations & Growth",
        ["产品 / 设计工程", "ML / 软件工程"],
        "产品界面、数据与控制层；不推出专业设计履历或任职年限",
    ),
    "ml-research": (
        "Computer Vision / Quantum Capstone",
        ["RL / 研究 / 评估", "ML / 软件工程"],
        "模型实验与研究思维；不推出前沿 RL 训练或大规模模型训练经验",
    ),
}


def now() -> str:
    return datetime.now(UTC).isoformat()


def _time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except ValueError:
        return None


def _without_recorded(row: Row) -> Row:
    return {key: value for key, value in row.items() if key != "recorded_at"}


def load_config(home: Path) -> Row:
    return dict(yaml.safe_load((home / "config/sources/discovery.yaml").read_text()))


def direction_matches(title: str, description: str = "") -> list[str]:
    text = f"{title} {description}".casefold()
    return [name for name, terms in DIRECTIONS.items() if any(term in text for term in terms)]


def _recall_priority(row: Row) -> int:
    title = str(row.get("title") or row.get("name") or "")
    body = str(row.get("description", ""))
    value = 4 * len(direction_matches(title)) + len(direction_matches("", body))
    if row.get("category") in {"人工智能", "AI & Robotics", "Featured"}:
        value += 3
    if row.get("stage") in {"IPO", "Acquired", "Exited"}:
        value -= 8
    if re.search(
        r"recruit|account executive|sales development|\b(?:vp|director|head of)\b", title, re.I
    ):
        value -= 5
    return value


def profile_snapshot(store: LocalDataStore, home: Path, config: Row) -> Row:
    fact: Row = {
        "id": "opportunity-scope-20261102",
        "kind": "用户确认",
        "status": "CONFIRMED",
        "title": "按实际职责发现机会，不设职位名称白名单",
        "source_date": "2026-11-02",
        "source": "本聊天用户直接确认",
        "detail": "研究与开发均考虑：RL / Agent 评估、Applied AI、FDE、GTM、Product Design "
        "Engineer / Product Engineer 及相关跨职能职责；每来源每轮深读 20，"
        "全部来源合并每日最多 10 条。",
    }
    store.upsert(PREFIX + "facts", fact["id"], fact, "WORKBENCH_SCOPE_CONFIRMED")
    audit_path = home / "docs/WILLIAM_AGENTIC_APPLIED_AI_INTERVIEW_GRILL.md"
    audit = audit_path.read_text() if audit_path.exists() else ""
    projects = [
        {
            "id": key,
            "project": project,
            "directions": directions,
            "boundary": boundary,
            "source": str(audit_path.relative_to(home)),
            "source_date": "2026-08-31",
            "evidence_level": "HISTORICAL_PROJECT_AUDIT_NOT_REVERIFIED",
        }
        for key, (project, directions, boundary) in PROJECTS.items()
        if any(part.strip() in audit for part in project.split("/"))
    ]
    payload = {
        "version": config["profile_version"],
        "candidate": "william",
        "facts": [_without_recorded(row) for row in store.list(PREFIX + "facts")],
        "project_evidence": projects,
        "project_audit_hash": stable_hash(audit),
        "directions": DIRECTIONS,
        "unknown": [
            "任职年限、专业设计作品与大规模训练能力须逐岗核对",
            "当前工作授权、入职条件和签证支持须独立核查",
            "历史项目材料不是当前生产业绩或新一轮验证",
        ],
    }
    payload["digest"] = stable_hash(payload)
    store.upsert(SCAN + "profiles", payload["digest"], payload, "WORKBENCH_PROFILE_VERSIONED")
    return payload


def sync_sources(store: LocalDataStore, config: Row) -> None:
    for spec in config["sources"]:
        old = store.get(PREFIX + "channels", spec["id"])
        if not old:
            store.upsert(
                PREFIX + "channels",
                spec["id"],
                {
                    "id": spec["id"],
                    "name": spec["name"],
                    "url": spec["url"],
                    "category": "VC / Startup 发现",
                    "purpose": "公司发现、官方岗位核验与每日机会研究",
                    "limitations": spec["reason"],
                    "source_date": "2026-11-02",
                    "status": "已登记扫描入口 · 运行状态单独显示",
                },
                "WORKBENCH_CHANNEL_REGISTERED",
            )
    configured = {spec["id"]: spec for spec in config["sources"]}
    for channel in cast(list[Row], store.list(PREFIX + "channels")):
        spec = configured.get(channel["id"])
        previous = _without_recorded(store.get(SCAN + "sources", channel["id"]) or {})
        record = {
            **previous,
            "id": channel["id"],
            "name": channel["name"],
            "url": channel["url"],
            "mode": spec["mode"] if spec else "browser_review",
            "policy_url": spec.get("policy_url") if spec else None,
            "policy_reviewed_at": "2026-11-02" if spec else None,
            "policy_note": spec["reason"]
            if spec
            else "原渠道入口保留；需逐源核查公开列表、条款与浏览器覆盖后摄入。不是已自动采集。",
        }
        if record["mode"] == "restricted":
            record.update(status="RESTRICTED", coverage_complete=False)
        elif not previous:
            record.update(status="QUEUED", coverage_complete=False)
        store.upsert(SCAN + "sources", channel["id"], record, "WORKBENCH_SOURCE_REGISTERED")


def audit_channels(settings: Settings) -> list[Row]:
    """Inspect existing channel entry points without claiming a working collector."""
    config = load_config(settings.home)
    store = LocalDataStore(settings.database_path)
    sync_sources(store, config)
    configured = {spec["id"] for spec in config["sources"]}
    web = PublicWeb()
    receipts: list[Row] = []
    try:
        for source in cast(list[Row], store.list(SCAN + "sources")):
            if source["id"] in configured:
                continue
            receipt = _without_recorded(source)
            receipt.update(access_audited_at=now(), coverage_complete=False)
            try:
                response = web.get(source["url"])
                soup = BeautifulSoup(response.text, "html.parser")
                receipt.update(
                    http_status=response.status_code,
                    final_url=str(response.url),
                    page_title=soup.title.get_text(strip=True) if soup.title else None,
                    status="BROWSER_REVIEW_REQUIRED",
                    message="公开入口响应成功；尚需浏览器核对列表与覆盖，不代表已自动扫描。",
                )
                policy_links = [
                    public_url(str(a["href"]), str(response.url))
                    for a in soup.select("a[href]")
                    if re.search(r"terms|条款|用户协议|使用协议", a.get_text(" ", strip=True), re.I)
                    and str(a["href"]).startswith(("/", "http"))
                ]
                if policy_links:
                    policy_url = policy_links[0]
                    receipt["policy_url"] = policy_url
                    try:
                        policy = web.get(policy_url)
                        text = BeautifulSoup(policy.text, "html.parser").get_text(" ", strip=True)
                        excerpts = [
                            text[max(0, match.start() - 150) : match.end() + 250]
                            for match in list(
                                re.finditer(r"scrap|robot|automated access|爬虫|抓取", text, re.I)
                            )[:5]
                        ]
                        receipt["policy_excerpts"] = excerpts
                        receipt["policy_hash"] = stable_hash(text)
                        if excerpts:
                            receipt["message"] += " 条款含自动访问相关表述，需审阅后决定准入。"
                    except (httpx.HTTPError, ValueError, PermissionError) as error:
                        receipt["policy_error"] = str(error)
                else:
                    receipt["policy_note"] = "本页未定位到使用条款链接，自动准入保持待核。"
            except (httpx.HTTPError, ValueError, PermissionError) as error:
                receipt.update(
                    status="RESTRICTED" if isinstance(error, PermissionError) else "UNAVAILABLE",
                    message=f"入口审核未完成：{type(error).__name__}: {error}",
                )
            store.upsert(
                SCAN + "sources", source["id"], receipt, "WORKBENCH_CHANNEL_ACCESS_AUDITED"
            )
            receipts.append(receipt)
            print(f"渠道审核 {source['name']}: {receipt['status']}", flush=True)
    finally:
        web.close()
    _write_json(settings.home / "data/discovery/audit/channel-access.json", receipts)
    return receipts


def ingest_directory(store: LocalDataStore, payload: Row) -> Row:
    source = str(payload.get("source", ""))
    captured = _time(payload.get("captured_at"))
    rows = payload.get("companies")
    coverage = payload.get("coverage")
    if (
        payload.get("schema_version") != 1
        or not source
        or captured is None
        or captured > datetime.now(UTC) + timedelta(minutes=5)
        or not isinstance(rows, list)
        or not isinstance(coverage, dict)
    ):
        raise ValueError("Invalid discovery snapshot schema / capture time / coverage")
    digest = stable_hash(payload)
    receipt_id = source + ":" + digest
    if old := store.get(SCAN + "imports", receipt_id):
        return {**old, "idempotent_replay": True, "inserted": 0, "changed": 0}
    health = _without_recorded(store.get(SCAN + "sources", source) or {})
    last_capture = _time(health.get("captured_at"))
    if last_capture and captured <= last_capture:
        raise ValueError("Older or reused capture time cannot replace a newer directory")
    normalized: list[Row] = []
    for row in rows:
        if not isinstance(row, dict) or not str(row.get("name", "")).strip():
            raise ValueError("Company entries require a name")
        item = dict(row)
        item["detail_url"] = public_url(str(item.get("detail_url", "")))
        if item.get("website"):
            item["website"] = public_url(item["website"])
        identity = item["detail_url"] + "|" + item["name"].casefold()
        item.update(
            id=source + ":" + stable_hash(identity)[:20],
            source=source,
            source_hash=stable_hash(item),
        )
        normalized.append(item)
    if len({item["id"] for item in normalized}) != len(normalized):
        raise ValueError("Duplicate identities in directory snapshot")
    inserted = changed = 0
    with store.transaction():
        for item in normalized:
            old = _without_recorded(store.get(SCAN + "entries", item["id"]) or {})
            if not old:
                inserted += 1
            elif old.get("source_hash") != item["source_hash"]:
                changed += 1
            record = {
                **old,
                **item,
                "directory_name": item["name"],
                "first_seen_at": old.get("first_seen_at", payload["captured_at"]),
                "last_seen_at": payload["captured_at"],
                "source_captured_at": payload["captured_at"],
                "changed_at": payload["captured_at"]
                if old and old.get("source_hash") != item["source_hash"]
                else old.get("changed_at"),
                "identity_status": "VERIFIED_DOMAIN" if item.get("website") else "DETAIL_REQUIRED",
            }
            if old.get("name_verified") and item.get("name_verified") is False:
                record.update(name=old["name"], name_verified=True)
            if not item.get("website") and old.get("website"):
                record["website"] = old["website"]
            store.upsert(SCAN + "entries", item["id"], record, "WORKBENCH_DIRECTORY_OBSERVED")
        health.update(
            status="DIRECTORY_CAPTURED",
            captured_at=payload["captured_at"],
            last_success_at=payload["captured_at"],
            coverage=coverage,
            coverage_complete=coverage.get("complete") is True,
            directory_count=len(normalized),
            new_companies=inserted,
            changed_companies=changed,
        )
        store.upsert(SCAN + "sources", source, health, "WORKBENCH_DIRECTORY_CAPTURED")
        receipt = {
            "id": receipt_id,
            "source": source,
            "digest": digest,
            "captured_at": payload["captured_at"],
            "inserted": inserted,
            "changed": changed,
            "count": len(normalized),
            "idempotent_replay": False,
        }
        store.upsert(SCAN + "imports", receipt_id, receipt, "WORKBENCH_SNAPSHOT_IMPORTED")
    return receipt


def ingest_workbench_directory(settings: Settings, path: Path) -> Row:
    """Ingest an actually observed browser list or the existing workbench watchlist."""
    payload = json.loads(path.read_text())
    store = LocalDataStore(settings.database_path)
    source = str(payload.get("source", ""))
    if source == "workbench" and not store.get(SCAN + "sources", source):
        store.upsert(
            SCAN + "sources",
            source,
            {
                "id": source,
                "name": "既有 Workbench 官方复核",
                "mode": "browser_review",
                "status": "QUEUED",
                "coverage_complete": False,
                "policy_note": "本机历史候选清单；公司与岗位须回官方来源逐项复核。",
            },
            "WORKBENCH_WATCHLIST_REGISTERED",
        )
    registered = store.get(SCAN + "sources", source)
    if not registered or registered.get("mode") == "restricted":
        raise ValueError("Source is unknown or restricted; do not ingest an automated capture")
    return ingest_directory(store, payload)


def ingest_news(store: LocalDataStore, data: Row, observed_at: str) -> int:
    """Keep the official free summary and its raw date; an empty window erases nothing."""
    if _time(observed_at) is None or not isinstance(data.get("items"), list):
        raise ValueError("News requires a capture timestamp and items list")
    rows = []
    for item in data["items"]:
        if not isinstance(item, dict) or not str(item.get("title", "")).strip():
            raise ValueError("News requires a title")
        link = public_url(str(item.get("link", "")))
        rows.append(
            {
                "id": "itjuzi:" + stable_hash(link)[:24],
                "source": "itjuzi",
                "title": item["title"],
                "summary": item.get("summary"),
                "url": link,
                "published_at_raw": item.get("pub_date"),
                "published_timezone": None,
                "observed_at": observed_at,
                "coverage": "FREE_TODAY_SUMMARY_ONLY",
            }
        )
    inserted = 0
    with store.transaction():
        for row in rows:
            old = store.get(SCAN + "news", row["id"])
            inserted += int(old is None)
            row["first_seen_at"] = old.get("first_seen_at") if old else observed_at
            store.upsert(SCAN + "news", row["id"], row, "WORKBENCH_NEWS_OBSERVED")
    return inserted


def save_research(store: LocalDataStore, result: Row) -> Row:
    company = result["company"]
    observed = result["observed_at"]
    old = _without_recorded(store.get(SCAN + "entries", company["id"]) or {})
    boards = {board["id"]: board for board in old.get("boards", [])}
    boards.update({board["id"]: board for board in result["boards"]})
    record = {
        **old,
        **company,
        "research_observed_at": observed,
        "researched_hash": company.get("source_hash"),
        "research_errors": result["errors"],
        "pages": result["pages"],
        "boards": list(boards.values()),
        "research_status": "PARTIAL" if result["errors"] else "REVIEW_READY",
    }
    inserted = changed = 0
    by_board: dict[str, set[str]] = {}
    with store.transaction():
        for row in result["jobs"]:
            item = dict(row)
            item["url"] = job_url(item["url"])
            previous = _without_recorded(store.get(SCAN + "jobs", item["id"]) or {})
            content = {
                key: item.get(key)
                for key in (
                    "title",
                    "location",
                    "description",
                    "url",
                    "posted_at",
                    "employment_type",
                )
            }
            if not previous:
                inserted += 1
            elif previous.get("content_hash") != stable_hash(content):
                changed += 1
            item.update(
                content_hash=stable_hash(content),
                visibility="ACTIVE",
                source_ids=sorted(set(previous.get("source_ids", []) + [item["source"]])),
                entry_ids=sorted(set(previous.get("entry_ids", []) + [item["entry_id"]])),
                first_seen_at=previous.get("first_seen_at", observed),
                last_seen_at=observed,
                changed_at=observed
                if previous and previous.get("content_hash") != stable_hash(content)
                else previous.get("changed_at"),
            )
            store.upsert(SCAN + "jobs", item["id"], item, "WORKBENCH_OFFICIAL_JOB_OBSERVED")
            by_board.setdefault(item.get("board", "employer_page"), set()).add(item["id"])
        complete = {board["id"] for board in result["boards"] if board["complete"]}
        for previous in cast(list[Row], store.list(SCAN + "jobs")):
            board_id = str(previous.get("board") or "")
            if (
                company["id"] in previous.get("entry_ids", [previous.get("entry_id")])
                and board_id in complete
                and previous["id"] not in by_board.get(board_id, set())
                and previous.get("visibility") == "ACTIVE"
            ):
                store.upsert(
                    SCAN + "jobs",
                    previous["id"],
                    {
                        **_without_recorded(previous),
                        "visibility": "CLOSED",
                        "closed_observed_at": observed,
                    },
                    "WORKBENCH_OFFICIAL_JOB_CLOSED",
                )
        store.upsert(SCAN + "entries", company["id"], record, "WORKBENCH_COMPANY_RESEARCHED")
    return {"new_jobs": inserted, "changed_jobs": changed, "jobs_observed": len(result["jobs"])}


def _barriers(title: str, description: str) -> list[str]:
    result = ["工作授权、签证支持与入职条件尚需确认"]
    if re.search(r"\bstaff\b|\bprincipal\b|\bdirector\b|\bsenior\b|\bhead of\b", title, re.I):
        result.append("职位名称含资深／负责人级别；须核对实际 ownership 与资历")
    years = sorted(set(re.findall(r"\b(\d{1,2})\+?\s*(?:years|年)", description, re.I)))
    if years:
        result.append("JD 出现年限表述 " + "/".join(years) + " 年；需核对是否属于硬要求")
    if re.search(r"Ph\.?D|doctorate|博士", description, re.I):
        result.append("JD 出现博士相关要求／偏好，须核对适用条款")
    return result


def review_candidates(store: LocalDataStore, profile: Row) -> list[Row]:
    combined: dict[str, Row] = {}
    company_history: dict[str, list[Row]] = {}
    for item in cast(list[Row], store.list("jobs")):
        if item.get("lead_type") == "H1B_ROLE_HISTORY":
            name = str(item.get("company_name", "")).casefold()
            company_history.setdefault(name, []).append(item)
        if (
            item.get("visibility") != "ACTIVE"
            or item.get("lead_type") != "CURRENT_JOB"
            or not item.get("official_apply_url")
        ):
            continue
        url = job_url(str(item["official_apply_url"]))
        times = item.get("source_captured_at") or {}
        captured = times.get("careers") if isinstance(times, dict) else None
        combined[url] = {
            "id": "role:" + stable_hash(url)[:24],
            "kind": "CURRENT_JOB",
            "company": item.get("company_name"),
            "title": item.get("title"),
            "description": item.get("description", ""),
            "location": item.get("location"),
            "url": url,
            "source_ids": list(item.get("platform_sources") or []),
            "observed_at": captured,
            "official_evidence": "既有官方 ATS 采集",
            "legacy_job_id": item["id"],
            "posted_at": item.get("posted_at"),
        }
    entries = {item["id"]: item for item in cast(list[Row], store.list(SCAN + "entries"))}
    for item in cast(list[Row], store.list(SCAN + "jobs")):
        url = job_url(item["url"])
        if item.get("visibility") != "ACTIVE":
            closed = _time(item.get("closed_observed_at"))
            legacy_observed = _time(combined.get(url, {}).get("observed_at"))
            if closed and (not legacy_observed or closed >= legacy_observed):
                combined.pop(url, None)
            continue
        old = combined.get(url, {})
        entry = entries.get(item["entry_id"], {})
        combined[url] = {
            **old,
            "id": "role:" + stable_hash(url)[:24],
            "kind": "CURRENT_JOB",
            "company": item["company"],
            "title": item["title"],
            "description": item["description"],
            "location": item.get("location"),
            "url": url,
            "observed_at": item["observed_at"],
            "source_ids": sorted(
                set(old.get("source_ids", []) + item.get("source_ids", [item["source"]]))
            ),
            "official_evidence": "渠道官网回链到雇主岗位／官方 ATS",
            "company_evidence": {
                "directory": entry.get("description"),
                "official_pages": entry.get("pages", []),
                "stage": entry.get("stage"),
            },
            "posted_at": item.get("posted_at"),
        }
    rows = list(combined.values())
    research_domains: set[str] = set()
    for item in entries.values():
        if not item.get("pages") or not item.get("website"):
            continue
        website = item["website"]
        company_domain = domain(website)
        if company_domain in research_domains:
            continue
        research_domains.add(company_domain)
        rows.append(
            {
                "id": "company:" + stable_hash(company_domain)[:24],
                "kind": "RESEARCH_LEAD",
                "company": item["name"],
                "title": "公司发展与参与机会研究",
                "description": item.get("official_description") or item.get("description", ""),
                "url": website,
                "source_urls": list(
                    dict.fromkeys(
                        [website, item["detail_url"]]
                        + [page["url"] for page in item.get("pages", [])]
                    )
                ),
                "source_ids": sorted(
                    {
                        entry["source"]
                        for entry in entries.values()
                        if entry.get("website") and domain(entry["website"]) == company_domain
                    }
                ),
                "observed_at": item.get("research_observed_at"),
                "company_evidence": {
                    "directory": item.get("description"),
                    "official_pages": item.get("pages", []),
                    "stage": item.get("stage"),
                },
                "note": "公司研究线索；未从公司背景推出正在招聘或联创需求",
            }
        )
    for item in cast(list[Row], candidates(store)):
        if item.get("status") in {"CLOSED", "PAUSED", "JOINED"}:
            continue
        raw_urls = re.findall(r"https?://[^\s<>]+", str(item.get("source_url") or ""))
        evidence = [
            e
            for e in cast(list[Row], store.list(PREFIX + "evidence"))
            if e.get("candidate_id") == item["id"]
        ]
        evidence_urls = list(
            dict.fromkeys(raw_urls + [u for e in evidence for u in e.get("urls", [])])
        )
        rows.append(
            {
                "id": "workbench:" + item["id"],
                "kind": "RESEARCH_LEAD",
                "company": item["company"],
                "title": item.get("signal") or "公司／联创线索核验",
                "description": "\n".join(
                    str(item.get(k) or "") for k in ("fit", "signal", "objections", "next_action")
                ),
                "url": evidence_urls[0] if evidence_urls else None,
                "source_urls": evidence_urls,
                "source_ids": ["workbench"],
                "observed_at": item.get("source_date"),
                "tracks": item.get("tracks"),
                "workbench_candidate_id": item["id"],
                "human_status": item.get("status"),
                "historical_fit": item.get("fit"),
                "evidence": evidence,
                "note": "历史研究线索；当前岗位／联创需求须重新核实",
            }
        )
    for item in rows:
        title, body = str(item.get("title", "")), str(item.get("description", ""))
        matches = direction_matches(title, body)
        item["interest_directions"] = matches
        item["project_evidence_ids"] = [
            project["id"]
            for project in profile["project_evidence"]
            if set(matches).intersection(project["directions"])
        ]
        item["barriers"] = _barriers(title, body)
        captured = _time(item.get("observed_at"))
        if captured is None or datetime.now(UTC) - captured > timedelta(days=3):
            item["barriers"].append("证据日期未知或距今超过 3 天；不得当作本轮已核实")
        history = company_history.get(str(item.get("company", "")).casefold(), [])
        item["historical_sponsorship_context"] = {
            "records": len(history),
            "sources": sorted({s for h in history for s in h.get("platform_sources", [])}),
            "meaning": "名称关联的历史 LCA 背景，非岗位开放或当前赞助承诺；法律主体须核实",
        }
        item["recall_priority"] = _recall_priority(item)
    rows.sort(key=lambda item: (-item["recall_priority"], str(item.get("company")), item["id"]))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
    temporary.replace(path)


def refresh_known_boards(store: LocalDataStore, web: PublicWeb, day: str) -> list[Row]:
    """Job changes must be detected even when a VC directory entry has not changed."""
    receipts = []
    seen: set[str] = set()
    for entry in cast(list[Row], store.list(SCAN + "entries")):
        if not entry.get("website"):
            continue
        for board in entry.get("boards", []):
            identifier = board["id"]
            if identifier in seen:
                continue
            seen.add(identifier)
            observed = _time(board.get("observed_at"))
            if (
                board.get("complete") is True
                and observed
                and observed.astimezone(ZoneInfo("America/Chicago")).date().isoformat() == day
            ):
                continue
            provider, board_id = identifier.split(":", 1)
            result = {
                "company": entry,
                "observed_at": now(),
                "pages": entry.get("pages", []),
                "jobs": [],
                "boards": [],
                "errors": [],
            }
            try:
                jobs, coverage = read_board(web, provider, board_id)
                coverage["observed_at"] = result["observed_at"]
                result["jobs"], result["boards"] = jobs, [coverage]
                identify_jobs(result)
                receipts.append(
                    {"board": identifier, **save_research(store, result), "status": "CAPTURED"}
                )
            except (httpx.HTTPError, ValueError, PermissionError, KeyError, TypeError) as error:
                receipts.append({"board": identifier, "status": "UNAVAILABLE", "error": str(error)})
    return receipts


def scan_workbench(
    settings: Settings,
    *,
    force: bool = False,
    source: str | None = None,
    prepare_only: bool = False,
) -> Row:
    config = load_config(settings.home)
    extra_source = None
    if source and source not in {spec["id"] for spec in config["sources"]}:
        registered = LocalDataStore(settings.database_path).get(SCAN + "sources", source)
        if not registered or registered.get("mode") == "restricted":
            raise ValueError("Unknown or restricted discovery source")
        extra_source = {**registered, "mode": "browser_snapshot"}
    store = LocalDataStore(settings.database_path)
    day = datetime.now(ZoneInfo(config["timezone"])).date().isoformat()
    latest = store.get(SCAN + "runs", day)
    if latest and not force and not source and not prepare_only:
        return {**latest, "reused": True}
    sync_sources(store, config)
    if extra_source:
        config["sources"].append(extra_source)
    profile = profile_snapshot(store, settings.home, config)
    output = settings.home / "output/workbench" / day
    output.mkdir(parents=True, exist_ok=True)
    if latest:
        archive = output / "attempts" / str(latest["input_digest"])[:16]
        archive.mkdir(parents=True, exist_ok=True)
        for name in (
            "scan.json",
            "review-input.json",
            "all-candidates.json",
            "profile.json",
            "brief.json",
            "brief.md",
            "known-board-refresh.json",
        ):
            if (output / name).is_file() and not (archive / name).exists():
                shutil.copy2(output / name, archive / name)
    if prepare_only:
        return prepare_review(
            settings,
            store,
            config,
            profile,
            cast(Row, latest.get("counts", {})) if latest else {},
            [],
        )
    web = PublicWeb()
    counts: Row = {"new_companies": 0, "changed_companies": 0, "new_jobs": 0, "changed_jobs": 0}
    selected_source = source
    try:
        for spec in config["sources"]:
            if selected_source and spec["id"] != selected_source:
                continue
            source = spec["id"]
            health = _without_recorded(store.get(SCAN + "sources", source) or {})
            if spec["mode"] == "restricted":
                continue
            try:
                if spec["mode"] == "official_free_api":
                    response = web._request(
                        "POST",
                        "https://www.itjuzi.com/api/telegraph/get_list",
                        data={"date_scope": "today", "page": 1},
                        headers={"User-Agent": "itjuzi-bulletin-skill/2.0"},
                    )
                    payload = response.json()
                    if payload.get("status") != "success" or not isinstance(
                        payload.get("data"), dict
                    ):
                        raise ValueError(
                            "Official ITjuzi API did not return a successful data object"
                        )
                    data = payload["data"]
                    counts["new_news"] = counts.get("new_news", 0) + ingest_news(store, data, now())
                    _write_json(
                        output / "itjuzi-free.json", {"observed_at": now(), "response": payload}
                    )
                    health.update(
                        status="PARTIAL_CAPTURE"
                        if data.get("items")
                        else "EMPTY_WINDOW_UNVERIFIED",
                        checked_at=now(),
                        coverage_complete=False,
                        api_items=data.get("items_returned"),
                        api_total=data.get("total"),
                        date_scope=data.get("date_scope"),
                        message="官方免费今日摘要窗口；不代表网页／历史全量。空结果不删除旧线索。",
                    )
                    store.upsert(SCAN + "sources", source, health, "WORKBENCH_NEWS_WINDOW_OBSERVED")
                    continue
                if spec["mode"] == "browser_snapshot":
                    receipt = {"inserted": 0, "changed": 0}
                else:
                    payload = fetch_directory(web, spec)
                    _write_json(output / f"{source}-directory.json", payload)
                    receipt = ingest_directory(store, payload)
                counts["new_companies"] += receipt["inserted"]
                counts["changed_companies"] += receipt["changed"]
                queue = [
                    item
                    for item in cast(list[Row], store.list(SCAN + "entries"))
                    if item["source"] == source
                ]
                queue.sort(
                    key=lambda item: (
                        item.get("researched_hash") == item.get("source_hash"),
                        str(item.get("research_observed_at") or ""),
                        -_recall_priority(item),
                        item["id"],
                    )
                )
                selected = queue[: int(config["deep_read_per_source"])]
                successes = 0
                with ThreadPoolExecutor(max_workers=2) as pool:
                    pending_reads = {
                        pool.submit(read_employer, web, item): item for item in selected
                    }
                    for index, future in enumerate(as_completed(pending_reads), 1):
                        item = pending_reads[future]
                        print(
                            f"{spec['name']}: 深读 {index}/{len(selected)} {item['name']}",
                            flush=True,
                        )
                        try:
                            result = future.result()
                            for board in result["boards"]:
                                board["observed_at"] = result["observed_at"]
                            job_counts = save_research(store, result)
                            counts["new_jobs"] += job_counts["new_jobs"]
                            counts["changed_jobs"] += job_counts["changed_jobs"]
                            successes += bool(result["pages"])
                            _write_json(
                                output / "research" / f"{stable_hash(item['id'])[:20]}.json", result
                            )
                        except (
                            httpx.HTTPError,
                            ValueError,
                            PermissionError,
                            KeyError,
                            TypeError,
                        ) as error:
                            store.upsert(
                                SCAN + "entries",
                                item["id"],
                                {
                                    **_without_recorded(item),
                                    "last_attempt_at": now(),
                                    "research_status": "UNAVAILABLE",
                                    "research_errors": [f"{type(error).__name__}: {error}"],
                                },
                                "WORKBENCH_RESEARCH_FAILED",
                            )
                updated = _without_recorded(store.get(SCAN + "sources", source) or {})
                pending = sum(
                    item.get("researched_hash") != item.get("source_hash")
                    for item in store.list(SCAN + "entries")
                    if item["source"] == source
                )
                updated.update(
                    status="PARTIAL_RESEARCH" if pending else "RESEARCH_CAPTURED",
                    checked_at=now(),
                    deep_read_attempted=len(selected),
                    deep_read_with_pages=successes,
                    deep_read_limit=config["deep_read_per_source"],
                    research_pending=pending,
                    message="名录覆盖与公司／岗位深入研读分别计数；最终推荐等待 Codex 语义审阅。",
                )
                store.upsert(SCAN + "sources", source, updated, "WORKBENCH_SOURCE_RESEARCH_UPDATED")
            except (httpx.HTTPError, ValueError, PermissionError, KeyError, TypeError) as error:
                health = _without_recorded(store.get(SCAN + "sources", source) or health)
                health.update(
                    status="RESTRICTED" if isinstance(error, PermissionError) else "UNAVAILABLE",
                    checked_at=now(),
                    message=f"{type(error).__name__}: {error}",
                    coverage_complete=False,
                )
                store.upsert(SCAN + "sources", source, health, "WORKBENCH_SOURCE_FAILED")
        board_receipts = refresh_known_boards(store, web, day)
        _write_json(output / "known-board-refresh.json", board_receipts)
        for receipt in board_receipts:
            counts["new_jobs"] += receipt.get("new_jobs", 0)
            counts["changed_jobs"] += receipt.get("changed_jobs", 0)
    finally:
        web.close()
    return prepare_review(settings, store, config, profile, counts, board_receipts)


def prepare_review(
    settings: Settings,
    store: LocalDataStore,
    config: Row,
    profile: Row,
    counts: Row,
    board_receipts: list[Row],
) -> Row:
    day = datetime.now(ZoneInfo(config["timezone"])).date().isoformat()
    output = settings.home / "output/workbench" / day
    all_candidates = review_candidates(store, profile)
    zone = ZoneInfo(config["timezone"])

    def today(value: Any) -> bool:
        parsed = _time(value)
        return bool(parsed and parsed.astimezone(zone).date().isoformat() == day)

    legacy_urls = {
        job_url(str(row["official_apply_url"]))
        for row in store.list("jobs")
        if row.get("official_apply_url")
    }
    entries = store.list(SCAN + "entries")
    jobs = store.list(SCAN + "jobs")
    daily_counts = {
        "new_directory_records": sum(
            today(row.get("first_seen_at")) for row in entries if row.get("source") != "workbench"
        ),
        "changed_directory_records": sum(today(row.get("changed_at")) for row in entries),
        "new_jobs": sum(
            today(row.get("first_seen_at")) and row["url"] not in legacy_urls for row in jobs
        ),
        "changed_jobs": sum(today(row.get("changed_at")) for row in jobs),
        "new_news": sum(today(row.get("first_seen_at")) for row in store.list(SCAN + "news")),
    }
    # Keep diverse roles in the review packet; the complete pool remains a local artifact.
    per_company: Counter[str] = Counter()
    shortlist = []
    for item in all_candidates:
        name = str(item["company"])
        if not item["interest_directions"] or per_company[name] >= 3:
            continue
        shortlist.append(item)
        per_company[name] += 1
        if len(shortlist) >= 120:
            break
    source_health = store.list(SCAN + "sources")
    legacy_health = store.list("source_health")
    packet = {
        "schema_version": 1,
        "date": day,
        "timezone": config["timezone"],
        "prepared_at": now(),
        "profile": profile,
        "candidates": shortlist,
        "all_candidate_count": len(all_candidates),
        "all_candidates_digest": stable_hash(all_candidates),
        "source_health": source_health,
        "legacy_source_health": legacy_health,
        "counts": daily_counts,
        "attempt_counts": counts,
        "board_refresh": board_receipts,
        "news": store.list(SCAN + "news"),
        "recommendation_limit": config["recommendation_limit"],
        "review_instructions": "综合新目录、旧 Workbench 和官方岗位。"
        "按职责对照个人事实，最多 10 条，"
        "说明商业证据、匹配、门槛和下一步；不把历史 LCA 当在招。"
        "引用 packet 内的候选 ID、事实 ID 和证据链接。",
    }
    packet["digest"] = stable_hash(packet)
    _write_json(output / "all-candidates.json", all_candidates)
    _write_json(output / "review-input.json", packet)
    _write_json(output / "profile.json", profile)
    run = {
        "id": day,
        "date": day,
        "status": "REVIEW_REQUIRED",
        "prepared_at": packet["prepared_at"],
        "input_digest": packet["digest"],
        "profile_digest": profile["digest"],
        "counts": daily_counts,
        "attempt_counts": counts,
        "review_input": str(output / "review-input.json"),
        "all_candidate_count": len(all_candidates),
        "shortlist_count": len(shortlist),
        "reused": False,
    }
    store.upsert(SCAN + "runs", day, run, "WORKBENCH_SCAN_PREPARED")
    _write_json(output / "scan.json", run)
    return run


def publish_brief(settings: Settings, review_path: Path) -> Row:
    review = json.loads(review_path.read_text())
    config = load_config(settings.home)
    day = str(review.get("date", ""))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("Review requires an ISO date")
    output = settings.home / "output/workbench" / day
    packet = json.loads((output / "review-input.json").read_text())
    if review.get("input_digest") != packet["digest"]:
        raise ValueError("Review does not match the current evidence packet")
    recommendations = review.get("recommendations")
    if not isinstance(recommendations, list) or len(recommendations) > int(
        config["recommendation_limit"]
    ):
        raise ValueError("Daily recommendations must be a list of at most 10 overall")
    pool = json.loads((output / "all-candidates.json").read_text())
    if stable_hash(pool) != packet["all_candidates_digest"]:
        raise ValueError("Complete candidate pool does not match the review packet")
    known = {row["id"]: row for row in pool}
    facts = {
        row["id"] for row in packet["profile"]["facts"] + packet["profile"]["project_evidence"]
    }
    seen: set[str] = set()
    accepted: list[Row] = []
    for item in recommendations:
        identifier = item.get("candidate_id")
        if identifier not in known or identifier in seen:
            raise ValueError("Unknown or repeated candidate in daily review")
        row = known[identifier]
        if item.get("track") not in {"FULL_TIME", "COFOUNDER", "AI_PARTNERSHIP", "RESEARCH"}:
            raise ValueError("Unknown opportunity track")
        if item["track"] == "COFOUNDER" and (
            not item.get("cofounder_evidence") or "COFOUNDER" not in row.get("tracks", [])
        ):
            raise ValueError(
                "Co-founder recommendations require an observed invitation; "
                "founding jobs are not invitations"
            )
        if not all(
            str(item.get(key, "")).strip() for key in ("why", "fit", "barriers", "next_action")
        ):
            raise ValueError(
                "Every recommendation needs reasoning, fit, barriers and a next action"
            )
        if not item.get("fact_ids") or not set(item["fact_ids"]).issubset(facts):
            raise ValueError("Personal fit must cite known profile evidence IDs")
        allowed = set(row.get("source_urls", []) + ([row["url"]] if row.get("url") else []))
        allowed.update(
            page["url"] for page in row.get("company_evidence", {}).get("official_pages", [])
        )
        links = item.get("evidence_urls", [])
        if not links or not set(links).issubset(allowed):
            raise ValueError("Recommendation links must come from observed candidate evidence")
        seen.add(identifier)
        accepted.append({**item, "candidate": row, "rank": len(accepted) + 1})
    brief = {
        "schema_version": 1,
        "date": day,
        "timezone": config["timezone"],
        "input_digest": packet["digest"],
        "profile_digest": packet["profile"]["digest"],
        "reviewer": "Codex semantic review",
        "reviewed_at": review.get("reviewed_at") or now(),
        "summary": str(review.get("summary", "")),
        "recommendations": accepted,
        "source_health": packet["source_health"],
        "legacy_source_health": packet["legacy_source_health"],
        "counts": packet["counts"],
        "coverage_note": str(review.get("coverage_note", "")),
    }
    store = LocalDataStore(settings.database_path)
    previous = store.get(SCAN + "briefs", day)
    digest = stable_hash({key: value for key, value in brief.items() if key != "reviewed_at"})
    if previous and previous.get("content_hash") == digest:
        return {**previous, "idempotent_replay": True}
    brief["content_hash"] = digest
    run = _without_recorded(store.get(SCAN + "runs", day) or {})
    with store.transaction():
        store.upsert(SCAN + "briefs", day, brief, "WORKBENCH_DAILY_BRIEF_PUBLISHED")
        store.upsert(
            SCAN + "runs",
            day,
            {
                **run,
                "status": "PUBLISHED",
                "reviewed_at": brief["reviewed_at"],
                "recommendations": len(accepted),
            },
            "WORKBENCH_SCAN_REVIEWED",
        )
    _write_json(output / "brief.json", brief)
    lines = [f"# 每日机会重点 · {day}", "", brief["summary"], "", brief["coverage_note"], ""]
    for item in accepted:
        row = item["candidate"]
        lines.extend(
            [
                f"## {item['rank']}. {row['company']} · {row['title']}",
                f"路径：{item['track']}",
                f"值得看：{item['why']}",
                f"与你的关联：{item['fit']}",
                f"门槛：{item['barriers']}",
                f"下一步：{item['next_action']}",
                *[f"证据：{link}" for link in item["evidence_urls"]],
                "",
            ]
        )
    lines.extend(["## 渠道状态", ""])
    for source in packet["source_health"]:
        lines.append(
            f"- {source['name']}：{source['status']}；"
            f"名录 {source.get('directory_count', '未知')}；"
            f"待深读 {source.get('research_pending', '未知')}；"
            f"{source.get('message') or source.get('policy_note')}"
        )
    (output / "brief.md").write_text("\n".join(lines) + "\n")
    return brief


def latest_brief(store: LocalDataStore) -> Row | None:
    rows = store.list(SCAN + "briefs")
    return (
        max(rows, key=lambda row: (str(row.get("date")), str(row.get("reviewed_at"))))
        if rows
        else None
    )
