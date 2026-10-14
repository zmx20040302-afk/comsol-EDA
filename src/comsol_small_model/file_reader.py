from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .matlab_reader import inspect_matlab_file


TEXT_EXTENSIONS = {".txt", ".md", ".log", ".py", ".json", ".csv", ".m"}
PDF_MAX_PAGES = 50
PDF_ANALYSIS_CHARS = 50000
PPTX_MAX_SLIDES = 80
MODEL_FEATURE_PATTERNS = {
    "parameters": [
        r"model\.param\.set\(\s*'([^']+)'",
        r"\.param\(\)\.set\(\s*\"([^\"]+)\"",
        r"inputParam\.set\(\s*'([^']+)'",
        r"inputParam\(\)\.set\(\s*\"([^\"]+)\"",
    ],
    "geometry": [
        r"\.geom(?:\(\)|\('[^']+'\)|\(\"[^\"]+\"\))?\.create\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
        r"\.geom\(['\"]([^'\"]+)['\"]\)\.feature\(['\"]([^'\"]+)['\"]\)\.set\(['\"]([^'\"]+)['\"]",
    ],
    "physics": [
        r"\.physics\.create\(\s*'([^']+)'\s*,\s*'([^']+)'",
        r"\.physics\(\)\.create\(\s*\"([^\"]+)\"\s*,\s*\"([^\"]+)\"",
    ],
    "materials": [
        r"\.material(?:\(\)|\('[^']+'\)|\(\"[^\"]+\"\))?\.create\(\s*['\"]([^'\"]+)['\"]",
        r"\.material\(['\"]([^'\"]+)['\"]\)\.propertyGroup",
    ],
    "mesh": [
        r"\.mesh(?:\(\)|\('[^']+'\)|\(\"[^\"]+\"\))?\.create\(\s*['\"]([^'\"]+)['\"]",
        r"\.mesh\(['\"]([^'\"]+)['\"]\)\.feature\(['\"]([^'\"]+)['\"]\)\.set\(['\"]([^'\"]+)['\"]",
    ],
    "studies": [
        r"\.study\(['\"]([^'\"]+)['\"]\)\.create\(['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",
        r"\.study\(\)\.create\(\s*\"([^\"]+)\"",
    ],
    "results": [
        r"\.result(?:\(\)|\('[^']+'\)|\(\"[^\"]+\"\))?\.create\(\s*['\"]([^'\"]+)['\"]",
        r"\.result\.numerical\.create\(\s*'([^']+)'\s*,\s*'([^']+)'",
        r"\.result\(\)\.numerical\(\)\.create\(\s*\"([^\"]+)\"\s*,\s*\"([^\"]+)\"",
    ],
    "boundary_conditions": [
        r"\.feature\(['\"]([^'\"]+)['\"]\)\.selection\.set\(([^)]*)\)",
        r"\.feature\(\"([^\"]+)\"\)\.selection\(\)\.set\(([^)]*)\)",
        r"\.feature\(['\"]([^'\"]+)['\"]\)\.set\(['\"]([^'\"]+)['\"]",
    ],
}


