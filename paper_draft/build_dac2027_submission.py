from __future__ import annotations

import hashlib
import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "paper_draft" / "dac2027_contract_guided_comsol_submission.docx"
WORKFLOW_FIGURE = ROOT / "paper_draft" / "assets" / "workflow.png"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def load_verified_p3_result(root: Path = ROOT) -> dict | None:
    """Return the sealed P3 report only when every publication gate is verifiable."""
    readiness = load_json(root / "generated" / "dac2027" / "p3" / "readiness_status.json")
    if not readiness.get("p3_main_result_gate_passed"):
        return None
    relative = str(readiness.get("report_path") or "").strip()
    expected_hash = str(readiness.get("report_sha256") or "").strip().lower()
    report_path = root / relative if relative else Path()
    if not relative or not expected_hash or not report_path.is_file() or sha256(report_path) != expected_hash:
        return None
    report = load_json(report_path)
    if not report.get("publication_main_result"):
        return None
    if (
        int(report.get("task_count", 0) or 0) != 24
        or int(report.get("family_count", 0) or 0) != 8
        or int(report.get("measured_observation_count", 0) or 0) != 192
        or int(report.get("expected_observation_count", 0) or 0) != 192
    ):
        return None
    return report


def method_label(method: str) -> str:
    return {
        "direct_llm": "Direct LLM",
        "retrieval_llm": "Retrieval LLM",
        "existing_selector": "Existing selector",
        "contract_dependency_v11": "Contract dependency",
    }.get(method, method.replace("_", " ").title())


def set_columns(section, count: int = 2, space_twips: int = 300) -> None:
    sect_pr = section._sectPr
    cols = sect_pr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sect_pr.append(cols)
    cols.set(qn("w:num"), str(count))
    cols.set(qn("w:space"), str(space_twips))


def set_cell_margins(cell, top=55, start=65, bottom=55, end=65) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = borders.find(qn(f"w:{edge}"))
        if tag is None:
            tag = OxmlElement(f"w:{edge}")
            borders.append(tag)
        tag.set(qn("w:val"), "single")
        tag.set(qn("w:sz"), "4")
        tag.set(qn("w:color"), "D9D9D9")


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_font(run, size: float = 10, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Times New Roman"
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Times New Roman")
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Times New Roman")
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.62)
    section.bottom_margin = Inches(0.62)
    section.left_margin = Inches(0.67)
    section.right_margin = Inches(0.67)
    section.header_distance = Inches(0.2)
    section.footer_distance = Inches(0.2)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Times New Roman")
    normal._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Times New Roman")
    normal.font.size = Pt(10)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.space_after = Pt(2.2)
    normal.paragraph_format.line_spacing = 1.0
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for name, size, before, after in (
        ("Heading 1", 11, 5.5, 2.5),
        ("Heading 2", 10.2, 4, 1.8),
    ):
        style = doc.styles[name]
        style.font.name = "Times New Roman"
        style._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Times New Roman")
        style._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Times New Roman")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    props = doc.core_properties
    props.title = "Contract Guided Requirement to Multiphysics Compilation for EDA"
    props.subject = ""
    props.author = ""
    props.last_modified_by = ""
    props.keywords = ""
    props.comments = ""
    props.category = ""


def add_title(doc: Document) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("Contract Guided Requirement to Multiphysics Compilation for Electronic Design Automation")
    set_font(r, 15, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(5)
    r = p.add_run("Anonymous submission")
    set_font(r, 9.5)


def add_abstract(doc: Document, p3_result: dict | None = None) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.35)
    p.paragraph_format.right_indent = Inches(0.35)
    p.paragraph_format.space_after = Pt(2)
    lead = p.add_run("Abstract—")
    set_font(lead, 8.7, bold=True, italic=True)
    external_sentence = "We release a frozen protocol for a 24 task, eight family external evaluation; its independent results are intentionally withheld until collection is complete."
    if p3_result:
        full = p3_result.get("methods", {}).get("contract_dependency_v11", {})
        external_sentence = (
            "A sealed 24 task, eight family external evaluation produced "
            f"{int(full.get('gate_correct_count', 0))}/24 correct gate decisions and "
            f"{int(full.get('physics_and_coupling_exact_count', 0))}/24 exact physics and coupling selections for the complete method."
        )
    text = (
        "Engineering intent does not directly specify the physics interfaces, couplings, boundaries, and validation evidence needed for an executable multiphysics model. We present a contract guided compiler that maps requested observables to COMSOL dependencies, blocks missing or contradictory requests, and permits execution only after reviewable static and physical gates. On 24 project authored development tasks, the complete method made 24/24 correct gate decisions and 22/24 exact physics and coupling selections; direct and retrieval language model baselines each made 16/24 correct gate decisions. Two frozen EDA scenarios then completed fresh post freeze COMSOL solves. "
        + external_sentence
    )
    r = p.add_run(text)
    set_font(r, 8.7, italic=True)

    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.35)
    p.paragraph_format.right_indent = Inches(0.35)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("Index Terms—")
    set_font(r, 8.5, bold=True, italic=True)
    r = p.add_run("EDA automation, multiphysics simulation, COMSOL, requirement contracts, physical validation, language model agents")
    set_font(r, 8.5, italic=True)


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_paragraph(style=f"Heading {level}")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
    p.add_run(text)


