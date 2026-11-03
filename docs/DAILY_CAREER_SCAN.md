# 每日个性化机会扫描

唯一调度入口是 Codex 桌面定时任务 `hcis-9`，目标为原 HCIS 聊天，时间统一为
America/Chicago 每日 08:00。`config/sources/platforms.yaml` 的
`schedule.driver=codex_heartbeat` 阻止本地 Scheduler 重复采集。电脑与 Codex 应用需运行；
浏览器来源还需可用会话。漏跑后只处理最新一轮，不能重新标记旧快照。

每来源每轮最多深读 20 家公司，其余留队；最终从**所有来源合计最多推荐 10 条**。
公司清单、当前岗位和明确联创邀请分别处理。Founding Engineer、股权、融资或 VC 背书
不构成联创邀请，也不构成公司商业成功的证明。允许少于 10 条或没有新推荐。

## 每轮步骤

1. 保留原自动化的四来源刷新、浏览器覆盖记录和官方链接检查：H1BData、MyVisaJobs、
   H1BGrader、官方 Careers。使用当前配置中的 William/Rody 查询，沿用原第一页边界。
   历史 LCA 只作背景；受限或失败保留旧资料及其真实日期。
2. 读取 `KANBAN.md` 的 CAREER-003、`config/sources/discovery.yaml` 和本轮来源状态。
   运行 `.venv/bin/python -m hcis.cli scan-workbench`。正常每日调用一次；同日重放复用结果。
   `--source <id>` 仅补跑指定失败来源；`--force` 表示重新访问新证据，会再消耗一轮深读额度。
   不为调试反复全来源重跑。
3. 四个 VC 名录先建立公开列表基线，再读新增／变化公司及其公开 Careers、官方 ATS。
   已找到的完整 ATS 每日复查，即使 VC 卡片没有变化。列表覆盖、深读尝试、读到页面、
   ATS 完整性分别计数；失败不等于零岗位。目录中的域名也可能过期或转作他用，须核对业务。
4. 审阅原渠道中 `BROWSER_REVIEW_REQUIRED` 的入口：先核条款、robots、登录与实际可见列表。
   在允许自动读取的情况下，通过现有浏览器读取本轮最多 20 家公司；记录实际页数／行数、
   是否有后页及真实 observed_at。技术入口成功不等于该渠道采集成功。
   可将实际观察整理为下方格式，再运行
   `.venv/bin/python -m hcis.cli ingest-workbench-directory <snapshot.json>`，
   随后 `scan-workbench --source <id>` 深读其官方来源。
   YC、TechCrunch 当前受限，禁止用此入口伪装自动抓取成功；仅接收用户实际提供的公司线索，
   在 `workbench` 来源中追踪雇主官方证据。不得跨过验证码、MFA、登录或付费墙。
5. 旧 Workbench 的 45 个候选也进入总候选池，保留人工状态。选中的历史候选须回官方核岗，
   必要时从其原证据中读取明确岗位页。主页没有 Careers 链接不代表没有招聘。
   IT 桔子免费新闻摘要保存在 `news` 中；按业务相关性寻找公司官方进展／岗位，最多深读 20 家。
   免费 `today` 不覆盖历史或网页全部快讯，保留 `published_at_raw`，时区未知时不自行转换。
6. 读取 `output/workbench/芝加哥日期/review-input.json`，进行 Codex 综合语义审阅。
   120 条只是便于阅读的召回样本，不是最终排名；须结合新闻、旧候选和
   `all-candidates.json` 扩读未入样本的研究、设计工程、产品、FDE、GTM 等职责。
   用 `profile` 的已确认事实与项目材料逐项解释；区分经历证据、可迁移推断和未知条件。
   不从职位名推定匹配，不把课程／原型视为任职年限或前沿训练经验。
   任何官方新读取必须保存实际正文、链接与观察时间，再 `scan-workbench --prepare-only`
   更新审阅输入；旧证据的日期保持不变。
