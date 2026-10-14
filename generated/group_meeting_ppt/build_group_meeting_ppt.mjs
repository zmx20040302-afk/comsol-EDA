import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const outDir = "D:/桌面/codex/comsol1/comsol_training_small_model/generated/group_meeting_ppt/output";
const finalPath = "D:/桌面/codex/comsol1/comsol_training_small_model/generated/COMSOL_水力压裂小模型组会展示.pptx";
const assetDir = "D:/桌面/codex/comsol1/comsol_training_small_model/generated/group_meeting_assets";
const W = 1280;
const H = 720;
const C = { ink: "#111111", muted: "#5D6470", panel: "#EDEDED", rule: "#B8BCC4", accent: "#3D8DFF", pale: "#EAF5FB", white: "#FFFFFF" };

async function blob(path) {
  const bytes = await fs.readFile(path);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

function box(slide, x, y, w, h, fill = "none", line = "none", name = "box") {
  return slide.shapes.add({ geometry: "rect", name, position: { left: x, top: y, width: w, height: h }, fill, line: { style: "solid", fill: line, width: line === "none" ? 0 : 1 } });
}

function txt(slide, text, x, y, w, h, size, color = C.ink, bold = false, name = "text", align = "left") {
  const t = slide.shapes.add({ geometry: "textbox", name, position: { left: x, top: y, width: w, height: h }, fill: "none", line: { style: "solid", fill: "none", width: 0 } });
  t.text = text;
  t.text.style = { fontSize: size, color, bold, typeface: "Arial", alignment: align, verticalAlignment: "top", autoFit: "shrinkText", insets: { top: 0, right: 0, bottom: 0, left: 0 } };
  return t;
}

function footer(slide, n) {
  box(slide, 42, 650, 1196, 1, C.rule, C.rule, "footer-rule");
  txt(slide, "本地论文与 COMSOL 小模型运行记录", 42, 665, 560, 20, 12, C.muted, false, "source-footer");
  txt(slide, String(n), 1184, 662, 54, 22, 13, C.muted, false, "slide-number", "right");
}

async function main() {
  await fs.mkdir(outDir, { recursive: true });
  const p = Presentation.create({ slideSize: { width: W, height: H } });
  const articleShot = await blob(`${assetDir}/article_learning_ui.png`);
  const codeShot = await blob(`${assetDir}/code_analysis_ui.png`);

  // Slide 1: cover-image-field layout adapted from Codex Grid slide 08.
  {
    const s = p.slides.add(); s.background.fill = C.white;
    txt(s, "水力压裂论文驱动的小模型建模演示", 42, 42, 575, 132, 54, C.ink, true, "title");
    txt(s, "将 Word 论文的研究对象、参数与物理问题，整理为可审核的 COMSOL 分步建模任务。", 42, 206, 548, 102, 25, C.muted, false, "subtitle");
    box(s, 42, 340, 150, 8, C.accent, C.accent, "accent-rule");
    txt(s, "本次输入", 42, 380, 200, 28, 18, C.muted, true, "label");
    txt(s, "《COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究》", 42, 418, 548, 92, 27, C.ink, true, "paper-name");
    txt(s, "论文解析：23 段文本 · 9 类参数 · 8 个相似案例检索结果", 42, 544, 550, 56, 19, C.muted, false, "evidence");
    box(s, 658, 42, 580, 588, C.pale, C.rule, "article-shot-frame");
    s.images.add({ blob: articleShot, contentType: "image/png", alt: "小模型读取水力压裂论文后的学习界面", fit: "cover", position: { left: 668, top: 52, width: 560, height: 568 }, geometry: "rect" });
    footer(s, 1);
    s.speakerNotes.textFrame.setText("[Sources]\n- 本地论文：D:/桌面/COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究.docx\n- 本地界面截图：generated/group_meeting_assets/article_learning_ui.png");
  }

  // Slide 2: workflow + evidence.
  {
    const s = p.slides.add(); s.background.fill = C.white;
    txt(s, "论文内容已被转成七步建模流程与代码包", 42, 38, 910, 58, 40, C.ink, true, "title");
    txt(s, "每一步都保留判断依据，当前结果用于方案审核，而不是直接求解。", 42, 106, 760, 34, 20, C.muted, false, "subtitle");
    const steps = ["1 物理场", "2 材料", "3 几何", "4 网格", "5 研究", "6 结果", "7 代码包"];
    steps.forEach((item, i) => {
      const x = 42 + i * 169;
      box(s, x, 168, 146, 52, i === 6 ? C.pale : C.panel, i === 6 ? C.accent : C.rule, `step-${i + 1}`);
      txt(s, item, x + 10, 182, 126, 24, 17, i === 6 ? C.ink : C.muted, i === 6, `step-text-${i + 1}`, "center");
      if (i < 6) txt(s, "→", x + 147, 180, 20, 28, 19, C.muted, false, `arrow-${i + 1}`, "center");
    });
    box(s, 42, 258, 548, 338, C.panel, C.rule, "modeling-summary");
    txt(s, "本次建模判断", 68, 282, 260, 30, 22, C.ink, true, "judgement-title");
    txt(s, "• 固体力学 + 孔隙流/达西流\n• 裂纹：相场或内聚区二选一\n• 2D 平面应变；300 mm 方域，中心 15 mm 钻孔\n• 围压、注入压力与煤层非均质性作为主要工况\n• 钻孔和预期裂纹区局部加密网格", 68, 328, 478, 180, 20, C.ink, false, "judgement-copy");
    txt(s, "生成状态：review_required；尚未对该水力压裂代码执行求解。", 68, 536, 478, 34, 17, "#A13A24", true, "review-warning");
    box(s, 620, 258, 618, 338, C.pale, C.rule, "code-shot-frame");
    s.images.add({ blob: codeShot, contentType: "image/png", alt: "小模型对生成 MATLAB 代码的分析界面", fit: "contain", position: { left: 632, top: 270, width: 594, height: 270 }, geometry: "rect" });
    txt(s, "代码读回检查：130 行 · COMSOL API · 20 参数 · 3 物理接口钩子 · 8 项输出", 644, 552, 560, 28, 16, C.muted, false, "code-evidence", "center");
    footer(s, 2);
    s.speakerNotes.textFrame.setText("[Sources]\n- 本地论文：D:/桌面/COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究.docx\n- 本地流程：generated/staged_workflows/Build_a_COMSOL_hydraulic_fracturing_mode_20260803111808.workflow.json\n- 本地界面截图：generated/group_meeting_assets/code_analysis_ui.png");
  }

  // Slide 3: capability assessment.
  {
    const s = p.slides.add(); s.background.fill = C.white;
    txt(s, "结论：小模型已能组织建模，尚不能替代裂纹模型校准", 42, 38, 1110, 58, 39, C.ink, true, "title");
    box(s, 42, 140, 558, 412, "#F5FAFE", C.accent, "ready-panel");
    txt(s, "已经可用", 70, 170, 200, 30, 25, C.ink, true, "ready-title");
    txt(s, "• 读取 Word、PDF、MATLAB、Java 与案例资料\n• 提取参数、总结理论、检索本地案例记忆\n• 给出物理场、几何、材料、边界与研究建议\n• 分步审批并输出 MATLAB/Java 建模骨架\n• 已在更简单的二维热传导标杆中验证 COMSOL → CSV → 代理模型重训练闭环", 70, 220, 486, 240, 21, C.ink, false, "ready-copy");
    box(s, 638, 140, 600, 412, C.panel, C.rule, "gap-panel");
    txt(s, "本案例暴露的关键缺口", 668, 170, 360, 30, 25, C.ink, true, "gap-title");
    txt(s, "• 通用代码把二维几何误建为 3D，且缺少命名选择\n• 流动接口应由层流改为孔隙介质/达西流\n• 相场/内聚区裂纹与断裂参数尚未落实\n• 生成代码仍需静态检查、mphserver 编译和结果校验\n• 需用试验或现场数据标定起裂压力、路径和长度", 668, 220, 526, 220, 19, C.ink, false, "gap-copy");
    box(s, 42, 580, 1196, 50, C.ink, C.ink, "recommendation-band");
    txt(s, "建议下一步：先建立一个可运行的单孔水力压裂参考模型，再用 20–50 组扫参案例训练自动建模与校验规则。", 66, 593, 1140, 24, 19, C.white, true, "recommendation", "center");
    footer(s, 3);
    s.speakerNotes.textFrame.setText("[Sources]\n- 水力压裂建模包：generated/demo_hydraulic_fracture_package/Build_a_COMSOL_hydraulic_fracturing_mode_20260803111808.final_modeling_package.md\n- 代码审查：generated/demo_hydraulic_fracture_package/final_code/build_a_comsol_hydraulic_fracturing_mode_20260803111808.m\n- 热传导标杆训练记录：项目 generated 目录内的 COMSOL 训练与验证结果。");
  }

  for (const [i, slide] of p.slides.items.entries()) {
    const png = await p.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(`${outDir}/slide-${String(i + 1).padStart(2, "0")}.png`, new Uint8Array(await png.arrayBuffer()));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(`${outDir}/slide-${String(i + 1).padStart(2, "0")}.layout.json`, await layout.text());
  }
  const montage = await p.export({ format: "webp", montage: true, scale: 1 });
  await fs.writeFile(`${outDir}/deck-montage.webp`, new Uint8Array(await montage.arrayBuffer()));
  const pptx = await PresentationFile.exportPptx(p);
  await pptx.save(finalPath);
  console.log(finalPath);
}

main().catch((err) => { console.error(err); process.exitCode = 1; });
