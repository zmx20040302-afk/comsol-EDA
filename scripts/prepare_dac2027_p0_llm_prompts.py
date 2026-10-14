from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p0_evaluation import validate_blind_tasks


OUTPUT_INSTRUCTION = """只输出一个 JSON 对象，不要输出 Markdown。字段必须为：
{"predicted_interfaces": ["接口ID"], "predicted_couplings": ["耦合ID"], "predicted_study": "研究类型", "predicted_blocked": true或false}
若关键信息缺失、需求冲突或超出支持范围，predicted_blocked 必须为 true。不得补造用户未提供的关键边界、材料、单位或工况。"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    tasks_path = ROOT / "benchmarks" / "dac2027_p0" / "blind_tasks.measured.jsonl"
    protocol = json.loads((ROOT / "configs" / "dac2027_p0_protocol.json").read_text(encoding="utf-8"))
    tasks = [json.loads(line) for line in tasks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    validate_blind_tasks(tasks, protocol)
    corpus_paths = [ROOT / item for item in protocol["run_controls"]["retrieval_corpus"]]
    corpus = "\n\n".join(f"### {path.relative_to(ROOT)}\n{path.read_text(encoding='utf-8')}" for path in corpus_paths)
    output = ROOT / "generated" / "dac2027" / "p0" / "llm_prompts"
    manifest = {"corpus_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in corpus_paths}, "prompts": []}
    for method in ("direct_llm", "retrieval_llm"):
        method_dir = output / method
        method_dir.mkdir(parents=True, exist_ok=True)
        for task in tasks:
            context = "" if method == "direct_llm" else f"\n\n冻结检索资料：\n{corpus}"
            prompt = f"你负责把工程需求编译成 COMSOL 建模意图。\n\n工程需求：\n{task['requirement']}\n\n{OUTPUT_INSTRUCTION}{context}\n"
            path = method_dir / f"{task['id']}.txt"
            path.write_text(prompt, encoding="utf-8")
            manifest["prompts"].append({"task_id": task["id"], "method": method, "path": str(path.relative_to(ROOT)), "sha256": sha256(path)})
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"prompt_count": len(manifest["prompts"]), "output": str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