7. 将最终审阅写入本机 `review.json`，使用下方结构。每条包含商业／产品证据、为何相关、
   真正门槛和下一步。核对 seniority、地点、工作授权限制、实习性质与完整 JD；
   同一公司不同地点的重复岗位通常只占一个重点。无当前联创证据时明确写“本轮未核实”。
8. 运行 `.venv/bin/python -m hcis.cli publish-workbench-brief <review.json>`。
   该命令校验输入摘要、完整候选池、事实 ID、观察到的链接和全日总量；未审阅清单不能发布。
   读回 `brief.md`／`brief.json` 和工作台“每日扫描”。在原聊天交付最多 10 条重点、
   覆盖／失败／积压及用户下一步。保存状态不等于已申请或联系。

## 输入格式

浏览器公司快照（`source` 必须已登记且未受限；`workbench` 用于既有候选或用户提供线索）：

```json
{
  "schema_version": 1,
  "source": "渠道ID",
  "captured_at": "本轮真实的带时区ISO时间",
  "coverage": {"complete": false, "scope": "实际读取页数、行数与截断范围"},
  "companies": [{"name": "实际公司名", "detail_url": "实际详情URL", "website": "已确认官网或null", "description": "实际业务描述"}]
}
```

`read_employer`、`identify_jobs`、`save_research` 可用于保存从原候选证据中实际读到的官方
岗位正文；来源 ID、公司条目和链接必须保留关联。只核一条岗位时不能声明整个 ATS 完整，
也不能关闭未读取的旧岗位。不得将任意网页、搜索摘要或第三方聚合页标为官方 JD。

最终审阅（以下占位文字需替换为本轮观察与判断）：

```json
{
  "date": "芝加哥ISO日期",
  "input_digest": "review-input.json中的digest",
  "summary": "本轮判断及优先行动",
  "coverage_note": "来源覆盖、失败、陈旧与未核实联创需求",
  "recommendations": [{
    "candidate_id": "完整候选池中的ID",
    "track": "FULL_TIME",
    "why": "产品／商业事实及其证据边界",
    "fit": "已证经历与可迁移能力的对应",
    "barriers": "真实资历、地点、实习或授权限制",
    "next_action": "用户可执行的具体下一步",
    "fact_ids": ["profile中的事实或项目ID"],
    "evidence_urls": ["该候选实际观察到的URL"]
  }]
}
```

路径允许 `FULL_TIME`、`RESEARCH`、`AI_PARTNERSHIP`；`COFOUNDER` 还需当前明确邀请证据。
实习不能写成毕业后全职；商业数字须标明公司自述，不能称为独立审计结论。

## 本机结果与恢复

- `data/hcis.sqlite3` 的 `workbench_scan_*` 集合保存来源、公司队列、岗位、新闻、画像版本、
  采集与审阅回执。它们与人工收藏／备注／进展分离，纳入“完整工作台 JSON”导出。
- `output/workbench/YYYY-MM-DD/` 保存原始名录、实际公司页面、完整候选池、审阅输入和日报。
  同日补跑的既有输入／日报存入 `attempts/`；完整候选池摘要防止审阅与证据错位。
- `scan-workbench --prepare-only` 不访问网络，仅用已存证据重建审阅包。
  `audit-workbench-sources` 检查原渠道公开入口及可定位的条款，输出需要浏览器补核的项，
  不会把 HTTP 200 当作完成接入。
- 目录全量不代表公司全部深读；同一公司可有多个机构出处，按官网关联，不能仅凭同名合并。
  四来源旧榜单供原 William/Rody 雷达继续使用，每日精选总量不按旧分数直接截取。
- 不安装第三方 Skill，不增加付费调用；不自动投递、外联、修改人工状态或上传私有资料。
  长期无人值守稳定性需实际定时运行验证，单次手动成功不能代替。
