from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CODE_EXTENSIONS = {
    ".m",
    ".java",
    ".py",
    ".json",
    ".xml",
    ".txt",
    ".md",
    ".csv",
}


@dataclass(frozen=True)
class CodeReadResult:
    path: str
    kind: str
    size_bytes: int
    line_count: int
    preview: str
    analysis: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodeEditResult:
    source_path: str
    output_path: str
    backup_path: str
    changed: bool
    mode: str
    replacements: int
    summary: list[str]
    analysis_before: dict[str, Any]
    analysis_after: dict[str, Any]
    preview: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_code_file(path: str | Path, preview_chars: int = 8000) -> CodeReadResult:
    source = _validate_code_path(Path(path), must_exist=True)
    text = source.read_text(encoding="utf-8", errors="replace")
    return CodeReadResult(
        path=str(source),
        kind=_code_kind(source),
        size_bytes=source.stat().st_size,
        line_count=len(text.splitlines()),
        preview=text[:preview_chars],
        analysis=analyze_code_text(text, source.suffix.lower()),
    )


def modify_code_file(
    path: str | Path,
    instruction: str,
    *,
    find_text: str = "",
    replace_text: str = "",
    append_text: str = "",
    output_path: str | Path | None = None,
    overwrite: bool = False,
    preview_chars: int = 8000,
) -> CodeEditResult:
    source = _validate_code_path(Path(path), must_exist=True)
    original = source.read_text(encoding="utf-8", errors="replace")
    output = _resolve_output_path(source, output_path, overwrite)
    _validate_code_path(output, must_exist=False)
    before = analyze_code_text(original, source.suffix.lower())

    new_text = original
    mode = "instruction_note"
    replacements = 0
    summary: list[str] = []

    if find_text:
        replacements = original.count(find_text)
        if replacements == 0:
            raise ValueError("find_text was not found in the source file")
        new_text = original.replace(find_text, replace_text)
        mode = "find_replace"
        summary.append(f"Replaced {replacements} occurrence(s) of the requested text.")
    elif append_text:
        new_text = original.rstrip() + "\n\n" + append_text.strip() + "\n"
        mode = "append"
        replacements = 1
        summary.append("Appended the provided code block to the file.")
    else:
        block = _instruction_block(instruction, source.suffix.lower())
        new_text = original.rstrip() + "\n\n" + block + "\n"
        summary.append("No direct find/replace text was provided, so a structured edit note was appended.")

    output.parent.mkdir(parents=True, exist_ok=True)
    backup = _backup_file(source)
    if output.exists() and output.resolve() == source.resolve():
        backup.write_text(original, encoding="utf-8")
    elif not backup.exists():
        backup.write_text(original, encoding="utf-8")
    output.write_text(new_text, encoding="utf-8")

    after = analyze_code_text(new_text, output.suffix.lower())
    summary.extend(_edit_summary(before, after, instruction, output))
    return CodeEditResult(
        source_path=str(source),
        output_path=str(output),
        backup_path=str(backup),
        changed=new_text != original or output.resolve() != source.resolve(),
        mode=mode,
        replacements=replacements,
        summary=summary,
        analysis_before=before,
        analysis_after=after,
        preview=new_text[:preview_chars],
    )


def analyze_code_text(text: str, suffix: str = "") -> dict[str, Any]:
    lowered = text.lower()
    lines = text.splitlines()
    return {
        "kind": _kind_from_suffix(suffix),
        "line_count": len(lines),
        "has_comsol_api": "model." in lowered or "modelutil" in lowered or "com.comsol" in lowered,
        "has_parameters": bool(re.search(r"model\.param|\.param\(\)\.set|inputParam", text)),
        "has_geometry": ".geom" in lowered,
        "has_physics": ".physics" in lowered,
        "has_materials": ".material" in lowered,
        "has_mesh": ".mesh" in lowered,
        "has_study": ".study" in lowered,
        "has_results": ".result" in lowered,
        "has_csv_export": ".csv" in lowered or ".save(" in lowered and "table" in lowered,
        "functions": _extract_functions(text, suffix),
        "classes": _extract_classes(text, suffix),
        "comsol_features": _extract_comsol_features(text),
        "suggestions": _code_suggestions(text),
    }


def _validate_code_path(path: Path, must_exist: bool) -> Path:
    resolved = path.resolve()
    if must_exist and not resolved.exists():
        raise FileNotFoundError(str(resolved))
    if resolved.suffix.lower() not in CODE_EXTENSIONS:
        raise ValueError(f"Unsupported code file extension: {resolved.suffix}")
    return resolved


