from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .knowledge_bridge import enrich_plan_with_external_knowledge


DEFAULT_MEMORY_PATH = Path("generated/case_memory/case_memory.json")


DOMAIN_KEYWORDS = {
    "geometry": [
        "geometry",
        "geom",
        "part",
        "assembly",
        "selection",
        "extrude",
        "workplane",
        "busbar",
        "snowflake",
        "koch",
        "fractal",
        "几何",
        "装配",
        "科赫",
        "雪花",
        "分形",
    ],
    "heat_transfer": ["heat", "temperature", "thermal", "tmax", "tavg", "传热", "温度", "热"],
    # "solid" alone occurs in names such as "Heat Transfer in Solids" and is
    # not evidence that Solid Mechanics should be added to a model.
    "structural": ["stress", "strain", "displacement", "solid mechanics", "mechanics", "结构", "应力", "位移", "流固", "弹性模量", "泊松比"],
    "electromagnetics": ["electric", "current", "voltage", "magnetic", "acdc", "电流", "电压", "电磁"],
    "fluid": ["flow", "velocity", "pressure", "cfd", "fluid", "流体", "流固", "流动", "压力", "速度", "黏度"],
    "electrochemistry": ["electrochem", "corrosion", "battery", "electrode", "电化学", "腐蚀", "电池"],
    "acoustics": ["acoustic", "pressure acoustics", "eigenfrequency", "声学", "声压"],
    "optimization": ["optimization", "objective", "constraint", "优化", "目标函数"],
}


def remember_case(card: dict[str, Any], memory_path: str | Path = DEFAULT_MEMORY_PATH) -> dict[str, Any]:
    memory = load_memory(memory_path)
    entry = _memory_entry(card)
    cases = [
        item
        for item in memory["cases"]
        if item.get("case_dir") != entry["case_dir"] and item.get("title") != entry["title"]
    ]
    cases.append(entry)
    memory["cases"] = sorted(cases, key=lambda item: item["title"])
    memory["updated_at"] = datetime.now(timezone.utc).isoformat()
    memory["knowledge_system"] = build_knowledge_system(memory)
    _write_memory(memory_path, memory)
    return {
        "memory_path": str(memory_path),
        "entry": entry,
        "case_count": len(memory["cases"]),
        "knowledge_system": memory["knowledge_system"],
    }


def remember_learning_summary(
    summary: dict[str, Any],
    memory_path: str | Path = DEFAULT_MEMORY_PATH,
    title: str = "",
) -> dict[str, Any]:
    files = summary.get("files") if summary.get("kind") == "file_collection" else [summary]
    files = files if isinstance(files, list) else []
    content: dict[str, list[str]] = {
        key: []
        for key in (
            "parameters",
            "geometry",
            "physics",
            "materials",
            "mesh",
            "studies",
            "results",
            "boundary_conditions",
            "theory_keywords",
        )
    }
    source_files = []
    for item in files:
        if not isinstance(item, dict):
            continue
        source_files.append({"name": item.get("name", "file"), "kind": item.get("kind", "unknown")})
        details = item.get("details", {}) if isinstance(item.get("details"), dict) else {}
        extract = details.get("content_extract", {}) if isinstance(details.get("content_extract"), dict) else {}
        for key in content:
            content[key].extend(str(value) for value in extract.get(key, []) if str(value).strip())
    for key, values in content.items():
        content[key] = _dedupe_text(values, 80)
    kinds = summary.get("details", {}).get("kinds", {}) if isinstance(summary.get("details"), dict) else {}
    has_csv = bool(kinds.get("csv_table", 0))
    has_scripts = bool(kinds.get("matlab_livelink", 0) or kinds.get("matlab_text", 0) or kinds.get("comsol_java", 0))
    stage = "ready_for_surrogate_training" if has_csv else (
        "modeling_logic_learning_ready" if has_scripts else "knowledge_summary_only"
    )
    source_name = title.strip() or str(summary.get("name", "file_learning_summary"))
    parameters = [
        {"name": name, "value": "unknown", "description": "从文件摘要识别，数值和单位待确认"}
        for name in content["parameters"][:40]
    ]
    card = {
        "kind": "comsol_file_learning_card",
        "title": source_name,
        "case_dir": f"summary://{source_name}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_stage": stage,
        "file_summary": summary.get("details", {}),
        "parameters": parameters,
        "case_content": {**content, "source_extracts": []},
        "thoughts": ["该条目由文件学习总结自动持久化，可用于后续案例检索和建模判断。"],
        "implementation_path": ["复核物理场、几何、材料、边界、研究和输出证据。"],
        "gaps": _summary_memory_gaps(content, has_csv),
        "source_files": source_files,
        "post_learning_summary": {
            "kind": "post_file_learning_summary",
            "summary": f"已把 {len(files)} 个文件的摘要写入案例记忆。",
        },
    }
    return remember_case(card, memory_path)


