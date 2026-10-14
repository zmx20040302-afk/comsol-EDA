from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_MASTER_CASE_INDEX = Path("comsol_master_cases_index.json")
DEFAULT_DOCS_INDEX = Path("comsol_64_all_docs_index.json")


def compare_with_external_knowledge(
    card: dict[str, Any],
    case_index_path: str | Path = DEFAULT_MASTER_CASE_INDEX,
    docs_index_path: str | Path = DEFAULT_DOCS_INDEX,
    top_k: int = 3,
) -> dict[str, Any]:
    query = _card_query(card)
    case_matches = query_case_index(query, case_index_path, top_k=top_k)
    docs_matches = query_docs_index(query, docs_index_path, top_k=top_k)
    return {
        "kind": "external_knowledge_alignment",
        "query": query,
        "case_index": str(case_index_path),
        "docs_index": str(docs_index_path),
        "case_matches": case_matches,
        "docs_matches": docs_matches,
        "training_improvements": _training_improvements(card, case_matches, docs_matches),
    }


def query_case_index(query: str, index_path: str | Path = DEFAULT_MASTER_CASE_INDEX, top_k: int = 3) -> list[dict[str, Any]]:
    path = Path(index_path)
    if not path.exists():
        return []
    payload = _load_json_index(str(path))
    ranked = _rank_items(query, payload, payload.get("cases", []), text_key="searchable_text", title_key="name", top_k=top_k)
    matches = []
    for score, case in ranked:
        fields = case.get("fields", {})
        supported_fields = [name for name, values in fields.items() if values]
        field_gaps = [name for name, values in fields.items() if not values]
        matches.append(
            {
                "case_id": case.get("case_id", ""),
                "title": case.get("name", ""),
                "score": round(score, 4),
                "root": case.get("root", ""),
                "supported_fields": supported_fields,
                "field_gaps": field_gaps,
                "parameter_count": len(case.get("parameters", [])),
                "files": case.get("files", [])[:8],
            }
        )
    return matches


def query_docs_index(query: str, index_path: str | Path = DEFAULT_DOCS_INDEX, top_k: int = 3) -> list[dict[str, Any]]:
    path = Path(index_path)
    if not path.exists():
        return []
    payload = _load_json_index(str(path))
    ranked = _rank_items(query, payload, payload.get("pages", []), text_key="text", title_key="document", top_k=top_k)
    matches = []
    for score, page in ranked:
        matches.append(
            {
                "score": round(score, 4),
                "module": page.get("module", ""),
                "document": page.get("document", ""),
                "page": page.get("page", ""),
                "path": page.get("path", ""),
                "excerpt": _clean_text(str(page.get("text", "")))[:500],
            }
        )
    return matches


def enrich_plan_with_external_knowledge(plan: dict[str, Any], requirement: str) -> dict[str, Any]:
    case_matches = query_case_index(requirement)
    docs_matches = query_docs_index(requirement)
    plan["external_case_matches"] = case_matches
    plan["official_doc_matches"] = docs_matches
    plan["training_path"] = _merge_unique(
        plan.get("training_path", []),
        [
            "Search the master COMSOL case knowledge base for similar evidence before adapting settings.",
            "Cross-check COMSOL API and feature usage against the official documentation index.",
            "Keep unsupported settings marked as unknown until verified in COMSOL or by source evidence.",
        ],
    )
    plan["limitations"] = _merge_unique(
        plan.get("limitations", []),
        _external_limitations(case_matches, docs_matches),
    )
    return plan


def _card_query(card: dict[str, Any]) -> str:
    parts = [
        str(card.get("title", "")),
        str(card.get("training_stage", "")),
        " ".join(card.get("thoughts", [])),
        " ".join(card.get("implementation_path", [])),
        " ".join(card.get("gaps", [])),
    ]
    for param in card.get("parameters", [])[:20]:
        parts.extend([str(param.get("name", "")), str(param.get("description", "")), str(param.get("value", ""))])
    for source in card.get("source_files", [])[:12]:
        parts.extend([str(source.get("name", "")), str(source.get("kind", ""))])
    return " ".join(part for part in parts if part).strip()


