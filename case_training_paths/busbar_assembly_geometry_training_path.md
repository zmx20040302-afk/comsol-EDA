# 母线板装配几何系列教程：小模型训练路径

## 1. 案例定位

案例目录：

```text
D:/桌面/codex/案例下载/COMSOL/母线板装配几何系列教程/
```

该案例主要是 **COMSOL 几何建模与装配序列教程**，核心训练价值是让小模型学习：

- 如何用 COMSOL 几何 Part / Sequence / Subsequence 构建复杂装配
- 如何组织参数化几何尺寸
- 如何从 MATLAB LiveLink 和 Java 导出代码还原模型树
- 如何把几何参数转成可扫描变量
- 如何为后续物理场仿真生成可训练数据

当前目录没有现成的参数扫描 CSV，因此暂时不能直接训练数值代理模型；需要先由 COMSOL 运行参数扫描并导出结果。

## 2. 文件分工

### PDF 学习文档

```text
models.mph.busbar_assembly_geometry.pdf
models.mph.busbar_assembly_groups_geometry.pdf
```

用途：

- 学习案例目标、几何构建步骤和装配逻辑
- 提取建模顺序、几何对象、参数说明、教程意图
- 作为小模型的“案例说明”和“建模理论来源”

### MATLAB LiveLink 脚本

```text
busbar_assembly_geom_sequence.m
busbar_assembly_geom_subsequence.m
busbar_assembly_groups_geom_sequence.m
```

用途：

- 训练小模型识别 COMSOL LiveLink 建模语法
- 提取几何创建顺序、Part、WorkPlane、Extrude、Selection、参数引用
- 作为自动生成 MATLAB 建模脚本的模板来源

### Java 导出代码

```text
busbar_assembly_geom_sequence.java
busbar_assembly_geom_subsequence.java
busbar_assembly_groups_geom_sequence.java
```

用途：

- 与 MATLAB 脚本交叉验证模型树
- 学习 COMSOL Java API 中的 geometry feature、selection、parameter 调用模式
- 作为模型结构摘要和标签命名参考

### COMSOL MPH 模型

```text
busbar_assembly_geom_sequence.mph
busbar_assembly_geom_sequence.zh_CN.mph
busbar_assembly_geom_subsequence.mph
busbar_assembly_geom_subsequence.zh_CN.mph
busbar_assembly_groups_geom_sequence.mph
busbar_assembly_groups_geom_sequence.zh_CN.mph
```

用途：

- COMSOL 原始模型
- 需要在 COMSOL with MATLAB 中导出摘要后，才能可靠进入小模型知识库

建议导出：

```matlab
summary = export_mph_summary('busbar_assembly_geom_sequence.mph', 'busbar_assembly_geom_sequence_summary.json');
summary = export_mph_summary('busbar_assembly_geom_subsequence.mph', 'busbar_assembly_geom_subsequence_summary.json');
summary = export_mph_summary('busbar_assembly_groups_geom_sequence.mph', 'busbar_assembly_groups_geom_sequence_summary.json');
```

### 参数文件

```text
busbar_assembly_groups_geom_parameters.txt
busbar_assembly_groups_geom_parameters.zh_CN.txt
```

用途：

- 提取几何参数名称、默认值、单位、含义
- 作为参数扫描设计的输入变量来源

关键参数包括：

```text
c_g_w, c_g_l, c_g_h
s_l, s_w, s_h, s_di, s_c_w, s_c_l
c_c_r, c_c_h, c_c_d
r_c_h, r_c_w
e_c_h, e_c_lx, e_c_lz
a_c_h, a_c_w
r_d, r_l
i_b_h, i_b_l, i_b_w
b_di, b_r
```

## 3. 第一阶段：案例阅读与建模逻辑学习

目标：

```text
让小模型理解该案例如何搭建几何，而不是先预测数值结果。
```

在网页中读取以下文件：

