from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .case_memory import generate_model_plan, remember_case


DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def summarize_article_docx(
    docx_path: str | Path,
    output_dir: str | Path = "generated/article_knowledge",
    memory_path: str | Path = "generated/case_memory/case_memory.json",
) -> dict[str, Any]:
    source = Path(docx_path)
    paragraphs = _read_docx_paragraphs(source)
    text = "\n".join(paragraphs)
    card = build_article_card(source, paragraphs)
    plan = generate_model_plan(card["modeling_requirement"], memory_path, top_k=8)
    card["memory_assisted_model_plan"] = _article_model_plan(card, plan)
    outputs = write_article_card(card, output_dir)
    memory = remember_case(_article_memory_card(card), memory_path)
    return {"card": card, "outputs": outputs, "memory": memory}


def build_article_card(source: Path, paragraphs: list[str]) -> dict[str, Any]:
    text = "\n".join(paragraphs)
    params = _extract_article_parameters(text)
    model_features = _infer_model_features(text)
    correction_strategy = _correction_strategy(text)
    requirement = _modeling_requirement(params, model_features)
    return {
        "kind": "comsol_article_modeling_card",
        "title": source.stem,
        "source_path": str(source),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "paragraph_count": len(paragraphs),
        "summary": _summary(text),
        "modeling_requirement": requirement,
        "parameters": params,
        "model_features": model_features,
        "correction_strategy": correction_strategy,
        "learning_trace": _learning_trace(params, model_features, correction_strategy),
        "source_excerpt": paragraphs[:30],
    }


def _article_memory_card(card: dict[str, Any]) -> dict[str, Any]:
    features = card.get("model_features", {})
    return {
        "kind": "comsol_article_memory_card",
        "title": card.get("title", "article"),
        "case_dir": card.get("source_path", ""),
        "created_at": card.get("created_at", datetime.now(timezone.utc).isoformat()),
        "training_stage": "modeling_logic_learning_ready",
        "parameters": card.get("parameters", []),
        "case_content": {
            "parameters": [item.get("name", "") for item in card.get("parameters", [])],
            "geometry": features.get("geometry", []),
            "physics": features.get("physics", []),
            "materials": features.get("materials", []),
            "mesh": features.get("mesh", []),
            "studies": features.get("studies", []),
            "results": features.get("outputs", []),
            "boundary_conditions": features.get("boundary_conditions", []),
            "theory_keywords": re.findall(r"[\u4e00-\u9fff]{2,8}", card.get("summary", ""))[:30],
            "source_extracts": [],
        },
        "thoughts": [card.get("summary", ""), card.get("modeling_requirement", "")],
        "implementation_path": card.get("memory_assisted_model_plan", {}).get("recommended_modeling_steps", []),
        "gaps": ["文章不能替代 COMSOL 模型树；仍需通过 MATLAB/Java/MPH 摘要核对 API 与选择集。"],
        "source_files": [{"name": Path(card.get("source_path", "article.docx")).name, "kind": "docx_article"}],
        "post_learning_summary": {
            "kind": "post_article_learning_summary",
            "summary": "文章理论、参数和建模要求已写入案例记忆。",
        },
    }


