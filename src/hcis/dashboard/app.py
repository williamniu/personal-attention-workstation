from __future__ import annotations

from datetime import datetime
from typing import cast

import streamlit as st

from hcis.api.app import data_store
from hcis.dashboard.tables import (
    COLUMNS,
    DATE_COLUMNS,
    EDITABLE_COLUMNS,
    NUMBER_COLUMNS,
    SOURCE_LABELS,
    UNKNOWN,
    ZONE,
    display_rows,
    filter_rows,
    local_time,
    sort_rows,
)
from hcis.settings import get_settings
from hcis.sources.platforms import (
    MANUAL_STATUSES,
    PLATFORM_SOURCES,
    blended_opportunities,
    recompute_opportunities,
    refresh_source,
)

STATUS_LABELS = {
    "NEW": "新发现 / New",
    "RESEARCH": "待研究 / Research",
    "SAVED": "已收藏 / Saved",
    "REFERRAL_RESEARCH": "待联系内部员工 / Referral Research",
    "READY": "准备申请 / Ready",
    "APPLIED": "已申请 / Applied",
    "INTERVIEW": "面试中 / Interview",
    "OFFER": "Offer",
    "REJECTED_CLOSED": "拒绝或关闭 / Rejected or Closed",
    "IGNORED": "忽略 / Ignored",
}
def _save_state(candidate_id: str, row: dict[str, object]) -> None:
    job_id = str(row["job_id"])
    key = f"{candidate_id}:{job_id}"
    store = data_store()
    current = store.get("opportunity_states", key) or {}
    store.upsert(
        "opportunity_states",
        key,
        {
            **current,
            "id": key,
            "candidate_id": candidate_id,
            "job_id": job_id,
            "favorite": bool(row.get("favorite", False)),
            "manual_status": row.get("manual_status", "NEW"),
            "notes": row.get("notes", ""),
        },
        "OPPORTUNITY_STATE_UPDATED",
    )


def _render_table(
    rows: list[dict[str, object]], candidate_id: str, key: str, editing: bool,
    source: str | None = None,
) -> None:
    displayed = display_rows(rows, source)
    prefix = f"{candidate_id}-{key}"
    with st.expander("逐列筛选 / Filter any column"):
        fields = st.multiselect(
            "筛选列（多个条件同时生效）", list(COLUMNS), format_func=COLUMNS.__getitem__,
            key=f"filters-{prefix}",
        )
        for field in fields:
            left, right = st.columns([1, 2])
            operators = ["包含", "等于", "未知", "已知"]
            if field in NUMBER_COLUMNS or field in DATE_COLUMNS:
                operators += ["≥", "≤"]
            operator = left.selectbox(
                COLUMNS[field], operators, key=f"op-{prefix}-{field}"
            )
            value = right.text_input(
                f"{COLUMNS[field]}：筛选值", disabled=operator in {"未知", "已知"},
                key=f"value-{prefix}-{field}",
                help="日期使用 YYYY-MM-DD；数值比较使用数字。",
            )
            try:
                displayed = filter_rows(displayed, field, operator, value)
            except ValueError:
                st.error(f"{COLUMNS[field]} 需要有效数字。")
                return
    left, right = st.columns([3, 1])
    default_sort = "score" if key == "top" else "first_seen_at"
    sort_field = left.selectbox(
        "排序列 / Sort any column", list(COLUMNS), index=list(COLUMNS).index(default_sort),
        format_func=COLUMNS.__getitem__, key=f"sort-{prefix}",
    )
    descending = right.toggle("降序 / Descending", value=True, key=f"desc-{prefix}")
    displayed = sort_rows(displayed, sort_field, descending)
    st.caption(
        f"显示 {len(displayed):,} / {len(rows):,} 条；全部匹配行均已加载，可滚动到底。"
        "点击任意列头也可排序；时间为纽约时间，空白表示未知。"
    )
    if key == "top":
        st.caption("此视图专门展示多来源精选 20 条；完整数据在各渠道和“全部结果”。")
    if not displayed:
        st.info("没有符合当前筛选条件的记录。")
        return
    column_config = {field: st.column_config.TextColumn(label) for field, label in COLUMNS.items()}
    for field in NUMBER_COLUMNS:
        column_config[field] = st.column_config.NumberColumn(COLUMNS[field])
    for field in ("apply", "official_apply_url", "source_url", "company_size_source_url",
                  "chinese_workforce_source_url"):
        column_config[field] = st.column_config.LinkColumn(COLUMNS[field])
    column_config["favorite"] = st.column_config.CheckboxColumn(COLUMNS["favorite"])
    column_config["manual_status"] = st.column_config.SelectboxColumn(
        COLUMNS["manual_status"], options=sorted(MANUAL_STATUSES), required=True
    )
    if not editing:
        st.dataframe(
            displayed, hide_index=True, width="stretch", height=620,
            column_config=column_config, key=f"table-{prefix}",
        )
        return
    edited = st.data_editor(
        displayed, hide_index=True, width="stretch", height=620,
        disabled=[field for field in COLUMNS if field not in EDITABLE_COLUMNS],
        column_config=column_config, key=f"editor-{prefix}",
    )
    if st.button("保存人工状态 / Save", key=f"save-{prefix}"):
        originals = {row["job_id"]: row for row in displayed}
        for row in edited:
            if any(row[field] != originals[row["job_id"]][field] for field in EDITABLE_COLUMNS):
                _save_state(candidate_id, row)
        recompute_opportunities(get_settings())
        st.session_state.pop("editing_rows", None)
        st.success("已保存；William 与 Rody 的状态互不影响 / Saved independently.")
        st.rerun()