def remember_physics_correction(
    requirement: str,
    corrected_physics: str,
    rationale: str = "",
    memory_path: str | Path = DEFAULT_MEMORY_PATH,
) -> dict[str, Any]:
    requirement = " ".join(str(requirement or "").split())
    corrected_physics = " ".join(str(corrected_physics or "").split())
    if not requirement:
        raise ValueError("requirement is empty")
    if not corrected_physics:
        raise ValueError("corrected_physics is empty")
    memory = load_memory(memory_path)
    corrections = [
        item
        for item in memory.get("physics_corrections", [])
        if not (
            str(item.get("requirement", "")).lower() == requirement.lower()
            and str(item.get("corrected_physics", "")).lower() == corrected_physics.lower()
        )
    ]
    entry = {
        "kind": "physics_selection_correction",
        "requirement": requirement,
        "corrected_physics": corrected_physics,
        "rationale": rationale,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "keywords": sorted(_tokens(requirement + " " + corrected_physics + " " + rationale))[:120],
        "search_text": " ".join([requirement, corrected_physics, rationale]),
    }
    corrections.append(entry)
    memory["physics_corrections"] = sorted(corrections, key=lambda item: item["updated_at"], reverse=True)
    memory["updated_at"] = datetime.now(timezone.utc).isoformat()
    memory["knowledge_system"] = build_knowledge_system(memory)
    _write_memory(memory_path, memory)
    return {
        "memory_path": str(memory_path),
        "correction": entry,
        "correction_count": len(memory["physics_corrections"]),
        "knowledge_system": memory["knowledge_system"],
    }


def load_memory(memory_path: str | Path = DEFAULT_MEMORY_PATH) -> dict[str, Any]:
    path = Path(memory_path)
    if path.exists():
        memory = json.loads(path.read_text(encoding="utf-8"))
        memory.setdefault("physics_corrections", [])
        memory.setdefault("template_validations", [])
        return memory
    return {
        "kind": "comsol_case_memory",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "cases": [],
        "physics_corrections": [],
        "template_validations": [],
        "knowledge_system": {},
    }


