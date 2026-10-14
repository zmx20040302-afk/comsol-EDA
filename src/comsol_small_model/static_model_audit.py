from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_PARAM_DEF = re.compile(r"model\.param(?:\(\))?\.set\(\s*['\"]([A-Za-z_]\w*)['\"]")
_SET_EXPR = re.compile(r"\.set\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]")
_CREATE_TAG = re.compile(r"\.create\(\s*['\"]([A-Za-z_]\w*)['\"]")
_RESULT_EXPR = re.compile(r"\.set\(\s*['\"]expr['\"]\s*,\s*['\"]([^'\"]+)['\"]")
_UNITS = {"m", "mm", "cm", "um", "nm", "s", "ms", "kg", "g", "k", "pa", "mpa", "gpa", "v", "a", "w", "hz", "khz", "mhz", "mol"}
_CONSTANTS = {"pi", "inf", "nan", "true", "false", "on", "off", "normal", "custom", "all", "none", "freq", "time"}


def contract_sha256(contract: dict[str, Any]) -> str:
    canonical = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def audit_generated_model_code(
    contract: dict[str, Any],
    matlab_code: str,
    java_code: str = "",
) -> dict[str, Any]:
    """Audit generated COMSOL code before a license or solver is started."""
    text = str(matlab_code or "")
    combined = text + "\n" + str(java_code or "")
    findings: list[dict[str, Any]] = []

    def add(rule: str, severity: str, message: str, evidence: str = "") -> None:
        findings.append({"rule": rule, "severity": severity, "message": message, "evidence": evidence[:400]})

    definitions = set(_PARAM_DEF.findall(combined))
    for expression in _SET_EXPR.findall(combined):
        if "." in expression or expression in definitions:
            continue
        tokens = re.findall(r"\b[A-Za-z_]\w*\b", expression)
        candidates = [
            token for token in tokens
            if token not in definitions and token.lower() not in _UNITS | _CONSTANTS
            and not token.startswith(("comp", "geom", "mesh", "std", "dset"))
        ]
        if len(tokens) == 1 and candidates:
            add("PARAM_UNDEFINED", "error", f"表达式引用未定义参数：{candidates[0]}", expression)

    if re.search(r"\.selection(?:\(\))?\.set\(\s*(?:\[\s*\]|\{\s*\})\s*\)", combined):
        add("SELECTION_EMPTY", "error", "发现显式空选择，边界或域条件不会作用于任何实体。")
    if re.search(r"\.selection(?:\(\))?\.named\(\s*['\"]\s*['\"]\s*\)", combined):
        add("SELECTION_EMPTY", "error", "发现空的命名选择引用。")

    has_physics = ".physics" in combined
    has_material = ".material" in combined
    if has_physics and not has_material:
        add("MATERIAL_MISSING", "error", "代码创建了物理接口，但没有材料节点或材料属性分配。")
    if has_material and ".selection" not in combined:
        add("MATERIAL_SCOPE_UNVERIFIED", "warning", "材料节点存在，但未发现可审计的域选择。")
    if has_physics and ".study" not in combined:
        add("STUDY_MISSING", "error", "代码创建了物理接口，但没有研究步骤。")
    if ".study" in combined and not re.search(r"(?:Stationary|TimeDependent|Frequency|Eigenfrequency)", combined):
        add("STUDY_TYPE_MISSING", "error", "研究节点存在，但未发现受支持的研究类型。")

    tags = _CREATE_TAG.findall(combined)
    duplicates = sorted({tag for tag in tags if tags.count(tag) > 2})
    if duplicates:
        add("TAG_DUPLICATE", "warning", "同一标签被多次创建，请核对所属节点作用域。", ", ".join(duplicates))

    physics_tags = set(re.findall(r"\.physics(?:\(\))?\.create\(\s*['\"]([A-Za-z_]\w*)['\"]", combined))
    allowed_prefixes = physics_tags | {"T", "u", "v", "w", "p", "c", "solid", "ec", "ht", "spf", "acpr", "tds"}
    for expression in _RESULT_EXPR.findall(combined):
        # An expression can start with an operator or a parameter, for example
        # ``maxop1(spf.U)`` or ``rho_fluid*aveout(spf.U)``.  Inspect only the
        # identifiers that directly qualify a dotted COMSOL result variable.
        prefixes = set(re.findall(r"\b([A-Za-z_]\w*)\.", expression))
        for prefix in sorted(prefixes - allowed_prefixes):
            add("RESULT_VARIABLE_UNKNOWN", "error", f"结果表达式前缀与已创建物理接口不匹配：{prefix}", expression)

    if re.search(r"(?:mphsave|pngfilename|filename)[^\n]*['\"][^'\"]*(?:\.\./|\.\.\\)[^'\"]*['\"]", combined, re.I):
        add("OUTPUT_PATH_UNSAFE", "error", "保存或导出路径包含父目录跳转。")
    if "mphsave" not in combined and "Saving is handled by the execution wrapper" not in combined:
        add("MPH_SAVE_MISSING", "warning", "未发现 MPH 保存调用或执行包装器声明。")

    errors = [row for row in findings if row["severity"] == "error"]
    warnings = [row for row in findings if row["severity"] == "warning"]
    return {
        "schema": "comsol-static-model-audit",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract_sha256": contract_sha256(contract),
        "passed": not errors,
        "summary": {"errors": len(errors), "warnings": len(warnings), "rules_checked": 9},
        "findings": findings,
        "traceability": {
            "defined_parameters": sorted(definitions),
            "physics_tags": sorted(physics_tags),
            "contract_version": str(contract.get("schemaVersion", contract.get("version", ""))),
        },
    }


def audit_generated_model_files(
    contract: dict[str, Any],
    matlab_path: str | Path,
    java_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    matlab = Path(matlab_path)
    java = Path(java_path)
    report = audit_generated_model_code(
        contract,
        matlab.read_text(encoding="utf-8", errors="replace"),
        java.read_text(encoding="utf-8", errors="replace") if java.is_file() else "",
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["path"] = str(output)
    return report
