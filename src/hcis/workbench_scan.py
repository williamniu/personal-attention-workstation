"""Collect evidence, prepare a review packet, and publish a bounded daily career brief.

Recall rules prepare inputs. The scheduled Codex chat supplies the semantic review;
an unreviewed shortlist is never presented as accepted personalized recommendations.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from contextlib import nullcontext
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
    identify_jobs,
    job_url,
    public_url,
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
            "url": spec["url"] if spec else channel["url"],
            "mode": spec["mode"] if spec else "browser_review",
            "policy_url": spec.get("policy_url") if spec else None,
            "policy_reviewed_at": "2026-11-02" if spec else None,
            "policy_note": spec["reason"]
            if spec
            else "原渠道入口保留；需逐源核查公开列表、条款与浏览器覆盖后摄入。不是已自动采集。",
            "user_deferred": bool(spec and spec.get("user_deferred")),
            "deferred_reason": spec.get("deferred_reason") if spec else None,
        }
        if record["mode"] == "browser_session" and previous.get("mode") != "browser_session":
            record.update(
                status="BROWSER_SESSION_REQUIRED", coverage_complete=False,
                capture_method="iab", browser_state="UNKNOWN",
                message="采集路径已切换内置浏览器；历史 HTTP / API 记录保留原日期，"
                        "待本轮页面核验。",
            )
        elif record["mode"] == "restricted":
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


def _directory_identity(store: LocalDataStore, source: str, item: Row) -> str:
    identity = item["detail_url"] + "|" + item["name"].casefold()
    identifier = source + ":" + stable_hash(identity)[:20]
    if store.get(SCAN + "entries", identifier):
        return identifier
    # A new view or a verified display name must not duplicate an existing company.
    by_detail = [row for row in store.list(SCAN + "entries")
                 if row["source"] == source and row.get("detail_url") == item["detail_url"]]
    if len(by_detail) == 1:
        return str(by_detail[0]["id"])
    matches = [
        row for row in cast(list[Row], store.list(SCAN + "entries"))
        if row["source"] == source and (
            (row.get("detail_url") == item["detail_url"]
             and str(row.get("directory_name", row["name"])).casefold()
             == item["name"].casefold())
            or (item.get("website") and row.get("website")
                and domain(row["website"]) == domain(item["website"])
                and row["name"].casefold() == item["name"].casefold())
        )
    ]
    return str(matches[0]["id"]) if len(matches) == 1 else identifier


def ingest_directory(store: LocalDataStore, payload: Row, *, atomic: bool = True) -> Row:
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
        item.update(
            id=_directory_identity(store, source, item),
            source=source,
            source_hash=stable_hash(item),
        )
        normalized.append(item)
    if len({item["id"] for item in normalized}) != len(normalized):
        raise ValueError("Duplicate identities in directory snapshot")
    inserted = changed = 0
    with store.transaction() if atomic else nullcontext():
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
            if payload.get("capture_method") == "iab":
                record.update(directory_capture_method="iab",
                              directory_browser_observed_at=payload["captured_at"])
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
    configured = {row["id"]: row for row in load_config(settings.home)["sources"]}
    if source in configured and configured[source]["mode"] == "browser_session":
        raise ValueError("This source requires ingest-workbench-browser and IAB capture evidence")
    if not registered or registered.get("mode") == "restricted":
        raise ValueError("Source is unknown or restricted; do not ingest an automated capture")
    return ingest_directory(store, payload)


def ingest_news(store: LocalDataStore, data: Row, observed_at: str) -> int:
    """Legacy offline import only; browser scans never call the old free API."""
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


def _browser_pages(rows: Any, captured: datetime) -> list[Row]:
    if not isinstance(rows, list):
        raise ValueError("Browser pages must be a list")
    pages = []
    for row in rows:
        observed = _time(row.get("observed_at")) if isinstance(row, dict) else None
        if not observed or observed > captured or not str(row.get("text", "")).strip():
            raise ValueError("Rendered pages require text and an actual observation time")
        if row.get("text_kind", "RENDERED_TEXT") not in {"RENDERED_TEXT", "BROWSER_REVIEW_SUMMARY"}:
            raise ValueError("Unknown browser page text representation")
        pages.append({
            "url": public_url(str(row.get("url", ""))),
            "title": str(row.get("title", "")), "text": row["text"],
            "observed_at": row["observed_at"],
            "text_kind": row.get("text_kind", "RENDERED_TEXT"),
            "links": [{"url": public_url(str(link["url"])),
                       "label": str(link.get("label", ""))} for link in row.get("links", [])],
        })
    return pages


def _official_job_chain(company: Row, pages: list[Row], url: str) -> bool:
    """Require rendered employer pages and their visible links to the captured JD."""
    website = company.get("website")
    if not website or domain(url) in {"ycombinator.com", "workatastartup.com"}:
        return False
    reachable = {job_url(page["url"]) for page in pages
                 if domain(page["url"]) == domain(website)}
    for _ in pages:
        added = {job_url(link["url"]) for page in pages
                 if job_url(page["url"]) in reachable for link in page["links"]}
        if added.issubset(reachable):
            break
        reachable.update(added)
    return job_url(url) in reachable


def ingest_browser_capture(settings: Settings, path: Path) -> Row:
    """Ingest rendered IAB observations atomically; this function makes no web requests."""
    payload = json.loads(path.read_text())
    config = load_config(settings.home)
    specs = {row["id"]: row for row in config["sources"]}
    source = str(payload.get("source", ""))
    store = LocalDataStore(settings.database_path)
    spec = specs.get(source) or store.get(SCAN + "sources", source) or {}
    if spec.get("mode") not in {"browser_session", "browser_review"}:
        raise ValueError("Unknown source or source is not registered for browser capture")
    captured = _time(payload.get("captured_at"))
    browser = payload.get("browser", {})
    coverage = payload.get("coverage", {})
    status = payload.get("status")
    success = status in {"CAPTURED", "PARTIAL_CAPTURE"}
    if (payload.get("schema_version") != 2 or not captured
            or captured > datetime.now(UTC) + timedelta(minutes=5)
            or browser.get("type") != "iab"
            or browser.get("login_state") not in {
                "SIGNED_IN", "SIGNED_OUT", "NOT_REQUIRED", "UNKNOWN"}
            or not isinstance(coverage, dict) or not coverage.get("scope")
            or status not in {"CAPTURED", "PARTIAL_CAPTURE", "LOGIN_REQUIRED",
                              "VERIFICATION_REQUIRED", "MEMBERSHIP_REQUIRED",
                              "BLANK_PAGE", "UNAVAILABLE"}):
        raise ValueError("Invalid IAB capture schema / timestamp / browser / status / coverage")
    if browser["login_state"] in {"SIGNED_IN", "SIGNED_OUT"} and not browser.get("login_evidence"):
        raise ValueError("Login state requires evidence visible on the current page")
    browser = {key: browser.get(key) for key in (
        "type", "context_id", "login_state", "login_evidence")}
    if coverage.get("complete") is True and (
        status != "CAPTURED" or coverage.get("render_complete") is not True
        or coverage.get("has_more") is not False
    ):
        raise ValueError("Complete coverage requires a fully rendered, exhausted browser view")
    digest = stable_hash(payload)
    receipt_id = source + ":browser:" + digest
    if old := store.get(SCAN + "imports", receipt_id):
        return {**old, "idempotent_replay": True, "inserted": 0, "changed": 0,
                "new_jobs": 0, "changed_jobs": 0, "new_news": 0}
    health = _without_recorded(store.get(SCAN + "sources", source) or {})
    previous = _time(health.get("browser_checked_at"))
    if previous and captured <= previous:
        raise ValueError("Older or reused capture time cannot replace a newer browser attempt")
    pages = _browser_pages(payload.get("pages", []), captured)
    if success and not pages:
        raise ValueError("A successful browser capture needs rendered page evidence")
    companies = []
    for row in payload.get("companies", []):
        company = {key: row[key] for key in (
            "name", "detail_url", "website", "description", "stage", "category",
            "tags", "name_verified", "company_status",
        ) if key in row}
        if not str(company.get("name", "")).strip():
            raise ValueError("Company entries require a name")
        company["detail_url"] = public_url(str(company.get("detail_url", "")))
        if company.get("website"):
            company["website"] = public_url(company["website"])
        company.update(id=_directory_identity(store, source, company), source=source)
        companies.append(company)
    if len({row["id"] for row in companies}) != len(companies):
        raise ValueError("Duplicate company identities in browser capture")
    known = {row["id"]: row for row in cast(list[Row], store.list(SCAN + "entries"))
             if row["source"] == source}
    known.update({row["id"]: {**known.get(row["id"], {}), **row} for row in companies})
    research = payload.get("research", [])
    if not isinstance(research, list) or len(research) > int(config["deep_read_per_source"]):
        raise ValueError("Browser deep reads must not exceed the per-source limit of 20")
    results = []
    for row in research:
        existing_company = known.get(row.get("entry_id"))
        if not existing_company or existing_company.get("source") != source:
            raise ValueError("Browser research requires a known company entry_id from this source")
        company = existing_company
        observed = _time(row.get("observed_at"))
        if not observed or observed > captured:
            raise ValueError("Browser research requires an actual observation time")
        prior_observation = _time(company.get("research_observed_at"))
        if prior_observation and observed < prior_observation:
            raise ValueError("Older browser research cannot replace newer company evidence")
        official_pages = _browser_pages(row.get("pages", []), observed)
        page_urls = {job_url(page["url"]) for page in official_pages
                     if page["text_kind"] == "RENDERED_TEXT"}
        jobs = []
        for item in row.get("jobs", []):
            url = job_url(public_url(str(item.get("url", ""))))
            kind = item.get("evidence_kind")
            if (url not in page_urls or not str(item.get("title", "")).strip()
                    or not str(item.get("description", "")).strip()
                    or kind not in {"OFFICIAL_EMPLOYER", "PLATFORM_LISTING"}):
                raise ValueError("A job needs a captured JD page and explicit evidence kind")
            if (kind == "OFFICIAL_EMPLOYER"
                    and not _official_job_chain(company, official_pages, url)):
                raise ValueError("Official JD needs a visible link chain from the employer website")
            jobs.append({key: item[key] for key in (
                "url", "title", "description", "location", "posted_at", "employment_type",
                "salary", "evidence_kind", "board", "provider",
            ) if key in item} | {"capture_method": "iab", "browser": browser})
        boards = row.get("boards", [])
        for board in boards:
            if board.get("complete") is True and (
                board.get("render_complete") is not True or board.get("has_more") is not False
                or board.get("unfiltered") is not True
                or job_url(str(board.get("url", ""))) not in page_urls
            ):
                raise ValueError("Closing jobs requires an exhausted, unfiltered browser board")
        result = {"company": company, "observed_at": row["observed_at"], "browser": browser,
                  "pages": official_pages, "jobs": jobs, "boards": boards,
                  "errors": list(row.get("errors", []))}
        identify_jobs(result)
        results.append(result)
    round_id = str(payload.get("round_id") or captured.astimezone(
        ZoneInfo(config["timezone"])).date().isoformat())
    earlier = [row for row in cast(list[Row], store.list(SCAN + "imports"))
               if row.get("source") == source and row.get("round_id") == round_id]
    attempted = {key for row in earlier for key in row.get("research_entry_ids", [])}
    read_pages = {key for row in earlier for key in row.get("research_success_ids", [])}
    attempted.update(row["company"]["id"] for row in results)
    read_pages.update(row["company"]["id"] for row in results if row["pages"])
    if len(attempted) > int(config["deep_read_per_source"]):
        raise ValueError("Chunked browser captures must also respect the 20-company round limit")
    news = []
    for row in payload.get("news", []):
        if not str(row.get("title", "")).strip():
            raise ValueError("Browser news requires a visible title")
        link = public_url(str(row.get("url", "")))
        news.append({
            "id": source + ":" + stable_hash(link)[:24], "source": source, "url": link,
            **{key: row.get(key) for key in (
                "title", "summary", "published_at_raw", "published_timezone")},
            "observed_at": payload["captured_at"], "capture_method": "iab", "browser": browser,
            "coverage": coverage,
        })
    if not success and (companies or results or news):
        raise ValueError("Failed / blocked browser attempts cannot assert new source data")
    counts = {"inserted": 0, "changed": 0, "new_jobs": 0, "changed_jobs": 0, "new_news": 0}
    with store.transaction():
        sync_sources(store, config)
        if companies:
            directory = {"schema_version": 1, "source": source,
                         "capture_method": "iab",
                         "captured_at": payload["captured_at"], "coverage": coverage,
                         "companies": [{key: value for key, value in row.items()
                                        if key not in {"id", "source"}} for row in companies]}
            imported = ingest_directory(store, directory, atomic=False)
            counts.update({key: imported[key] for key in ("inserted", "changed")})
        for result in results:
            entry = store.get(SCAN + "entries", result["company"]["id"])
            result["company"] = _without_recorded(entry or result["company"])
            if result["pages"]:
                totals = save_research(store, result, atomic=False)
                for key in ("new_jobs", "changed_jobs"):
                    counts[key] += totals[key]
            else:
                store.upsert(SCAN + "entries", result["company"]["id"], {
                    **result["company"], "last_attempt_at": result["observed_at"],
                    "research_status": "UNAVAILABLE", "research_errors": result["errors"],
                }, "WORKBENCH_BROWSER_RESEARCH_FAILED")
        for row in news:
            old = store.get(SCAN + "news", row["id"])
            counts["new_news"] += old is None
            row["first_seen_at"] = old["first_seen_at"] if old else row["observed_at"]
            store.upsert(SCAN + "news", row["id"], row, "WORKBENCH_BROWSER_NEWS_OBSERVED")
        health = _without_recorded(store.get(SCAN + "sources", source) or health)
        health.update(
            status=status, checked_at=payload["captured_at"],
            browser_checked_at=payload["captured_at"], capture_method="iab", browser=browser,
            browser_state=browser["login_state"], coverage=coverage,
            coverage_complete=coverage.get("complete") is True,
            browser_digest=digest, visible_count=coverage.get("visible_total"),
            round_id=round_id, deep_read_attempted=len(attempted),
            deep_read_with_pages=len(read_pages),
            directory_count=sum(row["source"] == source
                                for row in store.list(SCAN + "entries")),
            browser_company_count=len(companies),
            research_pending=sum(row.get("capture_method") != "iab"
                                 or row.get("researched_hash") != row.get("source_hash")
                                 for row in store.list(SCAN + "entries")
                                 if row["source"] == source),
            message=str(payload.get("message") or coverage["scope"]),
        )
        if success:
            health.update(browser_last_success_at=payload["captured_at"],
                          last_success_at=payload["captured_at"])
        store.upsert(SCAN + "sources", source, health, "WORKBENCH_BROWSER_ATTEMPT_OBSERVED")
        receipt = {"id": receipt_id, "source": source, "digest": digest, "status": status,
                   "captured_at": payload["captured_at"], "capture_method": "iab",
                   "browser": browser, "coverage": coverage, "round_id": round_id,
                   "research_entry_ids": [row["company"]["id"] for row in results],
                   "research_success_ids": [row["company"]["id"] for row in results
                                            if row["pages"]],
                   **counts, "idempotent_replay": False}
        store.upsert(SCAN + "imports", receipt_id, receipt, "WORKBENCH_BROWSER_CAPTURE_IMPORTED")
    _write_json(settings.home / "output/workbench/browser" / source / f"{digest}.json", payload)
    return receipt


def save_research(store: LocalDataStore, result: Row, *, atomic: bool = True) -> Row:
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
        **({"browser": result["browser"], "capture_method": "iab"}
           if result.get("browser") else {}),
    }
    inserted = changed = 0
    by_board: dict[str, set[str]] = {}
    with store.transaction() if atomic else nullcontext():
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
            "employment_type": item.get("employment_type"),
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
            "kind": "PLATFORM_JOB" if item.get("evidence_kind") == "PLATFORM_LISTING"
            else "CURRENT_JOB",
            "company": item["company"],
            "title": item["title"],
            "description": item["description"],
            "location": item.get("location"),
            "url": url,
            "observed_at": item["observed_at"],
            "source_ids": sorted(
                set(old.get("source_ids", []) + item.get("source_ids", [item["source"]]))
            ),
            "official_evidence": "平台岗位正文，雇主官方 JD 待核实"
            if item.get("evidence_kind") == "PLATFORM_LISTING"
            else "渠道官网回链到雇主岗位／官方 ATS",
            "capture_method": item.get("capture_method", "HISTORICAL_HTTP"),
            "browser": item.get("browser"),
            "company_evidence": {
                "directory": entry.get("description"),
                "official_pages": entry.get("pages", []),
                "stage": entry.get("stage"),
            },
            "posted_at": item.get("posted_at"),
            "employment_type": item.get("employment_type"),
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
                "capture_method": item.get("capture_method", "HISTORICAL_HTTP"),
                "browser": item.get("browser"),
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


def browser_worklist(store: LocalDataStore, config: Row, day: str) -> Row:
    """Queue actual IAB visits; generating a queue never claims a page was visited."""
    sources = []
    for spec in config["sources"]:
        health = store.get(SCAN + "sources", spec["id"]) or {}
        checked = _time(health.get("browser_checked_at"))
        visited_today = bool(checked and checked.astimezone(ZoneInfo(config["timezone"]))
                             .date().isoformat() == day)
        entries = [row for row in store.list(SCAN + "entries") if row["source"] == spec["id"]]
        entries.sort(key=lambda row: (
            row.get("capture_method") == "iab",
            -_recall_priority(row), str(row.get("research_observed_at") or ""), row["id"],
        ))
        pending = []
        for row in entries:
            observed = _time(row.get("research_observed_at"))
            if (row.get("capture_method") != "iab" or not observed
                    or observed.astimezone(ZoneInfo(config["timezone"])).date().isoformat() != day):
                pending.append(row)
        sources.append({
            "id": spec["id"], "name": spec["name"], "url": spec.get("url"), "browser": "iab",
            "visited_today": visited_today,
            "status": health.get("status", "BROWSER_SESSION_REQUIRED"),
            "browser_state": health.get("browser_state", "UNKNOWN"),
            "browser_checked_at": health.get("browser_checked_at"),
            "user_deferred": bool(spec.get("user_deferred")),
            "deferred_reason": spec.get("deferred_reason"),
            "pending_companies": len(pending), "deep_read_limit": config["deep_read_per_source"],
            "companies": [{key: row.get(key) for key in (
                "id", "name", "detail_url", "website", "description", "boards",
            )} for row in pending[:int(config["deep_read_per_source"])]],
            "instructions": spec["deferred_reason"] if spec.get("user_deferred") else
                            "从实际页面读取新增／变化线索；使用可见筛选、分页、公司弹窗与官网回链。"
                            "同一轮含既有待复查岗位，深读合计最多20家公司。需要登录或验证及时交接。",
        })
    return {"schema_version": 2, "date": day, "timezone": config["timezone"],
            "capture_method": "iab", "sources": sources}


def _capture_revision(store: LocalDataStore, profile: Row, pool: list[Row]) -> str:
    return stable_hash({
        "profile": profile["digest"], "candidates": pool,
        "sources": [_without_recorded(row) for row in store.list(SCAN + "sources")],
    })


def scan_workbench(
    settings: Settings,
    *,
    force: bool = False,
    source: str | None = None,
    prepare_only: bool = False,
) -> Row:
    """Prepare browser work and a review packet from saved evidence. No network fallback."""
    config = load_config(settings.home)
    store = LocalDataStore(settings.database_path)
    sync_sources(store, config)
    if source and source not in {spec["id"] for spec in config["sources"]}:
        registered = store.get(SCAN + "sources", source)
        if not registered or registered.get("mode") == "restricted":
            raise ValueError("Unknown or restricted discovery source")
        config["sources"].append(registered)
    profile = profile_snapshot(store, settings.home, config)
    day = datetime.now(ZoneInfo(config["timezone"])).date().isoformat()
    latest = store.get(SCAN + "runs", day)
    revision = _capture_revision(store, profile, review_candidates(store, profile))
    if (latest and latest.get("capture_method") == "iab"
            and latest.get("capture_revision") == revision
            and not force and not source and not prepare_only):
        _write_json(settings.home / "output/workbench" / day / "browser-worklist.json",
                    browser_worklist(store, config, day))
        return {**latest, "reused": True}
    output = settings.home / "output/workbench" / day
    output.mkdir(parents=True, exist_ok=True)
    if latest:
        archive = output / "attempts" / str(latest["input_digest"])[:16]
        archive.mkdir(parents=True, exist_ok=True)
        for name in ("scan.json", "review-input.json", "all-candidates.json", "profile.json",
                     "brief.json", "brief.md", "known-board-refresh.json", "browser-worklist.json"):
            if (output / name).is_file() and not (archive / name).exists():
                shutil.copy2(output / name, archive / name)
    worklist = browser_worklist(store, config, day)
    if source:
        worklist["sources"] = [row for row in worklist["sources"] if row["id"] == source]
    _write_json(output / "browser-worklist.json", worklist)
    return prepare_review(settings, store, config, profile, {}, [])


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
        "browser_company_reviews": sum(row.get("capture_method") == "iab"
                                       and today(row.get("research_observed_at"))
                                       for row in entries),
        "browser_jobs_observed": sum(row.get("capture_method") == "iab"
                                     and today(row.get("observed_at")) for row in jobs),
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
        "capture_method": "iab",
        "browser_worklist": str(output / "browser-worklist.json"),
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
        "capture_method": "iab",
        "capture_revision": _capture_revision(store, profile, all_candidates),
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
        if item["track"] == "FULL_TIME" and row["kind"] != "CURRENT_JOB":
            raise ValueError("Full-time recommendations require an observed employer official JD")
        employment = str(row.get("employment_type", "")).casefold()
        if item["track"] == "FULL_TIME" and (re.search(
            r"\bintern(?:ship)?\b|实习|\bpart[- ]time\b",
            str(row.get("title", "")) + " " + employment, re.I,
        ) or employment in {"contract", "contractor", "temporary"}):
            raise ValueError("Internship / part-time / contract roles cannot be labeled full-time")
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