def _candidate_view(candidate_id: str, display_name: str, editing: bool) -> None:
    opportunities = (
        st.session_state["editing_rows"] if editing else data_store().list("opportunities")
    )
    rows = [
        row
        for row in opportunities
        if row.get("candidate_id") == candidate_id and row.get("action_lane") != "REJECT"
    ]
    rows.sort(key=lambda row: float(str(row.get("score", 0))), reverse=True)
    all_tags = sorted({str(tag) for row in rows for tag in cast(list[object], row.get("tags", []))})
    total = len(rows)
    left, middle, right = st.columns(3)
    selected_tag = left.selectbox(
        "标签 / Tag", ["全部 / All", *all_tags], key=f"tag-{candidate_id}"
    )
    selected_status = middle.selectbox(
        "人工状态 / Status",
        ["全部 / All", *MANUAL_STATUSES],
        format_func=lambda value: STATUS_LABELS.get(value, value),
        key=f"status-{candidate_id}",
    )
    favorites_only = right.toggle("仅收藏 / Favorites only", key=f"fav-{candidate_id}")
    if selected_tag != "全部 / All":
        rows = [row for row in rows if selected_tag in cast(list[object], row.get("tags", []))]
    if selected_status != "全部 / All":
        rows = [row for row in rows if row.get("manual_status") == selected_status]
    if favorites_only:
        rows = [row for row in rows if row.get("favorite")]
    source_counts = {
        source: sum(source in cast(list[str], row.get("platform_sources", [])) for row in rows)
        for source in PLATFORM_SOURCES
    }
    st.caption(
        "渠道覆盖 / Source coverage: "
        + " · ".join(
            f"{SOURCE_LABELS[source]} {source_counts[source]}" for source in PLATFORM_SOURCES
        )
    )
    verify = [
        row
        for row in rows
        if row.get("h1b_assessment") in {"UNKNOWN_NEEDS_VERIFICATION", "UNVERIFIED_HIGH_POTENTIAL"}
    ]
    views = {
        "all": ("全部结果 / All results", rows),
        **{source: (SOURCE_LABELS[source], [
            row for row in rows if source in cast(list[str], row.get("platform_sources", []))
        ]) for source in PLATFORM_SOURCES},
        "top": ("多来源 Top 20 / Blended", blended_opportunities(rows)),
        "verify": ("H-1B 待人工核验 / Verify", verify),
    }
    tabs = st.tabs(
        [label for label, _ in views.values()], key=f"channel-{candidate_id}", on_change="rerun"
    )
    for (key, (_label, selected)), tab in zip(views.items(), tabs, strict=True):
        if tab.open:
            with tab:
                _render_table(
                    selected, candidate_id, key, editing, key if key in PLATFORM_SOURCES else None
                )
    st.caption(f"{display_name}: 筛选后 {len(rows):,} / 共 {total:,} 条可见机会")


