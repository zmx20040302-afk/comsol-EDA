# 问题一投稿证据采集包

该目录冻结三类补充证据的输入，不能把模板或项目组自行填写的数据当作真实外部证据。

## 外部模型整段重生成

运行 `scripts/prepare_dac_problem1_publication_evidence.py` 后，在
`generated/dac/problem1_publication/external_regeneration_responses.jsonl` 中得到六条模板。
把每条记录的完整模型输出和运行元数据填入，并将 `record_status` 改成 `measured`，再运行：

```powershell
python scripts/evaluate_dac_problem1_external_regeneration.py
```

同一冻结模型、温度 0、相同输出预算，每个任务只执行一次主分析。局部补丁不能作为整段重生成结果。

## 第三方盲测

把 `blind_task_submission_template.jsonl` 交给未参与规则开发的任务作者。作者只写自然语言需求；另一位人员独立裁决接口、耦合、研究类型与是否应阻断。每条记录必须保留不同的 `author_id` 和 `adjudicator_id`。至少 24 条任务、8 个器件族。导入前运行：

```powershell
python scripts/validate_dac_problem1_blind_tasks.py path/to/submission.jsonl
```

项目内部作者、模板行、合成行和作者兼任裁决者的记录会被拒绝。

## COMSOL 端到端子集

`end_to_end_contracts.jsonl` 冻结六个完整需求，覆盖六类已验证物理模板。执行脚本先用 v1.1 编译需求，再关联同一合同的 COMSOL Java 重建、求解、MPH 保存和物理验收记录。该子集验证代表模板，不能外推为任意几何自动生成能力。