@dataclass(frozen=True)
class FileSummary:
    name: str
    kind: str
    size_bytes: int
    details: dict[str, Any]
    preview: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize_file(path: str | Path, preview_chars: int = 4000) -> FileSummary:
    source = Path(path)
    suffix = source.suffix.lower()
    size = source.stat().st_size

    if suffix == ".m":
        matlab = inspect_matlab_file(source)
        text = _read_text_preview(source, preview_chars)
        return FileSummary(
            name=source.name,
            kind="matlab_livelink",
            size_bytes=size,
            details={
                "parameters": len(matlab.parameters),
                "physics": matlab.physics,
                "studies": matlab.studies,
                "results": matlab.results,
                "content_extract": extract_model_content(text, "matlab_livelink"),
            },
            preview=text,
        )

    if suffix == ".csv":
        details, preview = _summarize_csv(source, preview_chars)
        return FileSummary(source.name, "csv_table", size, details, preview)

    if suffix == ".java":
        text = _read_text_preview(source, preview_chars)
        details = _summarize_java_text(text)
        details["content_extract"] = extract_model_content(text, "comsol_java")
        return FileSummary(source.name, "comsol_java", size, details, text)

    if suffix == ".pdf":
        details, preview = _summarize_pdf(source, preview_chars)
        details["content_extract"] = extract_model_content(preview, "pdf_document")
        details["simple_summary"] = _pdf_simple_summary(source.name, details, preview)
        return FileSummary(source.name, "pdf_document", size, details, preview)

    if suffix == ".pptx":
        details, preview = _summarize_pptx(source, preview_chars)
        details["content_extract"] = extract_model_content(preview, "presentation_document")
        return FileSummary(source.name, "presentation_document", size, details, preview)

    if suffix == ".json":
        text = _read_text_preview(source, preview_chars)
        details = _summarize_json_text(text)
        details["content_extract"] = extract_model_content(text, "json")
        return FileSummary(source.name, "json", size, details, text)

    if suffix == ".mph":
        details, preview = _summarize_mph_model(source, preview_chars)
        return FileSummary(
            name=source.name,
            kind="comsol_mph",
            size_bytes=size,
            details=details,
            preview=preview,
        )

    if suffix in TEXT_EXTENSIONS:
        text = _read_text_preview(source, preview_chars)
        return FileSummary(source.name, "text", size, {"content_extract": extract_model_content(text, "text")}, text)

    return FileSummary(
        name=source.name,
        kind="unknown",
        size_bytes=size,
        details={"readable": False},
        preview="Unsupported file type for direct preview.",
    )


def summarize_files(paths: list[str | Path], preview_chars: int = 4000) -> dict[str, Any]:
    summaries = [summarize_file(path, preview_chars=preview_chars).as_dict() for path in paths]
    return summarize_collection(summaries)


def summarize_uploaded_text(name: str, content: str, preview_chars: int = 4000) -> FileSummary:
    suffix = Path(name).suffix.lower()
    encoded_size = len(content.encode("utf-8", errors="replace"))

    if suffix == ".json":
        return FileSummary(name, "json", encoded_size, _summarize_json_text(content), content[:preview_chars])

    if suffix == ".csv":
        rows = list(csv.reader(content.splitlines()))
        header = rows[0] if rows else []
        return FileSummary(
            name,
            "csv_table",
            encoded_size,
            {"columns": header, "rows_seen": max(0, len(rows) - 1), "source": "browser_upload"},
            content[:preview_chars],
        )

    if suffix == ".m":
        content_extract = extract_model_content(content, "matlab_text")
        return FileSummary(
            name,
            "matlab_text",
            encoded_size,
            {
                "parameter_mentions": content.count("model.param.set"),
                "physics_mentions": content.count(".physics.create"),
                "study_mentions": content.count(".study("),
                "content_extract": content_extract,
            },
            content[:preview_chars],
        )

    if suffix == ".java":
        details = _summarize_java_text(content)
        details["content_extract"] = extract_model_content(content, "comsol_java")
        return FileSummary(name, "comsol_java", encoded_size, details, content[:preview_chars])

    if suffix == ".pdf":
        details = {
            "readable": False,
            "source": "browser_upload",
            "reason": "Browser text upload cannot decode binary PDFs.",
        }
        details["simple_summary"] = _pdf_simple_summary(name, details, "")
        return FileSummary(
            name,
            "pdf_document",
            encoded_size,
            details,
            "Use path-based reading for PDFs so Python can extract text with pypdf or pdfplumber.",
        )

    if suffix == ".mph":
        return FileSummary(
            name,
            "comsol_mph",
            encoded_size,
            {"readable": False, "source": "browser_upload"},
            "Uploaded .mph content cannot be decoded in the browser path. Export a summary with COMSOL LiveLink.",
        )

    return FileSummary(name, "text", encoded_size, {"content_extract": extract_model_content(content, "text")}, content[:preview_chars])