def _legacy_dashboard() -> None:
    st.title("H-1B 求职情报系统 / Career Intelligence")
    st.caption(
        "发现、分析、排序、收藏和人工状态管理；不自动投递或联系。 "
        "/ Discovery and human-controlled tracking only."
    )
    editing = st.toggle("编辑收藏、人工状态和备注（暂停页面自动更新）", key="editing")
    if editing:
        if "editing_rows" not in st.session_state:
            st.session_state["editing_rows"] = data_store().list("opportunities")
        st.info("编辑期间固定表格内容，保存完成后关闭编辑开关即可恢复自动更新。")
    else:
        st.session_state.pop("editing_rows", None)

    with st.sidebar:
        st.subheader("数据源刷新 / Source refresh")
        for source in PLATFORM_SOURCES:
            if st.button(
                f"刷新 {SOURCE_LABELS[source]}",
                key=f"refresh-{source}",
                width="stretch",
            ):
                with st.spinner(f"正在刷新 {SOURCE_LABELS[source]}..."):
                    result = refresh_source(get_settings(), source, request_new_snapshot=True)
                st.session_state["last_refresh"] = result
        last_refresh = st.session_state.get("last_refresh")
        if last_refresh:
            st.json(last_refresh)
            if last_refresh.get("status") == "BROWSER_SESSION_REQUIRED":
                st.info(
                    "浏览器刷新已入队。需要在现有 Chrome 会话中完成实际采集；"
                    "若遇到登录或安全验证，来源会保留旧快照及其真实时间。"
                )
        st.caption(
            "每日任务唯一调度：Codex，纽约时间 08:00；本地 Scheduler 不重复启动采集。"
            "浏览器来源是否更新成功，以实际采集时间和来源状态为准。"
        )


    @st.fragment(run_every=None if editing else "30s")
    def live_results() -> None:
        now = datetime.now(ZONE)
        health = {str(row["source"]): row for row in data_store().list("source_health")}
        overview = []
        attention = []
        for source in PLATFORM_SOURCES:
            row = health.get(source, {})
            captured = local_time(row.get("captured_at"))
            stale = captured == UNKNOWN or captured[:10] != now.date().isoformat()
            status = str(row.get("status", "NOT_RUN"))
            coverage = cast(dict[str, object], row.get("coverage") or {})
            overview.append({
                "来源": SOURCE_LABELS[source], "本轮状态": status,
                "最近成功采集（纽约）": captured,
                "最近尝试 / 检查（纽约）": local_time(row.get("checked_at")),
                "新鲜度": "旧快照 / 未采集" if stale else "今日采集",
                "采集覆盖": ("完整" if coverage.get("complete") is True
                           else "部分" if coverage.get("complete") is False else "未声明"),
                "最近快照原始行数": row.get("raw_jobs"),
                "最近快照去重岗位数": row.get("jobs"),
                "最近采集新增岗位": row.get("new_jobs"),
            })
            if stale or status != "HEALTHY":
                attention.append(f"{SOURCE_LABELS[source]}：{status}，采集于 {captured}")
        st.dataframe(overview, hide_index=True, width="stretch")
        if attention:
            st.warning("部分渠道未完整更新。" + "；".join(attention))
            with st.expander("查看来源失败原因"):
                for source, row in health.items():
                    if row.get("message"):
                        st.text(f"{SOURCE_LABELS.get(source, source)}: {row['message']}")
        st.caption(
            f"页面读取时间：{now:%Y-%m-%d %H:%M:%S}（纽约）。"
            + ("编辑模式下暂停自动更新。" if editing else "每 30 秒自动读取最新入库结果。")
            + "每条线索的采集时间独立保留；来源今天成功，不代表该来源的所有旧记录今天仍被观察到。"
        )
        st.caption(
            "人数规模、华人比例只展示有公开来源的值；缺少依据显示未知。"
            "中文工作环境单独列出，不据姓名、国籍或工作语言推算华人比例。"
        )
        for candidate_id, tab in zip(
            ("william", "girlfriend"),
            st.tabs(["William", "Rody"], key="candidate-tab", on_change="rerun"),
            strict=True,
        ):
            if tab.open:
                with tab:
                    _candidate_view(
                        candidate_id, "William" if candidate_id == "william" else "Rody", editing
                    )


    live_results()


from hcis.dashboard.workbench import NAVIGATION, render_workspace

st.set_page_config(page_title="William · 毕业后机会工作台", page_icon="◈", layout="wide")
workspace_store = data_store()
pending_navigation = st.session_state.pop("_workbench_nav_target", None)
if pending_navigation in NAVIGATION:
    st.session_state["career-navigation"] = pending_navigation
with st.sidebar:
    st.markdown("### ◈ William")
    st.caption("毕业后机会工作台 · 本机私有")
    navigation = st.radio(
        "工作区", NAVIGATION, key="career-navigation",
        index=0 if workspace_store.list("workbench_candidates") else len(NAVIGATION) - 1,
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("全职 · 联创 / 创业 · 企业 AI 合作")
    st.caption("来源有日期，进展有记录，细节可展开。")

if navigation == "H-1B 原工作台":
    _legacy_dashboard()
else:
    render_workspace(workspace_store, navigation)
