from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from zoneinfo import ZoneInfo

from hcis.sources.platforms import PLATFORM_SOURCES

ZONE = ZoneInfo("America/New_York")
UNKNOWN = "未知 / Unknown"
SOURCE_LABELS = {
    "myvisajobs": "MyVisaJobs",
    "h1bdata": "H1BData.info",
    "h1bgrader": "H1BGrader",
    "careers": "官方 Careers",
}
COLUMNS = {
    "company": "公司 / Company",
    "title": "岗位 / Title",
    "captured_at": "采集时间（本渠道 / 最新）",
    "first_seen_at": "首次采集时间",
    "company_size": "公司人数规模",
    "chinese_workforce_level": "华人比例高低（来源披露）",
    "chinese_workforce_percent": "华人占比 %（来源披露）",
    "score": "综合分 / Score",
    "location": "地点 / Location",
    "h1b": "H-1B 核验状态",
    "salary_min": "薪资下限 USD",
    "salary_max": "薪资上限 USD",
    "posted_at": "职位发布时间",
    "source_date": "来源日期 / LCA 日期",
    "lead_type": "线索类型",
    "employment_type": "雇佣类型",
    "company_type": "公司类型",
    "employee_count_min": "人数下限",
    "employee_count_max": "人数上限",
    "company_size_source_url": "人数规模证据链接",
    "company_size_observed_at": "人数规模证据日期",
    "chinese_workforce_source_url": "华人比例证据链接",
    "chinese_workforce_observed_at": "华人比例证据日期",
    "chinese_workforce_scope": "华人比例统计口径",
    "chinese_workforce_evidence": "华人比例证据原文",
    "chinese_environment": "中文工作环境",
    "chinese_environment_evidence": "中文工作环境证据",
    "sources": "渠道 / Sources",
    **{f"captured_{source}": f"{label} 采集时间" for source, label in SOURCE_LABELS.items()},
    "source_url": "本渠道来源链接",
    "official_apply_url": "官方申请链接",
    "apply": "发现 / 申请链接",
    "careers_status": "官方岗位状态",
    "tags": "标签 / Tags",
    "favorite": "收藏 / Favorite",
    "manual_status": "人工状态 / Status",
    "notes": "备注 / Notes",
    "job_id": "岗位 ID",
}
NUMBER_COLUMNS = {
    "score", "salary_min", "salary_max", "employee_count_min", "employee_count_max",
    "chinese_workforce_percent",
}
DATE_COLUMNS = {
    "captured_at", "first_seen_at", "posted_at", "source_date", "company_size_observed_at",
    "chinese_workforce_observed_at", *(f"captured_{source}" for source in PLATFORM_SOURCES),
}
EDITABLE_COLUMNS = {"favorite", "manual_status", "notes"}


def is_unknown(value: object) -> bool:
    return value is None or str(value).strip().upper() in {
        "", "UNKNOWN", "UNVERIFIED", UNKNOWN.upper(),
    }


def local_time(value: object) -> str:
    if is_unknown(value):
        return UNKNOWN
    raw = str(value)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        for pattern in ("%m/%d/%Y", "%m/%d/%y"):
            try:
                return datetime.strptime(raw, pattern).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return UNKNOWN
    if len(raw) == 10:
        return raw  # A date alone is not midnight UTC.
    return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(ZONE).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def display_rows(
    rows: list[dict[str, object]], source: str | None = None
) -> list[dict[str, object]]:
    displayed = []
    for row in rows:
        sources = cast(list[str], row.get("platform_sources") or [])
        captures = dict(cast(dict[str, str], row.get("source_captured_at") or {}))
        if len(sources) == 1 and row.get("last_seen_at"):
            captures.setdefault(sources[0], str(row["last_seen_at"]))
        low, high = row.get("employee_count_min"), row.get("employee_count_max")
        size = UNKNOWN
        # Company/team language is not evidence of anyone's ethnicity or an employee ratio.
        size_sourced = bool(row.get("company_size_source_url"))
        share_sourced = bool(
            row.get("chinese_workforce_source_url") and row.get("chinese_workforce_evidence")
            and row.get("chinese_workforce_scope")
        )
        if size_sourced:
            if low is not None and high is not None:
                size = f"{float(str(low)):g}–{float(str(high)):g} 人"
            elif low is not None:
                size = f"≥ {float(str(low)):g} 人"
            elif high is not None:
                size = f"≤ {float(str(high)):g} 人"
        urls = cast(dict[str, str], row.get("source_urls") or {})
        record = {field: row.get(field) for field in COLUMNS}
        record.update({
            "company": row.get("company_name"),
            "captured_at": captures.get(source) if source else row.get("last_seen_at"),
            "company_size": size,
            "employee_count_min": low if size_sourced else None,
            "employee_count_max": high if size_sourced else None,
            "chinese_workforce_level": (
                row.get("chinese_workforce_level") if share_sourced else None
            ),
            "chinese_workforce_percent": (
                row.get("chinese_workforce_percent") if share_sourced else None
            ),
            "h1b": row.get("h1b_assessment"),
            "sources": ", ".join(sources),
            "source_url": urls.get(source) if source else next(iter(urls.values()), None),
            "apply": row.get("apply_url"),
            "tags": ", ".join(cast(list[str], row.get("tags") or [])),
            **{f"captured_{name}": captures.get(name) for name in PLATFORM_SOURCES},
        })
        for field in COLUMNS:
            if field in DATE_COLUMNS:
                record[field] = local_time(record[field])
            elif field in NUMBER_COLUMNS:
                record[field] = None if is_unknown(record[field]) else float(str(record[field]))
            elif field.endswith("_url") or field == "apply":
                record[field] = None if is_unknown(record[field]) else str(record[field])
            elif isinstance(record[field], list):
                record[field] = "; ".join(
                    str(value) for value in cast(list[object], record[field])
                ) or UNKNOWN
            elif field not in EDITABLE_COLUMNS and is_unknown(record[field]):
                record[field] = UNKNOWN
        displayed.append(record)
    return displayed


def filter_rows(
    rows: list[dict[str, object]], field: str, operator: str, value: str = ""
) -> list[dict[str, object]]:
    def matches(row: dict[str, object]) -> bool:
        actual = row.get(field)
        if operator == "未知":
            return is_unknown(actual)
        if operator == "已知":
            return not is_unknown(actual)
        if not value:
            return True
        if field in NUMBER_COLUMNS and operator == "等于":
            return not is_unknown(actual) and float(str(actual)) == float(value)
        if operator in {"≥", "≤"}:
            if is_unknown(actual):
                return False
            if field in NUMBER_COLUMNS:
                number, bound = float(str(actual)), float(value)
                return number >= bound if operator == "≥" else number <= bound
            text = str(actual)
            return text >= value if operator == "≥" else text[:len(value)] <= value
        text = str(actual).casefold()
        return text == value.casefold() if operator == "等于" else value.casefold() in text

    return [row for row in rows if matches(row)]


def sort_rows(
    rows: list[dict[str, object]], field: str, descending: bool
) -> list[dict[str, object]]:
    known = [row for row in rows if not is_unknown(row.get(field))]
    missing = [row for row in rows if is_unknown(row.get(field))]
    def sort_value(row: dict[str, object]) -> float | str:
        if field == "company_size":
            low = row.get("employee_count_min")
            return float(str(row.get("employee_count_max") if low is None else low))
        if field in NUMBER_COLUMNS:
            return float(str(row[field]))
        return str(row[field]).casefold()

    return sorted(known, key=sort_value, reverse=descending) + missing