def add_paragraph(doc: Document, text: str, *, lead: str = "", first_indent: bool = True) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = Inches(0.14) if first_indent else Inches(0)
    p.paragraph_format.space_after = Pt(2.2)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    if lead:
        r = p.add_run(lead)
        set_font(r, 10, bold=True)
    r = p.add_run(text)
    set_font(r, 10)


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.16)
        p.paragraph_format.first_line_indent = Inches(-0.11)
        p.paragraph_format.space_after = Pt(1.2)
        r = p.add_run("• ")
        set_font(r, 9.5, bold=True)
        r = p.add_run(item)
        set_font(r, 9.5)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)
    header_pr = table.rows[0]._tr.get_or_add_trPr()
    header_pr.append(OxmlElement("w:cantSplit"))
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.width = Inches(widths[index])
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_margins(cell)
        shade_cell(cell, "D9E2F3")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(header)
        set_font(r, 7.4, bold=True)
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        row_pr = table.rows[-1]._tr.get_or_add_trPr()
        row_pr.append(OxmlElement("w:cantSplit"))
        for index, value in enumerate(values):
            cell = cells[index]
            cell.width = Inches(widths[index])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            if row_index % 2:
                shade_cell(cell, "F7F9FC")
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 0.9
            p.paragraph_format.keep_with_next = row_index < len(rows) - 1
            r = p.add_run(value)
            set_font(r, 7.2)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)


def add_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    set_font(r, 8, bold=True)


def add_page_break(doc: Document) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.add_run().add_break(WD_BREAK.PAGE)


def add_reference(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.16)
    p.paragraph_format.first_line_indent = Inches(-0.16)
    p.paragraph_format.space_after = Pt(1.2)
    p.paragraph_format.line_spacing = 0.88
    r = p.add_run(text)
    set_font(r, 7.4)


