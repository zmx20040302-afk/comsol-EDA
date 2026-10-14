from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ID = "dac2027-p0-blind-20261013"
CAMPAIGN_DIR = ROOT / "benchmarks" / "dac2027_p0" / CAMPAIGN_ID
GENERATED_DIR = ROOT / "generated" / "dac2027" / "p0"
STATUSES = ("complete", "missing", "conflict")


AUTHOR_INSTRUCTION = """# DAC 2027 P0 第三方需求任务作者包 {family_slot}

你需要为同一个真实电子器件或结构族编写三条 COMSOL 建模需求。请使用你熟悉但未提供给本项目的方法开发者的案例。

1. `complete`：执行建模所需的关键目标、工况和边界信息齐全。
2. `missing`：有意删除至少一项会影响可解性或物理正确性的关键信息。
3. `conflict`：包含一项明确且会阻止安全执行的物理冲突。

要求：

- 作者必须在本项目团队之外，并填写可审计的匿名 ID 与单位。
- 不要查看或运行待比较的四种方法。
- 三条任务必须属于同一个器件或结构族。
- 不要在需求中标注它属于 complete、missing 或 conflict。
- 不要填写标准答案；标准答案由另一位裁决者独立完成。
- 提交后不得再根据方法输出修改需求。

本包槽位：

- blind-{family_slot}-complete
- blind-{family_slot}-missing
- blind-{family_slot}-conflict

在本机打开 `http://127.0.0.1:8891/`，选择对应槽位提交。
"""


ADJUDICATOR_INSTRUCTION = """# DAC 2027 P0 独立裁决包 {family_slot}

作者提交三条需求后，由另一位人员独立标注：

- COMSOL 物理接口 ID；
- 多物理场耦合 ID；
- 研究类型；
- 是否必须阻断自动执行。

裁决者不得与作者使用相同 ID，不得查看任何方法输出，也不得为提高系统分数而修改标签。出现争议时只记录争议，不得在开封方法结果后回改标准答案。

在本机打开 `http://127.0.0.1:8891/`，作者提交完成后选择对应槽位裁决。
"""


def main() -> int:
    (CAMPAIGN_DIR / "author_packets").mkdir(parents=True, exist_ok=True)
    (CAMPAIGN_DIR / "adjudicator_packets").mkdir(parents=True, exist_ok=True)
    (CAMPAIGN_DIR / "returns" / "authors").mkdir(parents=True, exist_ok=True)
    (CAMPAIGN_DIR / "returns" / "adjudicators").mkdir(parents=True, exist_ok=True)
    slots = []
    for family_index in range(1, 9):
        family_slot = f"f{family_index:02d}"
        author_packet = CAMPAIGN_DIR / "author_packets" / f"{family_slot}_author.md"
        adjudicator_packet = CAMPAIGN_DIR / "adjudicator_packets" / f"{family_slot}_adjudicator.md"
        if not author_packet.exists():
            author_packet.write_text(AUTHOR_INSTRUCTION.format(family_slot=family_slot), encoding="utf-8")
        if not adjudicator_packet.exists():
            adjudicator_packet.write_text(ADJUDICATOR_INSTRUCTION.format(family_slot=family_slot), encoding="utf-8")
        for status in STATUSES:
            slots.append({
                "task_id": f"blind-{family_slot}-{status}",
                "family_slot": family_slot,
                "status": status,
                "author_state": "awaiting_external_author",
                "adjudication_state": "locked_until_author_submission",
            })
    manifest_path = CAMPAIGN_DIR / "campaign_manifest.json"
    if not manifest_path.exists():
        manifest = {
            "schema": "dac2027-p0-blind-campaign",
            "schemaVersion": "1.0.0",
            "campaign_id": CAMPAIGN_ID,
            "started_at": datetime.now().astimezone().isoformat(),
            "state": "collecting_external_authors",
            "task_count": 24,
            "family_count": 8,
            "slots": slots,
            "method_results_unsealed": False,
            "evidence_policy": "Only externally authored and separately adjudicated measured rows can enter blind_tasks.measured.jsonl."
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    status = {
        "schema": "dac2027-p0-acquisition-status",
        "campaign_id": CAMPAIGN_ID,
        "state": "collecting_external_authors",
        "slots_started": 24,
        "author_submissions": len(list((CAMPAIGN_DIR / "returns" / "authors").glob("*.json"))),
        "adjudicator_submissions": len(list((CAMPAIGN_DIR / "returns" / "adjudicators").glob("*.json"))),
        "measured_blind_tasks": 0,
        "intake_url": "http://127.0.0.1:8891/",
        "publication_evidence": False,
    }
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    (GENERATED_DIR / "acquisition_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"campaign": str(CAMPAIGN_DIR), **status}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
