# DAC 2027 投稿 P0 执行状态

更新时间：2026-10-13

## P0 的范围

本轮 P0 指一个月投稿计划中的最高优先级证据，不是项目早期同名的软件阶段。评测对象固定为“从工程需求编译出物理接口、耦合、研究类型和安全阻断决策”，投稿方向固定为 DAC AI1.5。

P0 包含四项：第三方独立任务、四方法同任务对照、关键消融、配对统计。端到端 COMSOL 六类实机证据继续沿用问题一已有报告，但不能代替第三方需求任务。

## 已完成

| 项目 | 产物 | 状态 |
|---|---|---|
| 冻结协议 | `configs/dac2027_p0_protocol.json` | 已完成 |
| 第三方盲测模板 | `benchmarks/dac2027_p0/blind_tasks.template.jsonl` | 24 槽位已生成 |
| 四方法观测格式 | `benchmarks/dac2027_p0/method_response_schema.json` | 已完成 |
| 本地基线执行器 | `scripts/run_dac2027_p0_local_methods.py` | 已完成，第三方任务到位后运行 |
| LLM 冻结提示生成器 | `scripts/prepare_dac2027_p0_llm_prompts.py` | 已完成，第三方任务到位后生成 48 个提示 |
| 防止证据混用 | 任务校验器拒绝内部作者、模板行、作者兼任复核者和不平衡数据 | 已完成 |
| 统一指标 | 物理接口与耦合完全匹配、研究类型、阻断准确率、错误放行、错误阻断 | 已完成 |
| 统计 | Wilson 95% 区间、双侧精确 McNemar、配对 bootstrap | 已完成 |
| 冻结清单 | `generated/dac2027/p0/freeze_manifest.json` | 方法、模板和运行器 11 个文件已记录 SHA-256 |
| 消融 | 去依赖图、去否定感知完整性、去安全门 | 已完成 |
| 内部先导 | 24 条、8 个族、三种状态各 8 条 | 已完成，不能作为主结果 |
| 主平台 P0 控制区 | `web_app.py` | 已完成，实时显示 24/24/24/96 四级进度和论文证据门 |
| 可点击采集入口 | `http://127.0.0.1:8891/` | 已完成，主平台可直接打开 |
| Windows 一键启动集成 | `start_windows.bat`、`start_local_8880.bat` | 已完成，自动检查或启动 8891 采集服务 |

## 内部先导结果

| 方法 | 接口与耦合完全匹配 | 研究类型 | 阻断判断 | 错误放行 |
|---|---:|---:|---:|---:|
| 现有选择器 | 21/24 | 24/24 | 19/24 | 2/16 |
| v1.0 依赖图，无否定感知完整性 | 22/24 | 24/24 | 16/24 | 8/16 |
| v1.1 完整方法 | 22/24 | 24/24 | 24/24 | 0/16 |
| 去安全门 | 22/24 | 24/24 | 8/24 | 16/16 |

v1.1 相对 v1.0 的阻断判断精确 McNemar 检验为 p=0.007812；相对去安全门为 p=0.000031。因为任务由项目组编写，这些数值只说明实现与消融管线正常。

接口与耦合的两条失败为 `v11-final-laser-missing` 和 `v11-final-manifold-missing`。两条任务均被安全门正确阻断，但缺失条件文本导致正向物理证据不足。论文应分别报告“选择完全匹配”和“安全门正确”，不能把阻断正确写成选择正确。

## 尚未通过的论文证据门

当前 `p0_publication_gate_passed=false`，原因只有两类外部观测尚未产生：

1. 项目组之外的作者尚未提交 24 条需求，独立复核者也尚未签署期望答案。
2. 同一批盲测任务上的 `direct_llm`、`retrieval_llm`、`existing_selector`、`contract_dependency_v11` 共 96 条实测记录尚未完成。

这些观测不能由程序自动伪造。收集完成后运行 `scripts/evaluate_dac2027_p0.py`，报告会自动完成指标、置信区间和配对检验。

## 第三方采集活动

采集活动 `dac2027-p0-blind-20261013` 已于 2026-10-13 启动。24 个槽位已经按 8 个器件族和三种任务类型建立，本地采集入口为 `http://127.0.0.1:8891/`。当前状态为：作者提交 0/24、独立裁决 0/24、密封任务 0/24。

主平台右侧“DAC P0 第三方盲测”区会每 10 秒读取一次实际文件计数，并明确显示作者、裁决、密封任务、四方法实测和 P0 论文证据门。点击“打开第三方采集入口”即可进入 24 槽位页面；Windows 一键启动脚本会自动复用或启动该服务。

每个器件族有独立的作者说明和裁决说明。页面禁止覆盖已提交记录，要求作者与裁决者 ID 不同，并在全部 24 条作者记录和 24 条裁决记录齐全后才生成 `blind_tasks.measured.jsonl` 与 SHA-256 密封清单。方法运行必须等到密封完成后才能开始。

## 执行入口

```powershell
# 重建模板和查看门状态
.venv\Scripts\python.exe scripts\prepare_dac2027_p0.py

# 内部先导，仅用于调试
.venv\Scripts\python.exe scripts\run_dac2027_p0_internal_pilot.py

# 验证第三方任务并生成 96 行响应表
.venv\Scripts\python.exe scripts\evaluate_dac2027_p0.py --prepare-responses

# 四方法完成后生成论文结果
.venv\Scripts\python.exe scripts\evaluate_dac2027_p0.py `
  --responses benchmarks\dac2027_p0\method_responses.measured.jsonl
```

机器可读状态位于 `generated/dac2027/p0/readiness_status.json`，内部先导明细位于 `generated/dac2027/p0/internal_pilot_report.json`。
