# DAC 2027 投稿 P0：第三方盲测包

本目录用于收集论文主结果所需的独立任务和四方法观测。项目现有的 24 条内部冻结任务仅用于调试评测器，不得复制、改写或计入本目录的论文结果。

## 1. 第三方任务

正式采集活动已经启动。本机打开 `http://127.0.0.1:8891/` 可以查看 24 个槽位并分别完成作者提交和独立裁决。活动文件位于 `dac2027-p0-blind-20261013/`。

1. 将 `blind_tasks.template.jsonl` 复制为 `blind_tasks.measured.jsonl`。
2. 由项目组之外的任务作者填写 8 个器件/结构族；每族各写 1 条完整、1 条信息缺失、1 条显式冲突需求。
3. 由不同人员独立复核物理接口、耦合、研究类型和是否应阻断。
4. 填写作者、单位、复核者、时间和独立性声明，并把 `record_status` 改为 `measured`。
5. 运行：`.venv\Scripts\python.exe scripts\evaluate_dac2027_p0.py --prepare-responses`。
6. 运行 `scripts\run_dac2027_p0_local_methods.py`，自动填写两个确定性本地方法的 48 行。
7. 运行 `scripts\prepare_dac2027_p0_llm_prompts.py`，生成直接 LLM 与检索 LLM 的 48 个冻结提示。外部模型调用需使用同一冻结模型和全新会话，并把真实返回、耗时和版本写回响应表。

验证器强制要求 24 条任务、8 个族、三类任务各 8 条，并拒绝模板行、内部作者声明以及作者兼任复核者。

## 2. 四方法统一运行

对同一批 24 条任务依次运行：

- `direct_llm`：只提供原始需求和统一输出格式；
- `retrieval_llm`：提供冻结的检索语料和统一输出格式；
- `existing_selector`：平台现有选择器；
- `contract_dependency_v11`：任务合同、依赖图和否定感知完整性门组成的完整方法。

每个任务与方法组合只保留一条 `measured` 记录，共 96 条。记录物理接口、耦合、研究类型、阻断决策、完成时间、交互次数、人工修改量、模型版本和运行时间。不得补齐缺失观测，不得把模板行改名为结果。

## 3. 统计与证据边界

评测报告给出 Wilson 95% 区间、完整方法相对各基线的双侧精确 McNemar 检验，以及完成时间的配对 bootstrap 区间。第三方身份和单位仍需人工审计；程序只能核对声明与 ID 一致性。

最终评测命令：

```powershell
.venv\Scripts\python.exe scripts\evaluate_dac2027_p0.py `
  --tasks benchmarks\dac2027_p0\blind_tasks.measured.jsonl `
  --responses benchmarks\dac2027_p0\method_responses.measured.jsonl
```
