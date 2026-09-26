# A题总体技术路线图 v001

2026-09-26，根据用户提供的五张优秀论文路线图制作纵向单页总图。

## 交付

- `deliverables/技术路线图_可编辑.pptx`：121个原生形状与文本对象，无整页栅格图片，可分别修改文字、框及连接线。
- `deliverables/技术路线图.svg`：矢量源图。
- `deliverables/技术路线图.pdf`：单页论文插图。
- `deliverables/技术路线图_高清.png`：3600×4980像素。

## 内容依据

第一问采用正式v009双候选流程，对应`src/portfolio_scheduler.py`、`baseline.py`、`region_scheduler.py`及`outputs/08_full/主要报告.md`。未把六图局部试验写入正式主线。

第二问采用正式v011，对应`src/scene_b_active_cores.py`、`scene_b_paired_order.py`、`scene_b_adaptive.py`及`outputs/09_problem2/v011_summary_20260926/REPORT.md`。单核为独立候选；双方法候选用于k≥2。代理代价只用于候选内部筛选，最终按目标N核实际Makespan选择。

第三问采用正式v004，对应`src/scene_b_window_components.py`及`outputs/10_problem3/v004_full_20260926/REPORT.md`。新窗口候选改变子图划分及核分配，不沿用早期“固定分核只调顺序”的叙述。窗口法借鉴来源与MIT许可保留在原代码及`scene_b_window_components.LICENSE`，图中未作原创声明。基准加三个窗口候选按Cache Makespan选择，并以同方案有无L2对照区分收益。

## 构建与验证

`.build/build.mjs`从同一几何定义生成原生PPTX与SVG，再导出PNG和PDF。字体为Microsoft YaHei。PPTX结构、字体和布局检查通过，无检查发现。已检查渲染图。尚未在Microsoft PowerPoint应用中人工打开验证。

原始赛题、代码、数据及既有实验结果均未修改。路线图中的范围依据现有正式记录，不代表重新运行了算法实验。