def _resolve_output_path(source: Path, output_path: str | Path | None, overwrite: bool) -> Path:
    if output_path:
        return Path(output_path).resolve()
    if overwrite:
        return source.resolve()
    return source.with_name(f"{source.stem}.codex_edit{source.suffix}").resolve()


def _backup_file(source: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return source.with_name(f"{source.name}.{stamp}.bak")


def _code_kind(path: Path) -> str:
    return _kind_from_suffix(path.suffix.lower())


def _kind_from_suffix(suffix: str) -> str:
    return {
        ".m": "matlab",
        ".java": "java",
        ".py": "python",
        ".json": "json",
        ".xml": "xml",
        ".csv": "csv",
        ".md": "markdown",
        ".txt": "text",
    }.get(suffix.lower(), "code")


def _instruction_block(instruction: str, suffix: str) -> str:
    clean = " ".join(str(instruction or "Review and modify this file.").split())
    if suffix == ".java":
        return "\n".join(
            [
                "// Codex edit note:",
                f"// {clean}",
                "// TODO: replace this note with a concrete COMSOL API change after reviewing boundary IDs and model dependencies.",
            ]
        )
    if suffix in {".py"}:
        return "\n".join(
            [
                "# Codex edit note:",
                f"# {clean}",
                "# TODO: replace this note with the concrete implementation after reviewing call sites.",
            ]
        )
    if suffix in {".json"}:
        return json.dumps({"codex_edit_note": clean}, ensure_ascii=False, indent=2)
    return "\n".join(
        [
            "% Codex edit note:",
            f"% {clean}",
            "% TODO: replace this note with a concrete COMSOL modeling code change after verification.",
        ]
    )


def _extract_functions(text: str, suffix: str) -> list[str]:
    if suffix == ".m":
        return re.findall(r"^\s*function\s+(?:\[[^\]]+\]\s*=\s*)?([A-Za-z]\w*)", text, flags=re.MULTILINE)[:30]
    if suffix == ".py":
        return re.findall(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", text, flags=re.MULTILINE)[:30]
    if suffix == ".java":
        return re.findall(r"\b(?:public|private|protected)?\s*(?:static\s+)?[\w<>\[\]]+\s+([A-Za-z_]\w*)\s*\(", text)[:30]
    return []


def _extract_classes(text: str, suffix: str) -> list[str]:
    if suffix == ".py":
        return re.findall(r"^\s*class\s+([A-Za-z_]\w*)", text, flags=re.MULTILINE)[:30]
    if suffix == ".java":
        return re.findall(r"\bclass\s+([A-Za-z_]\w*)", text)[:30]
    return []


def _extract_comsol_features(text: str) -> dict[str, list[str]]:
    patterns = {
        "parameters": r"(?:model\.param\.set|\.param\(\)\.set)\(([^;\n]+)",
        "physics": r"(?:physics\.create|\.physics\(\)\.create)\(([^;\n]+)",
        "geometry": r"(?:geom.*?\.create|\.geom\(\).*?\.create)\(([^;\n]+)",
        "studies": r"(?:study.*?\.create|\.study\(\).*?\.create)\(([^;\n]+)",
        "results": r"(?:result.*?\.create|\.result\(\).*?\.create)\(([^;\n]+)",
    }
    return {
        key: [re.sub(r"\s+", " ", item).strip()[:160] for item in re.findall(pattern, text)[:20]]
        for key, pattern in patterns.items()
    }


def _code_suggestions(text: str) -> list[str]:
    analysis_text = text.lower()
    suggestions = []
    if "model." in analysis_text and ".save" not in analysis_text:
        suggestions.append("Add an explicit model.save or export step after the baseline solve is verified.")
    if ".physics" in analysis_text and ".selection" not in analysis_text:
        suggestions.append("Review boundary selections; generated COMSOL code should avoid relying on unverified entity IDs.")
    if ".study" in analysis_text and ".result" not in analysis_text:
        suggestions.append("Add result or derived-value exports so the model can produce CSV training targets.")
    if ".csv" not in analysis_text and "table" not in analysis_text:
        suggestions.append("Add a table export when this code is intended to generate surrogate-training data.")
    return suggestions


def _edit_summary(before: dict[str, Any], after: dict[str, Any], instruction: str, output: Path) -> list[str]:
    summary = [f"Output written to {output}."]
    for key in ("has_parameters", "has_geometry", "has_physics", "has_materials", "has_mesh", "has_study", "has_results"):
        if before.get(key) != after.get(key):
            summary.append(f"{key} changed from {before.get(key)} to {after.get(key)}.")
    if instruction:
        summary.append("Instruction recorded: " + " ".join(str(instruction).split())[:300])
    return summary