def build() -> None:
    p3_result = load_verified_p3_result()
    doc = Document()
    configure_document(doc)
    add_title(doc)
    add_abstract(doc, p3_result)

    body_section = doc.add_section(WD_SECTION.CONTINUOUS)
    body_section.page_width = Inches(8.5)
    body_section.page_height = Inches(11)
    body_section.top_margin = Inches(0.62)
    body_section.bottom_margin = Inches(0.62)
    body_section.left_margin = Inches(0.67)
    body_section.right_margin = Inches(0.67)
    set_columns(body_section, 2, 300)

    add_heading(doc, "I. INTRODUCTION")
    add_paragraph(doc, "Electronic products increasingly require coupled electrical, thermal, structural, fluid, acoustic, and transport analyses. A designer may ask for peak temperature, voltage drop, thermally induced displacement, pressure drop, or a resonance frequency without naming the numerical interfaces needed to compute that observable. Translating the request into a solver model therefore requires decisions about physics, couplings, geometry, materials, boundary conditions, studies, outputs, mesh, and acceptance tests. A plausible script can still be unsafe when decisive information is absent or internally inconsistent.")
    add_paragraph(doc, "Language model agents have begun to automate EDA scripts and finite element inputs [1]–[5]. Their tool calls and execution feedback improve over single pass generation, but solver completion does not establish that the selected model answers the requested engineering question. For multiphysics EDA, a system must also decide when a request is insufficient to execute, preserve that decision across code generation and repair, and record physical evidence independently of the model that proposed the script.")
    add_paragraph(doc, "We study the following falsifiable question: can an explicit requirement and dependency contract reduce unsafe progression from engineering intent to COMSOL execution while retaining complete requests? The proposed workflow converts requested observables into typed interface and coupling dependencies, checks interface specific completeness, and exposes a blocking decision before code generation. Static, execution, and physical validation gates then determine whether a generated model may support an EDA decision.")
    add_paragraph(doc, "The paper makes three bounded contributions:")
    add_bullets(doc, [
        "A contract guided dependency compiler that links requested observables to COMSOL interfaces, couplings, studies, critical inputs, and clarification reasons.",
        "A local authority model in which language model output is advisory, while deterministic gates control construction, execution, repair, evidence, and surrogate release.",
        "A frozen evaluation structure that separates project authored development evidence from a sealed external, family disjoint experiment with repeated language model runs."
    ])
    if p3_result:
        add_paragraph(doc, "The measured comparison uses 24 project authored development tasks, two post freeze COMSOL EDA scenarios, and a sealed prospective evaluation of 24 external tasks from eight disjoint families. The external table is generated only from the hash verified report after all 192 required observations are present.")
    else:
        add_paragraph(doc, "The current measured comparison uses 24 project authored development tasks and two post freeze COMSOL EDA scenarios. It supports debugging and controlled comparison, not an independent generalization claim. The external evaluation protocol is frozen before data acquisition; its result table remains absent until the required tasks and repetitions are complete.")

    add_heading(doc, "II. CONTRACT GUIDED COMPILATION")
    add_heading(doc, "A. Typed requirement contract", 2)
    add_paragraph(doc, "Every request is converted into a versioned contract containing the engineering objective, design and operating variables with units and ranges, geometry and material assumptions, physics interfaces, couplings, boundary and initial conditions, study, outputs, validation rules, evidence level, and unresolved fields. The contract is an execution boundary. A generated builder cannot add a decisive load, material property, grounding condition, heat transfer boundary, support, inlet, or study interpretation that the user did not provide or approve.")
    add_heading(doc, "B. Observable to dependency graph", 2)
    add_paragraph(doc, "The compiler starts from requested observables rather than surface keywords. Temperature creates a heat transfer dependency; voltage and current require electric currents; displacement and stress require solid mechanics; pressure drop requires flow; acoustic pressure and resonance create acoustic and frequency study dependencies. Joint observables activate candidate couplings: electrical and thermal goals imply electromagnetic heating, thermal and structural goals imply thermal expansion, and flow temperature goals imply nonisothermal flow. Each edge records its trigger, required evidence, and validation level.")
    add_paragraph(doc, "For a normalized request r, the compiler returns a tuple containing the interface set I, coupling set K, study S, blocking decision B, clarification set Q, and an evidence trace E. Evaluation uses exact set equality for I and K rather than partial credit, exact equality for S, and a binary comparison for B. The evidence trace identifies whether each interface came from direct text evidence or from an observable dependency. This representation separates a technically plausible interface list from an executable contract: the same interface prediction can be scored as unsafe when the boundary evidence needed to solve it is absent.")
    if WORKFLOW_FIGURE.is_file():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(str(WORKFLOW_FIGURE), width=Inches(3.25))
        add_caption(doc, "Fig. 1. Requirement, contract, execution, and evidence flow.")
    add_heading(doc, "C. Missing and conflicting evidence", 2)
    add_paragraph(doc, "A negation aware layer separates available evidence from clauses marked unavailable, unknown, unspecified, deferred, prohibited, or contradictory. Interface specific checks then decide whether execution is allowed. An electrothermal request may be blocked for absent current magnitude, ground, thermal environment, or material data. A thermal stress request may be blocked for absent mechanical support or reference temperature. A request for pressure drop that forbids flow or for a resonance frequency under a stationary study is recorded as an explicit conflict. The output includes reason codes and clarification questions instead of invented defaults.")
    add_caption(doc, "TABLE I. CONTRACT FIELDS AND AUTHORITY")
    add_table(doc, ["Field", "Source", "Effect"], [
        ["Objective and output", "Request", "Creates dependency edges"],
        ["Physics and coupling", "Compiler", "Requires traceable evidence"],
        ["Boundary and material", "Request or approval", "Blocks when decisive data are absent"],
        ["Validation rule", "Frozen contract", "Controls solved and passed labels"],
        ["Repair", "Diagnosed allowlist", "Cannot change contract semantics"]
    ], [0.9, 0.88, 1.44])
    add_heading(doc, "D. Ten auditable stages", 2)
    add_paragraph(doc, "Accepted contracts pass through model definition, geometry, materials, physics, boundaries, mesh, study, outputs, static audit, and approved generation. Execution records server connection, model tree construction, selection checks, meshing, study completion, result export, MPH save, and preview generation. Artifacts are fingerprinted. A single worker lock avoids concurrent LiveLink process trees, and a hard timeout terminates stalled MATLAB children.")
    add_heading(doc, "E. Repair boundary", 2)
    add_paragraph(doc, "One bounded repair may address a diagnosed syntax, tag, selection, expression, or solver setting fault. Geometry dimensions, material values, loads, boundary values, selected interfaces, coupling removal, validation thresholds, and the contract itself require renewed review. Tool success after an unauthorized semantic change is therefore not counted as a repaired success.")

    add_heading(doc, "III. EDA EXECUTION AND PHYSICAL EVIDENCE")
    add_heading(doc, "A. Physical acceptance", 2)
    add_paragraph(doc, "Solver convergence is necessary but insufficient. The platform evaluates case specific invariants: electrical current continuity, Joule power transfer, thermal energy balance, structural reaction and finite response, flow mass balance and pressure drop, acoustic reference frequency and wavelength resolution, and output finiteness. A model receives a solved label only when its required numerical and physical checks pass. MPH, CSV, logs, previews, code, contracts, reports, and hashes remain linked to the same task identifier.")
    add_paragraph(doc, "The validation contract distinguishes construction, numerical, and physical evidence. Construction evidence confirms that the requested model tree and selections exist. Numerical evidence confirms meshing, convergence, and finite outputs. Physical evidence applies invariants and declared thresholds. A task may therefore be constructed but not solved, solved but not physically accepted, or accepted for a named decision while remaining outside any product qualification claim. This state model prevents a successful process exit code from overwriting a failed balance or a missing output.")
    add_heading(doc, "B. Frozen EDA scenarios", 2)
    add_paragraph(doc, "Two machine readable EDA scenarios define decision variables, constraints, outputs, physics, stopping conditions, and selection rules before new COMSOL execution. The busbar power delivery scenario compares two nominal three dimensional designs under a 160 A terminal current. Both satisfy current and energy balance, maximum temperature, voltage drop, current density, and geometry gates. The frozen lower loss rule selects a design with 318.388 K peak temperature, 11.698 mV drop, 1.872 W Joule loss, and 0.2231 kg copper mass. The second point is retained as a lower mass tradeoff.")
    add_paragraph(doc, "The MEMS thermal actuator scenario couples electric currents, heat transfer, and structural response. A four point voltage and surface cooling grid contains three feasible points. The frozen maximum displacement rule selects 5.25 V and 22500 W/(m²·K), producing 507.377 K, 1.120 µm displacement, and 15.604 mW. The results support the named choices at the tested nominal points. They do not establish process corner robustness or fabricated device qualification.")
    add_caption(doc, "TABLE II. POST FREEZE EDA DECISIONS")
    add_table(doc, ["Scenario", "Fresh points", "Decision evidence"], [
        ["Busbar", "2", "2 feasible; lower loss selected"],
        ["MEMS actuator", "4", "3 feasible; maximum displacement selected"]
    ], [0.88, 0.62, 1.72])
    add_heading(doc, "C. Dual execution and local authority", 2)
    add_paragraph(doc, "Six mature representative templates spanning heat transfer, Joule heating, solid mechanics, nonisothermal flow, pressure acoustics, and species transport have completed current workstation MATLAB LiveLink runs with saved MPH and physical evidence. The same verified models were exported as template specific Java sources, compiled with the COMSOL 6.4 toolchain, reconstructed, solved, and saved as new MPH artifacts. This dual path checks that the evidence is not tied to one scripting front end. It does not prove portability to another workstation, which still requires a destination installation test.")
    add_heading(doc, "D. Assistant boundary", 2)
    add_paragraph(doc, "Offline parsing, contracts, generation, execution, and evidence remain local. A configured language model may explain a request or analyze a redacted failure, but it cannot mark a stage approved, start an unreviewed solve, modify evidence status, or release a surrogate. This separation allows language model assistance without assigning it authority over claims that depend on deterministic artifacts.")
    add_heading(doc, "E. Artifact and replay contract", 2)
    add_paragraph(doc, "Each accepted execution writes the normalized request, contract version, generator version, COMSOL and MATLAB path configuration, source hash, stage log, result table, MPH hash, and validation report. Replay first verifies frozen inputs and source hashes, then runs in a new output directory. Historical MPH files remain inspectable evidence but are not counted as a new workstation acceptance. Compact JSON and CSV artifacts are included in the reproducibility package; large binaries remain referenced by hash and must be regenerated where licensing permits.")

    add_heading(doc, "IV. CONTROLLED DEVELOPMENT EVALUATION")
    add_heading(doc, "A. Tasks and methods", 2)
    add_paragraph(doc, "The controlled development set contains 24 requirements from eight electronic device families, with eight complete, eight critical information missing, and eight explicit conflict tasks. Four methods receive the same text and output contract: a direct language model, a retrieval augmented language model, the existing selector, and the complete contract dependency compiler. The two language model methods use fresh sessions and produce structured outputs. This set was authored inside the project and is labelled development evidence throughout.")
    add_caption(doc, "TABLE III. PROJECT AUTHORED DEVELOPMENT RESULTS")
    add_table(doc, ["Method", "Physics exact", "Gate correct", "False safe / block"], [
        ["Direct LLM", "23/24", "16/24", "0 / 8"],
        ["Retrieval LLM", "23/24", "16/24", "0 / 8"],
        ["Existing selector", "21/24", "19/24", "2 / 3"],
        ["Contract dependency", "22/24", "24/24", "0 / 0"]
    ], [0.9, 0.72, 0.72, 0.9])
    add_paragraph(doc, "Both language model baselines match 23/24 physics and coupling labels but block all eight complete requests, yielding 16/24 correct gate decisions. The complete method matches 22/24 interface and coupling sets and makes 24/24 correct gate decisions. The existing selector makes two false safe and three false block decisions. The complete method therefore improves the safety decision under this controlled set while leaving two physics label errors visible.")
    add_heading(doc, "B. Confidence and paired comparison", 2)
    add_paragraph(doc, "The complete method gate accuracy is 1.000 with a Wilson 95% interval of [0.862, 1.000]. Zero false safe observations among 16 blocked tasks still has a Wilson upper bound of 0.194, which prevents a zero risk interpretation. The direct and retrieval gate accuracy is 0.667 with interval [0.467, 0.820]. The exact McNemar comparison between the complete method and each language model baseline is p=0.007812 for gate correctness. These values characterize the frozen development set only.")
    add_heading(doc, "C. Ablation", 2)
    add_paragraph(doc, "Removing negation aware completeness reduces correct gate decisions from 24/24 to 16/24 and creates eight false safe decisions. Removing the safety gate reduces correctness to 8/24 and creates 16/16 false safe decisions. The ablation supports the need for explicit negative evidence and an execution block. It cannot establish performance on independently written requirements.")
    add_heading(doc, "D. Evidence accounting", 2)
    add_paragraph(doc, "All 96 method rows are measured and retained with prompts, structured outputs, diagnostics, timing, interaction counts, and validity status. Invalid language model outputs would count as method failures rather than disappearing from the denominator. Development and submission gates are separate machine readable fields so a complete local experiment cannot be relabelled as independent publication evidence.")
    add_heading(doc, "E. Controlled method conditions", 2)
    add_paragraph(doc, "The four methods share the same requirement text, expected JSON fields, adjudicated labels, and scoring code. Direct and retrieval runs use the same model and reasoning budget; retrieval alone receives the frozen template catalog and contract schema. Deterministic methods run without network access. Method specific raw responses are preserved before parsing, and the parser rejects missing fields or values outside the contract. Runtime is reported separately because local deterministic execution and hosted language model latency are not directly comparable as computational costs.")
    add_heading(doc, "F. Observed failure taxonomy", 2)
    add_paragraph(doc, "The development errors fall into three actionable categories. A physics completion error omits or adds an interface or coupling. A study error selects a study inconsistent with the adjudicated target. A safety error either permits a missing or conflicting request or blocks a complete request. This separation matters because a conservative method may avoid false safe decisions by refusing useful tasks, as the two language model baselines do here. The complete method removes observed safety errors but still requires analysis of the two interface mismatches before any broader claim.")

    add_heading(doc, "V. INDEPENDENT PROTOCOL AND RELATED WORK")
    add_heading(doc, "A. Prospective P3 protocol", 2)
    add_paragraph(doc, "The independent evaluation protocol was frozen before external acquisition. It requires 24 requests from eight new device families. For each family, a project external author supplies one complete, one missing, and one conflict request; a different person adjudicates physics interfaces, couplings, study, and block decision without method outputs. The family labels must not overlap any declared development, validation, or P2 family. The accepted task file and protocol are sealed by SHA 256 before any method run.")
    add_paragraph(doc, "Direct and retrieval language model methods each run three independent sessions per task. The two deterministic methods each run once, producing 192 expected observations. The frozen evaluator reports task consensus, per family exact physics and study accuracy, gate accuracy, false safe and false block counts, Wilson intervals, exact McNemar tests, paired bootstrap completion time intervals, repeat agreement, and a failure taxonomy. Partial runs, synthetic rows, project authored replacements, and post unseal method changes do not pass the main result gate.")
    if p3_result:
        add_caption(doc, "TABLE IV. SEALED PROSPECTIVE EXTERNAL RESULTS")
        result_rows = []
        for method in ("direct_llm", "retrieval_llm", "existing_selector", "contract_dependency_v11"):
            values = p3_result.get("methods", {}).get(method, {})
            total = int(values.get("task_count", 24) or 24)
            result_rows.append([
                method_label(method),
                f"{int(values.get('physics_and_coupling_exact_count', 0))}/{total}; {int(values.get('study_exact_count', 0))}/{total}",
                f"{int(values.get('gate_correct_count', 0))}/{total}",
                f"{int(values.get('false_safe_count', 0))} / {int(values.get('false_block_count', 0))}",
            ])
        add_table(doc, ["Method", "Physics / study", "Gate", "False safe / block"], result_rows, [0.90, 0.82, 0.60, 0.90])
        comparisons = p3_result.get("paired_comparisons_against_full_method", {})
        p_values = []
        for method in ("direct_llm", "retrieval_llm", "existing_selector"):
            comparison = comparisons.get(method, {})
            p_value = comparison.get("gate_mcnemar", {}).get("p_value")
            if p_value is not None:
                p_values.append(f"{method_label(method)} p={float(p_value):.6g}")
        paired_text = "; ".join(p_values) if p_values else "paired p-values unavailable"
        add_paragraph(doc, f"The sealed report contains 24 externally authored tasks from eight disjoint families and all 192 required observations. Table IV is generated directly from that hash verified report. Exact paired McNemar gate comparisons against the complete method are: {paired_text}. Per-family results, Wilson intervals, repeat stability, timing, and the failure taxonomy remain in the artifact.")
    else:
        add_caption(doc, "TABLE IV. FROZEN INDEPENDENT EVALUATION CONTRACT")
        add_table(doc, ["Item", "Requirement", "Current"], [
            ["Tasks", "24 external", "0"],
            ["Families", "8 disjoint", "0"],
            ["Task types", "8 complete, 8 missing, 8 conflict", "Pending"],
            ["LLM repeats", "3 + 3 per task", "0"],
            ["Total observations", "192", "0"]
        ], [0.83, 1.52, 0.87])
        add_paragraph(doc, "At manuscript generation time the infrastructure gate passes, but accepted external tasks are 0/24, new families 0/8, and observations 0/192. No independent P3 result is reported. This explicit absence prevents a development table from being presented as generalization evidence. The final submission gate remains open until the sealed result exists.")
    add_heading(doc, "B. Related EDA agents", 2)
    add_paragraph(doc, "ChatEDA orchestrates RTL to GDSII scripts from natural language [1]. LayoutCopilot maps analog layout intent to commands and suggestions [2]. EDAid uses multiple agents for long EDA tool chains [3], AutoEDA standardizes microservice interactions [4], and FlowFixer EDA accepts repairs only after tool reruns and quality checks [5]. These systems establish the relevance of tool grounded agents in EDA. Our scope differs in the compiled object: observable dependencies, multiphysics couplings, critical engineering evidence, and physical acceptance rather than digital flow scripts or layout commands.")
    add_heading(doc, "C. Simulation agents", 2)
    add_paragraph(doc, "MooseAgent uses retrieval and iterative verification to generate MOOSE inputs [6]. ALL FEM combines fine tuned models, specialized agents, and runtime feedback for FEniCS [7]. PDE Agents studies graph augmented reasoning and execution [8], while MOOSEnger combines repository retrieval, executable diagnosis, and persistent memory [9]. We do not claim broader code generation. The intended distinction is a bounded COMSOL dependency compiler, a deterministic block decision, and explicit separation between advisory generation and authority to solve, validate, and release evidence.")
    add_heading(doc, "D. Position within DAC", 2)
    add_paragraph(doc, "The primary fit is AI based design flow automation because the system translates an engineering request into a guarded electronic and multiphysics design workflow. The secondary fit is benchmark and model evaluation because the contribution includes task contracts, method controls, confidence intervals, repeated runs, and explicit evidence tiers. The work is not an RTL generator, a physical design optimizer, or a general purpose simulation chatbot. Its EDA value is the prevention and diagnosis of invalid multiphysics progress before a designer commits compute time or accepts a nominal design decision.")

    add_heading(doc, "VI. DISCUSSION AND CONCLUSION")
    add_heading(doc, "A. What the evidence supports", 2)
    add_paragraph(doc, "The measured results show that exact interface selection and safe progression are distinct objectives. The language model baselines obtain high interface accuracy while blocking every complete request. The existing selector is less conservative but permits two blocked requests. The contract dependency method removes both observed gate error types on the development set, although the finite sample leaves a wide confidence interval and two interface label errors remain. The ablation localizes the gate improvement to the negative evidence and safety layers.")
    add_paragraph(doc, "The two EDA scenarios demonstrate the downstream meaning of the contract. Their frozen variables, constraints, outputs, selection rules, fresh solves, and physical reports support concrete nominal choices. They do not establish arbitrary COMSOL model generation, full manufacturing robustness, or physical agreement with fabricated devices. The six template executions establish traceability across representative mature builders and two scripting paths, not industrial coverage.")
    add_heading(doc, "B. Limitations and submission gate", 2)
    if p3_result:
        add_paragraph(doc, "The prospective experiment is limited to 24 independently authored tasks from eight case families and one frozen protocol. It supports a bounded comparison under those task definitions, not unrestricted COMSOL generation or industrial generalization. Human authors must still verify external identity, adjudication separation, every generated number and citation, conflicts, authorship, and the AI content statement before submission.")
    else:
        add_paragraph(doc, "The main limitation is the absence of independently authored results. P2 tasks were written inside the project. P3 acquisition and method runs remain at zero, so the current manuscript is a format complete evidence bounded draft rather than a finished DAC result. Submission requires the frozen 24 task and 192 observation experiment, human verification of external identity and adjudication separation, and replacement of this paragraph with the generated independent table and failure analysis. If those records are not complete, the research manuscript should not be submitted as finished work.")
    add_paragraph(doc, "The compiler uses a bounded lexicon and rule graph. New physics interfaces, geometry semantics, material models, contact, nonlinearities, bidirectional temperature dependence, and manufacturing constraints require explicit extensions and tests. COMSOL licensing and installation also limit reproduction. Another workstation must repeat a live template solve; copied MPH files cannot prove environment compatibility. No real temperature measurement currently supports claims about a fabricated physical system.")
    add_heading(doc, "C. Threats to validity", 2)
    add_paragraph(doc, "Internal validity is limited by project authored P2 tasks and adjudication choices. The frozen inputs and raw responses reduce selective reporting but do not remove author bias. Construct validity depends on exact interface and coupling labels, which can penalize alternative valid decompositions; the final protocol therefore preserves explanations and failure categories for manual review. External validity is limited by a bounded COMSOL catalog, eight planned external families, one workstation, and two detailed EDA scenarios. Statistical conclusions remain task level and should not be extrapolated to industrial model complexity or unrestricted language.")
    add_paragraph(doc, "Reproducibility is also conditional. Deterministic code, hashes, schemas, and compact results can be archived, but COMSOL and MATLAB licensing, version behavior, language model availability, and proprietary model weights may change. The protocol stores model identity, prompts, responses, and timing, and treats unavailable or invalid calls as failures. A later model version is a new experimental condition rather than a transparent replacement.")
    add_heading(doc, "D. Engineering use and artifact review", 2)
    add_paragraph(doc, "The compiler is intended to sit before expensive model execution. A designer starts with a requirement and receives a review object containing the selected physics, couplings, study, requested observables, unresolved evidence, and the reason for every block. An approved contract is then compiled through a mature builder rather than emitted as unrestricted solver code. The resulting bundle keeps the normalized request, contract, builder identity, executable source, solver log, MPH model, extracted values, preview, validation decisions, and file hashes under one task identifier. This structure lets a reviewer trace a reported temperature, displacement, or loss back to the dependency decision and the exact execution record that produced it.")
    add_paragraph(doc, "Human review remains part of the authority boundary. The language model may explain a missing boundary, suggest a material property, or propose a repair, but it cannot override the static gate, mark a failed solver run as valid, or release a physical result. A changed contract creates a new execution record instead of silently replacing the previous evidence. This separation supports debugging and audit: physics selection errors, study errors, build errors, solver errors, and acceptance failures remain distinguishable. It also makes an incomplete task useful for method evaluation because a correct refusal and its diagnostic evidence can be scored without pretending that a valid model was built.")
    add_heading(doc, "E. Frozen result insertion plan", 2)
    add_paragraph(doc, "The final external table will be generated directly from the sealed P3 report. It will include, for every method, task consensus exact physics and study accuracy, gate accuracy, false safe and false block counts, Wilson 95% intervals, completion time, interaction count, and repeat agreement where applicable. Pairwise McNemar tests will use the same task decisions, and paired bootstrap intervals will describe time differences. Per family results and the failure taxonomy will remain in the artifact even if space requires an aggregate table in the paper. Missing, invalid, or timed out model responses remain failures in the denominator.")
    add_paragraph(doc, "No method, prompt, parser, template, threshold, or adjudicated label may change after the external task seal. The manuscript builder reads the machine report and checks its protocol, task, response, and seal hashes before permitting an independent result claim. If fewer than 24 accepted tasks, eight disjoint families, or 192 measured observations are available, the builder retains the explicit pending statement used in this draft. This policy prevents partial campaigns, favorable subsets, synthetic replacements, and post hoc repairs from entering the principal comparison. Human authors then inspect the generated table, every cited artifact, and the disclosure before approving a submission PDF.")
    add_heading(doc, "F. Content Generated by AI", 2)
    add_paragraph(doc, "OpenAI Codex was used to help draft and edit the Abstract, Introduction, Related Work, Limitations, and Conclusion; to generate supporting Python and document formatting code; and to organize the reproducibility checklist. The system did not originate measured COMSOL outputs or external evaluation records. Human authors remain responsible for verifying every claim, citation, calculation, disclosure, and final sentence, and must revise this statement to match the actual submission process. No AI system is an author.")
    add_heading(doc, "G. Conclusion", 2)
    if p3_result:
        add_paragraph(doc, "A traceable requirement to multiphysics workflow must decide both what to model and when not to proceed. The proposed compiler links observables to COMSOL dependencies, exposes missing and conflicting evidence, and preserves deterministic authority over construction, execution, repair, and validation. Controlled development results, two post freeze EDA scenarios, and the sealed prospective experiment provide bounded evidence for the mechanism and its downstream use. Broader device families, workstations, and fabricated measurements remain future validation targets.")
    else:
        add_paragraph(doc, "A traceable requirement to multiphysics workflow must decide both what to model and when not to proceed. The proposed compiler links observables to COMSOL dependencies, exposes missing and conflicting evidence, and preserves deterministic authority over construction, execution, repair, and validation. Controlled development results and two post freeze EDA scenarios support the mechanism and its downstream use. The frozen external protocol defines the remaining test. Independent performance claims will be added only after the sealed acquisition and all required runs are complete.")
    add_heading(doc, "H. Reproducibility", 2)
    add_paragraph(doc, "The anonymous artifact package contains protocol JSON files, task and response schemas, evaluation code, tests, compact P1 and P2 reports, P3 readiness state, manuscript source, and SHA 256 hashes. It excludes credentials, personal paths, external identities, large MPH files, and unreviewed logs. The package records which claims are development, local execution, or pending external evidence.")

    add_page_break(doc)
    add_heading(doc, "REFERENCES")
    references = [
        "[1] Z. He et al., “ChatEDA: A Large Language Model Powered Autonomous Agent for EDA,” IEEE TCAD, 2024, arXiv:2308.10204.",
        "[2] B. Liu et al., “LayoutCopilot: An LLM-Powered Multiagent Collaborative Framework for Interactive Analog Layout Design,” IEEE TCAD, vol. 44, no. 8, pp. 3126–3139, 2025, doi:10.1109/TCAD.2025.3529805.",
        "[3] F. Wu et al., “Divergent Thoughts toward One Goal: LLM-based Multi-Agent Collaboration System for Electronic Design Automation,” Proc. NAACL, pp. 1615–1629, 2025.",
        "[4] Y. Lu et al., “AutoEDA: Enabling EDA Flow Automation through Microservice-Based LLM Agents,” arXiv:2508.01012, 2025.",
        "[5] “FlowFixer-EDA: A Tool-Feedback-Augmented Large Language Model Agent for Automated Diagnosis and Repair of Open-Source RTL-to-GDS Design Flow Failures,” IEEE Access, vol. 14, pp. 140412–140428, 2026, doi:10.1109/ACCESS.2026.3730896.",
        "[6] T. Zhang, Z. Liu, Y. Xin, and Y. Jiao, “MooseAgent: A LLM Based Multi-agent Framework for Automating Moose Simulation,” arXiv:2504.08621, 2025.",
        "[7] R. Deotale et al., “ALL-FEM: Agentic Large Language Models Fine-tuned for Finite Element Methods,” Comput. Methods Appl. Mech. Eng., 2026, doi:10.1016/j.cma.2026.118985.",
        "[8] S. Adhikari, G. Noorsumar, and Ø. Jensen, “PDE-Agents: An LLM-Orchestrated Multi-Agent Framework for Automated Finite Element Simulations with Knowledge Graph-Augmented Reasoning,” arXiv:2606.07850, 2026.",
        "[9] Z. Abulawi, M. Li, G. Giudicelli, Y. Liu, and C. Permann, “Deploying Frontier Agentic Technology in MOOSEnger, a Multiphysics-Capable AI Assistant,” arXiv:2608.15881, 2026.",
        "[10] COMSOL AB, COMSOL Multiphysics Reference Manual, version 6.4, 2026.",
        "[11] E. B. Wilson, “Probable Inference, the Law of Succession, and Statistical Inference,” J. Amer. Stat. Assoc., vol. 22, no. 158, pp. 209–212, 1927.",
        "[12] Q. McNemar, “Note on the Sampling Error of the Difference between Correlated Proportions or Percentages,” Psychometrika, vol. 12, pp. 153–157, 1947.",
        "[13] B. Efron and R. Tibshirani, An Introduction to the Bootstrap. Chapman and Hall/CRC, 1993.",
        "[14] ACM and IEEE, “DAC 2027 Research Manuscript Submissions,” 2026. [Online]. Available: https://dac.com/2027/program/research-manuscript-submissions"
    ]
    for reference in references:
        add_reference(doc, reference)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