```text
D:/桌面/codex/案例下载/COMSOL/母线板装配几何系列教程/models.mph.busbar_assembly_geometry.pdf
D:/桌面/codex/案例下载/COMSOL/母线板装配几何系列教程/models.mph.busbar_assembly_groups_geometry.pdf
D:/桌面/codex/案例下载/COMSOL/母线板装配几何系列教程/busbar_assembly_geom_sequence.m
D:/桌面/codex/案例下载/COMSOL/母线板装配几何系列教程/busbar_assembly_geom_sequence.java
D:/桌面/codex/案例下载/COMSOL/母线板装配几何系列教程/busbar_assembly_geom_subsequence.m
D:/桌面/codex/案例下载/COMSOL/母线板装配几何系列教程/busbar_assembly_geom_subsequence.java
D:/桌面/codex/案例下载/COMSOL/母线板装配几何系列教程/busbar_assembly_groups_geom_sequence.m
D:/桌面/codex/案例下载/COMSOL/母线板装配几何系列教程/busbar_assembly_groups_geom_sequence.java
D:/桌面/codex/案例下载/COMSOL/母线板装配几何系列教程/busbar_assembly_groups_geom_parameters.txt
```

然后点击：

```text
学习总结
```

预期输出：

- PDF 学习文档分组
- MATLAB 建模脚本分组
- Java 导出代码分组
- 参数 TXT 作为文本资料
- 几何训练路径建议

## 4. 第二阶段：建立几何参数约束

建议先把参数分成三类：

### 主要尺寸变量

```text
c_g_w, c_g_l, c_g_h
i_b_l, i_b_w, i_b_h
r_l, r_d
```

### 连接件变量

```text
r_c_h, r_c_w
e_c_h, e_c_lx, e_c_lz
a_c_h, a_c_w
```

### 孔、边距和细节变量

```text
b_di, b_r
s_di, s_c_w, s_c_l
c_c_r, c_c_h, c_c_d
```

约束原则：

- 所有长度保持正值
- 派生参数如 `s_l = c_g_l/2 - 2*s_di` 必须大于 0
- 派生参数如 `s_w = c_g_w/2 - 2*s_di` 必须大于 0
- 螺栓半径 `b_r` 应小于螺栓边距 `b_di`
- 孔、柱、杆、连接件不能超过所在母体尺寸

## 5. 第三阶段：COMSOL 参数扫描

该案例要成为可训练代理模型，需要在 COMSOL 中生成 CSV。

推荐扫描输入：

```text
c_g_w
c_g_l
s_di
c_c_r
r_d
r_l
i_b_w
i_b_h
b_r
b_di
```

推荐输出：

如果只训练几何代理模型：

```text
volume_total
surface_area_total
min_feature_size
geometry_build_success
entity_count
```

如果后续添加结构力学：

```text
max_displacement
max_von_mises_stress
reaction_force
```

如果后续添加电流/热：

```text
max_temperature
average_temperature
max_current_density
electric_resistance
```

推荐 CSV 格式：

```csv
c_g_w,c_g_l,s_di,c_c_r,r_d,r_l,i_b_w,i_b_h,b_r,b_di,volume_total,surface_area_total,geometry_build_success
400,800,10,40,20,160,120,10,6,20,1.23e-3,2.34,1
```

## 6. 第四阶段：训练小模型

当已经得到 CSV，例如：

```text
cases/busbar_assembly_geometry/busbar_geometry_sweep.csv
```

训练命令：

```powershell
cd D:/桌面/codex/comsol1/comsol_training_small_model
python -m src.comsol_small_model.cli train cases/busbar_assembly_geometry/busbar_geometry_sweep.csv busbar_geometry.joblib --inputs c_g_w c_g_l s_di c_c_r r_d r_l i_b_w i_b_h b_r b_di --outputs volume_total surface_area_total geometry_build_success
```

预测命令：

```powershell
python -m src.comsol_small_model.cli predict busbar_geometry.joblib --inputs 400 800 10 40 20 160 120 10 6 20
```

## 7. 推荐训练数据规模

```text
20-50 组：流程验证
100-300 组：几何代理初步可用
500-2000 组：适合稳定预测体积、面积、建模成功率
2000+ 组：适合加入结构、电流、热等多物理场输出
```

## 8. 该案例的小模型训练目标

短期目标：

```text
从 PDF/MATLAB/Java/TXT 学习几何建模流程，形成案例知识摘要。
```

中期目标：

```text
用参数扫描 CSV 训练几何代理模型，预测体积、面积、建模成功率。
```

长期目标：

```text
在几何基础上添加电流、结构或热物理场，训练多物理场代理模型。
```

## 9. 推荐实现顺序

```text
读取全部案例文件
  ↓
生成学习总结
  ↓
提取参数约束
  ↓
在 COMSOL 中设置参数扫描
  ↓
导出 CSV
  ↓
训练几何代理模型
  ↓
增加结构/电/热物理场
  ↓
训练多物理场代理模型
```
