# DAC 问题一 相关工作与贡献边界

更新时间：2026-10-12

## 1 检索范围

本轮检索覆盖 2023 至 2026 年的自动有限元与多物理场智能体、自然语言 EDA、工具反馈修正和 EDA 检索增强。优先记录论文主页、arXiv 原文和 IEEE Xplore 元数据。该检索用于限定当前稿件可以声称的贡献，不替代投稿前按 DAC 模板进行的系统综述。

## 2 最接近的工作

| 工作 | 已覆盖能力 | 与本项目的关系 |
|---|---|---|
| ChatEDA 2023 | 自然语言任务分解、脚本生成和 RTL 到 GDSII 工具执行 | 说明“自然语言驱动 EDA 工具”不是新概念 |
| MooseAgent 2025 | 从自然语言生成 MOOSE 输入，采用多智能体、向量库和迭代验证 | 说明“自然语言到多物理仿真输入”和“多轮验证”已有直接先例 |
| LayoutCopilot 2025 | 将高层模拟版图意图转换为可执行脚本并给出操作建议 | 说明“自然语言到 EDA 脚本”已有成熟相邻工作 |
| ALL FEM 2026 | 使用千余个已验证 FEniCS 脚本、专用模型、多智能体和运行反馈完成 FEM 代码生成与调试 | 说明“自动 FEM 闭环”和“运行反馈修正”已有系统性结果 |
| PDE Agents 2026 | 采用 GraphRAG、知识图谱、多个代理和验证流程自动完成 PDE 与 FEM 生命周期 | 说明“知识图谱增强的自动仿真”不能作为本项目独占创新点 |
| MOOSEnger 2026 | 通过仓库检索、可执行验证、故障诊断和持续记忆支持 MOOSE；按物理类别评测 | 说明检索、运行诊断和持久经验组合已有强基线 |
| FlowFixer EDA 2026 | 阶段化日志解析、知识检索、结构化补丁、工具复跑和质量门 | 说明“工具反馈局部修复”在 EDA 流程中已有直接工作 |

## 3 不能再使用的创新性表述

- 首个基于大模型的自动多物理场仿真系统。
- 首个从自然语言生成有限元或 COMSOL 脚本的系统。
- 首个采用多智能体、RAG、知识图谱或运行反馈完成仿真的系统。
- 首个用大模型完成 EDA 工具调用、故障诊断或局部修复的系统。
- 已经实现任意物理场、任意器件和任意几何的端到端自动建模。

## 4 当前可辩护的贡献

当前证据支持把贡献限定为一个 COMSOL 特定、可审计的工程方法：

1. 将用户要求的结果量显式编译成物理接口和耦合依赖，并记录每条补全边的来源。
2. 将完整、缺失、冲突和未验证耦合分成不同停止结果，阻断结果不能被远程助手绕过。
3. 使用带哈希的建模合同约束局部代码补丁，禁止自动修改几何、材料、载荷、边界值、物理接口和验收阈值。
4. 在开发完成后冻结方法和任务文件，对声明的电子器件族进行前瞻评测，并保留负面结果。

上述贡献是方法组合与证据协议上的增量贡献。它是否足以满足 DAC 的算法创新要求，仍取决于后续与冻结模型 API、RAG 基线和直接生成基线的等预算比较。

## 5 主要来源

1. He et al., ChatEDA A Large Language Model Powered Autonomous Agent for EDA, arXiv 2308.10204, 2023. https://arxiv.org/abs/2308.10204
2. Zhang et al., MooseAgent A LLM Based Multi agent Framework for Automating Moose Simulation, arXiv 2504.08621, 2025. https://arxiv.org/abs/2504.08621
3. Chen et al., LayoutCopilot An LLM Powered Multiagent Collaborative Framework for Interactive Analog Layout Design, IEEE TCAD, 2025, DOI 10.1109/TCAD.2025.3529805. https://ieeexplore.ieee.org/document/10841395/
4. Deotale et al., ALL FEM Agentic Large Language models Fine tuned for Finite Element Methods, arXiv 2603.21011, 2026. https://arxiv.org/abs/2603.21011
5. Adhikari et al., PDE Agents An LLM Orchestrated Multi Agent Framework for Automated Finite Element Simulations with Knowledge Graph Augmented Reasoning, arXiv 2606.07850, 2026. https://arxiv.org/abs/2606.07850
6. Abulawi et al., Deploying Frontier Agentic Technology in MOOSEnger, arXiv 2608.15881, 2026. https://arxiv.org/abs/2608.15881
7. FlowFixer EDA A Tool Feedback Augmented Large Language Model Agent for Automated Diagnosis and Repair of Open Source RTL to GDS Design Flow Failures, IEEE Access, 2026, DOI 10.1109/ACCESS.2026.3730896. https://ieeexplore.ieee.org/abstract/document/11683937/
