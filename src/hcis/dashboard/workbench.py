"""Progressive, local-only career workspace built on the existing HCIS store."""

from __future__ import annotations

import html
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import streamlit as st

from hcis.repositories import LocalDataStore
from hcis.settings import get_settings
from hcis.workbench import (
    BOARD_GROUPS, PREFIX, PRIORITIES, RELATION_LABELS, STATUSES, TRACKS,
    add_candidate, brief, candidates, export_workspace, import_workbook, merge_state,
    promote_legacy_opportunity, safe_url, save_candidate, save_relationship, save_task, urls,
)
from hcis.workbench_scan import SCAN, latest_brief

NAVIGATION = ("今日简报", "每日扫描", "机会看板", "关系与联系", "行动清单", "渠道与资料", "岗位雷达", "数据与备份", "H-1B 原工作台")
RELATION_STAGES = ("尚未复核", "准备沟通", "已发送 / 已邀请", "对方已接受", "对方已回复", "愿意内推", "内推已提交", "通话 / 面试", "持续合作", "暂缓 / 停止")
CSS = """
<style>
:root{--career-ink:#183b33;--career-accent:#18785d;--career-muted:#66776e;--career-line:#dce5dd}
.stApp{background:#f7f8f4;color:#193b33}
[data-testid="stSidebar"]{background:#edf2eb;border-right:1px solid var(--career-line)}
.block-container{padding-top:4.8rem;max-width:1480px;padding-bottom:4rem}
h1,h2,h3{color:var(--career-ink);letter-spacing:-.025em}
.career-eyebrow{font-size:.75rem;letter-spacing:.18em;font-weight:700;color:var(--career-accent);margin-bottom:.5rem}
.career-hero{border-bottom:1px solid var(--career-line);padding:0 0 1.3rem;margin-bottom:1.5rem}
.career-hero h1{font-size:2.3rem;margin:0 0 .45rem;font-weight:750}
.career-hero p{color:var(--career-muted);font-size:.96rem;margin:0;line-height:1.7}
.career-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.8rem;margin:1.1rem 0 1.6rem}
.career-kpi{background:white;border:1px solid var(--career-line);border-radius:14px;padding:1.05rem 1.2rem}
.career-kpi strong{font-size:1.9rem;display:block;color:var(--career-ink);line-height:1.3}
.career-kpi span{font-size:.82rem;color:var(--career-muted)}
.career-pill{display:inline-block;border-radius:20px;background:#e4f1e8;color:#216448;padding:.2rem .65rem;font-size:.75rem;margin:0 .25rem .35rem 0}
.career-company{font-size:1.12rem;font-weight:700;color:var(--career-ink);margin:.2rem 0 .35rem}
.career-subtle{font-size:.8rem;color:var(--career-muted);line-height:1.6}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:12px!important}
div.stButton>button{border-radius:9px;font-weight:500}
[data-testid="stForm"]{background:#fff;border-color:var(--career-line)}
@media(max-width:760px){.block-container{padding:4.2rem .8rem 3rem}.career-hero h1{font-size:1.75rem}.career-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.career-kpi{padding:.8rem}.career-kpi strong{font-size:1.6rem}}
</style>
"""


def _txt(value: object, fallback: str = "待补充 / 未知") -> str:
    return str(value).strip() if value not in (None, "") else fallback


def _short(value: object, limit: int = 160) -> str:
    raw = _txt(value)
    return raw if len(raw) <= limit else raw[:limit] + "…"


def _date(value: object) -> str:
    if not value:
        return "未知"
    return str(value).replace("T00:00:00", "").removesuffix("+00:00")


def _hero(title: str, description: str) -> None:
    st.html(f'<div class="career-hero"><div class="career-eyebrow">WILLIAM · CAREER WORKSPACE</div>'
            f'<h1>{html.escape(title)}</h1><p>{html.escape(description)}</p></div>')