def summarize_uploaded_binary(name: str, content: bytes, preview_chars: int = 4000) -> FileSummary:
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        details, preview = _summarize_pdf_bytes(content, preview_chars)
        details["source"] = "browser_binary_upload"
        details["content_extract"] = extract_model_content(preview, "pdf_document")
        details["simple_summary"] = _pdf_simple_summary(name, details, preview)
        return FileSummary(name, "pdf_document", len(content), details, preview)
    if suffix == ".mph":
        return FileSummary(
            name,
            "comsol_mph",
            len(content),
            {
                "readable": False,
                "binary_model": True,
                "source": "browser_binary_upload",
                "direct_read_supported": False,
                "recommendation": (
                    "MPH 已作为二进制模型识别。请使用扩展版 export_mph_summary.m "
                    "通过 COMSOL LiveLink 导出模型树摘要。"
                ),
            },
            "COMSOL MPH binary detected; internal model-tree extraction requires COMSOL API.",
        )
    text = content.decode("utf-8", errors="replace")
    return summarize_uploaded_text(name, text, preview_chars=preview_chars)


def summarize_uploaded_texts(files: list[dict[str, str]], preview_chars: int = 4000) -> dict[str, Any]:
    summaries = [
        summarize_uploaded_text(
            str(file.get("name", "uploaded.txt")),
            str(file.get("content", "")),
            preview_chars=preview_chars,
        ).as_dict()
        for file in files
    ]
    return summarize_collection(summaries)


