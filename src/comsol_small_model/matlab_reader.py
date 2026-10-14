from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


PARAM_RE = re.compile(
    r"model\.param\.set\(\s*'(?P<name>[^']+)'\s*,\s*'(?P<value>[^']*)'(?:\s*,\s*'(?P<description>[^']*)')?\s*\)"
)
PHYSICS_RE = re.compile(
    r"\.physics\.create\(\s*'(?P<tag>[^']+)'\s*,\s*'(?P<interface>[^']+)'\s*,\s*'(?P<geom>[^']+)'\s*\)"
)
STUDY_RE = re.compile(
    r"model\.study\('(?P<study>[^']+)'\)\.create\(\s*'(?P<tag>[^']+)'\s*,\s*'(?P<type>[^']+)'\s*\)"
)
RESULT_RE = re.compile(
    r"model\.result\.create\(\s*'(?P<tag>[^']+)'\s*,\s*'(?P<type>[^']+)'\s*\)"
)


@dataclass(frozen=True)
class MatlabModelSummary:
    path: str
    parameters: list[dict[str, str]]
    physics: list[dict[str, str]]
    studies: list[dict[str, str]]
    results: list[dict[str, str]]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def inspect_matlab_file(path: str | Path) -> MatlabModelSummary:
    source = Path(path)
    text = source.read_text(encoding="utf-8", errors="replace")
    return MatlabModelSummary(
        path=str(source),
        parameters=[m.groupdict(default="") for m in PARAM_RE.finditer(text)],
        physics=[m.groupdict(default="") for m in PHYSICS_RE.finditer(text)],
        studies=[m.groupdict(default="") for m in STUDY_RE.finditer(text)],
        results=[m.groupdict(default="") for m in RESULT_RE.finditer(text)],
    )
