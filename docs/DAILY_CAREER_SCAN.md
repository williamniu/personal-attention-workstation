# 每日个性化机会扫描

唯一调度入口是 Codex 桌面定时任务 `hcis-9`，在原 HCIS 聊天按
America/Chicago 每日 08:00 运行。`config/sources/platforms.yaml` 的
`schedule.driver=codex_heartbeat` 阻止本地 Scheduler 重复采集。
电脑与 Codex 应用需运行，浏览器需有可用会话；未来定时稳定性以实际回执为准。

每来源每轮最多深读 20 家公司，未完成留队；新旧所有来源合计每日最多推荐 10 条，允许少于
10 条。研究、RL／Agent 评估、产品与设计工程、开发、FDE、GTM、DevRel 等按职责判断。
Founding Engineer、股权、融资或 VC 背书不构成明确联创邀请或商业成功证明。

## 采集路径

本次 8 个入口及其公司／招聘详情**只用 Codex 内置浏览器（IAB）读取实际渲染页面**：
YC Companies、YC Jobs、TechCrunch Startups、IT 桔子、CRV、Sequoia、MindWorks、源码资本。
使用该浏览器内的实际登录态，不假定 Chrome 或其他聊天已登录就可复用。
不直接请求 IT 桔子免费 API、名录 HTTP／搜索索引或 ATS 接口；不使用 Chrome 回退。
网页自身正常加载的数据可以读取，但不读取后台响应、隐藏脚本状态、cookie、local storage、
密码或验证码。不新装自动化浏览器服务。

原四来源的既有授权流程、数据和人工状态继续保留，参加同一个总候选池；其历史 HTTP／ATS
数据不是本轮 IAB 观察。旧两条 IT 桔子免费摘要仅作历史，保留原日期和覆盖范围。
网站声明与技术可读性分别记录；实际出现登录、验证、会员限制或空白时准确交接，不绕过。
IT 桔子目前按用户要求暂略过（配置 `user_deferred=true`），保留渠道及历史数据；
定时任务不访问它、不重复请求登录，也不以 API 补数，待用户要求恢复后再处理。

## 每轮步骤

1. 沿用原自动化的四来源刷新、William/Rody 查询范围、历史 LCA 边界和官方链接检查。
   失败保留旧数据和真实采集时间；不把保存回执时间当作重新观察时间。
2. 读取 `config/sources/discovery.yaml` 与本指南。运行
   `.venv/bin/python -m hcis.cli scan-workbench`，读取当日 `browser-worklist.json`。
   此命令只生成浏览器待办和审阅输入，不访问网络，也不等于完成采集。
   `--force` 仅重建待办／审阅包；`--source <id>` 缩小待办；`--prepare-only` 只准备审阅。
3. 使用 IAB 逐一访问 8 个实际入口。记录当前登录证据、实际页数、可见数量、加载状态、
   筛选／视图、是否有后页；未知不填完整。YC 先读公开列表，有登录需求及时请用户操作。
   CRV 先 Featured，再从页面切换 All；Sequoia 须切换 All Companies 并核对 Load More；
   MindWorks 读筛选和详情，不采隐藏退出标签；源码资本须点击公司标志后读弹窗及官网回链，
   VC 自身招聘不算被投公司岗位。TechCrunch 读文章正文并沿公司公开回链研究。
   IT 桔子只读其网页；空白不等于零条或没有会员。不得改用 API 补数。
4. 把实际观察写成 schema_version=2 快照，运行
   `.venv/bin/python -m hcis.cli ingest-workbench-browser <capture.json>`。
   首次公司列表摄入后读回 `workbench_scan_entries` 的 ID（或重新生成待办），再逐公司深读
   实际官网、Careers 与岗位正文，按相同格式分批摄入。每来源同一 `round_id` 合计最多 20 家，
   默认 round_id 为芝加哥日期；分批不重置额度。额外一轮须明确使用新 round_id，不为凑数重跑。
   首页／详情／岗位分别保留真实观察时间与可见链接；本轮未读到的旧正文不改日期。
   只核几条岗位不能标整个招聘板完整，部分失败不关闭旧岗位。
5. 旧 Workbench 候选一并研究，保留人工状态。选中旧线索应经 IAB 回官方核实。
   YC 等平台岗位可保存为 PLATFORM_LISTING；须进一步找到雇主官网回链和完整 JD 才能作为
   已核实的全职岗位。任意搜索摘要或第三方聚合页面不能冒充雇主官方 JD。
6. 执行 `scan-workbench --prepare-only`。读取当日 `review-input.json` 和
   `all-candidates.json`，结合版本化个人事实和项目证据综合审阅。120 条召回样本不是最终榜单；
   扩读相关职责，区分个人经历、可迁移推断和未知条件，不从职位名推定匹配。
   岗位须核对资历、地点、工作授权、实习性质及完整职责，商业指标注明公司自述或独立证据。