def summarize_collection(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    kinds: dict[str, int] = {}
    total_size = 0
    for summary in summaries:
        kind = str(summary.get("kind", "unknown"))
        kinds[kind] = kinds.get(kind, 0) + 1
        total_size += int(summary.get("size_bytes", 0))

    return {
        "name": f"{len(summaries)} files",
        "kind": "file_collection",
        "size_bytes": total_size,
        "details": {
            "count": len(summaries),
            "kinds": kinds,
            "matlab_files": kinds.get("matlab_livelink", 0) + kinds.get("matlab_text", 0),
            "csv_files": kinds.get("csv_table", 0),
            "json_files": kinds.get("json", 0),
            "mph_files": kinds.get("comsol_mph", 0),
            "pdf_files": kinds.get("pdf_document", 0),
            "pptx_files": kinds.get("presentation_document", 0),
            "java_files": kinds.get("comsol_java", 0),
        },
        "files": summaries,
        "preview": _collection_preview(summaries),
    }


def build_learning_summary(summary: dict[str, Any]) -> dict[str, Any]:
    files = summary.get("files") if summary.get("kind") == "file_collection" else [summary]
    if not isinstance(files, list):
        files = []

    grouped = {
        "comsol_models": [],
        "matlab_builders": [],
        "java_exports": [],
        "pdf_documents": [],
        "presentation_documents": [],
        "training_tables": [],
        "constraints_or_metadata": [],
        "other": [],
    }

    for file in files:
        kind = file.get("kind", "unknown")
        item = _learning_item(file)
        if kind == "comsol_mph":
            grouped["comsol_models"].append(item)
        elif kind in {"matlab_livelink", "matlab_text"}:
            grouped["matlab_builders"].append(item)
        elif kind == "comsol_java":
            grouped["java_exports"].append(item)
        elif kind == "pdf_document":
            grouped["pdf_documents"].append(item)
        elif kind == "presentation_document":
            grouped["presentation_documents"].append(item)
        elif kind == "csv_table":
            grouped["training_tables"].append(item)
        elif kind == "json":
            grouped["constraints_or_metadata"].append(item)
        else:
            grouped["other"].append(item)

    recommendations = []
    if grouped["matlab_builders"] or grouped["java_exports"]:
        recommendations.append("Use MATLAB/Java sources to recover COMSOL parameter names, physics interfaces, studies, and result settings.")
    if grouped["pdf_documents"]:
        recommendations.append("Use PDFs as learning context: problem definition, assumptions, governing equations, validation targets, and expected results.")
    if grouped["presentation_documents"]:
        recommendations.append("Use presentation slides as concise case context: objectives, assumptions, validation figures, and conclusions.")
    if grouped["training_tables"]:
        recommendations.append("Use CSV tables as surrogate model datasets after confirming input/output columns and units.")
    if grouped["comsol_models"]:
        recommendations.append("Use COMSOL with MATLAB to export .mph summaries before automatic reasoning over the full model tree.")
    if grouped["constraints_or_metadata"]:
        recommendations.append("Use JSON files as constraints, exported metadata, or saved model summaries.")

    pdf_simple_summaries = _pdf_simple_summaries(files)

    return {
        "kind": "learning_summary",
        "source": summary.get("name", "file"),
        "groups": grouped,
        "pdf_simple_summaries": pdf_simple_summaries,
        "recommendations": recommendations,
        "comsol_modeling_logic": [
            "A COMSOL model is a structured finite element record: parameters, geometry, selections, materials, physics features, boundary conditions, mesh, study/solver, results, and exports.",
            "PDF documents provide theory and validation context; MATLAB/Java files provide executable model-tree evidence; MPH summaries provide authoritative metadata; CSV files provide trainable numerical behavior.",
            "小模型不应猜测缺失设置；应引用已有文件证据，明确标注未知项，只根据已验证记录生成带约束的建模脚本。",
        ],
        "workflow": [
            "Read related PDF, MATLAB, Java, MPH summary, and CSV files together.",
            "Extract physics, parameters, geometry, boundary conditions, mesh, solver, and result outputs.",
            "校验或创建约束 JSON。",
            "Generate a LiveLink MATLAB builder script.",
            "Run COMSOL sweeps and export CSV data.",
            "Train and validate the surrogate model.",
        ],
    }


def _collection_preview(summaries: list[dict[str, Any]]) -> str:
    lines = []
    for summary in summaries:
        lines.append(
            f"- {summary.get('name', 'file')} [{summary.get('kind', 'unknown')}], "
            f"{summary.get('size_bytes', 0)} bytes"
        )
    return "\n".join(lines)


def _pdf_simple_summaries(files: list[dict[str, Any]]) -> list[dict[str, str]]:
    summaries = []
    for file in files:
        if file.get("kind") != "pdf_document":
            continue
        details = file.get("details", {}) if isinstance(file, dict) else {}
        if not isinstance(details, dict):
            details = {}
        summaries.append(
            {
                "name": str(file.get("name", "file.pdf")),
                "summary": str(
                    details.get("simple_summary")
                    or _pdf_simple_summary(
                        str(file.get("name", "file.pdf")),
                        details,
                        str(file.get("preview", "")),
                    )
                ),
            }
        )
    return summaries


def _pdf_simple_summary(name: str, details: dict[str, Any], preview: str) -> str:
    extract = details.get("content_extract", {}) if isinstance(details, dict) else {}
    if not isinstance(extract, dict):
        extract = {}
    physics = [str(item) for item in extract.get("physics", []) if str(item).strip()]
    studies = [str(item) for item in extract.get("studies", []) if str(item).strip()]
    theory = [str(item) for item in extract.get("theory_keywords", []) if str(item).strip()]
    content_lines = [
        re.sub(r"\s+", " ", str(item).strip())
        for item in extract.get("content_summary", [])
        if str(item).strip()
    ]
    if not content_lines:
        content_lines = _plain_summary_lines(preview)

    if not details.get("readable", False) and not preview.strip():
        return f"{name}: 已识别为 PDF 文件，但当前无法提取正文；需要使用路径读取并安装 pypdf 或 pdfplumber 后再学习其理论内容。"
    if not preview.strip() and not content_lines:
        return f"{name}: PDF 已被识别，但没有提取到可用文本；可作为案例说明文档记录，详细理论需要重新提取正文。"

    focus = ""
    if physics:
        focus = "，主要物理场线索为 " + "、".join(physics[:3])
    elif theory:
        focus = "，理论关键词为 " + "、".join(theory[:3])
    study_part = f"，研究类型线索为 {'、'.join(studies[:2])}" if studies else ""
    text_hint = "；".join(content_lines[:2])
    if text_hint:
        return f"{name}: 该 PDF 主要用于说明案例背景、建模目标、理论假设和验证结果{focus}{study_part}；核心内容可概括为：{text_hint}"
    return f"{name}: 该 PDF 主要用于说明案例背景、建模目标、理论假设和验证结果{focus}{study_part}。"


def _plain_summary_lines(text: str, limit: int = 2) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw.strip())
        if len(line) < 18:
            continue
        if line.lower().startswith(("model created", "application library", "introduction", "results")):
            lines.append(line[:220])
        elif any(token in line.lower() for token in ("model", "equation", "boundary", "result", "physics", "study", "geometry")):
            lines.append(line[:220])
        if len(lines) >= limit:
            break
    if lines:
        return lines
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw.strip())
        if len(line) >= 18:
            lines.append(line[:220])
        if len(lines) >= limit:
            break
    return lines