def _scan_time(value: object) -> str:
    if not value:
        return "未知"
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if not stamp.tzinfo:
        return f"{value}（时区未知）"
    return stamp.astimezone(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M %Z")


def _links(values: list[str], prefix: str = "原始来源", *, key: str) -> None:
    for index, value in enumerate(dict.fromkeys(values), 1):
        if url := safe_url(value):
            st.link_button(f"{prefix} {index} · {urlsplit(url).hostname}", url, key=f"{key}-{index}", width="stretch")


def _open(identifier: str) -> None:
    st.session_state["_workbench_nav_target"] = "机会看板"
    st.session_state["_workbench_focus_target"] = identifier
    st.rerun()


def _fact_cards(store: LocalDataStore, identifier: str | None = None) -> None:
    facts = store.list(PREFIX + "facts")
    for fact in facts:
        if identifier and fact.get("candidate_id") != identifier:
            continue
        with st.container(border=True):
            st.markdown(f"**{fact.get('title')}**")
            st.write(fact.get("detail"))
            st.caption(f"{fact.get('source')} · {_date(fact.get('source_date'))}")


def _evidence(store: LocalDataStore, row: dict[str, object], *, limit: int | None = None) -> None:
    identifier = row.get("parent_candidate_id") or row["id"]
    records = [item for item in store.list(PREFIX + "evidence") if item.get("candidate_id") == identifier]
    st.caption(f"{len(records)} 条原始证据 / 审查；保留事实日期和历史表述。")
    if not records:
        st.info("暂未关联独立证据；请先查看线索来源或补充材料。")
        if row.get("source_url"):
            _links(urls(row["source_url"]), key=f"empty-evidence-{row['id']}")
    for evidence in records[:limit]:
        with st.expander(f"{evidence.get('kind')} · {_date(evidence.get('source_date'))}"):
            if str(evidence.get("kind")) == "Labelbox referrer unnamed":
                st.info("这是旧时点的未知项。用户已在本线程确认内推人为曹磊 / Lei Cao；历史原文保留。")
            st.text(_txt(evidence.get("detail")))
            _links(list(evidence.get("urls") or []), key=f"evidence-{evidence['id']}")
            if evidence.get("source_text") and not evidence.get("urls"):
                st.caption(_txt(evidence["source_text"]))
    with st.expander("原始导入字段 / 旧雷达快照"):
        st.json(row.get("raw") or row)


def _related(store: LocalDataStore, row: dict[str, object]) -> list[dict[str, object]]:
    identifier = row.get("parent_candidate_id") or row["id"]
    return [item for item in merge_state(store, "relationships")
            if identifier in list(item.get("candidate_ids") or [])]


def _relationship_card(row: dict[str, object], *, key: str) -> None:
    st.markdown(f"**{row.get('name')}** · {_txt(row.get('company'))}")
    st.caption(_txt(row.get("role")))
    historical = str(row.get("historical_status", ""))
    st.write(RELATION_LABELS.get(historical, historical or "历史状态未知"))
    st.caption(f"历史证据：{_date(row.get('historical_date'))} · 记录 {row['id']}")
    if row.get("current_stage"):
        st.write(f"本机复核进度：{row['current_stage']}")
    if row.get("profile_url") and safe_url(row["profile_url"]):
        st.link_button("打开职业主页", str(row["profile_url"]), key=key, width="stretch")
    with st.expander("回复、限制与历史回执"):
        st.write("最新回复 / 人工记录")
        st.text(_txt(row.get("latest_reply")))
        st.write("身份与状态限制")
        st.text(_txt(row.get("limitations")))
        st.caption(f"原始文件标识：{_txt(row.get('source_file_id'))}")
        source_id = _txt(row.get("source_file_id"), "")
        if source_id.startswith("libfile_") and source_id.removeprefix("libfile_").isalnum():
            st.link_button("下载历史来源原件", f"https://chatgpt.com/api/library/files/{source_id}/download", key=f"receipt-{key}")
        st.text(_txt(row.get("next_action")))
        if row.get("notes"):
            st.text(_txt(row["notes"]))
        with st.expander("完整原始记录"):
            st.json(row.get("raw") or row)


def _progress_form(store: LocalDataStore, row: dict[str, object]) -> None:
    identifier = str(row["id"])
    status = str(row.get("status", "VERIFY"))
    priority = str(row.get("priority", "普通"))
    with st.form(f"progress-{identifier}"):
        a, b = st.columns(2)
        selected_status = a.selectbox("当前进展", list(STATUSES), index=list(STATUSES).index(status),
                                     format_func=STATUSES.__getitem__)
        selected_priority = b.selectbox("优先级", list(PRIORITIES), index=PRIORITIES.index(priority))
        selected_tracks = st.multiselect("机会路径（可多选）", list(TRACKS),
                                         default=list(row.get("tracks") or []), format_func=TRACKS.__getitem__)
        favorite = st.checkbox("加入重点收藏", value=bool(row.get("favorite")))
        next_action = st.text_area("下一步具体行动", value=_txt(row.get("next_action"), ""), height=100)
        a, b = st.columns(2)
        due = a.text_input("计划日期（可空，YYYY-MM-DD）", value=_txt(row.get("due_date"), ""))
        country = b.text_input("地点 / 国家（人工核实后填写）", value=_txt(row.get("country"), ""))
        notes = st.text_area("个人备注 / 决策理由", value=_txt(row.get("notes"), ""))
        with st.expander("现金、股权、权限与合作条件"):
            cash = st.text_area("现金条件", value=_txt(row.get("cash_terms"), ""))
            equity = st.text_area("股权、归属及稀释条件", value=_txt(row.get("equity_terms"), ""))
            authority = st.text_area("实际角色与决策权限", value=_txt(row.get("authority_terms"), ""))
            scope = st.text_area("业务流程、预算与试点验收", value=_txt(row.get("partner_scope"), ""))
        if st.form_submit_button("保存进展与下一步", type="primary", width="stretch"):
            try:
                save_candidate(store, identifier, {
                    "status": selected_status, "priority": selected_priority, "tracks": selected_tracks,
                    "favorite": favorite, "next_action": next_action, "due_date": due or None,
                    "country": country, "notes": notes, "cash_terms": cash, "equity_terms": equity,
                    "authority_terms": authority, "partner_scope": scope,
                })
            except ValueError as error:
                st.error(f"无法保存：{error}")
            else:
                st.session_state["_workbench_notice"] = "进展已保存，首页简报与看板会同步更新。"
                st.session_state.pop("wb-dialog-id", None)
                st.rerun()


def _detail(store: LocalDataStore, row: dict[str, object]) -> None:
    st.subheader(f"{row['company']} · 详细档案")
    st.caption(f"{row['id']} · {_txt(row.get('origin'))} · 研究证据日期 {_date(row.get('source_date'))}")
    _fact_cards(store, str(row["id"]))
    tabs = st.tabs(["机会与门槛", "证据与反方", "关系历史", "进展与下一步"])
    with tabs[0]:
        st.markdown(f"**研究结论：{_txt(row.get('verdict'))}**")
        for title, field in (("岗位 / 邀请 / 合作信号", "signal"), ("与你的匹配", "fit"),
                             ("主要反证与门槛", "objections"), ("建议的下一步", "next_action")):
            st.markdown(f"**{title}**")
            st.text(_txt(row.get(field)))
        if row.get("source_url"):
            _links(urls(row["source_url"]), "线索入口", key=f"source-{row['id']}")
        st.info("全职：核对职位与经历。联创：核对客户、现金与权限。企业合作：核对负责人、预算、数据和试点验收。未知项继续保留。")
    with tabs[1]:
        _evidence(store, row)
    with tabs[2]:
        related = _related(store, row)
        st.caption(f"关联 {len(related)} 条历史记录；记录数不等于独立人数。")
        for item in related:
            with st.container(border=True):
                _relationship_card(item, key=f"detail-profile-{row['id']}-{item['id']}")
        if not related:
            st.info("尚无已确认的关系关联。可在“关系与联系”中人工关联；不按姓名或公司片段自动合并。")
    with tabs[3]:
        _progress_form(store, row)
        events = [event for event in store.list(PREFIX + "events") if event.get("candidate_id") == row["id"]]
        for event in reversed(events[-10:]):
            with st.expander(f"{event.get('title')} · {_date(event.get('at'))}"):
                st.json(event.get("changes"))


def _dismiss_detail() -> None:
    st.session_state.pop("wb-dialog-id", None)


@st.dialog("机会完整档案", width="large", on_dismiss=_dismiss_detail)
def _detail_dialog(store: LocalDataStore, row: dict[str, object]) -> None:
    _detail(store, row)


def _overview(store: LocalDataStore) -> None:
    _hero("毕业后的下一步，一处掌握", "全职、联创与企业 AI 合作 · 从研究证据到个人行动，逐层查看。")
    daily = latest_brief(store)
    if daily:
        st.subheader(f"每日机会重点 · {daily['date']}")
        st.write(daily.get("summary"))
        for item in daily["recommendations"][:3]:
            row = item["candidate"]
            st.markdown(f"**{item['rank']}. {row['company']} · {row['title']}**")
            st.write(item["fit"])
        if st.button(f"查看全部 {len(daily['recommendations'])} 条重点与渠道状态", key="daily-open"):
            st.session_state["_workbench_nav_target"] = "每日扫描"
            st.rerun()
        st.caption(f"综合全部来源，每日最多 10 条 · 审阅时间 {_scan_time(daily.get('reviewed_at'))} · 芝加哥每日 08:00")

    @st.fragment(run_every="30s")
    def snapshot() -> None:
        report = brief(store)
        st.markdown(f"**当前阶段：{report['stage']}**")
        metrics = [(report["candidates"], "已管理机会条目"), (report["priority"], "当前重点 / 条件优先"),
                   (report["open_tasks"], "待办行动"), (report["completed_tasks"], "已完成事项")]
        st.html('<div class="career-kpis">' + ''.join(
            f'<div class="career-kpi"><strong>{value}</strong><span>{label}</span></div>'
            for value, label in metrics) + '</div>')
        st.caption(f"本机数据读取：{datetime.now(UTC):%Y-%m-%d %H:%M:%S} UTC · 每 30 秒更新进展简报。"
                   "网页、私信、招聘及外部回复不会在此自动刷新。")
        last = report.get("last_import")
        if isinstance(last, dict):
            counts = last.get("counts")
            count_text = ""
            if isinstance(counts, dict):
                count_text = f"{counts.get('candidates')} 个候选主体 · {counts.get('evidence')} 条证据 / 审查 · {counts.get('relationships')} 条历史联系。"
            st.caption(f"研究快照：{last.get('source_snapshot')} · {count_text}"
                       "机会条目、合格岗位、独立联系人和实际成果分别计数。")
        st.write(f"人工记录：沟通推进 {report['active_conversations']} · 收到书面条件 {report['written_terms']} · 已落地 {report['landed']}")
        with st.expander(f"历史联系已做了什么 · {report['historical_relationship_records']} 条记录"):
            st.write("保留独立回执，不按排名继承状态；以下为历史时点，最新回复需人工复核。")
            counts = report["historical_contact_statuses"]
            if isinstance(counts, dict):
                st.dataframe([{"历史回执状态": RELATION_LABELS.get(key, key), "记录数": value}
                              for key, value in counts.items()], hide_index=True, width="stretch")

    snapshot()
    left, right = st.columns([1.35, 1])
    with left:
        st.subheader("先看这几条")
        rows = [row for row in candidates(store) if row.get("priority") in {"优先", "条件优先"}
                and row.get("status") not in {"PAUSED", "CLOSED"}]
        for row in rows[:6]:
            with st.container(border=True):
                st.markdown(f"**{row['company']}** · {STATUSES.get(str(row.get('status')), '待核验')}")
                st.caption(_txt(row.get("verdict")))
                st.write(_short(row.get("next_action"), 145))
                if st.button("查看证据与管理", key=f"brief-open-{row['id']}", width="stretch"):
                    _open(str(row["id"]))
        if not rows:
            st.info("可以在机会看板中设置重点收藏与优先级。")
    with right:
        st.subheader("最近确认")
        _fact_cards(store, "C016")
        st.subheader("接下来要做")
        tasks = [task for task in store.list(PREFIX + "tasks") if task.get("status") == "OPEN"]
        tasks.sort(key=lambda task: (str(task.get("due_date") or "9999"), task.get("priority") != "优先"))
        for task in tasks[:5]:
            with st.container(border=True):
                st.write(task.get("title"))
                st.caption("未设日期" if not task.get("due_date") else f"计划：{task['due_date']}")
        st.subheader("已经完成")
        completed = [task for task in store.list(PREFIX + "tasks") if task.get("status") == "DONE"]
        for task in sorted(completed, key=lambda t: str(t.get("completed_at")), reverse=True)[:5]:
            with st.expander(f"✓ {task.get('title')}"):
                st.write(task.get("notes"))
                st.caption(_date(task.get("completed_at")))
    with st.expander("我的当前策略与选择边界"):
        for fact in store.list(PREFIX + "facts"):
            if fact.get("kind") == "当前策略":
                st.write(fact.get("detail"))


def _board(store: LocalDataStore) -> None:
    _hero("机会看板", "按路径和进展组织机会。研究结论保留原样，个人进展由你更新。")
    all_rows = candidates(store)
    a, b, c = st.columns([1, 1, 1.4])
    track = a.selectbox("机会路径", ["ALL", *TRACKS], format_func=lambda v: "全部路径" if v == "ALL" else TRACKS[v], key="wb-track")
    priority = b.selectbox("优先级筛选", ["全部", *PRIORITIES], key="wb-priority")
    search = c.text_input("搜索公司、职责、结论或备注", key="wb-search")
    favorites = st.toggle("只看重点收藏", key="wb-favorites")
    include_history = st.toggle("包含历史观察 / 暂缓归档", value=False, key="wb-include-history")
    rows = [row for row in all_rows
            if (track == "ALL" or track in list(row.get("tracks") or []))
            and (priority == "全部" or row.get("priority") == priority)
            and (not favorites or row.get("favorite"))
            and (include_history or track == "HISTORY" or priority == "观察" or search
                 or (row.get("status") not in {"WATCH", "PAUSED", "CLOSED"}
                     and "HISTORY" not in list(row.get("tracks") or [])))
            and (not search or search.casefold() in json.dumps(row, ensure_ascii=False).casefold())]
    st.caption(f"筛选后 {len(rows)} / {len(all_rows)} 条。历史候选仅作为线索保留；没有自动升级为合格岗位。")
    mode = st.segmented_control("展示方式", ["看板", "列表"], default="看板", key="wb-board-mode")
    if mode == "列表":
        st.dataframe([{"编号": row["id"], "主体": row["company"], "路径": " / ".join(TRACKS[str(t)] for t in list(row.get("tracks") or [])),
                       "优先级": row.get("priority"), "进展": STATUSES[str(row.get("status", "VERIFY"))],
                       "研究结论": row.get("verdict"), "下一步": row.get("next_action"), "计划日期": row.get("due_date")}
                      for row in rows], hide_index=True, width="stretch")
    else:
        grouping = st.segmented_control("看板分组", ["按机会路径", "按推进阶段"], default="按机会路径", key="wb-grouping")
        groups = ({key: label for key, label in TRACKS.items()
                   if key != "HISTORY" or include_history or track == "HISTORY" or search}
                  if grouping == "按机会路径" else {key: key for key in BOARD_GROUPS})
        if grouping == "按机会路径" and track != "ALL":
            groups = {track: TRACKS[track]}
        if grouping == "按机会路径":
            st.caption("同一主体可出现在多个路径中；共用同一份档案与进展，不重复计数。")
        for (group_key, label), column in zip(groups.items(), st.columns(len(groups)), strict=True):
            selected = [row for row in rows
                        if group_key in list(row.get("tracks") or [])] if grouping == "按机会路径" else [
                            row for row in rows if row.get("status", "VERIFY") in BOARD_GROUPS[group_key]]
            with column:
                st.markdown(f"**{label} · {len(selected)}**")
                for row in selected:
                    with st.container(border=True):
                        st.html(f'<div class="career-company">{html.escape(str(row["company"]))}</div>'
                                f'<span class="career-pill">{html.escape(str(row.get("priority")))}</span>')
                        st.caption(STATUSES[str(row.get("status", "VERIFY"))])
                        st.write(_short(row.get("verdict"), 65))
                        with st.expander("下一步 / 关键门槛"):
                            st.write(_short(row.get("next_action"), 260))
                            st.caption(_short(row.get("objections"), 260))
                        if st.button("展开档案", key=f"board-open-{group_key}-{row['id']}", width="stretch"):
                            st.session_state["_workbench_focus_target"] = str(row["id"])
                            st.rerun()
    with st.expander("新增个人机会 / 创业项目"):
        with st.form("wb-new-opportunity"):
            company = st.text_input("公司 / 项目名称")
            tracks = st.multiselect("所属路径", list(TRACKS), default=["FULL_TIME"], format_func=TRACKS.__getitem__)
            signal = st.text_area("岗位、邀请或合作内容")
            source = st.text_input("原始链接（可空）")
            action = st.text_input("下一步")
            if st.form_submit_button("加入看板"):
                try:
                    identifier = add_candidate(store, {"company": company, "tracks": tracks, "signal": signal,
                                                       "source_url": source, "next_action": action})
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state["_workbench_focus_target"] = identifier
                    st.rerun()
    if not all_rows:
        st.info("尚无研究数据，可在“数据与备份”中导入已审查工作簿。")
        return
    pending = st.session_state.pop("_workbench_focus_target", None)
    identifiers = [str(row["id"]) for row in all_rows]
    if pending in identifiers:
        st.session_state["wb-detail-selector"] = pending
        st.session_state["wb-dialog-id"] = pending
    if st.session_state.get("wb-detail-selector") not in identifiers:
        st.session_state["wb-detail-selector"] = identifiers[0]
    st.divider()
    names = {str(row["id"]): str(row["company"]) for row in all_rows}
    focus = st.selectbox("选择机会，继续展开完整档案", identifiers, key="wb-detail-selector", format_func=lambda value: f"{names[value]} · {value}")
    if st.button("展开所选机会完整档案", type="primary", key="wb-open-selected"):
        st.session_state["wb-dialog-id"] = focus
    dialog_id = st.session_state.get("wb-dialog-id")
    if dialog_id in identifiers:
        _detail_dialog(store, next(row for row in all_rows if row["id"] == dialog_id))


def _relationships(store: LocalDataStore) -> None:
    _hero("关系与联系", "先核对已有关系和回执，再决定下一步。历史发送、最新回复与实际内推分别记录。")
    rows = merge_state(store, "relationships")
    warm = {"C015", "C016", "C017", "C018", "C019", "C020"}
    rows.sort(key=lambda row: (
        row.get("current_stage", "尚未复核") in {"尚未复核", "暂缓 / 停止"},
        not any(identifier in warm for identifier in list(row.get("candidate_ids") or [])),
        str(row["id"]),
    ))
    a, b = st.columns([2, 1])
    query = a.text_input("搜索姓名、公司或角色", key="wb-relation-search")
    statuses = sorted({str(row.get("historical_status", "")) for row in rows})
    status = b.selectbox("历史回执状态", ["ALL", *statuses], format_func=lambda v: "全部状态" if v == "ALL" else RELATION_LABELS.get(v, v))
    selected = [row for row in rows if (status == "ALL" or row.get("historical_status") == status)
                and (not query or query.casefold() in json.dumps(row, ensure_ascii=False).casefold())]
    st.caption(f"{len(rows)} 条历史记录，筛选后 {len(selected)} 条；存在跨批次重叠，不能当作独立人数。未实时读取私信。")
    st.dataframe([{"记录": r["id"], "姓名": r.get("name"), "公司": r.get("company"),
                   "历史接触": RELATION_LABELS.get(str(r.get("historical_status")), str(r.get("historical_status"))),
                   "本机复核": r.get("current_stage", "尚未复核"), "主页": r.get("profile_url")}
                  for r in selected], hide_index=True, width="stretch", height=330,
                 column_config={"主页": st.column_config.LinkColumn("职业主页")})
    if not selected:
        return
    identifiers = [str(row["id"]) for row in selected]
    by_id = {str(row["id"]): row for row in selected}
    identifier = st.selectbox("展开联系人记录", identifiers,
                              format_func=lambda v: f"{by_id[v].get('name')} · {by_id[v].get('company')} · {v}")
    row = by_id[identifier]
    _relationship_card(row, key=f"relation-profile-{identifier}")
    if identifier == "N059":
        _fact_cards(store, "C016")
    options = {str(item["id"]): str(item["company"]) for item in candidates(store)}
    current = str(row.get("current_stage", "尚未复核"))
    with st.form(f"relation-review-{identifier}"):
        stage = st.selectbox("人工核实后的当前状态", RELATION_STAGES, index=RELATION_STAGES.index(current) if current in RELATION_STAGES else 0)
        reply = st.text_area("最新回复 / 内推 / 会谈记录（仅手动录入）", value=_txt(row.get("latest_reply"), ""))
        linked = st.multiselect("关联机会（按身份核实后选择）", list(options), default=[str(v) for v in list(row.get("candidate_ids") or []) if v in options], format_func=options.__getitem__)
        action = st.text_input("关系的下一步", value=_txt(row.get("next_action"), ""))
        notes = st.text_area("备注与回执引用", value=_txt(row.get("notes"), ""))
        if st.form_submit_button("保存本次复核", type="primary"):
            save_relationship(store, identifier, {"current_stage": stage, "latest_reply": reply,
                                                   "candidate_ids": linked, "next_action": action, "notes": notes})
            st.session_state["_workbench_notice"] = "已保存人工复核，原始回执保持不变。"
            st.rerun()


def _tasks(store: LocalDataStore) -> None:
    _hero("行动清单", "把想法变成可完成的下一步。研究交付、沟通与入职成果分别记录。")
    rows = store.list(PREFIX + "tasks")
    mode = st.segmented_control("任务范围", ["待办", "已完成", "全部"], default="待办")
    selected = [row for row in rows if mode == "全部" or row.get("status") == ("DONE" if mode == "已完成" else "OPEN")]
    selected.sort(key=lambda row: (str(row.get("due_date") or "9999"), row.get("priority") != "优先"))
    for row in selected:
        with st.container(border=True):
            a, b = st.columns([5, 1])
            a.markdown(f"**{'✓ ' if row.get('status') == 'DONE' else ''}{row.get('title')}**")
            a.caption(f"{row.get('priority', '普通')} · {'未设日期' if not row.get('due_date') else row['due_date']} · {_txt(row.get('source'), '个人行动')}")
            if row.get("status") == "OPEN":
                if b.button("完成", key=f"task-done-{row['id']}"):
                    save_task(store, {**row, "status": "DONE"})
                    st.rerun()
            elif row.get("status") == "DONE":
                if b.button("重新打开", key=f"task-reopen-{row['id']}"):
                    save_task(store, {**row, "status": "OPEN"})
                    st.rerun()
            with st.expander("详情与修改"):
                with st.form(f"task-edit-{row['id']}"):
                    title = st.text_input("任务", value=_txt(row.get("title")))
                    notes = st.text_area("说明", value=_txt(row.get("notes"), ""))
                    due = st.text_input("日期 YYYY-MM-DD（可空）", value=_txt(row.get("due_date"), ""))
                    if st.form_submit_button("保存任务"):
                        try:
                            save_task(store, {**row, "title": title, "notes": notes, "due_date": due or None})
                        except ValueError as error:
                            st.error(str(error))
                        else:
                            st.rerun()
            if row.get("candidate_id") and st.button("查看关联机会", key=f"task-open-{row['id']}"):
                _open(str(row["candidate_id"]))
    with st.expander("新增行动", expanded=not selected):
        options = {str(row["id"]): str(row["company"]) for row in candidates(store)}
        with st.form("new-workbench-task"):
            title = st.text_input("要完成什么")
            opportunity = st.selectbox("关联机会（可选）", ["", *options], format_func=lambda v: options.get(v, "不关联"))
            priority = st.selectbox("行动优先级", PRIORITIES, index=2)
            due = st.text_input("计划完成日期（可空）")
            notes = st.text_area("具体说明")
            if st.form_submit_button("加入行动清单"):
                try:
                    save_task(store, {"title": title, "candidate_id": opportunity, "priority": priority,
                                       "due_date": due or None, "notes": notes, "status": "OPEN", "source": "个人录入"})
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.rerun()


def _sources(store: LocalDataStore) -> None:
    _hero("渠道与资料", "保留发现入口、历史对话和原始成果。每个结论都能继续往下查。")
    channels_tab, assets_tab, review_tab = st.tabs(["渠道入口", "成果与历史对话", "全局反方审查"])
    with channels_tab:
        health = {row["id"]: row for row in store.list(SCAN + "sources")}
        rows = store.list(PREFIX + "channels")
        categories = list(dict.fromkeys(str(row["category"]) for row in rows))
        category = st.selectbox("渠道分组", ["全部", *categories])
        query = st.text_input("搜索渠道与用途")
        selected = [row for row in rows if (category == "全部" or row.get("category") == category)
                    and (not query or query.casefold() in json.dumps(row, ensure_ascii=False).casefold())]
        for row in selected:
            with st.expander(f"{row['name']} · {row['category']}"):
                st.write(row.get("purpose"))
                st.caption(_txt(row.get("limitations")))
                st.caption(f"入口核查日期：{row.get('source_date')}；具体企业与岗位需独立核验。")
                if current := health.get(row["id"]):
                    st.caption(f"扫描状态：{current.get('status')} · 最近成功 {_date(current.get('last_success_at'))}")
                    st.write(current.get("message") or current.get("policy_note"))
                _links(urls(row.get("url")), "打开渠道", key=f"channel-{row['id']}")
    with assets_tab:
        assets = store.list(PREFIX + "assets")
        kind = st.selectbox("资料类型", ["全部", *sorted({str(row.get('kind')) for row in assets})])
        home = get_settings().home.resolve()
        for row in assets:
            if kind != "全部" and row.get("kind") != kind:
                continue
            with st.expander(f"{row.get('title')} · {_date(row.get('source_date'))}"):
                st.write(row.get("description"))
                _links(urls(row.get("url")), "下载 Library 原件" if row.get("library_file_id") else "打开原对话 / 项目", key=f"asset-{row['id']}")
                local = row.get("local_path")
                if local:
                    path = (home / str(local)).resolve()
                    if path.is_relative_to(home) and path.is_file() and path.suffix in {".md", ".pdf", ".docx", ".xlsx"} and path.stat().st_size < 10_000_000:
                        st.download_button("下载本机资料", path.read_bytes(), file_name=path.name, key=f"asset-download-{row['id']}")
                elif not row.get("url"):
                    st.caption("保留原成果索引；原件可从历史对话或 Library 查找，未生成替代原件。")
    with review_tab:
        known = {str(row["id"]) for row in candidates(store)}
        records = [row for row in store.list(PREFIX + "evidence") if row.get("candidate_id") not in known]
        st.caption("跨公司、身份去重与证据标准的审查记录；公司级反方意见在各机会详情中。")
        for row in records:
            with st.expander(f"{row.get('kind')} · {_txt(row.get('company'), '全局')}"):
                st.text(_txt(row.get("detail")))
                _links(list(row.get("urls") or []), key=f"global-evidence-{row['id']}")


def _radar(store: LocalDataStore) -> None:
    _hero("岗位雷达 · 已有 HCIS", "从已有来源中检索，再把值得管理的条目纳入统一看板。旧分数不会覆盖新优先级。")
    a, b = st.columns([2, 1])
    search = a.text_input("搜索已有公司、职位或地点", key="wb-radar-search")
    kind = b.selectbox("线索类型", ["全部", "CURRENT_JOB", "H1B_ROLE_HISTORY"], format_func=lambda v: {"CURRENT_JOB": "系统标记当前岗位", "H1B_ROLE_HISTORY": "历史雇主 / LCA 线索"}.get(v, v))
    rows = [row for row in store.list("opportunities") if row.get("candidate_id") == "william"
            and (kind == "全部" or row.get("lead_type") == kind)
            and (not search or search.casefold() in " ".join(str(row.get(field, "")) for field in ("company_name", "title", "location")).casefold())]
    st.caption(f"匹配 {len(rows):,} 条；包含旧雷达记录，不代表全部仍开放或符合新条件。")
    page = int(st.number_input("页码（每页 50 条）", min_value=1, max_value=max(1, (len(rows) + 49) // 50), value=1))
    visible = rows[(page - 1) * 50:page * 50]
    st.dataframe([{"ID": row.get("id"), "公司": row.get("company_name"), "职位": row.get("title"),
                   "地点": row.get("location"), "类型": row.get("lead_type"), "证据时间": row.get("last_seen_at"),
                   "官方链接": row.get("official_apply_url"), "旧核验状态": row.get("h1b_assessment")}
                  for row in visible], hide_index=True, width="stretch", height=380,
                 column_config={"官方链接": st.column_config.LinkColumn("官方链接")})
    if visible:
        options = {str(row["id"]): row for row in visible}
        selected = st.selectbox("选择本页线索", list(options), format_func=lambda v: f"{options[v].get('company_name')} · {options[v].get('title')}")
        if st.button("纳入统一看板", type="primary"):
            identifier = promote_legacy_opportunity(store, selected)
            _open(identifier)
    with st.expander("来源新鲜度与原数据状态"):
        st.dataframe([{"来源": row.get("source"), "状态": row.get("status"), "采集时间": row.get("captured_at"), "检查时间": row.get("checked_at")}
                      for row in store.list("source_health")], hide_index=True, width="stretch")


def _daily_scan(store: LocalDataStore) -> None:
    _hero("每日扫描", "新旧来源综合研读 · 每日最多 10 条机会重点 · 芝加哥每日 08:00")
    report = latest_brief(store)
    runs = store.list(SCAN + "runs")
    latest_run = max(runs, key=lambda row: str(row.get("date"))) if runs else None
    if latest_run and (not report or latest_run["date"] > report["date"]
                       or latest_run.get("input_digest") != report.get("input_digest")):
        st.info(f"{latest_run['date']} 已采集资料，等待综合审阅；下方保留最近已审阅结果。")
    if not report:
        st.info("尚无已完成综合审阅的日报。采集清单不会直接冒充个性化推荐。")
    else:
        st.subheader(f"机会重点 · {report['date']}")
        st.write(report.get("summary"))
        st.caption(f"{len(report['recommendations'])} 条 · 审阅 {_scan_time(report.get('reviewed_at'))}")
        if report.get("coverage_note"):
            st.caption("部分来源受限或仍待深读；覆盖、时区与资格限制可展开查看。")
            with st.expander("本轮覆盖与筛选说明"):
                st.write(report["coverage_note"])
        for item in report["recommendations"]:
            row = item["candidate"]
            with st.expander(f"{item['rank']}. {row['company']} · {row['title']}", expanded=item["rank"] <= 2):
                st.caption(f"路径：{TRACKS.get(item['track'], '公司研究 / 待核验')} · "
                           f"地点：{_txt(row.get('location'))} · 证据时间 {_scan_time(row.get('observed_at'))}")
                for label, field in (("值得关注", "why"), ("与你的关联", "fit"),
                                     ("门槛与未知", "barriers"), ("下一步", "next_action")):
                    st.markdown(f"**{label}**")
                    st.write(item[field])
                _links(item["evidence_urls"], "查看证据 / 官方入口", key=f"daily-{report['date']}-{item['rank']}")
        path = get_settings().home / "output/workbench" / report["date"] / "brief.md"
        if path.is_file():
            st.download_button("下载本次机会简报", path.read_text(), f"career-brief-{report['date']}.md", "text/markdown")
    st.subheader("渠道覆盖与新鲜度")
    rows = store.list(SCAN + "sources")
    st.dataframe([{"渠道": row.get("name"), "状态": row.get("status"),
                   "名录记录": row.get("directory_count"), "深读尝试": row.get("deep_read_attempted"),
                   "读到公司页面": row.get("deep_read_with_pages"),
                   "待深读": row.get("research_pending"), "最近成功采集": _scan_time(row.get("last_success_at")),
                   "说明": row.get("message") or row.get("policy_note")}
                  for row in rows], hide_index=True, width="stretch")
    with st.expander("原 H-1B 来源状态与历史证据边界"):
        st.write("H1BData / MyVisaJobs 的 LCA 记录是历史背景；当前岗位以雇主官方页面为准。")
        st.dataframe([{"来源": row.get("source"), "状态": row.get("status"),
                       "真实采集时间": row.get("captured_at"), "说明": row.get("message")}
                      for row in store.list("source_health")], hide_index=True, width="stretch")
    with st.expander("定时任务在哪里运行、每天交付什么"):
        st.write("Codex 桌面应用 → 定时任务 → HCIS 每日机会扫描。它在本机项目运行，"
                 "电脑需开机且应用运行；浏览器来源还需要可用会话。每来源每轮深读最多 20 家，"
                 "新旧来源去重后由 Codex 综合审阅，每天总计最多 10 条，不凑数。")
        st.write("结果保存到本工作台、原 HCIS 聊天和 output/workbench/日期/brief.md。"
                 "失败、受限、积压和旧快照分别显示；不自动申请或联系。")


def _data(store: LocalDataStore) -> None:
    _hero("数据与备份", "原研究、人工进展和历史回执分别保存。可随时导出当前工作台。")
    st.download_button("导出完整工作台 JSON", export_workspace(store), "William_Career_Workspace.json", "application/json", type="primary")
    report = brief(store)
    lines = ["# William 毕业后机会简报", f"生成时间：{datetime.now(UTC).isoformat()}",
             f"当前阶段：{report['stage']}", f"管理条目：{report['candidates']}；待办：{report['open_tasks']}；已完成事项：{report['completed_tasks']}", ""]
    for row in candidates(store):
        lines.extend([f"## {row['company']}", f"进展：{STATUSES[str(row.get('status', 'VERIFY'))]}；优先级：{row.get('priority')}",
                      f"研究结论：{row.get('verdict')}", f"下一步：{row.get('next_action')}", f"证据日期：{row.get('source_date')}", ""])
    st.download_button("导出可阅读简报", "\n".join(lines), "William_Career_Brief.md", "text/markdown")
    st.subheader("导入记录")
    for item in store.list(PREFIX + "imports"):
        with st.expander(f"{item.get('file_name')} · {_date(item.get('imported_at'))}"):
            st.json(item)
    with st.expander("导入更新后的审查工作簿"):
        st.caption("相同文件不会重复导入。人工进展独立保存，不被新工作簿覆盖。")
        upload = st.file_uploader("选择工作簿（候选总览 / 证据与审查 / 关系历史）", type=["xlsx"])
        if upload and st.button("导入研究数据"):
            if upload.size > 10_000_000:
                st.error("文件超过 10 MB，请精简后导入。")
            else:
                import hashlib
                root = get_settings().home / "private" / "career-workbench-imports"
                root.mkdir(parents=True, exist_ok=True)
                path = root / f"upload-{hashlib.sha256(upload.getvalue()).hexdigest()}.xlsx"
                path.write_bytes(upload.getvalue())
                try:
                    result = import_workbook(store, path)
                except Exception as error:
                    st.error(f"工作簿未导入：{type(error).__name__}: {error}")
                else:
                    st.session_state["_workbench_notice"] = f"导入完成：{result.get('counts')}"
                    st.rerun()


def render_workspace(store: LocalDataStore, navigation: str) -> None:
    st.html(CSS)
    notice = st.session_state.pop("_workbench_notice", None)
    if notice:
        st.success(notice)
    renderers = {"今日简报": _overview, "每日扫描": _daily_scan, "机会看板": _board, "关系与联系": _relationships,
                 "行动清单": _tasks, "渠道与资料": _sources, "岗位雷达": _radar, "数据与备份": _data}
    renderers[navigation](store)
