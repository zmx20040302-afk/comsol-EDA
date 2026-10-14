from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_PREVIEW_CHARS = 500


ACTION_LABELS = {
    "/api/inspect-matlab": "解析 MATLAB LiveLink 文件",
    "/api/validate-constraints": "校验约束",
    "/api/generate-matlab": "生成 COMSOL MATLAB 建模脚本",
    "/api/generate-comsol-code": "生成 COMSOL MATLAB 和 Java 建模脚本",
    "/api/train": "训练代理模型",
    "/api/read-file": "读取单个文件",
    "/api/read-files": "读取多个文件",
    "/api/read-uploaded-file": "读取单个上传文件",
    "/api/read-uploaded-files": "读取多个上传文件",
    "/api/instruction": "分析语言指令",
    "/api/learning-summary": "生成学习总结",
    "/api/learn-case": "学习 COMSOL 案例并输出总结",
    "/api/learn-article": "学习文章并生成 COMSOL 修正方案",
    "/api/plan-model": "根据记忆库规划 COMSOL 模型",
    "/api/knowledge-system": "形成 COMSOL 跨案例知识体系",
}

ACTION_LABELS.update(
    {
        "/api/read-code": "读取并分析代码文件",
        "/api/modify-code": "修改代码并输出文件",
        "/api/staged-workflow": "创建分步 COMSOL 建模审批任务",
        "/api/approve-staged-step": "审批分步 COMSOL 建模步骤",
        "/api/finalize-staged-workflow": "生成完整 COMSOL 建模包",
        "/api/staged-workflow/queue-execution": "将已批准建模包加入 COMSOL 执行队列",
    }
)


def build_work_feedback(endpoint: str, request_payload: dict[str, Any], response_payload: dict[str, Any]) -> dict[str, Any]:
    ok = bool(response_payload.get("ok", False))
    feedback = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "action": ACTION_LABELS.get(endpoint, endpoint),
        "status": "success" if ok else "failed",
        "summary": _summary(endpoint, response_payload),
        "details": _details(endpoint, request_payload, response_payload),
        "next_steps": _next_steps(endpoint, response_payload),
    }
    return feedback


def append_work_log(log_path: str | Path, feedback: dict[str, Any]) -> None:
    destination = Path(log_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(feedback, ensure_ascii=False) + "\n")