def _read_text_preview(path: Path, preview_chars: int) -> str:
    return path.read_text(encoding="utf-8", errors="replace")[:preview_chars]


def _summarize_csv(path: Path, preview_chars: int) -> tuple[dict[str, Any], str]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        rows = list(csv.reader(handle))
    header = rows[0] if rows else []
    sample_rows = rows[1:6] if len(rows) > 1 else []
    preview_lines = [",".join(row) for row in rows[: min(len(rows), 8)]]
    return (
        {"columns": header, "rows": max(0, len(rows) - 1), "sample_rows": sample_rows},
        "\n".join(preview_lines)[:preview_chars],
    )


def _summarize_json_text(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"valid": False, "error": str(exc)}
    if isinstance(parsed, dict):
        return {"valid": True, "type": "object", "keys": list(parsed.keys())[:40]}
    if isinstance(parsed, list):
        return {"valid": True, "type": "array", "items": len(parsed)}
    return {"valid": True, "type": type(parsed).__name__}


def _summarize_mph_model(path: Path, preview_chars: int) -> tuple[dict[str, Any], str]:
    sidecars = _mph_sidecar_files(path)
    evidence_texts = []
    sidecar_details = []
    for sidecar in sidecars:
        try:
            text = _read_text_preview(sidecar, preview_chars)
        except OSError:
            continue
        evidence_texts.append(f"## {sidecar.name}\n{text}")
        sidecar_details.append(
            {
                "name": sidecar.name,
                "kind": _sidecar_kind(sidecar),
                "size_bytes": sidecar.stat().st_size,
            }
        )

    evidence_text = "\n\n".join(evidence_texts)
    if evidence_text:
        preview = evidence_text[:preview_chars]
        content_extract = extract_model_content(evidence_text, "comsol_mph_sidecar")
        recommendation = "MPH is binary, but related MATLAB/Java/JSON sidecar evidence was loaded for model-tree learning."
    else:
        preview = "COMSOL .mph is a proprietary binary model file. Direct Python parsing is not reliable."
        content_extract = extract_model_content(path.stem, "comsol_mph_name")
        recommendation = "Use COMSOL with MATLAB and matlab/export_mph_summary.m to export a JSON summary next to this .mph file."

    return (
        {
            "readable": False,
            "binary_model": True,
            "sidecar_files": sidecar_details,
            "sidecar_count": len(sidecar_details),
            "content_extract": content_extract,
            "recommendation": recommendation,
        },
        preview,
    )


