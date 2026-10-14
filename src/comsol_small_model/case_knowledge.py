from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .file_reader import build_learning_summary, summarize_files
from .knowledge_bridge import compare_with_external_knowledge


SUPPORTED_CASE_EXTENSIONS = {".pdf", ".pptx", ".m", ".java", ".mph", ".txt", ".json", ".csv", ".md"}
RESERVED_PARAMETER_NAMES = {
    "class",
    "def",
    "else",
    "for",
    "from",
    "function",
    "if",
    "import",
    "package",
    "public",
    "return",
    "static",
    "while",
}


def summarize_case_directory(
    case_dir: str | Path,
    title: str | None = None,
    output_dir: str | Path = "generated/case_knowledge",
    prompt_summary: str = "",
) -> dict[str, Any]:
    case_path = Path(case_dir)
    if not case_path.exists() or not case_path.is_dir():
        raise FileNotFoundError(f"Case directory not found: {case_path}")

    files = _case_files(case_path)
    if not files:
        raise ValueError(f"No supported COMSOL case files found in {case_path}")

    collection = summarize_files(files)
    learning = build_learning_summary(collection)
    card = build_case_card(case_path, collection, learning, title=title, prompt_summary=prompt_summary)
    outputs = write_case_card(card, output_dir)
    return {"card": card, "outputs": outputs}