@lru_cache(maxsize=4)
def _load_json_index(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _rank_items(
    query: str,
    payload: dict[str, Any],
    items: list[dict[str, Any]],
    text_key: str,
    title_key: str,
    top_k: int,
) -> list[tuple[float, dict[str, Any]]]:
    vectors = payload.get("vectors")
    idf = payload.get("idf")
    if vectors and idf and len(vectors) == len(items):
        scored = [
            (_similarity(query, idf, vector) + 0.2 * _title_overlap(query, str(item.get(title_key, ""))), item)
            for item, vector in zip(items, vectors)
        ]
    else:
        query_tokens = set(_tokenize(query))
        scored = []
        for item in items:
            text = f"{item.get(title_key, '')} {item.get(text_key, '')}"
            tokens = set(_tokenize(text))
            score = len(query_tokens & tokens) / math.sqrt(max(len(tokens), 1))
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [(score, item) for score, item in scored[:top_k] if score > 0]


def _similarity(question: str, idf: dict[str, float], vector: dict[str, float]) -> float:
    counts = Counter(_tokenize(question))
    query = {
        token: (1 + math.log(frequency)) * idf[token]
        for token, frequency in counts.items()
        if token in idf
    }
    norm = math.sqrt(sum(value * value for value in query.values())) or 1
    return sum((value / norm) * float(vector.get(token, 0)) for token, value in query.items())


def _title_overlap(query: str, title: str) -> float:
    query_tokens = set(_tokenize(query))
    title_tokens = set(_tokenize(title))
    return len(query_tokens & title_tokens) / max(len(title_tokens), 1)


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9_./+-]{2,}", lowered)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", lowered)
    chinese: list[str] = []
    for run in chinese_runs:
        chinese.extend(run[index : index + 2] for index in range(max(1, len(run) - 1)))
    return latin + chinese


def _training_improvements(
    card: dict[str, Any],
    case_matches: list[dict[str, Any]],
    docs_matches: list[dict[str, Any]],
) -> list[str]:
    file_summary = card.get("file_summary", {})
    improvements = [
        "将单案例摘要升级为：本地案例证据 + 总案例库相似案例 + 官方文档校对的三层学习结果。",
        "学习完成后先判断证据字段是否覆盖 geometry、materials、physics、boundary_conditions、mesh、solver、results。",
    ]
    if case_matches:
        improvements.append("优先对齐相似案例中已有证据的参数、物理场、网格、求解器和结果导出设置。")
    else:
        improvements.append("未找到可用总案例库匹配时，只把当前案例作为局部经验，不自动推断未见过的 COMSOL 设置。")
    if docs_matches:
        improvements.append("生成或修改 LiveLink MATLAB/Java API 前，使用官方文档索引核对接口和节点含义。")
    else:
        improvements.append("缺少官方文档索引匹配时，将 API 用法标记为待校对。")
    if file_summary.get("csv_files", 0) == 0:
        improvements.append("没有 CSV 时只完成建模逻辑学习；需要先完成 COMSOL 参数扫描、导出 CSV，再训练代理模型。")
    else:
        improvements.append("已有 CSV 时进入代理模型训练，并记录候选模型、误差、样本预测和改进建议。")
    return improvements


def _external_limitations(case_matches: list[dict[str, Any]], docs_matches: list[dict[str, Any]]) -> list[str]:
    limitations = []
    if not case_matches:
        limitations.append("No external master case match was found; rely on local case memory and review settings manually.")
    if not docs_matches:
        limitations.append("No official documentation match was found; API usage should be checked before execution.")
    if case_matches and any(match.get("field_gaps") for match in case_matches):
        limitations.append("External similar cases have missing evidence fields; do not infer unsupported COMSOL settings.")
    return limitations


def _merge_unique(first: list[str], second: list[str]) -> list[str]:
    merged = []
    for item in [*first, *second]:
        if item and item not in merged:
            merged.append(item)
    return merged


def _clean_text(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