def _summarize_pptx(path: Path, preview_chars: int) -> tuple[dict[str, Any], str]:
    """Extract visible text from PPTX slides without requiring PowerPoint."""
    try:
        with zipfile.ZipFile(path) as archive:
            slide_names = sorted(
                (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
                key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),
            )[:PPTX_MAX_SLIDES]
            slides = []
            for name in slide_names:
                root = ElementTree.fromstring(archive.read(name))
                text = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t")).strip()
                if text:
                    slides.append(text)
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        return ({"readable": False, "error": str(exc), "slide_count": 0}, "PPTX 内容无法读取。")

    preview = "\n".join(f"第 {index + 1} 页：{text}" for index, text in enumerate(slides))[:preview_chars]
    return (
        {
            "readable": True,
            "slide_count": len(slide_names),
            "slides_with_text": len(slides),
            "text_characters": sum(len(text) for text in slides),
        },
        preview or "PPTX 未提取到可见文字；可能主要包含图片、公式或图表。",
    )


def _mph_sidecar_files(path: Path) -> list[Path]:
    candidates = []
    stem = path.stem
    for suffix in (".m", ".java", ".json", ".txt", ".md"):
        candidates.extend(path.parent.glob(f"{stem}*{suffix}"))
    candidates.extend(path.parent.glob(f"*{stem}*summary*.json"))
    candidates.extend(path.parent.glob(f"*{stem}*model*.json"))
    return sorted({item.resolve() for item in candidates if item.is_file() and item.resolve() != path.resolve()})


def _sidecar_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".m":
        return "matlab_livelink_sidecar"
    if suffix == ".java":
        return "comsol_java_sidecar"
    if suffix == ".json":
        return "mph_summary_json"
    return "mph_text_sidecar"


def _summarize_java_text(text: str) -> dict[str, Any]:
    return {
        "model_param_set": text.count(".param().set(") + text.count(".param.set("),
        "physics_create": text.count(".physics().create(") + text.count(".physics.create("),
        "study_create": text.count(".study().create(") + text.count(".study.create("),
        "result_create": text.count(".result().create(") + text.count(".result.create("),
        "mesh_mentions": text.count(".mesh(") + text.count(".mesh()."),
        "material_mentions": text.count(".material(") + text.count(".material()."),
    }


def extract_model_content(text: str, kind: str = "text") -> dict[str, Any]:
    normalized = text[:50000]
    physics = _extract_pattern_values(normalized, MODEL_FEATURE_PATTERNS["physics"])
    physics.extend(_text_physics_hints(normalized))
    studies = _extract_pattern_values(normalized, MODEL_FEATURE_PATTERNS["studies"])
    studies.extend(_text_study_hints(normalized))
    extract = {
        "kind": "case_content_extract",
        "source_kind": kind,
        "parameters": _extract_pattern_values(normalized, MODEL_FEATURE_PATTERNS["parameters"]),
        "geometry": _extract_pattern_values(normalized, MODEL_FEATURE_PATTERNS["geometry"]),
        "physics": _dedupe_text(physics, 30),
        "materials": _extract_pattern_values(normalized, MODEL_FEATURE_PATTERNS["materials"]),
        "mesh": _extract_pattern_values(normalized, MODEL_FEATURE_PATTERNS["mesh"]),
        "studies": _dedupe_text(studies, 30),
        "results": _extract_pattern_values(normalized, MODEL_FEATURE_PATTERNS["results"]),
        "boundary_conditions": _extract_pattern_values(normalized, MODEL_FEATURE_PATTERNS["boundary_conditions"]),
        "theory_keywords": _theory_keywords(normalized),
        "content_summary": _content_summary(normalized),
    }
    extract["evidence_score"] = sum(
        len(extract[key])
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
    )
    return extract


def _extract_pattern_values(text: str, patterns: list[str], limit: int = 30) -> list[str]:
    values: list[str] = []
    seen = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            groups = [group.strip() for group in match.groups() if group and group.strip()]
            value = " / ".join(groups) if groups else match.group(0).strip()
            value = re.sub(r"\s+", " ", value)[:180]
            if value and value not in seen:
                seen.add(value)
                values.append(value)
            if len(values) >= limit:
                return values
    return values


