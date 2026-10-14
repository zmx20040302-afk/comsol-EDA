from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p0_evaluation import validate_blind_tasks


CAMPAIGN_ID = "dac2027-p0-blind-20261013"
CAMPAIGN_DIR = ROOT / "benchmarks" / "dac2027_p0" / CAMPAIGN_ID
AUTHOR_DIR = CAMPAIGN_DIR / "returns" / "authors"
JUDGE_DIR = CAMPAIGN_DIR / "returns" / "adjudicators"
OUTPUT_PATH = ROOT / "benchmarks" / "dac2027_p0" / "blind_tasks.measured.jsonl"
STATUS_PATH = ROOT / "generated" / "dac2027" / "p0" / "acquisition_status.json"
PROTOCOL_PATH = ROOT / "configs" / "dac2027_p0_protocol.json"
STATUSES = ("complete", "missing", "conflict")
STUDIES = ("Stationary", "TimeDependent", "Frequency", "Eigenfrequency")


def now() -> str:
    return datetime.now().astimezone().isoformat()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]


def slot_id(family_slot: str, status: str) -> str:
    if family_slot not in {f"f{i:02d}" for i in range(1, 9)} or status not in STATUSES:
        raise ValueError("无效任务槽位")
    return f"blind-{family_slot}-{status}"


def counts() -> dict:
    author = len(list(AUTHOR_DIR.glob("*.json")))
    judge = len(list(JUDGE_DIR.glob("*.json")))
    measured = 24 if OUTPUT_PATH.exists() else 0
    return {"author": author, "judge": judge, "measured": measured}


def update_status(state: str | None = None) -> None:
    current = counts()
    payload = {
        "schema": "dac2027-p0-acquisition-status",
        "campaign_id": CAMPAIGN_ID,
        "state": state or ("sealed_complete" if current["measured"] == 24 else "collecting_independent_adjudication" if current["author"] == 24 else "collecting_external_authors"),
        "slots_started": 24,
        "author_submissions": current["author"],
        "adjudicator_submissions": current["judge"],
        "measured_blind_tasks": current["measured"],
        "intake_url": "http://127.0.0.1:8891/",
        "publication_evidence": current["measured"] == 24,
        "updated_at": now(),
    }
    write_json(STATUS_PATH, payload)


def try_seal() -> None:
    if len(list(AUTHOR_DIR.glob("*.json"))) != 24 or len(list(JUDGE_DIR.glob("*.json"))) != 24:
        update_status()
        return
    protocol = read_json(PROTOCOL_PATH)
    rows = []
    for family_index in range(1, 9):
        family_slot = f"f{family_index:02d}"
        for status in STATUSES:
            task_id = slot_id(family_slot, status)
            author = read_json(AUTHOR_DIR / f"{task_id}.json")
            judge = read_json(JUDGE_DIR / f"{task_id}.json")
            rows.append({
                "id": task_id,
                "family": author["family"],
                "status": status,
                "requirement": author["requirement"],
                "domains": author["domains"],
                "interfaces": judge["interfaces"],
                "couplings": judge["couplings"],
                "study": judge["study"],
                "expected_blocked": judge["expected_blocked"],
                "record_status": "measured",
                "author_id": author["author_id"],
                "author_affiliation": author["author_affiliation"],
                "adjudicator_id": judge["adjudicator_id"],
                "independence_attestation": author["independence_attestation"] and judge["independence_attestation"],
                "authored_at": author["authored_at"],
                "adjudicated_at": judge["adjudicated_at"],
                "notes": judge.get("notes", ""),
            })
    validate_blind_tasks(rows, protocol)
    if OUTPUT_PATH.exists():
        raise RuntimeError("blind_tasks.measured.jsonl 已存在，拒绝覆盖已密封数据")
    OUTPUT_PATH.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    seal = {
        "campaign_id": CAMPAIGN_ID,
        "sealed_at": now(),
        "task_count": 24,
        "sha256": hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest(),
        "method_results_unsealed": False,
    }
    write_json(CAMPAIGN_DIR / "sealed_task_manifest.json", seal)
    update_status("sealed_complete")


