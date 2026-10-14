# DAC 2027 Related Work Positioning

## Submission position

The manuscript targets **AI1.5 AI based chip design flow automation**, with **AI1.1 benchmarks data sets and model evaluation for EDA** as the secondary category. Its contribution is a bounded compiler from engineering observables to COMSOL physics dependencies and execution gates for electrothermal and multiphysics EDA tasks.

The paper does not claim the first language model EDA agent, the first natural language finite element interface, the first retrieval augmented simulation assistant, or unrestricted automatic construction of arbitrary industrial models.

## Comparison matrix

| Work | Primary scope | Validation mechanism | Difference from this project |
|---|---|---|---|
| ChatEDA, 2023 and 2024 | Natural language orchestration of RTL to GDSII tools | Script execution and EDA flow evaluation | Focuses on digital implementation orchestration; this project compiles multiphysics observables, couplings, missing evidence, and physical acceptance gates. |
| LayoutCopilot, IEEE TCAD 2025 | Interactive analog layout commands and design suggestions | Syntactic and functional checks on layout operations | Addresses analog layout interaction; this project addresses COMSOL interface and study selection plus solver and physics evidence. |
| EDAid, NAACL 2025 | Multi agent collaboration for long EDA tool chains | Multiple agents and tool feedback | Improves orchestration reliability; this project uses deterministic contract and dependency gates before any model execution. |
| AutoEDA, 2025 | MCP based RTL to GDSII automation | Script quality and curated flow benchmarks | Standardizes microservice interaction; this project standardizes requirement, physics, validation, and artifact contracts for multiphysics EDA. |
| FlowFixer EDA, IEEE Access 2026 | Diagnosis and repair of RTL to GDS flow failures | Tool reruns and strict quality repair success | Repairs failed digital flows; this project prevents under specified or contradictory multiphysics requests from entering execution and limits repairs to contract preserving changes. |
| MooseAgent, 2025 | Natural language generation of MOOSE input files | Iterative verification on several physics cases | Uses retrieval and multi agent generation; this project emphasizes explicit blocking decisions, frozen evaluation, COMSOL artifacts, and EDA decisions. |
| ALL FEM, 2026 | Fine tuned agents that generate and debug FEniCS code | 39 FEM benchmarks with runtime feedback | Broad FEM code generation; this project uses a smaller bounded physics catalog with traceable requirement and physical validation contracts. |
| PDE Agents, 2026 | Graph augmented multi agent FEM automation | Ablations, verification and validation, and run history | Studies knowledge graph integration; this project studies contract dependency completion and false safe decisions. |
| MOOSEnger, 2026 | Repository grounded MOOSE agent with executable diagnosis and memory | Physics category prompt sets and executable feedback | Uses a capable tool agent; this project separates advisory language models from local authority to solve, validate, and release evidence. |

## Verified primary references

1. ChatEDA: https://arxiv.org/abs/2308.10204
2. LayoutCopilot: https://doi.org/10.1109/TCAD.2025.3529805
3. EDAid: https://aclanthology.org/2025.naacl-long.83/
4. AutoEDA: https://arxiv.org/abs/2508.01012
5. FlowFixer EDA: https://doi.org/10.1109/ACCESS.2026.3730896
6. MooseAgent: https://arxiv.org/abs/2504.08621
7. ALL FEM: https://doi.org/10.1016/j.cma.2026.118985
8. PDE Agents: https://arxiv.org/abs/2606.07850
9. MOOSEnger: https://arxiv.org/abs/2608.15881

## Claim boundary for the final paper

The current P2 comparison is project authored development evidence. The final paper may describe its measured values, but the abstract and conclusion must not present them as independent generalization evidence. The P3 main table and any independent performance claim must remain absent until all 24 external tasks, eight disjoint device families, and 192 required observations pass the frozen protocol.