def _text_physics_hints(text: str) -> list[str]:
    lowered = text.lower()
    hints = [
        ("Coefficient Form PDE", ("coefficient form pde", "系数形式偏微分方程")),
        ("General Form PDE", ("general form pde", "通用形式偏微分方程")),
        ("Weak Form PDE", ("weak form pde", "弱形式偏微分方程")),
        ("Heat Transfer", ("heat transfer", "传热", "温度场", "热传导", "导热", "对流换热", "辐射传热")),
        ("Solid Mechanics", ("solid mechanics", "固体力学", "结构力学", "应力", "应变", "位移")),
        ("Laminar Flow", ("laminar flow", "层流", "不可压缩流", "navier-stokes")),
        ("Turbulent Flow", ("turbulent flow", "湍流")),
        ("Transport of Diluted Species", ("transport of diluted species", "稀物质传递", "稀释物质传递", "浓度场")),
        ("Electric Currents", ("electric currents", "电流", "电势", "电压", "焦耳热")),
        ("Electrostatics", ("electrostatics", "静电", "电场")),
        ("Magnetic Fields", ("magnetic fields", "磁场", "磁通密度")),
        ("Pressure Acoustics", ("pressure acoustics", "压力声学", "声压", "声学")),
        ("Global ODEs and DAEs", ("global odes and daes", "全局 ode", "全局方程")),
        ("Domain ODEs and DAEs", ("domain odes and daes", "域 ode")),
        ("Optimization", ("optimization", "优化", "目标函数", "灵敏度")),
        ("Particle Tracing", ("particle tracing", "粒子追踪", "颗粒轨迹")),
        ("Ray Optics", ("ray optics", "射线光学")),
        ("Electromagnetic Waves", ("electromagnetic waves", "电磁波", "射频")),
    ]
    return [label for label, words in hints if any(word.lower() in lowered for word in words)]


def _text_study_hints(text: str) -> list[str]:
    lowered = text.lower()
    hints = [
        ("Stationary", ("stationary", "稳态")),
        ("Time Dependent", ("time dependent", "瞬态", "时间依赖")),
        ("Eigenvalue", ("eigenvalue", "特征值")),
        ("Eigenfrequency", ("eigenfrequency", "特征频率", "特征模态")),
        ("Frequency Domain", ("frequency domain", "频域")),
        ("Parametric Sweep", ("parametric sweep", "参数化扫描", "参数扫描")),
        ("Optimization", ("optimization", "优化")),
    ]
    return [label for label, words in hints if any(word.lower() in lowered for word in words)]


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


def _theory_keywords(text: str) -> list[str]:
    keywords = {
        "传热": ["heat transfer", "thermal", "temperature", "conduction", "convection", "radiation", "传热", "温度", "导热", "对流", "辐射"],
        "结构力学": ["solid mechanics", "stress", "strain", "displacement", "von mises", "结构", "应力", "应变", "位移"],
        "流体": ["fluid", "laminar", "turbulent", "velocity", "pressure", "navier", "流体", "层流", "湍流", "速度", "压力"],
        "电磁": ["electric", "current", "voltage", "magnetic", "电流", "电压", "电场", "磁场"],
        "声学": ["acoustic", "sound pressure", "eigenfrequency", "声学", "声压", "特征频率"],
        "多孔介质/裂隙": ["porous", "fracture", "darcy", "permeability", "hydraulic", "多孔", "裂隙", "裂纹", "渗透", "水力压裂"],
        "优化/参数扫描": ["optimization", "parametric sweep", "sensitivity", "优化", "参数扫描", "灵敏度"],
    }
    lowered = text.lower()
    found = []
    for label, words in keywords.items():
        if any(word.lower() in lowered for word in words):
            found.append(label)
    chinese_keywords = {
        "传热": ["传热", "温度", "导热", "对流", "辐射"],
        "结构力学": ["固体力学", "结构力学", "应力", "应变", "位移"],
        "流体": ["流体", "层流", "湍流", "速度", "压力"],
        "电磁": ["电流", "电压", "电场", "磁场", "焦耳热"],
        "声学": ["声学", "声压", "特征频率"],
        "PDE/方程建模": ["偏微分方程", "系数形式", "弱形式", "方程"],
        "量子/特征值": ["量子", "薛定谔", "特征值", "波函数", "能级"],
        "多孔介质/裂隙": ["多孔", "裂隙", "裂纹", "渗透", "水力压裂"],
        "优化/参数扫描": ["优化", "参数扫描", "灵敏度"],
    }
    for label, words in chinese_keywords.items():
        if label not in found and any(word.lower() in lowered for word in words):
            found.append(label)
    return found