def layout(body: str, title: str = "DAC 2027 P0 第三方盲测采集") -> bytes:
    current = counts()
    page = f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{html.escape(title)}</title><style>
body{{font-family:Arial,'Microsoft YaHei',sans-serif;margin:0;background:#f3f6f5;color:#172126}}main{{max-width:1120px;margin:28px auto;padding:0 20px}}
.top{{background:#163f3a;color:white;padding:22px 26px;border-radius:16px}}.stats{{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}}.stat,.card{{background:white;border:1px solid #d9e1df;border-radius:12px;padding:16px;box-shadow:0 2px 8px #0000000a}}
.stat b{{font-size:24px;color:#24695f}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{border:1px solid #d9e1df;padding:10px;text-align:left}}th{{background:#e6f0ee}}a,.button,button{{display:inline-block;background:#2f756b;color:white;padding:9px 13px;border-radius:8px;text-decoration:none;border:0;cursor:pointer}}a.secondary{{background:#687a77}}label{{display:block;font-weight:bold;margin:13px 0 5px}}input,textarea,select{{box-sizing:border-box;width:100%;padding:10px;border:1px solid #aebdb9;border-radius:7px;background:white}}textarea{{min-height:130px}}.ok{{color:#137333;font-weight:bold}}.pending{{color:#9a5d00}}.locked{{color:#777}}.notice{{padding:12px;background:#fff7db;border:1px solid #e7cf7c;border-radius:8px;margin:14px 0}}small{{color:#5c6c69}}
.guide{{background:white;border:1px solid #d9e1df;border-radius:12px;margin:14px 0;padding:4px 18px 14px}}details{{border-top:1px solid #e3e9e7;padding:12px 0}}details:first-of-type{{border-top:0}}summary{{font-size:17px;font-weight:bold;cursor:pointer;color:#225c54}}.guide h3{{margin:14px 0 6px}}.guide li{{margin:6px 0;line-height:1.55}}code{{background:#eef3f2;padding:2px 5px;border-radius:4px}}.mini{{font-size:13px;padding:6px 9px}}.anchor{{scroll-margin-top:18px}}
</style></head><body><main><div class='top'><h1>{html.escape(title)}</h1><p>24 个槽位已启动。任务作者和裁决者必须是不同人员；方法结果在任务密封前保持关闭。</p></div>
<div class='stats'><div class='stat'><b>{current['author']}/24</b><br>作者提交</div><div class='stat'><b>{current['judge']}/24</b><br>独立裁决</div><div class='stat'><b>{current['measured']}/24</b><br>已密封任务</div></div>{body}</main></body></html>"""
    return page.encode("utf-8")


def dashboard() -> bytes:
    rows = []
    labels = {"complete": "完整", "missing": "信息缺失", "conflict": "显式冲突"}
    for family_index in range(1, 9):
        family_slot = f"f{family_index:02d}"
        for status in STATUSES:
            task_id = slot_id(family_slot, status)
            author_exists = (AUTHOR_DIR / f"{task_id}.json").exists()
            judge_exists = (JUDGE_DIR / f"{task_id}.json").exists()
            author_action = "<span class='ok'>已提交</span>" if author_exists else f"<a href='/author?family={family_slot}&status={status}'>填写作者任务</a>"
            if judge_exists:
                judge_action = "<span class='ok'>已裁决</span>"
            elif author_exists:
                judge_action = f"<a class='secondary' href='/judge?family={family_slot}&status={status}'>独立裁决</a>"
            else:
                judge_action = "<span class='locked'>等待作者</span>"
            rows.append(f"<tr><td>{family_slot.upper()}</td><td>{labels[status]}</td><td>{task_id}</td><td>{author_action}</td><td>{judge_action}</td><td><a class='secondary mini' href='#guide-{status}'>如何判断</a></td></tr>")
    guide = """
<section class='guide' id='guide'>
<h2>填写前先判断任务是否合格</h2>
<p>本活动收集的是自然语言 COMSOL 建模需求。8 个器件或结构族，每个族分别提供一条完整需求、一条关键信息缺失需求和一条显式冲突需求，共 24 条。任务密封后，同一段需求将分别交给 Direct LLM、Retrieval LLM、现有选择器和任务合同依赖方法运行；两个 LLM 各独立重复 3 次，两个确定性方法各运行 1 次，总计 192 次方法观测。</p>
<details open><summary>一  三种任务类型如何区分</summary>
<div id='guide-complete' class='anchor'><h3>完整需求 complete</h3><p>目标、材料、激励、关键边界、工况、研究类型和输出量足以形成建模方案。正确系统应选择物理接口与耦合，并允许进入后续建模。</p><ul><li>应包含明确对象与目标，例如最高温度、压降、位移、特征频率或浓度。</li><li>应包含决定可解性的激励与边界，例如电流和接地、入口和出口、载荷和固定端。</li><li>应包含必要材料或物性来源、稳态或瞬态要求及输出量。</li><li>标准阻断答案必须为 <code>false</code>。</li></ul></div>
<div id='guide-missing' class='anchor'><h3>信息缺失 missing</h3><p>保留清楚的工程目标，但有意删除一项会影响可解性或物理正确性的关键条件。正确系统应指出缺失信息并停止，不得静默补默认值。</p><ul><li>电热问题可缺少环境温度、散热边界、电流值或接地条件。</li><li>流热问题可缺少入口流量、出口边界、流体材料或热边界。</li><li>结构问题可缺少支撑、载荷大小、材料弹性参数或参考温度。</li><li>声学与扩散问题可缺少介质、声学边界、扩散系数或时间范围。</li><li>标准阻断答案必须为 <code>true</code>。</li></ul></div>
<div id='guide-conflict' class='anchor'><h3>显式冲突 conflict</h3><p>需求目标和限制条件之间存在明确矛盾。冲突必须足以阻止安全执行，又要保持真实工程语言。</p><ul><li>要求计算最高温度，同时禁止传热物理场。</li><li>要求压降，同时声明流体速度恒为零或禁止流动接口。</li><li>要求热应力，同时禁止固体力学。</li><li>要求腔体特征频率，却强制使用稳态研究。</li><li>同一边界同时给出互不相容的边界条件。</li><li>标准阻断答案必须为 <code>true</code>。</li></ul></div>
<p><b>不要这样写：</b>“这是信息缺失任务”“系统应该选择电流接口”或“请阻断此任务”。方法运行时只能从工程需求本身判断类别。</p>
</details>
<details><summary>二  建议的八个新器件族与物理覆盖</summary>
<table><thead><tr><th>槽位</th><th>建议器件族</th><th>主要物理</th><th>重点判断</th></tr></thead><tbody>
<tr><td>F01</td><td>大电流板端连接器</td><td>电流 固体传热 焦耳热</td><td>电激励、接地与散热边界</td></tr>
<tr><td>F02</td><td>陶瓷功率电阻</td><td>电流 固体传热 焦耳热</td><td>电功率、温升和环境条件</td></tr>
<tr><td>F03</td><td>AI 芯片微通道冷却器</td><td>层流 流体传热 非等温流</td><td>入口、出口、流体和热边界</td></tr>
<tr><td>F04</td><td>陶瓷电容焊接组件</td><td>固体传热 固体力学 热膨胀</td><td>参考温度、固定端和热应力</td></tr>
<tr><td>F05</td><td>散热器底板</td><td>固体传热</td><td>热源、环境温度和散热方式</td></tr>
<tr><td>F06</td><td>探针卡弹性探针</td><td>固体力学</td><td>载荷、支撑、材料和位移</td></tr>
<tr><td>F07</td><td>声学检漏腔体</td><td>压力声学</td><td>声学介质、边界和频率研究</td></tr>
<tr><td>F08</td><td>光刻胶溶剂扩散单元</td><td>稀物质传递</td><td>扩散系数、浓度边界和时间</td></tr>
</tbody></table><p>这些是覆盖建议，不是可直接复制的盲测答案。第三方作者可以选择同等难度且未被项目内部集合使用的新器件族。</p>
</details>
<details><summary>三  作者填写什么以及不能填写什么</summary>
<p><b>作者填写：</b>匿名作者 ID、外部单位、器件族名称、自然语言工程需求、可选领域提示和独立性声明。</p>
<p><b>作者不能填写：</b>标准物理接口、耦合节点、研究类型、是否阻断或任何方法运行结果。作者不能查看方法输出，也不能在提交后根据系统表现改写需求。</p>
<p>同一 F01 至 F08 槽位的三条任务必须使用完全相同的器件族名称，八个槽位之间的器件族名称必须不同。</p>
</details>
<details><summary>四  裁决者需要给出的标准答案</summary>
<p>裁决者必须与作者 ID 不同，并在看不到方法输出的条件下填写以下四类答案：</p>
<table><thead><tr><th>项目</th><th>允许值</th></tr></thead><tbody>
<tr><td>物理接口</td><td><code>heat_transfer_solids</code>、<code>electric_currents</code>、<code>solid_mechanics</code>、<code>laminar_flow</code>、<code>heat_transfer_fluids</code>、<code>pressure_acoustics</code>、<code>transport_diluted_species</code></td></tr>
<tr><td>耦合</td><td><code>electromagnetic_heating</code>、<code>nonisothermal_flow</code>、<code>thermal_expansion</code>、<code>acoustic_structure_boundary</code>；没有耦合时留空</td></tr>
<tr><td>研究类型</td><td><code>Stationary</code>、<code>TimeDependent</code>、<code>Frequency</code>、<code>Eigenfrequency</code></td></tr>
<tr><td>阻断决策</td><td>完整需求为 false；信息缺失和显式冲突为 true</td></tr>
</tbody></table>
</details>
<details><summary>五  判断一条任务能否进入论文数据集</summary>
<ul><li>来自真实电子器件、封装、冷却、传感或制造场景。</li><li>至少有一个明确输出目标，且语言像真实工程需求。</li><li>完整任务具备关键激励和边界；缺失任务只删除一至两项关键条件；冲突任务存在可解释的明确矛盾。</li><li>没有复制项目现有任务，也没有直接提示标准答案。</li><li>作者来自项目团队之外，裁决者不是该条任务作者。</li><li>提交后不覆盖；全部 24 条作者记录与 24 条裁决记录齐全后统一密封。</li></ul>
<p><b>应拒绝：</b>只有“建立一个 COMSOL 模型”的空泛请求、24 条近似复制、直接写出接口答案、查看方法输出后回改，以及完全超出当前七类接口范围的完整任务。</p>
</details>
<details><summary>六  密封后的四方法比较与论文指标</summary>
<p>24 条任务密封后，每条任务分别运行 Direct LLM、Retrieval LLM、Existing Selector 和 Contract Dependency v1.1。Direct LLM 与 Retrieval LLM 各使用全新会话独立重复 3 次，两个确定性方法各运行 1 次。所有方法接收相同任务文本并返回相同 JSON 字段。</p>
<p>主要指标包括：物理接口与耦合完全匹配率、研究类型准确率、阻断准确率、错误放行率、错误阻断率、完成时间、交互次数和人工修改量。统计报告使用 Wilson 95% 区间、双侧精确 McNemar 检验和配对 bootstrap 时间区间。</p>
</details></section>"""
    body = "<div class='notice'>第三方人员应直接填写。项目开发者不要代填，也不要在密封前运行四种方法。</div>" + guide + "<h2>24 个任务槽位</h2><table><thead><tr><th>器件族槽位</th><th>任务类型</th><th>任务 ID</th><th>作者</th><th>裁决</th><th>说明</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    return layout(body)


class Handler(BaseHTTPRequestHandler):
    def send_html(self, content: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def redirect(self, location: str = "/") -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/":
            self.send_html(dashboard())
            return
        family = query.get("family", [""])[0]
        status = query.get("status", [""])[0]
        try:
            task_id = slot_id(family, status)
        except ValueError as exc:
            self.send_html(layout(f"<div class='card'>{html.escape(str(exc))}</div>"), 400)
            return
        if parsed.path == "/author":
            hints = {
                "complete": "完整需求：应包含目标、材料、激励、关键边界、研究类型和输出量；不得缺少影响可解性的条件。",
                "missing": "信息缺失：保留明确工程目标，但有意缺少一至两项关键条件；不要在正文中写出任务类别。",
                "conflict": "显式冲突：写入一个会阻止安全执行的明确矛盾；不要直接命令系统阻断。",
            }
            body = f"""<div class='card'><h2>任务作者填写 {task_id}</h2><form method='post' action='/submit-author'>
<div class='notice'>{hints[status]} <a class='secondary mini' href='/#guide-{status}'>查看详细判断标准</a></div>
<input type='hidden' name='family_slot' value='{family}'><input type='hidden' name='status' value='{status}'>
<label>匿名作者 ID</label><input name='author_id' required><label>外部单位</label><input name='author_affiliation' required>
<label>器件或结构族名称</label><input name='family_name' required><label>工程需求</label><textarea name='requirement' required></textarea>
<label>领域提示，可选，用逗号分隔</label><input name='domains'><label><input style='width:auto' type='checkbox' name='attestation' value='yes' required> 我确认自己不属于项目团队，未查看方法输出，并同意提交后不回改需求。</label><button type='submit'>提交并锁定</button></form></div>"""
            self.send_html(layout(body, "第三方需求作者提交"))
            return
        if parsed.path == "/judge":
            author_path = AUTHOR_DIR / f"{task_id}.json"
            if not author_path.exists():
                self.send_html(layout("<div class='card'>作者尚未提交，当前不能裁决。</div>"), 409)
                return
            author = read_json(author_path)
            options = "".join(f"<option value='{study}'>{study}</option>" for study in STUDIES)
            body = f"""<div class='card'><h2>独立裁决 {task_id}</h2><p><b>器件族：</b>{html.escape(author['family'])}</p><p><b>需求：</b>{html.escape(author['requirement'])}</p>
<form method='post' action='/submit-judge'><input type='hidden' name='family_slot' value='{family}'><input type='hidden' name='status' value='{status}'>
<label>裁决者匿名 ID</label><input name='adjudicator_id' required><label>物理接口 ID，用逗号分隔</label><input name='interfaces' required>
<label>耦合 ID，用逗号分隔；没有时留空</label><input name='couplings'><label>研究类型</label><select name='study'>{options}</select>
<label>是否必须阻断自动执行</label><select name='expected_blocked'><option value='false'>否</option><option value='true'>是</option></select>
<label>裁决备注，可选</label><textarea name='notes'></textarea><label><input style='width:auto' type='checkbox' name='attestation' value='yes' required> 我确认未参与该条需求编写、未查看方法输出，并独立完成裁决。</label><button type='submit'>提交并锁定裁决</button></form></div>"""
            self.send_html(layout(body, "独立裁决提交"))
            return
        self.send_error(404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        values = {key: rows[0] for key, rows in parse_qs(self.rfile.read(length).decode("utf-8")).items()}
        try:
            task_id = slot_id(values.get("family_slot", ""), values.get("status", ""))
            if self.path == "/submit-author":
                target = AUTHOR_DIR / f"{task_id}.json"
                if target.exists():
                    raise ValueError("该作者任务已提交，拒绝覆盖")
                if values.get("attestation") != "yes":
                    raise ValueError("必须确认独立性声明")
                affiliation = values.get("author_affiliation", "").strip()
                if affiliation.lower() in {"", "project_team", "internal", "same_project"}:
                    raise ValueError("作者单位必须是项目团队之外的单位")
                payload = {
                    "task_id": task_id, "family_slot": values["family_slot"], "status": values["status"],
                    "family": values.get("family_name", "").strip(), "requirement": values.get("requirement", "").strip(),
                    "domains": split_list(values.get("domains", "")), "author_id": values.get("author_id", "").strip(),
                    "author_affiliation": affiliation, "independence_attestation": True, "record_status": "authored",
                    "authored_at": now(),
                }
                if not payload["author_id"] or not payload["family"] or not payload["requirement"]:
                    raise ValueError("作者 ID、器件族和需求不能为空")
                normalized_family = payload["family"].casefold()
                for existing_path in AUTHOR_DIR.glob("*.json"):
                    existing = read_json(existing_path)
                    existing_family = str(existing.get("family", "")).strip().casefold()
                    if existing.get("family_slot") == payload["family_slot"] and existing_family != normalized_family:
                        raise ValueError("同一个器件族槽位的三条任务必须使用完全相同的器件族名称")
                    if existing.get("family_slot") != payload["family_slot"] and existing_family == normalized_family:
                        raise ValueError("八个器件族槽位必须使用不同的器件族名称")
                write_json(target, payload)
            elif self.path == "/submit-judge":
                author_path = AUTHOR_DIR / f"{task_id}.json"
                target = JUDGE_DIR / f"{task_id}.json"
                if not author_path.exists():
                    raise ValueError("作者任务尚未提交")
                if target.exists():
                    raise ValueError("该裁决已提交，拒绝覆盖")
                if values.get("attestation") != "yes":
                    raise ValueError("必须确认独立裁决声明")
                author = read_json(author_path)
                judge_id = values.get("adjudicator_id", "").strip()
                if not judge_id or judge_id == author["author_id"]:
                    raise ValueError("裁决者必须与作者不同")
                expected_blocked = values.get("expected_blocked") == "true"
                required_blocked = values["status"] != "complete"
                if expected_blocked != required_blocked:
                    raise ValueError("裁决与预注册任务类型不一致，请记录争议并联系项目负责人，不要强行提交")
                payload = {
                    "task_id": task_id, "adjudicator_id": judge_id, "interfaces": split_list(values.get("interfaces", "")),
                    "couplings": split_list(values.get("couplings", "")), "study": values.get("study", ""),
                    "expected_blocked": expected_blocked, "notes": values.get("notes", "").strip(),
                    "independence_attestation": True, "record_status": "adjudicated", "adjudicated_at": now(),
                }
                if not payload["interfaces"] or payload["study"] not in STUDIES:
                    raise ValueError("至少填写一个物理接口并选择有效研究类型")
                write_json(target, payload)
            else:
                self.send_error(404)
                return
            try_seal()
            self.redirect()
        except (ValueError, RuntimeError) as exc:
            self.send_html(layout(f"<div class='card'><h2>提交失败</h2><p>{html.escape(str(exc))}</p><p><a href='/'>返回</a></p></div>"), 400)

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8891)
    args = parser.parse_args()
    AUTHOR_DIR.mkdir(parents=True, exist_ok=True)
    JUDGE_DIR.mkdir(parents=True, exist_ok=True)
    update_status()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"ok": True, "url": f"http://{args.host}:{args.port}/", "campaign_id": CAMPAIGN_ID}, ensure_ascii=False), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
