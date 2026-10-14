# DAC 2027 投稿 P3：前瞻独立多案例评测与统计

更新时间：2026-10-14

## 1. P3 目标

P3 对应五项问题中的第四项“前瞻独立多案例评测与统计不足”。本阶段不复用 P2 的项目自编任务作为主结果，而是要求方法冻结后，在由项目组外作者编写、不同人员裁决、案例族与全部开发集合隔离的新任务上完成重复实测。

## 2. 冻结协议

- 外部任务：24 条。
- 新案例族：8 个，每族包含完整、缺失和冲突需求各 1 条。
- 对比方法：Direct LLM、Retrieval LLM、Existing Selector、Contract Dependency v1.1。
- 重复次数：两种 LLM 各对每条任务独立运行 3 次；两种确定性方法各运行 1 次。
- 总观测数：`24 × (3 + 3 + 1 + 1) = 192`。
- 隔离要求：8 个最终案例族不得与 v1.0、v1.1 的开发、验证和最终集合重叠。
- 密封要求：外部任务通过作者、裁决者和完整性校验后，先保存任务 SHA-256，再运行任何方法。
- 冻结要求：任务解封后不得修改方法源文件、检索语料、输出合同或统计规则。

## 3. 统计与错误报告

P3 评测器同时输出：

1. 每个方法的任务级共识结果。
2. 物理接口与耦合完全匹配率、研究类型准确率和阻断准确率。
3. 错误放行率、错误阻断率及 Wilson 95% 区间。
4. 完整方法相对各基线的双侧精确 McNemar 检验。
5. 配对完成时间 bootstrap 95% 区间。
6. 每个案例族的独立结果。
7. LLM 三次运行的一致任务数和发生预测变化的任务清单。
8. 物理或耦合错误、研究类型错误、错误放行和错误阻断四类失败统计。

## 4. 当前状态

| 项目 | 当前值 | 状态 |
|---|---:|---|
| 冻结协议 | 1/1 | 完成 |
| 方法、检索语料和历史集合哈希 | 10/10 | 通过 |
| 案例族隔离检查器 | 已实现 | 通过自动测试 |
| 重复运行响应合同 | 192 条 | 已冻结 |
| 统计和失败分类管线 | 已实现 | 通过自动测试 |
| P3 专项测试 | 6/6 | 通过 |
| 外部任务 | 0/24 | 等待 P0 第三方采集 |
| 外部新案例族 | 0/8 | 等待 P0 第三方采集 |
| 重复实测 | 0/192 | 未开始，任务尚未密封 |
| P3 本机基础设施门 | 通过 | 可以接收真实数据 |
| P3 独立主结果门 | 未通过 | 不得生成主结果数值 |

当前未生成任何合成主结果，也没有把 P2 的 24 条项目自编任务重新标为独立数据。只有 P0 第三方任务通过校验、案例族隔离和 SHA-256 密封后，P3 才会创建 192 行响应表并允许开始运行。

## 5. 运行入口

刷新当前状态：

```powershell
.\.venv\Scripts\python.exe scripts\prepare_dac2027_p3.py
```

外部任务齐全后密封：

```powershell
.\.venv\Scripts\python.exe scripts\prepare_dac2027_p3.py --seal
```

全部 192 条实测齐全后评分：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_dac2027_p3.py
```

密封后自动执行并支持断点续跑：

```powershell
.\.venv\Scripts\python.exe scripts\run_dac2027_p3.py --llm-workers 4
```

## 6. 主要产物

- 冻结协议：`configs/dac2027_p3_protocol.json`
- 评测模块：`src/comsol_small_model/dac2027_p3_evaluation.py`
- 状态和密封入口：`scripts/prepare_dac2027_p3.py`
- 四方法重复运行器：`scripts/run_dac2027_p3.py`
- 最终评分入口：`scripts/evaluate_dac2027_p3.py`
- 基础设施冻结入口：`scripts/freeze_dac2027_p3.py`
- 自动测试：`tests/test_dac2027_p3.py`
- 冻结清单：`generated/dac2027/p3/infrastructure_freeze_manifest.json`
- 机器状态：`generated/dac2027/p3/readiness_status.json`
- 网页接口：`GET /api/dac2027/p3/status`
- 网页校验与密封接口：`POST /api/dac2027/p3/prepare`
- 外部盲测执行指南：`DAC2027_P3_EXTERNAL_CAMPAIGN_GUIDE.md`

## 7. 证据边界

P3 当前关闭了“如何做独立、多案例、重复和统计评测”的基础设施缺口，但尚未关闭“真实独立结果”缺口。剩余工作需要真实外部作者和独立裁决者，项目代码不能自行制造这些记录。