def _content_summary(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw.strip())
        if not line:
            continue
        if any(token in line.lower() for token in ("model.", "physics", "geom", "study", "mesh", "result", "参数", "几何", "边界", "方程", "材料")):
            lines.append(line[:240])
        if len(lines) >= 12:
            break
    return lines


def _summarize_pdf(path: Path, preview_chars: int) -> tuple[dict[str, Any], str]:
    try:
        return _summarize_pdf_with_pypdf(path, preview_chars)
    except ModuleNotFoundError:
        try:
            return _summarize_pdf_with_pdfplumber(path, preview_chars)
        except ModuleNotFoundError as exc:
            return (
                {
                    "readable": False,
                    "missing_dependency": exc.name,
                    "recommendation": "安装 pypdf 或 pdfplumber 以提取 PDF 文本。",
                },
                "PDF detected. Text extraction requires pypdf or pdfplumber.",
            )
    except Exception as exc:  # noqa: BLE001
        return ({"readable": False, "error": str(exc)}, "PDF detected, but text extraction failed.")


def _summarize_pdf_with_pypdf(path: Path, preview_chars: int) -> tuple[dict[str, Any], str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    texts = []
    for page in reader.pages[:PDF_MAX_PAGES]:
        texts.append(page.extract_text() or "")
        if sum(len(item) for item in texts) >= PDF_ANALYSIS_CHARS:
            break
    text = "\n".join(texts).strip()
    return (
        {"readable": True, "pages": len(reader.pages), "extractor": "pypdf", "preview_pages": len(texts)},
        text[: max(preview_chars, PDF_ANALYSIS_CHARS)],
    )


def _summarize_pdf_with_pdfplumber(path: Path, preview_chars: int) -> tuple[dict[str, Any], str]:
    import pdfplumber

    texts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:PDF_MAX_PAGES]:
            texts.append(page.extract_text() or "")
            if sum(len(item) for item in texts) >= PDF_ANALYSIS_CHARS:
                break
        page_count = len(pdf.pages)
    text = "\n".join(texts).strip()
    return (
        {"readable": True, "pages": page_count, "extractor": "pdfplumber", "preview_pages": len(texts)},
        text[: max(preview_chars, PDF_ANALYSIS_CHARS)],
    )


def _summarize_pdf_bytes(content: bytes, preview_chars: int) -> tuple[dict[str, Any], str]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        return (
            {
                "readable": False,
                "missing_dependency": exc.name,
                "recommendation": "运行 pip install -r requirements.txt 安装 pypdf。",
            },
            "",
        )
    try:
        reader = PdfReader(io.BytesIO(content))
        texts = []
        for page in reader.pages[:PDF_MAX_PAGES]:
            texts.append(page.extract_text() or "")
            if sum(len(item) for item in texts) >= PDF_ANALYSIS_CHARS:
                break
        text = "\n".join(texts).strip()
        return (
            {
                "readable": True,
                "pages": len(reader.pages),
                "extractor": "pypdf_binary_upload",
                "preview_pages": len(texts),
            },
            text[: max(preview_chars, PDF_ANALYSIS_CHARS)],
        )
    except Exception as exc:  # noqa: BLE001
        return ({"readable": False, "error": str(exc)}, "")


def _learning_item(file: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": file.get("name", "file"),
        "kind": file.get("kind", "unknown"),
        "details": file.get("details", {}),
        "preview": str(file.get("preview", ""))[:600],
    }
