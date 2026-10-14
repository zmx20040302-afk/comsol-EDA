from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CATALOG_PATH = Path(__file__).resolve().parents[2] / "template_catalog.json"


def load_validated_templates() -> list[dict[str, Any]]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "comsol-validated-template-catalog":
        raise ValueError("template catalog schema is invalid")
    return list(payload.get("templates", []))


def select_validated_template(requirement: str, root: str | Path = ".") -> dict[str, Any]:
    text = str(requirement or "").lower()
    ranked = []
    for item in load_validated_templates():
        hits = [word for word in item["keywords"] if word.lower() in text]
        if hits:
            ranked.append((len(hits), item, hits))
    if not ranked:
        return {"matched": False, "reason": "当前需求未匹配到已验证模板，应进入分步建模与人工审批流程。", "candidates": []}
    ranked.sort(key=lambda row: row[0], reverse=True)
    score, item, hits = ranked[0]
    path = (Path(root) / item["path"]).resolve()
    return {"matched": True, "template_id": item["id"], "template_name": item["name"], "template_path": str(path), "matched_keywords": hits, "confidence": min(0.95, 0.5 + 0.15 * score), "required_information": item["required"], "verification": item["verification"], "reason": f"需求包含关键词：{'、'.join(hits)}，优先复用{item['name']}模板。验证状态：{item['verification']}。"}