def build_case_card(
    case_path: Path,
    collection: dict[str, Any],
    learning: dict[str, Any],
    title: str | None = None,
    prompt_summary: str = "",
) -> dict[str, Any]:
    details = collection.get("details", {})
    parameters = _extract_parameters(collection)
    case_content = _extract_case_content(collection)
    has_training_csv = details.get("csv_files", 0) > 0
    has_model_scripts = details.get("matlab_files", 0) > 0 or details.get("java_files", 0) > 0
    has_pdf = details.get("pdf_files", 0) > 0
    has_pptx = details.get("pptx_files", 0) > 0
    has_mph = details.get("mph_files", 0) > 0
    prompt_summary = " ".join(str(prompt_summary or "").split())

    training_stage = "ready_for_surrogate_training" if has_training_csv else "needs_comsol_sweep_csv"
    if has_model_scripts and not has_training_csv:
        training_stage = "modeling_logic_learning_ready"

    thoughts = []
    if has_pdf:
        thoughts.append("PDF 文档用于理解案例目的、建模顺序、理论假设和验证目标。")
    if has_pptx:
        thoughts.append("PPT 演示文稿用于补充案例目标、关键假设、结果图说明和结论。")
    if prompt_summary:
        thoughts.append("用户提示词已作为临时 PDF 摘要使用，用于补充案例目的、理论假设、几何参数和建模目标。")
    if has_model_scripts:
        thoughts.append("MATLAB 和 Java 文件是 COMSOL 模型树的可执行证据，应驱动自动建模脚本生成。")
    if has_mph:
        thoughts.append("MPH 文件需要通过 COMSOL with MATLAB 导出摘要后，才能可靠使用内部模型设置。")
    if parameters:
        thoughts.append("参数文本和脚本证据可转换为约束和参数扫描变量。")
    if case_content["totals"]["model_tree_items"] > 0:
        thoughts.append("已从案例内容中抽取到模型树证据，可用于学习几何、物理场、材料、网格、研究和结果设置。")
    if not has_training_csv:
        thoughts.append("未发现训练 CSV，因此数值代理模型训练前需要先导出 COMSOL 参数扫描数据。")
    else:
        thoughts.append("已发现 CSV 数据，可先检查输入/输出列再训练。")

    card = {
        "kind": "comsol_case_card",
        "title": title or case_path.name,
        "case_dir": str(case_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_stage": training_stage,
        "file_summary": {
            "count": details.get("count", 0),
            "kinds": details.get("kinds", {}),
            "matlab_files": details.get("matlab_files", 0),
            "java_files": details.get("java_files", 0),
            "pdf_files": details.get("pdf_files", 0),
            "pptx_files": details.get("pptx_files", 0),
            "mph_files": details.get("mph_files", 0),
            "csv_files": details.get("csv_files", 0),
            "json_files": details.get("json_files", 0),
        },
        "parameters": parameters,
        "case_content": case_content,
        "learning_summary": learning,
        "pdf_simple_summaries": _pdf_summaries_with_prompt(learning.get("pdf_simple_summaries", []), prompt_summary),
        "prompt_summary": prompt_summary,
        "thoughts": thoughts,
        "implementation_path": _implementation_path(has_training_csv),
        "gaps": _gaps(has_training_csv, has_mph, parameters),
        "source_files": [
            {
                "name": file.get("name"),
                "kind": file.get("kind"),
                "size_bytes": file.get("size_bytes"),
                "details": file.get("details", {}),
            }
            for file in collection.get("files", [])
        ],
    }
    card["modeling_principles"] = _modeling_principles(card)
    card["physics_judgement"] = _physics_judgement(card)
    card["geometry_parameter_learning"] = _geometry_parameter_learning(card)
    card["deep_learning_plan"] = _deep_learning_plan(card)
    card["case_extension"] = _case_extension(card)
    card["learning_progress"] = _learning_progress(card)
    card["post_learning_summary"] = _post_learning_summary(card)
    card["knowledge_alignment"] = compare_with_external_knowledge(card)
    return card


def write_case_card(card: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    slug = _slugify(str(card["title"]))
    json_path = destination / f"{slug}.case.json"
    md_path = destination / f"{slug}.case.md"
    index_path = destination / "case_knowledge_index.json"

    json_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(case_card_markdown(card), encoding="utf-8")
    _upsert_index(index_path, card, json_path, md_path)
    return {"json": str(json_path), "markdown": str(md_path), "index": str(index_path)}


def _pdf_summaries_with_prompt(pdf_summaries: list[dict[str, str]], prompt_summary: str) -> list[dict[str, str]]:
    summaries = list(pdf_summaries or [])
    if prompt_summary:
        summaries.append(
            {
                "name": "user_prompt_as_pdf_summary",
                "summary": "用户提示词替代 PDF 摘要：" + prompt_summary,
            }
        )
    return summaries


def case_card_markdown(card: dict[str, Any]) -> str:
    lines = [
        f"# {card['title']}",
        "",
        f"- Case directory: `{card['case_dir']}`",
        f"- Training stage: `{card['training_stage']}`",
        f"- Created at: `{card['created_at']}`",
        "",
        "## File Summary",
        "",
    ]
    for key, value in card["file_summary"].items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Extracted Parameters", ""])
    if card["parameters"]:
        for param in card["parameters"][:80]:
            lines.append(
                f"- `{param['name']}` = `{param['value']}`"
                + (f" - {param['description']}" if param.get("description") else "")
            )
    else:
        lines.append("- No explicit parameter table was detected.")

    content = card.get("case_content", {})
    totals = content.get("totals", {})
    lines.extend(["", "## 内容级读取结果", ""])
    lines.append(f"- 模型树证据数量: {totals.get('model_tree_items', 0)}")
    lines.append(f"- 理论关键词: {', '.join(content.get('theory_keywords', [])) or '未自动识别'}")
    for section in ("geometry", "physics", "materials", "mesh", "studies", "results", "boundary_conditions"):
        values = content.get(section, [])
        if values:
            lines.append(f"- {section}: {', '.join(values[:12])}")
    source_extracts = content.get("source_extracts", [])
    if source_extracts:
        lines.extend(["", "### 文件内容证据", ""])
        for item in source_extracts[:20]:
            lines.append(
                f"- `{item.get('name', '')}`: "
                f"参数={len(item.get('parameters', []))}, "
                f"几何={len(item.get('geometry', []))}, "
                f"物理场={len(item.get('physics', []))}, "
                f"研究={len(item.get('studies', []))}, "
                f"结果={len(item.get('results', []))}"
            )

    pdf_summaries = card.get("pdf_simple_summaries", [])
    if pdf_summaries:
        lines.extend(["", "## 每个 PDF 文件的简单总结", ""])
        for item in pdf_summaries:
            lines.append(f"- `{item.get('name', '')}`: {item.get('summary', '')}")

    physics_judgement = card.get("physics_judgement", {})
    if physics_judgement:
        lines.extend(["", "## PDF Summary and Physics Judgement", ""])
        lines.append(f"- Simple summary: {physics_judgement.get('simple_summary', '')}")
        lines.append(f"- Primary physics: `{physics_judgement.get('primary_physics', '')}`")
        lines.append(f"- Study type: `{physics_judgement.get('study_type', '')}`")
        lines.append(f"- Judgement rule: {physics_judgement.get('judgement_rule', '')}")
        evidence = physics_judgement.get("evidence", [])
        if evidence:
            lines.extend(["", "### Judgement Evidence", ""])
            for item in evidence[:8]:
                lines.append(f"- {item}")

    geometry_learning = card.get("geometry_parameter_learning", {})
    if geometry_learning:
        lines.extend(["", "## PDF Keywords to Geometry/Parameter/MATLAB Mapping", ""])
        lines.append(f"- Summary: {geometry_learning.get('summary', '')}")
        keywords = geometry_learning.get("pdf_keywords", [])
        if keywords:
            lines.append(f"- PDF keywords: {', '.join(keywords[:20])}")
        for row in geometry_learning.get("matlab_mapping", [])[:12]:
            lines.append(
                f"- `{row.get('keyword', '')}` -> {row.get('modeling_content', '')}; "
                f"MATLAB: `{row.get('matlab_action', '')}`"
            )
        checks = geometry_learning.get("geometry_parameter_checks", [])
        if checks:
            lines.extend(["", "### Geometry and Parameter Checks", ""])
            lines.extend(f"- {item}" for item in checks[:12])

    principles = card.get("modeling_principles", {})
    if principles:
        lines.extend(["", "## Modeling Principles Learned", ""])
        lines.append(f"- Readiness: `{principles.get('readiness', '')}`")
        for section in ("core_sequence", "physics_reasoning", "automation_evidence", "verification_logic"):
            values = principles.get(section, [])
            if values:
                lines.extend(["", f"### {section}", ""])
                for item in values:
                    lines.append(f"- {item}")

    extension = card.get("case_extension", {})
    if extension:
        lines.extend(["", "## Thinking and Extension", ""])
        lines.append(f"- Readiness: `{extension.get('readiness', '')}`")
        for section in (
            "transferable_knowledge",
            "extension_questions",
            "new_model_directions",
            "parameter_sweep_ideas",
            "code_generation_ideas",
            "risk_checks",
        ):
            values = extension.get(section, [])
            if values:
                lines.extend(["", f"### {section}", ""])
                for item in values:
                    lines.append(f"- {item}")

    lines.extend(["", "## Thoughts", ""])
    for thought in card["thoughts"]:
        lines.append(f"- {thought}")

    summary = card.get("post_learning_summary", {})
    if summary:
        lines.extend(["", "## Learning Summary After This Case", ""])
        lines.append(f"- Summary: {summary.get('summary', '')}")
        lines.append(f"- Training readiness: {summary.get('training_readiness', '')}")
        lines.append(f"- Reusable confidence: {summary.get('reusable_confidence', '')}")
        lines.extend(["", "### 学到的建模逻辑", ""])
        for item in summary.get("learned_modeling_logic", []):
            lines.append(f"- {item}")
        lines.extend(["", "### Reusable Assets", ""])
        for item in summary.get("reusable_assets", []):
            lines.append(f"- {item}")
        lines.extend(["", "### Learning Process and Evidence", ""])
        for item in summary.get("learning_trace", []):
            lines.append(f"- **{item.get('step', '')}**")
            lines.append(f"  - Evidence: {item.get('evidence', '')}")
            lines.append(f"  - Judgement: {item.get('judgement', '')}")
        lines.extend(["", "### Next Actions", ""])
        for item in summary.get("next_actions", []):
            lines.append(f"- {item}")

    deep_learning = card.get("deep_learning_plan", {})
    if deep_learning:
        lines.extend(["", "## Deep Learning Capability Plan", ""])
        lines.append(f"- Readiness: `{deep_learning.get('readiness', '')}`")
        lines.append(f"- Score: `{deep_learning.get('readiness_score', 0)}`")
        lines.extend(["", "### Candidate Inputs", ""])
        for item in deep_learning.get("candidate_inputs", [])[:30]:
            lines.append(f"- `{item}`")
        lines.extend(["", "### Candidate Outputs", ""])
        for item in deep_learning.get("candidate_outputs", [])[:30]:
            lines.append(f"- `{item}`")
        lines.extend(["", "### Training Workflow", ""])
        for item in deep_learning.get("workflow", []):
            lines.append(f"- {item}")
        lines.extend(["", "### Dataset Requirements", ""])
        for item in deep_learning.get("dataset_requirements", []):
            lines.append(f"- {item}")

    alignment = card.get("knowledge_alignment", {})
    if alignment:
        lines.extend(["", "## External Knowledge Alignment", ""])
        lines.extend(["", "### Similar Master Cases", ""])
        matches = alignment.get("case_matches", [])
        if matches:
            for match in matches[:5]:
                fields = ", ".join(match.get("supported_fields", [])) or "topic only"
                lines.append(
                    f"- `{match.get('title', '')}` score={match.get('score', '')}; "
                    f"fields={fields}; parameters={match.get('parameter_count', 0)}"
                )
        else:
            lines.append("- No master case index match was available.")
        lines.extend(["", "### Official Documentation Checks", ""])
        docs = alignment.get("docs_matches", [])
        if docs:
            for doc in docs[:5]:
                lines.append(
                    f"- `{doc.get('document', '')}` page {doc.get('page', '')}; "
                    f"module={doc.get('module', '')}; score={doc.get('score', '')}"
                )
        else:
            lines.append("- No official documentation index match was available.")
        lines.extend(["", "### Training Improvements", ""])
        for item in alignment.get("training_improvements", []):
            lines.append(f"- {item}")

    lines.extend(["", "## Implementation Path", ""])
    for step in card["implementation_path"]:
        lines.append(f"- {step}")

    lines.extend(["", "## Gaps", ""])
    for gap in card["gaps"]:
        lines.append(f"- {gap}")

    lines.extend(["", "## Source Files", ""])
    for file in card["source_files"]:
        lines.append(f"- `{file['name']}` ({file['kind']}, {file['size_bytes']} bytes)")
    lines.append("")
    return "\n".join(lines)


def _case_files(case_path: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in case_path.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_CASE_EXTENSIONS
        ]
    )


def _extract_parameters(collection: dict[str, Any]) -> list[dict[str, str]]:
    parameters: dict[str, dict[str, str]] = {}
    for file in collection.get("files", []):
        if file.get("kind") not in {"text", "matlab_livelink", "matlab_text", "comsol_java"}:
            continue
        preview = str(file.get("preview", ""))
        for param in _extract_parameter_lines(preview):
            parameters.setdefault(param["name"], param)
    return list(parameters.values())


def _extract_case_content(collection: dict[str, Any]) -> dict[str, Any]:
    sections = {
        "parameters": [],
        "geometry": [],
        "physics": [],
        "materials": [],
        "mesh": [],
        "studies": [],
        "results": [],
        "boundary_conditions": [],
        "theory_keywords": [],
    }
    source_extracts = []
    for file in collection.get("files", []):
        details = file.get("details", {}) if isinstance(file, dict) else {}
        extract = details.get("content_extract", {}) if isinstance(details, dict) else {}
        if not isinstance(extract, dict):
            continue
        source_item = {
            "name": file.get("name", "file"),
            "kind": file.get("kind", "unknown"),
            "evidence_score": extract.get("evidence_score", 0),
            "content_summary": extract.get("content_summary", [])[:8],
        }
        for key in sections:
            values = [str(value) for value in extract.get(key, []) if str(value).strip()]
            source_item[key] = values[:20]
            sections[key].extend(values)
        source_extracts.append(source_item)

    deduped = {key: _dedupe(values, limit=80) for key, values in sections.items()}
    model_tree_items = sum(
        len(deduped[key])
        for key in ("parameters", "geometry", "physics", "materials", "mesh", "studies", "results", "boundary_conditions")
    )
    return {
        "kind": "case_content_learning",
        **deduped,
        "source_extracts": sorted(source_extracts, key=lambda item: item.get("evidence_score", 0), reverse=True),
        "totals": {
            "model_tree_items": model_tree_items,
            "source_files_with_content": sum(1 for item in source_extracts if item.get("evidence_score", 0) > 0),
            "source_files_checked": len(source_extracts),
        },
    }


def _dedupe(values: list[str], limit: int = 80) -> list[str]:
    result = []
    seen = set()
    for value in values:
        normalized = re.sub(r"\s+", " ", value.strip())
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
        if len(result) >= limit:
            break
    return result


def _extract_parameter_lines(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%") or stripped.startswith("//"):
            continue
        if stripped.endswith(";"):
            matlab_match = re.search(
                r"model\.param\.set\(\s*'(?P<name>[^']+)'\s*,\s*'(?P<value>[^']+)'(?:\s*,\s*'(?P<description>[^']*)')?",
                stripped,
            )
            if matlab_match:
                rows.append(
                    {
                        "name": matlab_match.group("name"),
                        "value": matlab_match.group("value"),
                        "description": matlab_match.group("description") or "",
                        "source": "matlab_param_set",
                    }
                )
                continue
            matlab_input_match = re.search(
                r"inputParam\.set\(\s*'(?P<name>[^']+)'\s*,\s*'(?P<value>[^']+)'",
                stripped,
            )
            if matlab_input_match:
                rows.append(
                    {
                        "name": matlab_input_match.group("name"),
                        "value": matlab_input_match.group("value"),
                        "description": "geometry input parameter",
                        "source": "matlab_geometry_input_param",
                    }
                )
                continue
            java_match = re.search(
                r"\.param\(\)\.set\(\s*\"(?P<name>[^\"]+)\"\s*,\s*\"(?P<value>[^\"]+)\"(?:\s*,\s*\"(?P<description>[^\"]*)\")?",
                stripped,
            )
            if java_match:
                rows.append(
                    {
                        "name": java_match.group("name"),
                        "value": java_match.group("value"),
                        "description": java_match.group("description") or "",
                        "source": "java_param_set",
                    }
                )
                continue
            java_input_match = re.search(
                r"inputParam\(\)\.set\(\s*\"(?P<name>[^\"]+)\"\s*,\s*\"(?P<value>[^\"]+)\"",
                stripped,
            )
            if java_input_match:
                rows.append(
                    {
                        "name": java_input_match.group("name"),
                        "value": java_input_match.group("value"),
                        "description": "geometry input parameter",
                        "source": "java_geometry_input_param",
                    }
                )
            continue
        table_match = re.match(r"^(?P<name>[A-Za-z]\w*)\s+(?P<value>[^\s]+(?:\[[^\]]+\])?)\s*(?P<desc>\".*\")?$", stripped)
        if table_match and _is_valid_parameter_name(table_match.group("name")):
            rows.append(
                {
                    "name": table_match.group("name"),
                    "value": table_match.group("value"),
                    "description": (table_match.group("desc") or "").strip('"'),
                    "source": "parameter_table",
                }
            )
            continue
    return rows


def _geometry_parameter_learning(card: dict[str, Any]) -> dict[str, Any]:
    content = card.get("case_content", {}) if isinstance(card.get("case_content"), dict) else {}
    parameters = card.get("parameters", []) if isinstance(card.get("parameters"), list) else []
    pdf_keywords = _dedupe(
        [str(item) for item in content.get("theory_keywords", [])]
        + [
            str(item.get("summary", ""))
            for item in card.get("pdf_simple_summaries", [])
            if isinstance(item, dict)
        ],
        limit=30,
    )
    mapping = _matlab_keyword_mapping(content, parameters)
    geometry = [str(item) for item in content.get("geometry", []) if str(item).strip()]
    physics = [str(item) for item in content.get("physics", []) if str(item).strip()]
    checks = [
        "先根据 PDF 关键词判断几何对象、控制变量和输出量，再用 MATLAB/Java 模型树证据确认。",
        "全局参数应优先来自 model.param.set、inputParam 或案例参数表，缺失时用待确认占位参数。",
        "几何应先参数化，再创建命名选择集，避免后续边界条件依赖不稳定的实体编号。",
        "MATLAB 建模应按 parameter -> geom.create/feature -> selection -> physics.create -> mesh -> study 的顺序生成。",
    ]
    if geometry:
        checks.append("已识别几何证据：" + "；".join(geometry[:6]))
    if physics:
        checks.append("已识别物理场证据：" + "；".join(physics[:6]))
    if parameters:
        checks.append("已识别参数：" + "、".join(str(item.get("name", "")) for item in parameters[:12]))
    return {
        "kind": "geometry_parameter_matlab_mapping",
        "summary": "将 PDF 关键词、案例建模内容和 MATLAB/Java API 证据整理为可复用的几何与参数建模知识。",
        "pdf_keywords": pdf_keywords,
        "matlab_mapping": mapping,
        "geometry_parameter_checks": checks,
        "learned_capability": [
            "根据需求判断几何维度、几何对象和参数化变量。",
            "把 PDF 中的理论/模型关键词映射到 MATLAB LiveLink 建模 API。",
            "回答几何模型与参数问题，并给出可修改的 MATLAB 建模骨架。",
        ],
    }


def _matlab_keyword_mapping(content: dict[str, Any], parameters: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for param in parameters[:12]:
        name = str(param.get("name", "")).strip()
        if name:
            rows.append(
                {
                    "keyword": name,
                    "modeling_content": str(param.get("description") or "案例参数/扫描变量"),
                    "matlab_action": f"model.param.set('{name}', value, description)",
                }
            )
    mapping_rules = [
        ("Rectangle", "矩形/二维计算域", "model.component('comp1').geom('geom1').create(tag, 'Rectangle')"),
        ("Block", "三维块体/实体计算域", "model.component('comp1').geom('geom1').create(tag, 'Block')"),
        ("Circle", "圆孔、圆柱截面或钻孔", "model.component('comp1').geom('geom1').create(tag, 'Circle')"),
        ("Cylinder", "圆柱体、管道或三维钻孔", "model.component('comp1').geom('geom1').create(tag, 'Cylinder')"),
        ("Difference", "布尔差集/开孔/去除几何", "geom.feature(tag).selection('input').set(...)"),
        ("Union", "几何并集/装配合并", "model.component('comp1').geom('geom1').create(tag, 'Union')"),
        ("Import", "导入 CAD/STL/扫描数据几何", "model.component('comp1').geom('geom1').create(tag, 'Import')"),
        ("Extrude", "二维截面拉伸成三维结构", "model.component('comp1').geom('geom1').create(tag, 'Extrude')"),
        ("SolidMechanics", "结构力学物理场", "model.component('comp1').physics.create('solid','SolidMechanics','geom1')"),
        ("HeatTransfer", "传热物理场", "model.component('comp1').physics.create('ht','HeatTransfer','geom1')"),
        ("LaminarFlow", "层流流体物理场", "model.component('comp1').physics.create('spf','LaminarFlow','geom1')"),
        ("ElectricCurrents", "电流物理场", "model.component('comp1').physics.create('ec','ElectricCurrents','geom1')"),
    ]
    haystack = " ".join(
        str(value)
        for key in ("geometry", "physics", "materials", "mesh", "studies", "results", "boundary_conditions", "theory_keywords")
        for value in content.get(key, [])
    )
    for keyword, modeling_content, matlab_action in mapping_rules:
        if keyword.lower() in haystack.lower():
            rows.append(
                {
                    "keyword": keyword,
                    "modeling_content": modeling_content,
                    "matlab_action": matlab_action,
                }
            )
    if not rows:
        rows.append(
            {
                "keyword": "parameterized_geometry",
                "modeling_content": "先建立参数化基准几何，再按 PDF/脚本证据替换为案例几何。",
                "matlab_action": "model.param.set(...) + model.component('comp1').geom('geom1').create(...)",
            }
        )
    return rows[:30]


def _is_valid_parameter_name(name: str) -> bool:
    return name.lower() not in RESERVED_PARAMETER_NAMES


def _implementation_path(has_training_csv: bool) -> list[str]:
    steps = [
        "把 PDF、MATLAB、Java、MPH、TXT、JSON 和 CSV 证据作为一个完整案例包读取。",
        "Extract model purpose, geometry sequence, parameters, selections, and model-tree features.",
        "Convert detected parameters into a constraints JSON with units and valid ranges.",
        "Use MATLAB/Java evidence to generate or adapt a LiveLink MATLAB builder.",
    ]
    if has_training_csv:
        steps.extend(
            [
                "Inspect CSV columns and choose surrogate inputs and outputs.",
                "Train the local surrogate model and review RMSE, MAE, R2, and warnings.",
            ]
        )
    else:
        steps.extend(
            [
                "Run a COMSOL parametric sweep over selected parameters.",
                "Export a CSV containing input parameters and target outputs.",
                "Train the local surrogate model after the CSV exists.",
            ]
        )
    return steps


def _physics_judgement(card: dict[str, Any]) -> dict[str, Any]:
    content = card.get("case_content", {}) if isinstance(card.get("case_content"), dict) else {}
    title = str(card.get("title", "COMSOL case"))
    physics = [str(item) for item in content.get("physics", []) if str(item).strip()]
    studies = [str(item) for item in content.get("studies", []) if str(item).strip()]
    theory = [str(item) for item in content.get("theory_keywords", []) if str(item).strip()]
    pdf_lines = _pdf_content_lines(content)
    primary_physics = _primary_physics_name(physics, theory, pdf_lines)
    coupling = _case_coupling(title, physics, theory, pdf_lines)
    study_type = _primary_study_type(studies, pdf_lines)
    problem_hint = _problem_hint(title, theory, pdf_lines)

    if coupling:
        primary_physics = coupling["primary_physics"]
        summary = (
            f"{title} 涉及{problem_hint}；从脚本和理论证据看，应采用"
            f"{coupling['label']}。主物理场为 {primary_physics}，"
            f"并耦合 {'、'.join(coupling['coupled_physics'])}"
            + (f"，采用 {study_type} 研究。" if study_type else "。")
        )
    elif primary_physics:
        summary = (
            f"{title} 主要研究{problem_hint}，PDF 用来说明问题目标、基本假设和求解对象；"
            f"从核心内容看，建模时应优先选择 {primary_physics}"
            + (f"，并采用 {study_type} 研究。" if study_type else "。")
        )
    else:
        summary = (
            f"{title} 的 PDF 可用于理解案例目的、假设和操作步骤；当前证据还不足以唯一确定物理场，"
            "后续应结合 MATLAB/Java 中的 physics.create 或 COMSOL 模型树再确认。"
        )

    evidence = []
    if pdf_lines:
        evidence.extend([f"PDF: {line}" for line in pdf_lines[:4]])
    if physics:
        evidence.append("脚本/文本识别到的物理场: " + ", ".join(physics[:8]))
    if studies:
        evidence.append("识别到的研究类型: " + ", ".join(studies[:6]))
    if theory:
        evidence.append("理论关键词: " + ", ".join(theory[:8]))

    return {
        "kind": "physics_judgement_from_case",
        "simple_summary": summary,
        "primary_physics": primary_physics or "needs_more_evidence",
        "coupled_physics": coupling["coupled_physics"] if coupling else [],
        "multiphysics_nodes": coupling["multiphysics_nodes"] if coupling else [],
        "study_type": study_type or "unknown",
        "judgement_rule": _physics_judgement_rule(primary_physics, study_type),
        "evidence": _dedupe(evidence, 12),
        "reusable_training_note": (
            "后续判断物理场时，先读 PDF 中的问题目标和方程关键词，再用 MATLAB/Java 的 physics.create "
            "校验接口名称；若两者一致，就把该接口作为自动建模的主物理场。"
        ),
    }


def _case_coupling(title: str, physics: list[str], theory: list[str], pdf_lines: list[str]) -> dict[str, Any] | None:
    """Identify only couplings supported by two distinct interface or topic signals."""
    joined = " ".join([title, *physics, *theory, *pdf_lines]).lower()
    electric = any(token in joined for token in ("conductivemedia", "electriccurrents", "electric currents", "电流", "电压", "电势", "焦耳"))
    heat = any(token in joined for token in ("heattransfer", "heat transfer", "传热", "温度", "热"))
    structural = any(token in joined for token in ("solidmechanics", "solid mechanics", "固体力学", "结构力学", "热应力", "热膨胀"))

    if electric and heat and structural:
        return {"label": "电-热-结构耦合", "primary_physics": "Electric Currents", "coupled_physics": ["Heat Transfer", "Solid Mechanics"], "multiphysics_nodes": ["Joule Heating", "Thermal Expansion"]}
    if electric and heat:
        return {"label": "电-热耦合 / 焦耳热", "primary_physics": "Electric Currents", "coupled_physics": ["Heat Transfer"], "multiphysics_nodes": ["Joule Heating"]}
    if heat and structural:
        return {"label": "热-结构耦合 / 热应力", "primary_physics": "Heat Transfer", "coupled_physics": ["Solid Mechanics"], "multiphysics_nodes": ["Thermal Expansion"]}
    return None

def _pdf_content_lines(content: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for source in content.get("source_extracts", []):
        if not isinstance(source, dict) or source.get("kind") != "pdf_document":
            continue
        for item in source.get("content_summary", []):
            text = re.sub(r"\s+", " ", str(item).strip())
            if text:
                lines.append(text[:220])
    return _dedupe(lines, 8)


def _primary_physics_name(physics: list[str], theory: list[str], pdf_lines: list[str]) -> str:
    joined = " ".join(physics + theory + pdf_lines).lower()
    if any(token in joined for token in ("laminarflow", "laminar flow", "层流", "不可压缩流", "navier", "blasius")):
        return "Laminar Flow"
    if any(token in joined for token in ("turbulentflow", "turbulent flow", "湍流")):
        return "Turbulent Flow"
    ordered = [
        ("Coefficient Form PDE", ("coefficientformpde", "coefficient form pde", "系数形式偏微分方程", "薛定谔", "schrodinger", "black-scholes", "kdv")),
        ("Heat Transfer", ("heattransfer", "heat transfer", "传热", "温度", "导热")),
        ("Solid Mechanics", ("solidmechanics", "solid mechanics", "固体力学", "结构力学", "应力", "应变")),
        ("Transport of Diluted Species", ("dilutedspecies", "transport of diluted species", "稀物质", "浓度")),
        ("Electric Currents", ("electriccurrents", "electric currents", "电流", "电势", "电压")),
        ("Pressure Acoustics", ("pressureacoustics", "pressure acoustics", "声学", "声压")),
        ("Optimization", ("optimization", "优化", "目标函数")),
    ]
    for label, tokens in ordered:
        if any(token in joined for token in tokens):
            return label
    if physics:
        first = physics[0]
        parts = [part.strip() for part in re.split(r"/", first) if part.strip()]
        return parts[-1] if parts else first
    return ""


def _primary_study_type(studies: list[str], pdf_lines: list[str]) -> str:
    joined = " ".join(studies + pdf_lines).lower()
    ordered = [
        ("Eigenvalue", ("eigenvalue", "特征值")),
        ("Eigenfrequency", ("eigenfrequency", "特征频率", "特征模态")),
        ("Time Dependent", ("time dependent", "瞬态", "时间依赖")),
        ("Stationary", ("stationary", "稳态")),
        ("Frequency Domain", ("frequency domain", "频域")),
        ("Parametric Sweep", ("parametric sweep", "参数扫描", "参数化扫描")),
    ]
    for label, tokens in ordered:
        if any(token in joined for token in tokens):
            return label
    if studies:
        first = studies[0]
        parts = [part.strip() for part in re.split(r"/", first) if part.strip()]
        return parts[-1] if parts else first
    return ""


def _problem_hint(title: str, theory: list[str], pdf_lines: list[str]) -> str:
    joined = " ".join([title] + theory + pdf_lines).lower()
    if any(token in joined for token in ("焦耳", "joule", "conductivemedia", "electriccurrents")):
        return "电流分布、焦耳热和温升"
        return "量子能级或波函数分布"
    if any(token in joined for token in ("应力", "应变", "位移", "stress", "strain")):
        return "结构受力、变形或强度响应"
    if any(token in joined for token in ("流体", "层流", "速度", "压力", "flow", "fluid", "blasius")):
        return "流动速度、压力或输运过程"
    if any(token in joined for token in ("传热", "温度", "heat", "thermal")):
        return "温度场和热传递过程"
    if any(token in joined for token in ("电流", "电压", "电场", "current", "voltage")):
        return "电流、电势或电磁场分布"
    if any(token in joined for token in ("声", "acoustic")):
        return "声压、模态或频域声学响应"
    return "模型中的主要物理现象和输出量"


def _physics_judgement_rule(primary_physics: str, study_type: str) -> str:
    if primary_physics == "Coefficient Form PDE":
        return "若 PDF 强调自定义方程、薛定谔方程、能级、波函数或特征值，优先判断为系数形式 PDE；再用脚本中的 CoefficientFormPDE 校验。"
    if primary_physics:
        suffix = f"；研究类型可由 {study_type} 确认。" if study_type else "；研究类型需要继续从研究步骤确认。"
        return f"若 PDF 的核心量和方程关键词指向 {primary_physics}，并且脚本/文本中出现同类接口，就把它作为主物理场{suffix}"
    return "先根据 PDF 的核心物理量提出候选物理场，再用 MATLAB/Java/MPH 摘要中的 physics.create 做最终确认。"


def _modeling_principles(card: dict[str, Any]) -> dict[str, Any]:
    file_summary = card.get("file_summary", {})
    content = card.get("case_content", {})
    parameters = card.get("parameters", [])
    has_scripts = file_summary.get("matlab_files", 0) > 0 or file_summary.get("java_files", 0) > 0
    has_mph = file_summary.get("mph_files", 0) > 0
    has_model_tree = content.get("totals", {}).get("model_tree_items", 0) > 0

    core_sequence = [
        "先定义全局参数和单位，再建立几何与选择集。",
        "随后配置材料、物理场接口、边界条件、网格、研究/求解器和结果导出。",
        "自动建模时必须保持 COMSOL 模型树顺序一致，避免先创建依赖后创建上游对象。",
    ]
    if parameters:
        core_sequence.append(f"本案例已提取 {len(parameters)} 个参数，可作为约束 JSON 和参数扫描变量。")
    if content.get("geometry"):
        core_sequence.append("几何证据显示模型可以从脚本中的 geom/feature 序列恢复。")

    physics_reasoning = []
    if content.get("physics"):
        physics_reasoning.append("物理场接口来自 MATLAB/Java/摘要中的 physics.create 证据，应作为自动建模的主约束。")
        physics_reasoning.extend([f"识别到物理场证据：{item}" for item in content.get("physics", [])[:8]])
    if content.get("boundary_conditions"):
        physics_reasoning.append("边界条件和选择集需要复核边界编号；自动生成代码时应标注人工确认点。")
    if content.get("theory_keywords"):
        physics_reasoning.append("理论关键词可用于判断控制方程、变量含义和验证目标。")

    automation_evidence = []
    if has_scripts:
        automation_evidence.append("MATLAB/Java 文件可直接提供 COMSOL API 调用顺序，是自动建模最可靠的文本证据。")
    if has_mph:
        automation_evidence.append("MPH 文件被视为权威模型来源；若存在同名 MATLAB/Java/JSON 摘要，系统会读取这些旁路证据。")
    if content.get("materials"):
        automation_evidence.append("材料节点已识别，生成脚本时应保留材料标签、属性组和单位。")
    if content.get("mesh"):
        automation_evidence.append("网格节点已识别，后续应将网格尺寸或网格序列写入可复用模板。")

    verification_logic = [
        "生成模型后先运行基准算例，再做网格无关性和参数扫描。",
        "若需要训练代理模型，必须导出包含输入参数和目标输出的 CSV。",
        "训练后用未参与训练的 COMSOL 结果复核 RMSE、MAE、R2 和物理趋势。",
    ]
    if content.get("results"):
        verification_logic.append("结果节点可用于确定导出量和训练目标。")

    readiness = "modeling_principles_ready" if has_model_tree or has_scripts or has_mph else "needs_more_modeling_evidence"
    return {
        "kind": "comsol_modeling_principles",
        "readiness": readiness,
        "core_sequence": core_sequence,
        "physics_reasoning": physics_reasoning or ["当前未识别到明确物理场，需要补充 MATLAB/Java/MPH 摘要或 PDF 理论说明。"],
        "automation_evidence": automation_evidence or ["当前自动建模证据不足，建议补充 COMSOL 导出的 MATLAB 或 Java 文件。"],
        "verification_logic": verification_logic,
    }


def _post_learning_summary(card: dict[str, Any]) -> dict[str, Any]:
    file_summary = card.get("file_summary", {})
    parameters = card.get("parameters", [])
    case_content = card.get("case_content", {})
    content_totals = case_content.get("totals", {})
    has_scripts = file_summary.get("matlab_files", 0) > 0 or file_summary.get("java_files", 0) > 0
    has_pdf = file_summary.get("pdf_files", 0) > 0
    has_mph = file_summary.get("mph_files", 0) > 0
    has_csv = file_summary.get("csv_files", 0) > 0

    learned_logic = [
        "Case files were treated as one COMSOL evidence package: documentation, scripts, binary model files, parameters, and data.",
        "The model tree should be reconstructed in this order: parameters, geometry, selections, materials, physics, mesh, study, results, and exports.",
    ]
    if has_scripts:
        learned_logic.append("MATLAB/Java scripts provide reusable COMSOL API call patterns for automated model construction.")
    if has_pdf:
        learned_logic.append("PDF documentation provides modeling purpose, assumptions, theoretical context, and validation targets.")
    if has_mph:
        learned_logic.append("MPH files are remembered as authoritative model artifacts, but detailed internal settings require COMSOL/LiveLink extraction.")
    if parameters:
        learned_logic.append("检测到的参数可用于生成约束 JSON，后续也可作为代理模型训练的扫描变量。")
    if content_totals.get("model_tree_items", 0):
        learned_logic.append(
            "已完成内容级读取：从案例文件中抽取了参数、几何、物理场、材料、网格、研究、结果和边界条件等模型树证据。"
        )

    reusable_assets = []
    if parameters:
        reusable_assets.append(f"{len(parameters)} extracted parameters with values/descriptions.")
    if has_scripts:
        reusable_assets.append("LiveLink MATLAB or COMSOL Java script structure.")
    if has_pdf:
        reusable_assets.append("Theory and workflow evidence from PDF documents.")
    if has_mph:
        reusable_assets.append("Original MPH files for later COMSOL-side verification.")
    if has_csv:
        reusable_assets.append("CSV data for direct surrogate training.")
    if content_totals.get("model_tree_items", 0):
        reusable_assets.append(f"{content_totals.get('model_tree_items', 0)} 条内容级模型树证据。")

    next_actions = list(card.get("implementation_path", []))
    if not has_csv:
        next_actions.append("几何和建模逻辑验证后，运行 COMSOL 参数扫描并导出 CSV 训练数据。")

    return {
        "kind": "post_case_learning_summary",
        "title": card.get("title", "case"),
        "summary": (
            f"已学习 {card.get('title', 'case')} 的 {file_summary.get('count', 0)} 个文件；"
            f"训练阶段={card.get('training_stage', 'unknown')}；参数数量={len(parameters)}；"
            f"内容证据={content_totals.get('model_tree_items', 0)} 条。"
        ),
        "learned_modeling_logic": learned_logic,
        "reusable_assets": reusable_assets or ["No reusable asset was detected automatically."],
        "training_readiness": (
            "ready_for_surrogate_training"
            if has_csv
            else "modeling_logic_ready_but_needs_comsol_sweep_csv"
        ),
        "reusable_confidence": _reusable_confidence(has_scripts, has_pdf, has_mph, parameters, has_csv),
        "learning_trace": _learning_trace(card),
        "next_actions": next_actions,
    }


def _learning_trace(card: dict[str, Any]) -> list[dict[str, str]]:
    file_summary = card.get("file_summary", {})
    parameters = card.get("parameters", [])
    case_content = card.get("case_content", {})
    content_totals = case_content.get("totals", {})
    source_files = card.get("source_files", [])
    has_scripts = file_summary.get("matlab_files", 0) > 0 or file_summary.get("java_files", 0) > 0
    has_pdf = file_summary.get("pdf_files", 0) > 0
    has_mph = file_summary.get("mph_files", 0) > 0
    has_csv = file_summary.get("csv_files", 0) > 0
    script_names = [
        str(file.get("name"))
        for file in source_files
        if file.get("kind") in {"matlab_livelink", "matlab_text", "comsol_java"}
    ][:6]

    trace = [
        {
            "step": "1. 文件证据读取",
            "evidence": (
                f"共读取 {file_summary.get('count', 0)} 个案例文件；"
                f"MATLAB={file_summary.get('matlab_files', 0)}，"
                f"Java={file_summary.get('java_files', 0)}，"
                f"PDF={file_summary.get('pdf_files', 0)}，"
                f"MPH={file_summary.get('mph_files', 0)}，"
                f"CSV={file_summary.get('csv_files', 0)}。"
            ),
            "judgement": "这些文件被合并为一个 COMSOL 案例证据包，用于同时学习建模流程、参数和训练可行性。",
        },
        {
            "step": "2. 内容级模型树抽取",
            "evidence": (
                f"抽取到模型树证据 {content_totals.get('model_tree_items', 0)} 条；"
                f"几何={len(case_content.get('geometry', []))}，"
                f"物理场={len(case_content.get('physics', []))}，"
                f"材料={len(case_content.get('materials', []))}，"
                f"网格={len(case_content.get('mesh', []))}，"
                f"研究={len(case_content.get('studies', []))}，"
                f"结果={len(case_content.get('results', []))}。"
            ),
            "judgement": (
                "模型已读取案例内容并抽取 COMSOL 模型树结构，可用于后续自动建模和代码生成。"
                if content_totals.get("model_tree_items", 0)
                else "当前文件内容中尚未自动抽取到明确模型树结构；需要补充脚本、MPH 摘要或更完整文本。"
            ),
        },
        {
            "step": "3. 建模脚本识别",
            "evidence": (
                "检测到可复用的 MATLAB/Java 建模脚本："
                + (", ".join(script_names) if script_names else "未检测到 MATLAB/Java 脚本")
            ),
            "judgement": (
                "脚本中的 COMSOL API 调用可用于恢复模型树顺序，并辅助生成 LiveLink MATLAB 自动建模脚本。"
                if has_scripts
                else "缺少脚本时，只能依赖文档和其他文本线索推断建模逻辑。"
            ),
        },
        {
            "step": "4. 参数与约束提取",
            "evidence": f"从文本、MATLAB 或 Java 证据中提取到 {len(parameters)} 个参数。",
            "judgement": (
                "这些参数可转成约束 JSON，并作为后续 COMSOL 参数扫描和代理模型训练的输入变量。"
                if parameters
                else "暂未发现显式参数，需要人工补充参数范围或从 COMSOL/LiveLink 中进一步导出。"
            ),
        },
        {
            "step": "5. 理论与模型来源判断",
            "evidence": (
                f"PDF 文档={file_summary.get('pdf_files', 0)}，"
                f"MPH 模型={file_summary.get('mph_files', 0)}。"
            ),
            "judgement": _theory_and_model_judgement(has_pdf, has_mph),
        },
        {
            "step": "6. 训练阶段判断",
            "evidence": f"CSV 训练数据文件数量为 {file_summary.get('csv_files', 0)}。",
            "judgement": (
                "已有 CSV，可继续检查输入/输出列并训练本地代理模型。"
                if has_csv
                else "当前完成的是建模逻辑学习；还需要运行 COMSOL 参数扫描并导出 CSV，才能进行数值代理模型训练。"
            ),
        },
        {
            "step": "7. 记忆库补充",
            "evidence": f"案例标题为 {card.get('title', 'case')}，训练阶段为 {card.get('training_stage', 'unknown')}。",
            "judgement": "该案例的文件摘要、参数、建模逻辑和下一步动作会写入案例知识库，并可被后续自动建模方案检索复用。",
        },
    ]
    return trace


def _theory_and_model_judgement(has_pdf: bool, has_mph: bool) -> str:
    if has_pdf and has_mph:
        return "PDF 用于补充理论、假设和教程目标；MPH 作为权威模型文件，后续应通过 COMSOL/LiveLink 提取内部设置。"
    if has_pdf:
        return "PDF 可提供理论、假设和操作流程，但缺少 MPH 时需要用脚本或人工步骤重建模型。"
    if has_mph:
        return "MPH 是权威模型文件，但缺少 PDF 时理论背景和验证目标需要从脚本、文件名或后续人工说明补充。"
    return "未检测到 PDF 或 MPH，当前判断主要依赖脚本文本和参数线索。"


def _case_extension(card: dict[str, Any]) -> dict[str, Any]:
    file_summary = card.get("file_summary", {})
    content = card.get("case_content", {})
    parameters = card.get("parameters", [])
    physics = [str(item) for item in content.get("physics", [])]
    geometry = [str(item) for item in content.get("geometry", [])]
    studies = [str(item) for item in content.get("studies", [])]
    results = [str(item) for item in content.get("results", [])]
    theory = [str(item) for item in content.get("theory_keywords", [])]
    has_scripts = file_summary.get("matlab_files", 0) > 0 or file_summary.get("java_files", 0) > 0
    has_csv = file_summary.get("csv_files", 0) > 0
    has_mph = file_summary.get("mph_files", 0) > 0

    transferable = [
        "Reuse the learned COMSOL order: parameters -> geometry -> selections -> materials -> physics -> mesh -> study -> results.",
        "Treat extracted parameters as future constraint variables and parametric sweep inputs.",
    ]
    if physics:
        transferable.append("Transfer recognized physics interfaces to similar requirements: " + ", ".join(physics[:6]) + ".")
    if geometry:
        transferable.append("Reuse geometry construction patterns when new requirements share shape, import, array, sweep, or boolean operations.")
    if studies:
        transferable.append("Use the learned study types as solver starting points: " + ", ".join(studies[:5]) + ".")
    if results:
        transferable.append("Use detected result nodes as candidate validation and training targets: " + ", ".join(results[:5]) + ".")

    extension_questions = [
        "Which parameters control geometry size, material response, boundary loading, and solver stability?",
        "Which output quantities can be converted into CSV columns for surrogate-model training?",
        "Can the same physics be tested under steady, transient, eigenfrequency, or parametric-sweep studies?",
    ]
    if theory:
        extension_questions.append("How do the theory keywords change governing equations, assumptions, or validation targets: " + ", ".join(theory[:8]) + "?")
    if has_mph:
        extension_questions.append("Can COMSOL/LiveLink export a model-tree summary from the MPH file to verify selections and boundary IDs?")

    code_ideas = [
        "Generate a baseline MATLAB LiveLink builder from the learned parameter and model-tree evidence.",
        "Generate a Java builder with comments on boundary selections that must be verified inside COMSOL.",
        "Create a CSV export script for derived values before training a numerical surrogate.",
    ]
    if has_scripts:
        code_ideas.insert(0, "Use existing MATLAB/Java scripts as the highest-confidence source for API call order.")

    risk_checks = [
        "Boundary IDs and named selections must be verified after geometry changes.",
        "Material properties and units must be checked before using generated scripts for real simulation.",
        "Mesh independence and baseline-solve convergence should be checked before parameter sweeps.",
    ]
    if not has_csv:
        risk_checks.append("No CSV sweep data was detected, so current learning supports reasoning and code generation more than numerical surrogate training.")
    if not has_scripts:
        risk_checks.append("No MATLAB/Java script was detected; generated automation should be reviewed more carefully.")

    readiness_score = 0
    readiness_score += 25 if physics else 0
    readiness_score += 20 if geometry else 0
    readiness_score += 20 if parameters else 0
    readiness_score += 20 if has_scripts else 0
    readiness_score += 15 if has_csv else 0
    readiness = "ready_for_reasoning_and_extension" if readiness_score >= 45 else "needs_more_evidence_for_reliable_extension"

    return {
        "kind": "case_thinking_and_extension",
        "readiness": readiness,
        "readiness_score": readiness_score,
        "transferable_knowledge": _dedupe(transferable, 12),
        "extension_questions": _dedupe(extension_questions, 12),
        "new_model_directions": _dedupe(_extension_directions(physics, theory), 12),
        "parameter_sweep_ideas": _dedupe(_parameter_sweep_ideas(parameters, physics, has_csv), 12),
        "code_generation_ideas": _dedupe(code_ideas, 12),
        "risk_checks": _dedupe(risk_checks, 12),
    }


def _extension_directions(physics: list[str], theory: list[str]) -> list[str]:
    text = " ".join(physics + theory).lower()
    directions = []
    if any(token in text for token in ("heat", "thermal", "temperature", "传热", "温度")):
        directions.extend(
            [
                "Extend to temperature sensitivity studies by sweeping heat source, convection coefficient, and thermal conductivity.",
                "Couple heat transfer with structural stress or electric losses when the requirement includes deformation or Joule heating.",
            ]
        )
    if any(token in text for token in ("solid", "stress", "strain", "mechanics", "结构", "应力")):
        directions.extend(
            [
                "Extend to load-case comparison, stress concentration analysis, and displacement safety checks.",
                "Build a corrected model workflow that separates geometry repair, material assignment, constraints, and load verification.",
            ]
        )
    if any(token in text for token in ("flow", "fluid", "pressure", "laminar", "流体", "压力")):
        directions.extend(
            [
                "Extend to inlet/outlet sensitivity, pressure-drop prediction, and flow-uniformity analysis.",
                "Add coupled transport, porous media, or nonisothermal flow when concentration or temperature fields are involved.",
            ]
        )
    if any(token in text for token in ("electric", "current", "voltage", "magnetic", "电流", "电压")):
        directions.extend(
            [
                "Extend to terminal-current, resistance, field-distribution, and Joule-loss studies.",
                "Use electric-current outputs as coupling sources for thermal or structural models.",
            ]
        )
    if not directions:
        directions.append("Create a similar baseline model, then add one controlled extension at a time: geometry, material, boundary condition, study type, or output target.")
    return directions


def _parameter_sweep_ideas(parameters: list[dict[str, str]], physics: list[str], has_csv: bool) -> list[str]:
    ideas = []
    for param in parameters[:8]:
        name = str(param.get("name", "")).strip()
        if name:
            ideas.append(f"Sweep `{name}` around the learned value `{param.get('value', '')}` and export target outputs to CSV.")
    text = " ".join(physics).lower()
    if "heat" in text or "thermal" in text:
        ideas.append("Sweep heat source, heat-transfer coefficient, thermal conductivity, and ambient temperature.")
    if "solid" in text or "stress" in text:
        ideas.append("Sweep load, Young's modulus, thickness, fixed constraints, and contact/fracture parameters.")
    if "flow" in text or "laminar" in text:
        ideas.append("Sweep inlet velocity, viscosity, density, channel size, and pressure boundary values.")
    if not has_csv:
        ideas.append("Create a COMSOL parametric sweep table first; each row should contain input parameters and derived output quantities.")
    return ideas or ["Define 3-8 important input parameters, run a small design of experiments, and export CSV for local training."]


def _deep_learning_plan(card: dict[str, Any]) -> dict[str, Any]:
    file_summary = card.get("file_summary", {})
    case_content = card.get("case_content", {})
    parameters = card.get("parameters", [])
    source_files = card.get("source_files", [])
    has_csv = file_summary.get("csv_files", 0) > 0
    has_scripts = file_summary.get("matlab_files", 0) > 0 or file_summary.get("java_files", 0) > 0
    has_model_tree = case_content.get("totals", {}).get("model_tree_items", 0) > 0

    candidate_inputs = _candidate_training_inputs(parameters, case_content, source_files)
    candidate_outputs = _candidate_training_outputs(case_content, source_files)
    score = 0
    score += 30 if has_csv else 0
    score += 25 if candidate_inputs else 0
    score += 20 if candidate_outputs else 0
    score += 15 if has_scripts else 0
    score += 10 if has_model_tree else 0

    if has_csv and candidate_inputs and candidate_outputs:
        readiness = "ready_for_local_surrogate_training"
    elif has_scripts and candidate_inputs:
        readiness = "ready_to_generate_comsol_sweep_dataset"
    else:
        readiness = "needs_more_case_evidence_before_training"

    dataset_requirements = [
        "每一行代表一次 COMSOL 参数扫描或验证运行。",
        "输入列应来自案例参数、几何尺寸、材料参数、边界条件或工况变量。",
        "输出列应来自最大值、平均值、积分量、目标函数、误差、位移、应力、温度、流量、电流等可验证结果。",
        "训练前保留单位说明，并把 CSV、约束 JSON、生成脚本和模型报告一起保存为同一个训练记录。",
    ]
    if not has_csv:
        dataset_requirements.insert(0, "当前案例未发现 CSV，需要先用 COMSOL 参数扫描导出训练数据。")

    return {
        "kind": "comsol_case_deep_learning_plan",
        "readiness": readiness,
        "readiness_score": score,
        "candidate_inputs": candidate_inputs,
        "candidate_outputs": candidate_outputs,
        "dataset_requirements": dataset_requirements,
        "model_candidates": [
            "dummy_mean_baseline: 检查数据是否真的有可学习信号。",
            "ridge_scaled: 小样本、近似线性响应的稳健基线。",
            "random_forest: 捕捉非线性和参数交互，适合中小型 COMSOL 扫描表。",
            "mlp_scaled: 用标准化后的神经网络学习连续响应面，需要更多样本并检查收敛。",
        ],
        "workflow": [
            "读取 PDF/MATLAB/Java/MPH/CSV，把案例整理为统一证据包。",
            "从脚本和文本中提取参数、几何、物理场、材料、网格、研究和结果节点。",
            "把候选输入参数转成约束 JSON，并确定扫描范围。",
            "运行 COMSOL 参数扫描，导出包含输入列和目标输出列的 CSV。",
            "对比 baseline、Ridge、RandomForest、MLP，按测试 RMSE/MAE/R2 选择最佳模型。",
            "用未参与训练的新 COMSOL 结果复核代理模型，并把训练报告写回案例记忆库。",
        ],
        "limitations": _deep_learning_limitations(has_csv, candidate_inputs, candidate_outputs, has_scripts),
    }


def _learning_progress(card: dict[str, Any]) -> list[dict[str, Any]]:
    file_summary = card.get("file_summary", {})
    case_content = card.get("case_content", {})
    deep_learning = card.get("deep_learning_plan", {})
    return [
        {"percent": 8, "label": "接收案例目录", "detail": card.get("case_dir", "")},
        {
            "percent": 22,
            "label": "扫描可学习文件",
            "detail": (
                f"文件={file_summary.get('count', 0)}, "
                f"MATLAB={file_summary.get('matlab_files', 0)}, Java={file_summary.get('java_files', 0)}, "
                f"PDF={file_summary.get('pdf_files', 0)}, MPH={file_summary.get('mph_files', 0)}, CSV={file_summary.get('csv_files', 0)}"
            ),
        },
        {
            "percent": 42,
            "label": "抽取 COMSOL 模型树证据",
            "detail": f"模型树证据 {case_content.get('totals', {}).get('model_tree_items', 0)} 条",
        },
        {
            "percent": 62,
            "label": "形成深度学习训练计划",
            "detail": f"准备度={deep_learning.get('readiness', '')}, 分数={deep_learning.get('readiness_score', 0)}",
        },
        {
            "percent": 82,
            "label": "写入案例记忆库",
            "detail": "保存案例摘要、参数、建模逻辑、训练缺口和可复用资产。",
        },
        {"percent": 100, "label": "完成学习总结", "detail": "已生成 JSON、Markdown、索引和可展示的判断依据。"},
    ]


def _candidate_training_inputs(
    parameters: list[dict[str, str]],
    case_content: dict[str, Any],
    source_files: list[dict[str, Any]],
) -> list[str]:
    names: list[str] = []
    for param in parameters:
        name = str(param.get("name", "")).strip()
        if name:
            names.append(name)
    for value in case_content.get("parameters", []):
        token = str(value).split(" / ")[0].strip()
        if token:
            names.append(token)
    for column in _csv_columns(source_files):
        if not _looks_like_output_column(column):
            names.append(column)
    return _dedupe(names, limit=40)


def _candidate_training_outputs(case_content: dict[str, Any], source_files: list[dict[str, Any]]) -> list[str]:
    names = [column for column in _csv_columns(source_files) if _looks_like_output_column(column)]
    text = " ".join(
        str(item)
        for key in ("results", "studies", "physics", "theory_keywords")
        for item in case_content.get(key, [])
    ).lower()
    suggestions = [
        ("Tmax", ("heat", "thermal", "temperature", "传热", "温度")),
        ("Tavg", ("heat", "thermal", "temperature", "传热", "温度")),
        ("max_von_mises_stress", ("stress", "solid", "structural", "应力")),
        ("max_displacement", ("displacement", "solid", "structural", "位移")),
        ("pressure_drop", ("pressure", "flow", "fluid", "压力")),
        ("max_velocity", ("velocity", "flow", "fluid", "速度")),
        ("terminal_current", ("current", "electric", "voltage", "电流")),
        ("objective_value", ("optimization", "objective", "目标")),
    ]
    for name, keywords in suggestions:
        if any(keyword in text for keyword in keywords):
            names.append(name)
    if not names:
        names.extend(["primary_quantity_of_interest", "validation_error"])
    return _dedupe(names, limit=30)


def _csv_columns(source_files: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for file in source_files:
        details = file.get("details", {}) if isinstance(file, dict) else {}
        if file.get("kind") == "csv_table":
            columns.extend(str(column) for column in details.get("columns", []) if str(column).strip())
    return columns


def _looks_like_output_column(name: str) -> bool:
    return bool(
        re.search(
            r"(out|output|result|target|tmax|tavg|temp|temperature|stress|strain|disp|pressure|velocity|flux|current|voltage|loss|power|force|volume|area|error|max|min|avg)",
            name,
            flags=re.IGNORECASE,
        )
    )


def _deep_learning_limitations(
    has_csv: bool,
    candidate_inputs: list[str],
    candidate_outputs: list[str],
    has_scripts: bool,
) -> list[str]:
    limitations = []
    if not has_csv:
        limitations.append("缺少可直接训练的 CSV；当前只能学习建模逻辑，不能完成数值代理模型训练。")
    if not candidate_inputs:
        limitations.append("未识别到足够输入参数，需要补充参数表或从 LiveLink/Java 脚本导出参数。")
    if not candidate_outputs:
        limitations.append("未识别到输出目标，需要指定最大温度、应力、位移、压降、电流等目标量。")
    if not has_scripts:
        limitations.append("缺少 MATLAB/Java 脚本时，自动建模只能依赖文档推断，需要人工复核更多步骤。")
    return limitations or ["当前案例具备开始训练代理模型的基本条件，但仍需用新 COMSOL 运行结果做外部验证。"]


def _reusable_confidence(
    has_scripts: bool,
    has_pdf: bool,
    has_mph: bool,
    parameters: list[dict[str, str]],
    has_csv: bool,
) -> str:
    score = int(has_scripts) + int(has_pdf) + int(has_mph) + int(bool(parameters)) + int(has_csv)
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def _gaps(has_training_csv: bool, has_mph: bool, parameters: list[dict[str, str]]) -> list[str]:
    gaps = []
    if not has_training_csv:
        gaps.append("Missing parameter-sweep CSV for numerical surrogate training.")
    if has_mph:
        gaps.append("MPH files need COMSOL with MATLAB summaries for reliable internal settings.")
    if not parameters:
        gaps.append("No parameter table was detected; parameters may need manual extraction from scripts or PDFs.")
    return gaps or ["No major gap detected from available files."]


def _upsert_index(index_path: Path, card: dict[str, Any], json_path: Path, md_path: Path) -> None:
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {"kind": "comsol_case_knowledge_index", "cases": []}

    entry = {
        "title": card["title"],
        "case_dir": card["case_dir"],
        "training_stage": card["training_stage"],
        "json": str(json_path),
        "markdown": str(md_path),
        "updated_at": card["created_at"],
        "file_summary": card["file_summary"],
    }
    cases = [
        case
        for case in index.get("cases", [])
        if case.get("case_dir") != card["case_dir"] and case.get("title") != card["title"]
    ]
    cases.append(entry)
    index["cases"] = sorted(cases, key=lambda item: item["title"])
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff._-]+", "_", value.strip(), flags=re.UNICODE)
    return slug.strip("_") or "comsol_case"