7. 在本机生成 `review.json`，运行 `publish-workbench-brief <review.json>`。
   发布校验当前输入摘要、完整候选池、事实 ID、已观察链接和总量。没有明确联创邀请时写明
   “本轮未核实”；实习只进入研究方向，不写成正式全职。没有新变化不重复包装旧机会。
8. 读回工作台“每日扫描”与 `brief.md`，在原 HCIS 聊天交付最多 10 条重点、来源覆盖／失败／
   陈旧日期／待深读数量和用户下一步。采集、推荐、投递分别处理，不自动联系或申请。

## 浏览器快照

以下占位内容必须替换为本轮真实页面观察；浏览器摄入不负责替代理由或生成虚构正文。

```json
{
  "schema_version": 2,
  "source": "配置中的来源ID",
  "round_id": "本轮标识，默认芝加哥日期",
  "captured_at": "真实且带时区的ISO时间",
  "browser": {"type": "iab", "login_state": "SIGNED_OUT", "login_evidence": "页面显示 Log in"},
  "status": "PARTIAL_CAPTURE",
  "coverage": {"complete": false, "render_complete": true, "has_more": true, "scope": "实际视图、筛选、页数、行数和截断"},
  "pages": [{"url": "实际页面URL", "title": "页面标题", "text": "实际渲染正文或标明范围的摘录", "observed_at": "真实ISO时间", "links": [{"label": "可见链接文字", "url": "实际链接"}]}],
  "companies": [{"name": "公司名", "detail_url": "实际详情或弹窗所属页面URL", "website": "已核实官网或null", "description": "实际业务描述"}],
  "news": [],
  "research": []
}
```

`login_state` 为 SIGNED_IN／SIGNED_OUT／NOT_REQUIRED／UNKNOWN；已登录或未登录须有当前可见证据。
成功状态为 CAPTURED／PARTIAL_CAPTURE；失败为 LOGIN_REQUIRED／VERIFICATION_REQUIRED／
MEMBERSHIP_REQUIRED／BLANK_PAGE／UNAVAILABLE，不能夹带新公司或岗位。
完整覆盖必须明确 `render_complete=true`、`has_more=false`，不能从没有看见后页自行推定。

`news` 项含 title、url、summary、published_at_raw、published_timezone，时间未知留空。
`research` 项含已登记的 entry_id、真实 observed_at、pages、jobs、boards、errors。
岗位项含实际 url、title、description、location、employment_type 和显式 evidence_kind：
OFFICIAL_EMPLOYER 或 PLATFORM_LISTING。岗位 URL 必须有对应的实际渲染页面；官方岗位还需在
pages 的可见 links 中存在从雇主官网到该 JD 的链路。所有页面使用上例格式。
人工压缩的公司业务笔记须标 `text_kind=BROWSER_REVIEW_SUMMARY`，与逐字渲染正文
`RENDERED_TEXT` 分开；摘要不能作为已读岗位全文。登录回执可保留非秘密的 context_id，
用于核对是否为同一浏览器上下文；不能保存 cookie 或认证数据。
仅对已完整读取的**无筛选**招聘板，boards 项才可含 id、url、complete=true、
render_complete=true、has_more=false、unfiltered=true；否则 boards 留空或 complete=false。

旧 `ingest-workbench-directory` 仅供历史 watchlist 离线导入，不能代替这 8 个来源的浏览器快照。

## 最终审阅

```json
{
  "date": "芝加哥ISO日期",
  "input_digest": "review-input.json中的digest",
  "summary": "本轮判断及优先行动",
  "coverage_note": "真实覆盖、登录失败、陈旧日期和未核实的联创需求",
  "recommendations": [{
    "candidate_id": "完整候选池中的ID",
    "track": "FULL_TIME",
    "why": "产品／商业证据及边界",
    "fit": "已证经历与可迁移能力的关联",
    "barriers": "资历、地点、实习或授权限制",
    "next_action": "用户可执行的下一步",
    "fact_ids": ["画像中的事实或项目ID"],
    "evidence_urls": ["候选已观察到的链接"]
  }]
}
```

FULL_TIME 须有雇主官方 JD；PLATFORM_JOB／公司线索／实习使用 RESEARCH。
AI_PARTNERSHIP 与 COFOUNDER 也须保留实际证据；联创另需当前明确邀请。

## 本机结果与恢复

`data/hcis.sqlite3` 的 `workbench_scan_*` 集合保存来源、公司队列、岗位、新闻、画像和回执，
与人工收藏、备注和进度分离，并纳入完整工作台 JSON 导出。
`output/workbench/browser/来源/摘要.json` 保存浏览器证据；当日目录保存待办、完整候选池、
审阅输入和日报。同日旧输入／日报存入 attempts，不覆盖其证据时间。
失败尝试单独记录 checked_at，保留上次实际成功时间；精确重放零新增，旧 API 不冒充浏览器。
私有数据库、原始页面和个人分析不上传 GitHub。不新增付费调用、第三方安装、外联或重复调度。