def _summary(endpoint: str, response: dict[str, Any]) -> str:
    if not response.get("ok", False):
        return f"{ACTION_LABELS.get(endpoint, endpoint)}失败：{response.get('error', '未知错误')}"

    if endpoint in {"/api/read-file", "/api/read-uploaded-file"}:
        summary = response.get("summary", {})
        return f"已读取 {summary.get('name', 'file')}，识别类型为 {summary.get('kind', 'unknown')}。"
    if endpoint in {"/api/read-files", "/api/read-uploaded-files"}:
        summary = response.get("summary", {})
        details = summary.get("details", {})
        return f"已读取 {details.get('count', 0)} 个文件，并生成文件集合摘要。"
    if endpoint == "/api/instruction":
        intents = response.get("response", {}).get("intent", [])
        return f"已识别指令意图：{', '.join(intents) if intents else 'general'}。"
    if endpoint == "/api/learning-summary":
        return "已根据当前文件证据生成 COMSOL 学习总结。"
    if endpoint == "/api/learn-case":
        summary = response.get("summary", {})
        card = response.get("card", {})
        return (
            f"已学习案例 {card.get('title', 'case')} 并输出总结："
            f"{summary.get('summary', '暂无总结')}"
        )
    if endpoint == "/api/learn-article":
        card = response.get("card", {})
        plan = card.get("memory_assisted_model_plan", {}) if isinstance(card, dict) else {}
        return (
            f"已学习文章 {card.get('title', 'article')}，并生成 COMSOL 修正方案；"
            f"匹配到 {len(plan.get('matched_cases', []))} 个记忆库案例。"
        )
    if endpoint == "/api/plan-model":
        plan = response.get("plan", {})
        matches = plan.get("matched_cases", []) if isinstance(plan, dict) else []
        return f"已根据 {len(matches)} 个记忆库匹配案例生成 COMSOL 建模方案。"
    if endpoint == "/api/knowledge-system":
        system = response.get("knowledge_system", {})
        return (
            f"已根据 {system.get('case_count', 0)} 个案例形成 COMSOL 知识体系，"
            f"覆盖 {system.get('domain_count', 0)} 个领域。"
        )
    if endpoint == "/api/validate-constraints":
        return "当前约束可以用于已支持的建模模板。"
    if endpoint == "/api/generate-matlab":
        return f"已生成 MATLAB 建模脚本：{response.get('path', '未知路径')}。"
    if endpoint == "/api/generate-comsol-code":
        outputs = response.get("outputs", {}) if isinstance(response.get("outputs"), dict) else {}
        return (
            "已生成记忆库辅助的 COMSOL MATLAB 和 Java 建模脚本："
            f"{outputs.get('matlab', '未知 MATLAB 路径')}；{outputs.get('java', '未知 Java 路径')}；"
            f"理论指导：{outputs.get('guidance', '未知指导报告路径')}。"
        )
    if endpoint == "/api/train":
        report = response.get("report", {})
        return (
            f"训练完成，最佳模型为 {report.get('best_model', 'unknown')}，"
            f"测试 RMSE 为 {report.get('test_rmse', 'unknown')}。"
        )
    if endpoint == "/api/inspect-matlab":
        summary = response.get("summary", {})
        return f"已解析 MATLAB 文件，提取到 {len(summary.get('parameters', []))} 个参数。"
    if endpoint == "/api/staged-workflow/queue-execution":
        job = response.get("job", {})
        return f"已将批准建模包加入执行队列，任务状态为 {job.get('status', 'unknown')}。"
    if endpoint.startswith("/api/jobs/") and endpoint.endswith("/approve-review"):
        job = response.get("job", {})
        return f"已批准执行复核，任务已重新排队，当前状态为 {job.get('status', 'unknown')}。"
    return "操作已完成。"


