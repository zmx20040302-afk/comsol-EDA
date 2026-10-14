from __future__ import annotations

import re
from pathlib import Path


def prepare_exported_case_builder(
    source_matlab: str | Path,
    source_java: str | Path,
    output_dir: str | Path,
    builder_name: str,
    model_label: str,
) -> dict[str, str]:
    """Make portable MATLAB/Java builders from COMSOL-exported case files."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    matlab_output = destination / f"{builder_name}.m"
    java_class = _java_class_name(builder_name)
    java_output = destination / f"{java_class}.java"

    matlab_source = Path(source_matlab).read_text(encoding="utf-8")
    java_source = Path(source_java).read_text(encoding="utf-8")
    matlab_output.write_text(
        _portable_matlab(matlab_source, builder_name, model_label),
        encoding="utf-8",
    )
    java_output.write_text(
        _portable_java(java_source, java_class, model_label),
        encoding="utf-8",
    )
    return {
        "matlab": str(matlab_output),
        "java": str(java_output),
        "builder_name": builder_name,
        "java_class": java_class,
    }


def _portable_matlab(source: str, builder_name: str, model_label: str) -> str:
    adapted = re.sub(
        r"^function\s+out\s*=\s*[^\s(]+\s*$",
        f"function out = {builder_name}()",
        source,
        count=1,
        flags=re.MULTILINE,
    )
    adapted = re.sub(r"^model\.modelPath\(.*?;\s*$", "model.modelPath(pwd);", adapted, count=1, flags=re.MULTILINE)
    adapted = re.sub(
        r"model\.label\('[^']*'\);",
        f"model.label('{model_label}');",
        adapted,
    )
    return "% Portable COMSOL case builder adapted from an exported case.\n" + adapted


def _portable_java(source: str, class_name: str, model_label: str) -> str:
    adapted = re.sub(r"public\s+class\s+\w+", f"public class {class_name}", source, count=1)
    adapted = re.sub(
        r"model\s*\.modelPath\(.*?;",
        'model.modelPath(".");',
        adapted,
        count=1,
        flags=re.DOTALL,
    )
    adapted = re.sub(
        r'model\.label\("[^"]*"\);',
        f'model.label("{model_label}");',
        adapted,
    )
    return "// Portable COMSOL case builder adapted from an exported case.\n" + adapted


def _java_class_name(builder_name: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", builder_name) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "ComsolCaseBuilder"