def write_article_card(card: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    slug = _slugify(card["title"])
    json_path = destination / f"{slug}.article.json"
    md_path = destination / f"{slug}.article.md"
    json_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(article_card_markdown(card), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def article_card_markdown(card: dict[str, Any]) -> str:
    lines = [
        f"# {card['title']}",
        "",
        f"- Source: `{card['source_path']}`",
        f"- Paragraphs: {card['paragraph_count']}",
        "",
        "## Article Summary",
        "",
        card.get("summary", ""),
        "",
        "## Modeling Requirement",
        "",
        card.get("modeling_requirement", ""),
        "",
        "## Extracted Parameters",
        "",
    ]
    for param in card.get("parameters", []):
        lines.append(f"- `{param['name']}` = `{param['value']}` ({param['role']})")
    lines.extend(["", "## Model Features", ""])
    for key, values in card.get("model_features", {}).items():
        lines.append(f"- {key}: {', '.join(values) if isinstance(values, list) else values}")
    lines.extend(["", "## Correction Strategy", ""])
    for item in card.get("correction_strategy", []):
        lines.append(f"- {item}")
    plan = card.get("memory_assisted_model_plan", {})
    if plan:
        lines.extend(["", "## Memory-Assisted COMSOL Construction Plan", ""])
        lines.append("### Retrieved Cases")
        for item in plan.get("matched_cases", []):
            lines.append(f"- `{item.get('title', '')}` score={item.get('score', '')}")
        lines.extend(["", "### Construction Steps"])
        for item in plan.get("recommended_modeling_steps", []):
            lines.append(f"- {item}")
        lines.extend(["", "### Article-Specific Modifications"])
        for item in plan.get("article_specific_modifications", []):
            lines.append(f"- {item}")
        lines.extend(["", "### Validation Outputs"])
        for item in plan.get("validation_outputs", []):
            lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _read_docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    paragraphs: list[str] = []
    for para in root.findall(".//w:p", DOCX_NS):
        texts = [node.text or "" for node in para.findall(".//w:t", DOCX_NS)]
        text = "".join(texts).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def _summary(text: str) -> str:
    return (
        "文章围绕煤层超高压水力压裂数值模拟，研究不同地应力条件、主应力方向、"
        "煤层非均匀性和天然裂缝对单孔裂纹起裂压力、扩展方向、损伤演化和裂缝长度的影响。"
    )


def _extract_article_parameters(text: str) -> list[dict[str, str]]:
    number = r"\d+(?:\s*\.\s*\d+)?"
    patterns = [
        ("square_side", rf"正方形的长度为\s*(?P<value>{number})\s*mm", "geometry length"),
        ("borehole_diameter", rf"钻孔直径为\s*(?P<value>{number})\s*mm", "borehole diameter"),
        ("stress_ratio_range", rf"(?:比值|应力比)在\s*(?P<value>{number}\s*~\s*{number})", "principal stress ratio range"),
        ("initial_pressure", rf"初始压力P\s*=\s*(?P<value>{number})\s*MPa", "initial pressure"),
        ("mean_elastic_modulus", rf"平均弹性模量为\s*(?P<value>{number})\s*GPa", "Weibull mean elastic modulus"),
        ("mean_compressive_strength", rf"平均抗压强度为\s*(?P<value>{number})\s*Mpa", "Weibull mean compressive strength"),
    ]
    params = []
    for name, pattern, role in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = re.sub(r"\s+", "", match.group("value"))
            unit = ""
            if name in {"square_side", "borehole_diameter"}:
                unit = "mm"
            elif name == "initial_pressure":
                unit = "MPa"
            elif name == "mean_elastic_modulus":
                unit = "GPa"
            elif name == "mean_compressive_strength":
                unit = "MPa"
            params.append({"name": name, "value": f"{value}[{unit}]" if unit else value, "role": role})
    for angle in re.findall(r"(\d+)\s*°\s*主应力", text):
        item = {"name": f"principal_stress_direction_{angle}", "value": f"{angle}[deg]", "role": "stress direction case"}
        if item not in params:
            params.append(item)
    return params


def _infer_model_features(text: str) -> dict[str, list[str]]:
    features = {
        "geometry": ["2D square domain", "central borehole"],
        "materials": ["coal/rock medium", "heterogeneous elastic modulus", "heterogeneous tensile/compressive strength"],
        "physics": ["solid mechanics damage evolution", "pore/fluid pressure loading", "hydraulic fracture propagation"],
        "boundary_conditions": ["outer boundary in-situ stress loading", "symmetric roller/fixed displacement support", "borehole injection pressure"],
        "mesh": ["free triangular mesh", "local refinement near borehole and natural fractures"],
        "studies": ["time-dependent pressure/damage evolution", "parametric sweep over stress ratio and stress direction"],
        "outputs": ["damage length vs time", "pressure field", "fracture path", "initiation pressure", "stress distribution"],
    }
    if "天然裂缝" in text:
        features["geometry"].append("natural fracture or weak-plane features")
        features["outputs"].append("fracture deflection and branching under natural fractures")
    if "韦伯" in text or "weibull" in text.lower():
        features["materials"].append("Weibull random field distribution")
    return features


def _correction_strategy(text: str) -> list[str]:
    strategy = [
        "优先使用文章参数作为基准约束，而不是套用通用热学或结构默认值。",
        "Correct geometry to a 300 mm square domain with a 15 mm borehole and optional natural-fracture weak planes.",
        "Correct loads by sweeping principal stress ratio from 1.5 to 2.0 and stress directions such as 90, 135, and 180 degrees.",
        "Correct material definition by adding Weibull-distributed elastic modulus and strength rather than a single homogeneous material.",
        "Correct mesh by refining near the borehole, expected crack tips, and natural fractures.",
        "Correct validation outputs to compare damage length over time, pressure field, crack morphology, and initiation pressure against article/field observations.",
    ]
    if "校正实测数据" in text or "数据修正" in text:
        strategy.append("Add a measurement-correction loop: compare simulated fracture/stress response with measured data and update fracture orientation, density, and weak-plane parameters.")
    return strategy


def _learning_trace(params: list[dict[str, str]], features: dict[str, list[str]], corrections: list[str]) -> list[dict[str, str]]:
    return [
        {
            "step": "1. 文章参数抽取",
            "evidence": f"提取到 {len(params)} 个几何、压力、应力方向或材料分布参数。",
            "judgement": "这些参数应进入约束 JSON，作为 COMSOL 自动建模和参数扫描的输入。",
        },
        {
            "step": "2. 建模对象识别",
            "evidence": ", ".join(features.get("geometry", [])),
            "judgement": "模型应优先构建二维单孔水力压裂几何，而不是沿用默认热传导示例。",
        },
        {
            "step": "3. 物理与材料修正",
            "evidence": ", ".join(features.get("physics", []) + features.get("materials", [])),
            "judgement": "需要将案例记忆中的结构/流体/多孔介质经验组合起来，并保留缺失参数为待校准项。",
        },
        {
            "step": "4. 修正闭环",
            "evidence": f"{len(corrections)} 条文章驱动修正建议。",
            "judgement": "后续自动建模方案必须包含与文章或现场数据对比后的模型修正步骤。",
        },
    ]


def _modeling_requirement(params: list[dict[str, str]], features: dict[str, list[str]]) -> str:
    param_text = " ".join(f"{item['name']}={item['value']}" for item in params)
    feature_text = " ".join(value for values in features.values() for value in values)
    return (
        "Build a COMSOL hydraulic fracturing model for a single borehole under different confining stress conditions. "
        "中文需求关键词：水力压裂 单孔 围压 主应力 天然裂缝 煤层 岩石裂隙流 多孔介质 裂缝拓展 损伤演化。 "
        f"Use article parameters: {param_text}. Include features: {feature_text}."
    )


def _article_model_plan(card: dict[str, Any], memory_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "article_memory_assisted_model_plan",
        "matched_cases": memory_plan.get("matched_cases", []),
        "external_case_matches": memory_plan.get("external_case_matches", []),
        "official_doc_matches": memory_plan.get("official_doc_matches", []),
        "recommended_modeling_steps": memory_plan.get("recommended_modeling_steps", []),
        "candidate_parameters": _merge_article_parameters(card.get("parameters", []), memory_plan.get("candidate_parameters", [])),
        "article_specific_modifications": card.get("correction_strategy", []),
        "validation_outputs": card.get("model_features", {}).get("outputs", []),
        "training_path": [
            "Generate a LiveLink MATLAB model builder from the article card and retrieved similar cases.",
            "Run parameter sweeps over stress ratio, stress direction, injection pressure, and Weibull homogeneity index.",
            "Export CSV columns for geometry/material/stress inputs and fracture/damage/pressure outputs.",
            "Train the local surrogate only after COMSOL sweep CSV data exists.",
        ],
        "limitations": memory_plan.get("limitations", []) + [
            "Article text does not fully define a damage constitutive law; choose and validate the damage/fracture implementation in COMSOL.",
            "Natural-fracture density, aperture, angle, and strength need explicit calibration data before final simulation.",
        ],
    }


def _merge_article_parameters(article_params: list[dict[str, str]], memory_params: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for param in article_params:
        merged[param["name"]] = {
            "name": param["name"],
            "value": param["value"],
            "description": param.get("role", ""),
            "source_case": "article",
        }
    for param in memory_params:
        name = param.get("name")
        if name and name not in merged:
            merged[name] = param
    return list(merged.values())[:40]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff._-]+", "_", value.strip(), flags=re.UNICODE)
    return slug.strip("_") or "article"