def _details(endpoint: str, request: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    details: dict[str, Any] = {
        "request": _safe_request_preview(request),
    }
    if "summary" in response:
        summary = response["summary"]
        if isinstance(summary, dict):
            details["summary_kind"] = summary.get("kind")
            details["summary_name"] = summary.get("name")
            details["summary_details"] = summary.get("details", {})
    if "report" in response:
        details["training_report"] = response["report"]
    if "path" in response:
        details["output_path"] = response["path"]
    if "outputs" in response and isinstance(response["outputs"], dict):
        details["outputs"] = response["outputs"]
    if "response" in response and isinstance(response["response"], dict):
        details["instruction_feedback"] = response["response"]
    if "plan" in response and isinstance(response["plan"], dict):
        details["matched_cases"] = response["plan"].get("matched_cases", [])
        details["inferred_domains"] = response["plan"].get("inferred_domains", [])
    if endpoint == "/api/learn-case":
        card = response.get("card", {})
        summary = response.get("summary", {})
        if isinstance(card, dict):
            details["case_title"] = card.get("title")
            details["training_stage"] = card.get("training_stage")
            details["file_summary"] = card.get("file_summary", {})
        if isinstance(summary, dict):
            details["learning_summary"] = summary
        details["outputs"] = response.get("outputs", {})
        details["memory"] = response.get("memory", {})
    if endpoint == "/api/learn-article":
        card = response.get("card", {})
        if isinstance(card, dict):
            details["article_title"] = card.get("title")
            details["paragraph_count"] = card.get("paragraph_count")
            details["parameter_count"] = len(card.get("parameters", []))
            details["correction_strategy"] = card.get("correction_strategy", [])
            details["matched_cases"] = card.get("memory_assisted_model_plan", {}).get("matched_cases", [])
        details["outputs"] = response.get("outputs", {})
    if endpoint == "/api/knowledge-system":
        system = response.get("knowledge_system", {})
        if isinstance(system, dict):
            details["case_count"] = system.get("case_count")
            details["domain_count"] = system.get("domain_count")
            details["capability_summary"] = system.get("capability_summary")
    return details


def _next_steps(endpoint: str, response: dict[str, Any]) -> list[str]:
    if not response.get("ok", False):
        return ["查看错误信息。", "检查文件路径、依赖项和必填输入。", "修复后重新执行。"]

    if endpoint in {"/api/read-file", "/api/read-files", "/api/read-uploaded-file", "/api/read-uploaded-files"}:
        return ["查看文件摘要。", "如果这些文件属于同一 COMSOL 案例，生成学习总结。", "提取约束，或选择 CSV 输入/输出列用于训练。"]
    if endpoint == "/api/learning-summary":
        return ["把提取出的参数转成约束。", "如果存在 MPH 文件，先导出 MPH 摘要。", "训练前创建或检查参数扫描 CSV。"]
    if endpoint == "/api/learn-case":
        summary = response.get("summary", {})
        if isinstance(summary, dict) and summary.get("next_actions"):
            return list(summary.get("next_actions", []))[:5]
        return ["查看生成的案例总结。", "在建模规划中复用该记忆案例。", "训练代理模型前创建 CSV 参数扫描数据。"]
    if endpoint == "/api/learn-article":
        return [
            "查看文章参数和模型修正要求。",
            "把文章参数转成约束 JSON。",
            "使用匹配到的记忆案例起草 LiveLink MATLAB 建模脚本。",
            "围绕应力比、主应力方向和材料非均质性运行 COMSOL 参数扫描。",
            "训练数值代理模型前先导出 CSV。",
        ]
    if endpoint == "/api/generate-matlab":
        return ["在 COMSOL with MATLAB 中运行生成脚本。", "复核选择集和边界编号。", "如果需要代理模型训练，导出参数扫描数据。"]
    if endpoint == "/api/generate-comsol-code":
        return [
            "打开 MATLAB 和 Java 建模脚本，复核推断出的物理接口。",
            "查看理论指导报告，并按修正建议完善现有脚本或模型摘要。",
            "用真实案例的几何和边界选择替换占位内容。",
            "先在 COMSOL 中完成一次基准求解，再开启参数扫描或代理模型训练。",
            "把修正后的脚本重新放入案例库，作为可复用建模样例。",
        ]
    if endpoint == "/api/train":
        report = response.get("report", {})
        warnings = report.get("warnings", []) if isinstance(report, dict) else []
        steps = ["检查候选模型对比、RMSE、MAE 和 R2。", "在已知验证点上运行预测。"]
        if isinstance(report, dict) and report.get("recommendations"):
            steps.extend(str(item) for item in report.get("recommendations", [])[:3])
        if warnings:
            steps.append("处理训练警告，通常需要增加 COMSOL 参数扫描样本。")
        return steps
    if endpoint == "/api/validate-constraints":
        return ["生成 MATLAB 建模脚本。", "在 COMSOL with MATLAB 中运行脚本。", "创建参数扫描数据用于训练。"]
    if endpoint == "/api/instruction":
        return response.get("response", {}).get("next_actions", []) or ["从右侧工具栏选择一个操作。"]
    if endpoint == "/api/plan-model":
        return ["查看匹配案例和推断物理域。", "把候选参数转成约束。", "生成或改写 LiveLink MATLAB 脚本。", "运行 COMSOL 参数扫描并生成训练数据。"]
    if endpoint == "/api/knowledge-system":
        return [
            "在建模需求中使用该知识体系匹配相近领域和案例。",
            "继续学习修正后的 MATLAB/Java/MPH 摘要，强化可复用建模模板。",
            "补充参数扫描 CSV，让知识体系同时拥有建模逻辑和数值训练数据。",
        ]
    return ["继续执行下一步建模或训练任务。"]


def _safe_request_preview(request: dict[str, Any]) -> dict[str, Any]:
    preview = {}
    for key, value in request.items():
        if key in {"content", "constraints_json"}:
            preview[key] = _truncate(str(value))
        elif key == "files" and isinstance(value, list):
            preview[key] = [
                {"name": item.get("name"), "content": _truncate(str(item.get("content", "")))}
                if isinstance(item, dict)
                else str(item)
                for item in value[:10]
            ]
        else:
            preview[key] = value
    return preview


def _truncate(value: str) -> str:
    if len(value) <= MAX_PREVIEW_CHARS:
        return value
    return value[:MAX_PREVIEW_CHARS] + "...[truncated]"