def refresh_knowledge_system(memory_path: str | Path = DEFAULT_MEMORY_PATH) -> dict[str, Any]:
    memory = load_memory(memory_path)
    for case in memory.get("cases", []):
        if isinstance(case, dict):
            if not case.get("case_extension"):
                case["case_extension"] = _memory_case_extension(case)
            case["quality"] = _entry_quality(case)
    memory["knowledge_system"] = build_knowledge_system(memory)
    memory["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_memory(memory_path, memory)
    return {
        "memory_path": str(memory_path),
        "case_count": len(memory.get("cases", [])),
        "knowledge_system": memory["knowledge_system"],
    }


def sync_template_validations(
    artifact_index_path: str | Path = "generated/execution_jobs/artifact_index.json",
    memory_path: str | Path = DEFAULT_MEMORY_PATH,
) -> dict[str, Any]:
    """Persist passed COMSOL template runs as evidence available to later reasoning."""
    index_path = Path(artifact_index_path)
    if not index_path.is_file():
        raise FileNotFoundError(f"artifact index not found: {index_path}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    latest: dict[str, dict[str, Any]] = {}
    for record in index.get("records", []):
        if not isinstance(record, dict) or record.get("status") != "completed":
            continue
        validation = record.get("validation", {})
        source = record.get("mph", {}).get("parameter_source", {})
        if not isinstance(validation, dict) or not validation.get("passed") or not isinstance(source, dict):
            continue
        template_path = str(source.get("path", ""))
        if not template_path:
            continue
        evidence = {
            "kind": "comsol_template_validation_evidence",
            "template_path": template_path,
            "model_name": str(source.get("model_name", "")),
            "physics": str(source.get("physics", validation.get("physics", ""))),
            "job_id": str(record.get("job_id", "")),
            "updated_at": str(record.get("updated_at", "")),
            "result_values": validation.get("values", {}),
            "checks": validation.get("checks", []),
            "mph_path": str(record.get("mph", {}).get("path", "")),
            "csv_path": str(record.get("results_csv", {}).get("path", "")),
            "reasoning_note": "该模板已由本地 COMSOL 实机求解并通过物理结果检查。",
        }
        previous = latest.get(template_path)
        if previous is None or evidence["updated_at"] >= previous["updated_at"]:
            latest[template_path] = evidence
    memory = load_memory(memory_path)
    memory["template_validations"] = sorted(latest.values(), key=lambda item: item["model_name"])
    memory["updated_at"] = datetime.now(timezone.utc).isoformat()
    memory["knowledge_system"] = build_knowledge_system(memory)
    _write_memory(memory_path, memory)
    return {"memory_path": str(memory_path), "artifact_index_path": str(index_path), "validation_count": len(latest), "template_validations": memory["template_validations"]}


def build_knowledge_system(memory: dict[str, Any]) -> dict[str, Any]:
    cases = [case for case in memory.get("cases", []) if isinstance(case, dict)]
    physics_corrections = [item for item in memory.get("physics_corrections", []) if isinstance(item, dict)]
    for case in cases:
        if not case.get("case_extension"):
            case["case_extension"] = _memory_case_extension(case)
    domains: dict[str, dict[str, Any]] = {}
    global_parameters: dict[str, dict[str, Any]] = {}
    global_physics: dict[str, int] = {}
    global_outputs: dict[str, int] = {}
    reusable_patterns: list[str] = []
    common_gaps: dict[str, int] = {}

    for case in cases:
        case_domains = case.get("domains", []) or _infer_domains(case.get("search_text", ""))
        for domain in case_domains:
            bucket = domains.setdefault(domain, _empty_domain(domain))
            bucket["case_count"] += 1
            _append_unique(bucket["cases"], case.get("title", "case"), 12)
            _extend_counted(bucket["physics"], case.get("case_content", {}).get("physics", []))
            _extend_counted(bucket["geometry"], case.get("case_content", {}).get("geometry", []))
            _extend_counted(bucket["studies"], case.get("case_content", {}).get("studies", []))
            _extend_counted(bucket["outputs"], _case_outputs(case))
            for param in case.get("parameters", []):
                name = str(param.get("name", "")).strip()
                if not name:
                    continue
                bucket["parameters"].setdefault(
                    name,
                    {
                        "name": name,
                        "description": str(param.get("description", "")),
                        "source_cases": [],
                    },
                )
                _append_unique(bucket["parameters"][name]["source_cases"], case.get("title", "case"), 6)
                global_parameters.setdefault(
                    name,
                    {
                        "name": name,
                        "description": str(param.get("description", "")),
                        "source_cases": [],
                    },
                )
                _append_unique(global_parameters[name]["source_cases"], case.get("title", "case"), 8)
        _extend_counted(global_physics, case.get("case_content", {}).get("physics", []))
        _extend_counted(global_outputs, _case_outputs(case))
        for item in _case_patterns(case):
            reusable_patterns.append(item)
        for gap in case.get("gaps", []):
            text = str(gap).strip()
            if text:
                common_gaps[text] = common_gaps.get(text, 0) + 1

    domain_cards = []
    for domain, bucket in sorted(domains.items(), key=lambda item: item[1]["case_count"], reverse=True):
        domain_cards.append(
            {
                "domain": domain,
                "case_count": bucket["case_count"],
                "cases": bucket["cases"],
                "core_physics": _top_counted(bucket["physics"], 10),
                "geometry_patterns": _top_counted(bucket["geometry"], 10),
                "study_patterns": _top_counted(bucket["studies"], 8),
                "typical_outputs": _top_counted(bucket["outputs"], 8),
                "parameters": list(bucket["parameters"].values())[:30],
                "modeling_logic": _domain_modeling_logic(domain, bucket),
            }
        )

    quality_audit = audit_memory(memory)
    return {
        "kind": "comsol_self_knowledge_system",
        "case_count": len(cases),
        "physics_correction_count": len(physics_corrections),
        "validated_template_count": len(memory.get("template_validations", [])),
        "template_validations": memory.get("template_validations", []),
        "physics_corrections": physics_corrections[:20],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "domain_count": len(domain_cards),
        "domains": domain_cards,
        "global_modeling_workflow": _global_modeling_workflow(cases),
        "global_parameters": list(global_parameters.values())[:80],
        "global_physics": _top_counted(global_physics, 20),
        "global_outputs": _top_counted(global_outputs, 20),
        "reusable_patterns": _dedupe_text(reusable_patterns, 40),
        "training_strategy": _knowledge_training_strategy(cases),
        "common_gaps": [{"gap": key, "count": value} for key, value in sorted(common_gaps.items(), key=lambda item: item[1], reverse=True)[:20]],
        "capability_summary": _capability_summary(cases, domain_cards),
        "quality_audit": quality_audit,
    }


def query_memory(query: str, memory_path: str | Path = DEFAULT_MEMORY_PATH, top_k: int = 5) -> dict[str, Any]:
    memory = load_memory(memory_path)
    query_tokens = _tokens(query)
    idf = _token_idf(memory.get("cases", []))
    scored = []
    for entry in memory.get("cases", []):
        score = _score(query_tokens, entry, idf)
        if score > 0:
            scored.append(
                {
                    "score": score,
                    "quality": entry.get("quality") or _entry_quality(entry),
                    "case": entry,
                }
            )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return {
        "kind": "case_memory_query",
        "query": query,
        "top_k": top_k,
        "matches": scored[:top_k],
        "case_count": len(memory.get("cases", [])),
    }


def query_physics_corrections(query: str, memory_path: str | Path = DEFAULT_MEMORY_PATH, top_k: int = 5) -> list[dict[str, Any]]:
    memory = load_memory(memory_path)
    query_tokens = _tokens(query)
    scored = []
    for entry in memory.get("physics_corrections", []):
        correction_tokens = set(entry.get("keywords", [])) | _tokens(entry.get("search_text", ""))
        overlap = query_tokens & correction_tokens
        if not overlap:
            continue
        score = len(overlap) / math.sqrt(max(len(correction_tokens), 1))
        scored.append({"score": score, "correction": entry})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def generate_model_plan(requirement: str, memory_path: str | Path = DEFAULT_MEMORY_PATH, top_k: int = 5) -> dict[str, Any]:
    retrieval = query_memory(requirement, memory_path=memory_path, top_k=top_k)
    memory = load_memory(memory_path)
    knowledge_system = memory.get("knowledge_system") or build_knowledge_system(memory)
    physics_corrections = query_physics_corrections(requirement, memory_path=memory_path, top_k=top_k)
    domains = _infer_domains(requirement)
    matched_cases = [item["case"] for item in retrieval["matches"]]
    parameters = _merge_parameters(matched_cases)
    outputs = _suggest_outputs(requirement, domains)
    plan = {
        "kind": "comsol_model_plan",
        "requirement": requirement,
        "inferred_domains": domains,
        "case_count": retrieval["case_count"],
        "matched_cases": [
            {
                "title": item["case"]["title"],
                "score": item["score"],
                "quality": item.get("quality", {}),
                "training_stage": item["case"].get("training_stage"),
                "domains": item["case"].get("domains", []),
            }
            for item in retrieval["matches"]
        ],
        "knowledge_system_context": _knowledge_system_context(knowledge_system, domains),
        "physics_corrections": physics_corrections,
        "recommended_modeling_steps": _modeling_steps(domains, bool(matched_cases)),
        "candidate_parameters": parameters[:30],
        "candidate_outputs": outputs,
        "analysis_path": _analysis_path(domains),
        "training_path": [
            "根据选定参数和范围创建或改写约束 JSON。",
            "结合已校验约束和相似案例证据生成 LiveLink MATLAB 建模脚本。",
            "运行 COMSOL 参数扫描并生成 CSV 数据。",
            "使用选定输入列和输出列训练本地代理模型。",
            "用未参与训练的 COMSOL 结果验证 RMSE、MAE、R2 和测试预测。",
        ],
        "limitations": _plan_limitations(retrieval["case_count"], matched_cases),
    }
    return enrich_plan_with_external_knowledge(plan, requirement)


def _memory_entry(card: dict[str, Any]) -> dict[str, Any]:
    case_content = card.get("case_content", {}) if isinstance(card.get("case_content"), dict) else {}
    physics_judgement = card.get("physics_judgement", {}) if isinstance(card.get("physics_judgement"), dict) else {}
    text_parts = [
        card.get("title", ""),
        card.get("case_dir", ""),
        card.get("training_stage", ""),
        card.get("prompt_summary", ""),
        card.get("post_learning_summary", {}).get("summary", ""),
        physics_judgement.get("simple_summary", ""),
        physics_judgement.get("primary_physics", ""),
        physics_judgement.get("study_type", ""),
        physics_judgement.get("judgement_rule", ""),
        physics_judgement.get("reusable_training_note", ""),
        " ".join(physics_judgement.get("evidence", [])),
        " ".join(
            f"{item.get('name', '')} {item.get('summary', '')}"
            for item in card.get("pdf_simple_summaries", [])
            if isinstance(item, dict)
        ),
        " ".join(card.get("thoughts", [])),
        " ".join(card.get("implementation_path", [])),
        " ".join(card.get("gaps", [])),
        " ".join(_flatten_principles(card.get("modeling_principles", {}))),
        " ".join(_flatten_extension(card.get("case_extension", {}))),
        " ".join(_flatten_geometry_parameter_learning(card.get("geometry_parameter_learning", {}))),
        " ".join(case_content.get("parameters", [])),
        " ".join(case_content.get("geometry", [])),
        " ".join(case_content.get("physics", [])),
        " ".join(case_content.get("materials", [])),
        " ".join(case_content.get("mesh", [])),
        " ".join(case_content.get("studies", [])),
        " ".join(case_content.get("results", [])),
        " ".join(case_content.get("boundary_conditions", [])),
        " ".join(case_content.get("theory_keywords", [])),
    ]
    for source in case_content.get("source_extracts", []):
        if isinstance(source, dict):
            text_parts.extend(
                [
                    source.get("name", ""),
                    " ".join(source.get("content_summary", [])),
                    " ".join(source.get("physics", [])),
                    " ".join(source.get("geometry", [])),
                ]
            )
    for param in card.get("parameters", []):
        text_parts.extend([param.get("name", ""), param.get("description", ""), param.get("value", "")])
    for source in card.get("source_files", []):
        text_parts.extend([source.get("name", ""), source.get("kind", "")])
    text = " ".join(text_parts)
    entry = {
        "title": card.get("title", "case"),
        "case_dir": card.get("case_dir", ""),
        "training_stage": card.get("training_stage", "unknown"),
        "prompt_summary": card.get("prompt_summary", ""),
        "updated_at": card.get("created_at", datetime.now(timezone.utc).isoformat()),
        "file_summary": card.get("file_summary", {}),
        "parameters": card.get("parameters", [])[:80],
        "case_content": _memory_case_content(case_content),
        "modeling_principles": card.get("modeling_principles", {}),
        "geometry_parameter_learning": card.get("geometry_parameter_learning", {}),
        "physics_judgement": physics_judgement,
        "case_extension": card.get("case_extension", {}),
        "post_learning_summary": card.get("post_learning_summary", {}),
        "knowledge_alignment": card.get("knowledge_alignment", {}),
        "thoughts": card.get("thoughts", []),
        "implementation_path": card.get("implementation_path", []),
        "gaps": card.get("gaps", []),
        "source_files": card.get("source_files", []),
        "domains": _infer_domains(text),
        "keywords": sorted(_tokens(text))[:300],
        "search_text": text,
    }
    entry["quality"] = _entry_quality(entry)
    return entry


def _flatten_principles(principles: dict[str, Any]) -> list[str]:
    if not isinstance(principles, dict):
        return []
    values: list[str] = []
    for key in ("core_sequence", "physics_reasoning", "automation_evidence", "verification_logic"):
        items = principles.get(key, [])
        if isinstance(items, list):
            values.extend(str(item) for item in items)
    values.append(str(principles.get("readiness", "")))
    return values


def _flatten_extension(extension: dict[str, Any]) -> list[str]:
    if not isinstance(extension, dict):
        return []
    values: list[str] = []
    for key in (
        "transferable_knowledge",
        "extension_questions",
        "new_model_directions",
        "parameter_sweep_ideas",
        "code_generation_ideas",
        "risk_checks",
    ):
        items = extension.get(key, [])
        if isinstance(items, list):
            values.extend(str(item) for item in items)
    values.append(str(extension.get("readiness", "")))
    return values


def _flatten_geometry_parameter_learning(learning: dict[str, Any]) -> list[str]:
    if not isinstance(learning, dict):
        return []
    values: list[str] = [str(learning.get("summary", ""))]
    for key in ("pdf_keywords", "geometry_parameter_checks", "learned_capability"):
        items = learning.get(key, [])
        if isinstance(items, list):
            values.extend(str(item) for item in items)
    for row in learning.get("matlab_mapping", []):
        if isinstance(row, dict):
            values.extend(
                [
                    str(row.get("keyword", "")),
                    str(row.get("modeling_content", "")),
                    str(row.get("matlab_action", "")),
                ]
            )
    return values


def _empty_domain(domain: str) -> dict[str, Any]:
    return {
        "domain": domain,
        "case_count": 0,
        "cases": [],
        "parameters": {},
        "physics": {},
        "geometry": {},
        "studies": {},
        "outputs": {},
    }


def _append_unique(items: list[Any], value: Any, limit: int) -> None:
    if value and value not in items and len(items) < limit:
        items.append(value)


def _extend_counted(counter: dict[str, int], values: list[Any]) -> None:
    for value in values:
        text = str(value).strip()
        if text:
            counter[text] = counter.get(text, 0) + 1


def _top_counted(counter: dict[str, int], limit: int) -> list[dict[str, Any]]:
    return [
        {"name": name, "count": count}
        for name, count in sorted(counter.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def _case_outputs(case: dict[str, Any]) -> list[str]:
    outputs = []
    deep = case.get("post_learning_summary", {})
    content = case.get("case_content", {})
    outputs.extend(content.get("results", []))
    outputs.extend(content.get("theory_keywords", []))
    if isinstance(deep, dict):
        outputs.extend(deep.get("reusable_assets", []))
    return [str(item) for item in outputs if str(item).strip()]


def _case_patterns(case: dict[str, Any]) -> list[str]:
    patterns: list[str] = []
    principles = case.get("modeling_principles", {})
    if isinstance(principles, dict):
        for key in ("core_sequence", "physics_reasoning", "automation_evidence", "verification_logic"):
            patterns.extend(str(item) for item in principles.get(key, []) if str(item).strip())
    summary = case.get("post_learning_summary", {})
    if isinstance(summary, dict):
        patterns.extend(str(item) for item in summary.get("learned_modeling_logic", []) if str(item).strip())
    judgement = case.get("physics_judgement", {})
    if isinstance(judgement, dict):
        patterns.extend(
            str(judgement.get(key, ""))
            for key in ("simple_summary", "primary_physics", "study_type", "judgement_rule", "reusable_training_note")
            if str(judgement.get(key, "")).strip()
        )
    extension = case.get("case_extension", {})
    if isinstance(extension, dict):
        for key in ("transferable_knowledge", "new_model_directions", "parameter_sweep_ideas", "code_generation_ideas"):
            patterns.extend(str(item) for item in extension.get(key, []) if str(item).strip())
    patterns.extend(str(item) for item in case.get("implementation_path", []) if str(item).strip())
    return patterns


def _memory_case_extension(case: dict[str, Any]) -> dict[str, Any]:
    content = case.get("case_content", {}) if isinstance(case.get("case_content"), dict) else {}
    parameters = case.get("parameters", []) if isinstance(case.get("parameters"), list) else []
    physics = [str(item) for item in content.get("physics", [])]
    geometry = [str(item) for item in content.get("geometry", [])]
    studies = [str(item) for item in content.get("studies", [])]
    outputs = [str(item) for item in content.get("results", [])]
    training_stage = str(case.get("training_stage", "unknown"))
    transferable = [
        "Reuse the learned model-building sequence from this memory entry.",
        "Use this case as evidence when future requirements share physics, geometry, parameters, or outputs.",
    ]
    if physics:
        transferable.append("Transfer physics evidence: " + ", ".join(physics[:6]) + ".")
    if geometry:
        transferable.append("Transfer geometry evidence: " + ", ".join(geometry[:6]) + ".")
    directions = [
        "Create a related baseline model and change one factor at a time: geometry, material, boundary condition, study, or output.",
        "Compare generated models against this case before accepting automatic COMSOL code.",
    ]
    sweep_ideas = []
    for param in parameters[:8]:
        name = str(param.get("name", "")).strip() if isinstance(param, dict) else ""
        if name:
            sweep_ideas.append(f"Sweep `{name}` and export validation outputs to CSV.")
    if outputs:
        sweep_ideas.append("Use learned result nodes as CSV targets: " + ", ".join(outputs[:6]) + ".")
    if "ready_for_surrogate_training" not in training_stage:
        sweep_ideas.append("Generate parameter-sweep CSV before numerical surrogate training.")
    code_ideas = [
        "Generate MATLAB/Java code from matched case parameters, physics, and study patterns.",
        "Annotate generated boundary selections because entity IDs can change after geometry edits.",
    ]
    if studies:
        code_ideas.append("Start generated solver setup from learned studies: " + ", ".join(studies[:5]) + ".")
    return {
        "kind": "case_thinking_and_extension",
        "readiness": "memory_entry_extension",
        "readiness_score": 40 + min(60, 10 * int(bool(physics)) + 10 * int(bool(geometry)) + 10 * int(bool(parameters))),
        "transferable_knowledge": _dedupe_text(transferable, 12),
        "extension_questions": [
            "Which parts of this case are reusable without changing assumptions?",
            "Which parameters should be swept before using this case for training?",
            "Which boundary selections require manual verification in a generated model?",
        ],
        "new_model_directions": _dedupe_text(directions, 12),
        "parameter_sweep_ideas": _dedupe_text(sweep_ideas, 12),
        "code_generation_ideas": _dedupe_text(code_ideas, 12),
        "risk_checks": [
            "Verify units, material properties, and boundary selections before solving.",
            "Run a baseline solve before parameter sweeps or surrogate training.",
        ],
    }


def _dedupe_text(values: list[str], limit: int) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = re.sub(r"\s+", " ", str(value).strip())
        if text and text not in seen:
            seen.add(text)
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _domain_modeling_logic(domain: str, bucket: dict[str, Any]) -> list[str]:
    logic = [
        f"Use {domain} cases as the first retrieval group when the requirement shares physics, geometry, or output targets.",
        "Start from parameters and geometry, then add selections, materials, physics, mesh, study, and result export.",
    ]
    physics = _top_counted(bucket["physics"], 3)
    if physics:
        logic.append("Prioritize learned physics interfaces: " + ", ".join(item["name"] for item in physics) + ".")
    studies = _top_counted(bucket["studies"], 3)
    if studies:
        logic.append("Reuse similar study patterns: " + ", ".join(item["name"] for item in studies) + ".")
    return logic


def _global_modeling_workflow(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stages = [
        ("requirement", "Clarify target physics, dimensions, assumptions, inputs, outputs, and validation criteria."),
        ("evidence", "Retrieve similar cases and official/document evidence before creating a new model."),
        ("parameters", "Define reusable parameters, units, sweep ranges, and constraints."),
        ("geometry", "Build or import geometry, then create named selections for later boundary assignment."),
        ("physics", "Assign materials, physics interfaces, loads, boundary conditions, and initial values."),
        ("mesh_study", "Create mesh, study sequence, solver settings, and a baseline solve."),
        ("validation", "Export derived values/plots and compare against theory, case expectations, or experiments."),
        ("surrogate", "Only after COMSOL sweep CSV exists, train and validate a local surrogate model."),
    ]
    return [
        {
            "stage": key,
            "description": description,
            "case_evidence_count": sum(1 for case in cases if key in str(case.get("search_text", "")).lower()),
        }
        for key, description in stages
    ]


def _knowledge_training_strategy(cases: list[dict[str, Any]]) -> list[str]:
    ready_csv = sum(1 for case in cases if case.get("training_stage") == "ready_for_surrogate_training")
    logic_ready = sum(1 for case in cases if case.get("training_stage") == "modeling_logic_learning_ready")
    return [
        f"Current memory contains {len(cases)} cases: {logic_ready} support modeling-logic learning and {ready_csv} contain direct CSV surrogate-training evidence.",
        "Treat PDF/MATLAB/Java/MPH evidence as modeling knowledge; treat CSV sweep tables as numerical training data.",
        "When no CSV is available, generate COMSOL sweep scripts first, export inputs/outputs, then train baseline, ridge, random forest, and MLP candidates.",
        "After each generated model is corrected in COMSOL, place the corrected MATLAB/Java/exported summary back into the case library and refresh this knowledge system.",
    ]


def _capability_summary(cases: list[dict[str, Any]], domains: list[dict[str, Any]]) -> str:
    if not cases:
        return "No cases have been learned yet; the system can only use general COMSOL modeling defaults."
    domain_names = ", ".join(domain["domain"] for domain in domains[:8]) or "general_multiphysics"
    return (
        f"The local COMSOL knowledge system has learned {len(cases)} cases across {len(domains)} domains "
        f"({domain_names}). It can retrieve similar cases, propose modeling logic, select candidate parameters/outputs, "
        "and explain what evidence is missing before automatic COMSOL code generation or surrogate training."
    )


def _knowledge_system_context(knowledge_system: dict[str, Any], domains: list[str]) -> dict[str, Any]:
    if not isinstance(knowledge_system, dict) or not knowledge_system.get("kind"):
        return {
            "kind": "knowledge_system_context",
            "available": False,
            "message": "No cross-case knowledge system is available yet.",
        }
    wanted = set(domains)
    matched = [
        domain
        for domain in knowledge_system.get("domains", [])
        if domain.get("domain") in wanted or not wanted
    ][:5]
    return {
        "kind": "knowledge_system_context",
        "available": True,
        "case_count": knowledge_system.get("case_count", 0),
        "domain_count": knowledge_system.get("domain_count", 0),
        "capability_summary": knowledge_system.get("capability_summary", ""),
        "matched_domains": matched,
        "global_modeling_workflow": knowledge_system.get("global_modeling_workflow", []),
        "training_strategy": knowledge_system.get("training_strategy", []),
        "common_gaps": knowledge_system.get("common_gaps", [])[:8],
        "quality_audit": knowledge_system.get("quality_audit", {}),
    }


def _memory_case_content(case_content: dict[str, Any]) -> dict[str, Any]:
    if not case_content:
        return {}
    return {
        "totals": case_content.get("totals", {}),
        "parameters": case_content.get("parameters", [])[:40],
        "geometry": case_content.get("geometry", [])[:40],
        "physics": case_content.get("physics", [])[:40],
        "materials": case_content.get("materials", [])[:30],
        "mesh": case_content.get("mesh", [])[:30],
        "studies": case_content.get("studies", [])[:30],
        "results": case_content.get("results", [])[:30],
        "boundary_conditions": case_content.get("boundary_conditions", [])[:30],
        "theory_keywords": case_content.get("theory_keywords", [])[:30],
    }


def audit_memory(memory: dict[str, Any]) -> dict[str, Any]:
    cases = [item for item in memory.get("cases", []) if isinstance(item, dict)]
    qualities = [item.get("quality") or _entry_quality(item) for item in cases]
    issue_counts: dict[str, int] = {}
    for quality in qualities:
        for issue in quality.get("issues", []):
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    average = sum(float(item.get("score", 0)) for item in qualities) / len(qualities) if qualities else 0.0
    return {
        "kind": "case_memory_quality_audit",
        "case_count": len(cases),
        "average_quality_score": round(average, 2),
        "high_quality_cases": sum(float(item.get("score", 0)) >= 70 for item in qualities),
        "usable_modeling_cases": sum(bool(item.get("usable_for_modeling")) for item in qualities),
        "surrogate_ready_cases": sum(bool(item.get("surrogate_ready")) for item in qualities),
        "issue_counts": [
            {"issue": issue, "count": count}
            for issue, count in sorted(issue_counts.items(), key=lambda row: row[1], reverse=True)
        ],
    }


def _entry_quality(entry: dict[str, Any]) -> dict[str, Any]:
    content = entry.get("case_content", {}) if isinstance(entry.get("case_content"), dict) else {}
    source_files = entry.get("source_files", []) if isinstance(entry.get("source_files"), list) else []
    file_summary = entry.get("file_summary", {}) if isinstance(entry.get("file_summary"), dict) else {}
    has_physics = bool(content.get("physics"))
    has_geometry = bool(content.get("geometry"))
    has_materials = bool(content.get("materials"))
    has_study = bool(content.get("studies"))
    has_boundary = bool(content.get("boundary_conditions"))
    has_results = bool(content.get("results"))
    has_parameters = bool(entry.get("parameters") or content.get("parameters"))
    has_sources = bool(source_files) or int(file_summary.get("count", 0) or 0) > 0
    has_csv = (
        entry.get("training_stage") == "ready_for_surrogate_training"
        or bool(file_summary.get("csv_files"))
        or any(item.get("kind") == "csv_table" for item in source_files if isinstance(item, dict))
    )
    checks = {
        "physics": has_physics,
        "geometry": has_geometry,
        "materials": has_materials,
        "study": has_study,
        "boundary_conditions": has_boundary,
        "results": has_results,
        "parameters": has_parameters,
        "source_files": has_sources,
        "training_csv": has_csv,
    }
    weights = {
        "physics": 20,
        "geometry": 15,
        "materials": 10,
        "study": 10,
        "boundary_conditions": 15,
        "results": 10,
        "parameters": 10,
        "source_files": 5,
        "training_csv": 5,
    }
    score = sum(weights[key] for key, passed in checks.items() if passed)
    labels = {
        "physics": "缺少物理场证据",
        "geometry": "缺少几何证据",
        "materials": "缺少材料证据",
        "study": "缺少研究/求解证据",
        "boundary_conditions": "缺少边界条件证据",
        "results": "缺少结果量证据",
        "parameters": "缺少参数证据",
        "source_files": "缺少来源文件记录",
        "training_csv": "缺少参数扫描 CSV",
    }
    return {
        "score": score,
        "checks": checks,
        "issues": [labels[key] for key, passed in checks.items() if not passed],
        "usable_for_modeling": has_physics and has_geometry and has_sources,
        "surrogate_ready": has_csv and has_parameters and has_results,
    }


def _summary_memory_gaps(content: dict[str, list[str]], has_csv: bool) -> list[str]:
    gaps = []
    if not content.get("physics"):
        gaps.append("缺少可验证的物理场证据。")
    if not content.get("geometry"):
        gaps.append("缺少可验证的几何证据。")
    if not content.get("boundary_conditions"):
        gaps.append("缺少边界条件和选择集证据。")
    if not has_csv:
        gaps.append("缺少 COMSOL 参数扫描 CSV，暂不能训练数值代理模型。")
    return gaps


def _token_idf(entries: list[dict[str, Any]]) -> dict[str, float]:
    total = max(len(entries), 1)
    counts: dict[str, int] = {}
    for entry in entries:
        tokens = set(entry.get("keywords", [])) | _tokens(entry.get("search_text", ""))
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
    return {
        token: math.log((total + 1) / (count + 1)) + 1.0
        for token, count in counts.items()
    }


def _write_memory(memory_path: str | Path, memory: dict[str, Any]) -> None:
    path = Path(memory_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")


def _tokens(text: str) -> set[str]:
    tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", text) if len(token) > 1}
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(run) > 1:
            tokens.add(run)
        tokens.update(run[index : index + 2] for index in range(max(0, len(run) - 1)))
        tokens.update(run[index : index + 3] for index in range(max(0, len(run) - 2)))
    return tokens


def _score(query_tokens: set[str], entry: dict[str, Any], idf: dict[str, float] | None = None) -> float:
    if not query_tokens:
        return 0.0
    case_tokens = set(entry.get("keywords", [])) | _tokens(entry.get("search_text", ""))
    overlap = query_tokens & case_tokens
    title = str(entry.get("title", ""))
    title_tokens = _tokens(title)
    title_overlap = query_tokens & title_tokens
    query_text = "".join(sorted(query_tokens, key=len, reverse=True))
    title_bonus = 0.0
    if title and title in query_text:
        title_bonus += 5.0
    title_bonus += len(title_overlap) * 2.5
    domain_bonus = len(set(entry.get("domains", [])) & set(_infer_domains(" ".join(query_tokens)))) * 2.0
    parameter_bonus = sum(1 for param in entry.get("parameters", []) if param.get("name", "").lower() in query_tokens) * 1.5
    weighted_overlap = sum((idf or {}).get(token, 1.0) for token in overlap)
    quality = entry.get("quality") or _entry_quality(entry)
    quality_factor = 0.35 + 0.65 * (float(quality.get("score", 0)) / 100.0)
    lexical = weighted_overlap / math.sqrt(max(len(case_tokens), 1))
    return (lexical + title_bonus + domain_bonus + parameter_bonus) * quality_factor


def _infer_domains(text: str) -> list[str]:
    lowered = text.lower()
    domains = []
    for domain, words in DOMAIN_KEYWORDS.items():
        if any(word.lower() in lowered for word in words):
            domains.append(domain)
    return domains or ["general_multiphysics"]


def _merge_parameters(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for case in cases:
        for param in case.get("parameters", []):
            name = param.get("name")
            if name and name not in merged:
                merged[name] = {
                    "name": name,
                    "value": param.get("value", ""),
                    "description": param.get("description", ""),
                    "source_case": case.get("title", ""),
                }
    return list(merged.values())


def _suggest_outputs(requirement: str, domains: list[str]) -> list[str]:
    lowered = requirement.lower()
    outputs = []
    if "geometry" in domains:
        outputs.extend(["volume_total", "surface_area_total", "entity_count", "geometry_build_success"])
    if "heat_transfer" in domains or "temperature" in lowered:
        outputs.extend(["Tmax", "Tavg", "heat_flux_integral"])
    if "structural" in domains:
        outputs.extend(["max_displacement", "max_von_mises_stress", "reaction_force"])
    if "electromagnetics" in domains:
        outputs.extend(["max_current_density", "electric_resistance", "terminal_current"])
    if "fluid" in domains:
        outputs.extend(["pressure_drop", "max_velocity", "flow_rate"])
    return outputs or ["primary_quantity_of_interest", "validation_error"]


def _modeling_steps(domains: list[str], has_cases: bool) -> list[str]:
    steps = [
        "Clarify model objective, dimensionality, input parameters, outputs, and validation targets.",
        "Choose geometry strategy: reuse similar case script, import CAD, or generate parametric geometry.",
        "Define materials, units, selections, and reusable parameter groups.",
        "Add physics interfaces and boundary/initial conditions.",
        "Create mesh and study sequence, then solve a baseline model.",
        "Export derived values and plots for validation.",
    ]
    if has_cases:
        steps.insert(1, "查看检索到的相似案例，并复用其参数命名、几何序列和 LiveLink API 调用模式。")
    if "optimization" in domains:
        steps.append("Add objective, constraints, and optimization study after the baseline model is verified.")
    return steps


def _analysis_path(domains: list[str]) -> list[str]:
    path = ["Baseline solve", "Mesh refinement check", "Parameter sweep", "Result validation"]
    if "heat_transfer" in domains:
        path.append("Temperature and heat-flux sensitivity analysis")
    if "structural" in domains:
        path.append("Stress/displacement safety check")
    if "electromagnetics" in domains:
        path.append("Current/field distribution and loss analysis")
    if "fluid" in domains:
        path.append("Pressure drop and flow uniformity analysis")
    path.append("Surrogate training dataset export")
    return path


def _plan_limitations(case_count: int, matched_cases: list[dict[str, Any]]) -> list[str]:
    limitations = []
    if case_count < 5:
        limitations.append("Case memory is still small; generated plans should be reviewed carefully.")
    if not matched_cases:
        limitations.append("No similar case was found; plan relies on general COMSOL modeling logic.")
    if matched_cases and all(case.get("training_stage") != "ready_for_surrogate_training" for case in matched_cases):
        limitations.append("Retrieved cases mainly support modeling logic; numerical training still needs CSV sweep data.")
    return limitations or ["No major limitation detected from current memory."]
