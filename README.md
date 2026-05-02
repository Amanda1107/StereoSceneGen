# 面向深度感知的多视角合成数据集构建系统

> 基于 BlenderProc 与 Blender Python API，实现多场景、多视角、RGB-D 配对数据集的自动化生成管线。

---

## 项目概述

本系统以多个高质量 `.blend` 三维场景为输入，自动完成相机阵列布置、场景可见性同步、批量渲染及 RGB-D 数据提取等全流程工作，最终输出可供深度估计、立体匹配等感知算法训练与评测使用的结构化数据集。

**核心能力：**
- 从原始 `.blend` 场景中动态继承相机内外参（位置、旋转、焦距）
- 自动同步场景集合层级可见性，忠实还原美术师的创作意图
- 以任意基线间距构建 `rows × cols` 相机阵列
- 批量渲染多个场景，输出 `.hdf5` 格式的 RGB + Distance 配对数据
- 将 `.hdf5` 解包为 `.png`（RGB）与 `.npy`（深度矩阵），并生成对数映射深度可视化图

---

## 目录结构

```
project/
├── assets/                         # 三维场景资产
│   ├── alley/
│   │   └── ph_hidden_alley.blend
│   ├── Namaqualand/
│   │   └── Namaqualand.blend
│   ├── pine_forest/
│   │   └── polyhaven_pine_fir_forest.blend
│   └── the_shed/
│       └── the_shed.blend
│
├── utils/
│   ├── io_utils.py                 # 文件 I/O 工具函数
│   └── vis_utils.py                # HDF5 转图像工具函数
│
├── alley_cube.py                   # 单场景渲染（含前景参照物放置）
├── alley_parameter.py              # 单场景渲染（手动参数调试版）
├── batch.py                        # 多场景批量渲染主脚本
├── visualization.py                # HDF5 解包，提取 RGB + Depth
├── depth_visualization.py          # 深度矩阵对数映射可视化
│
├── output/                         # BlenderProc 渲染原始输出（.hdf5）
├── output_colors/                  # 提取后的 RGB 图像（.png）
└── output_depths/                  # 提取后的深度矩阵（.npy）及可视化图
```

---

## 脚本说明

### `batch.py` — 批量渲染主脚本

核心生产脚本，遍历 `scene_configs` 列表中的所有场景配置，依次完成加载、可见性修复、相机阵列构建和渲染。

**功能亮点：**
- 每轮迭代前调用 `bproc.clean_up()` 确保多场景间状态完全隔离
- 自动提取原场景相机参数并传递给阵列构建函数
- 通过显式 `frame` 参数写入位姿，规避 BlenderProc 隐式帧管理引起的错位问题
- 冻结环境动画，防止场景内置动画污染静态阵列渲染

**配置项（`scene_configs`）：**

```python
scene_configs = [
    {
        "blend_path": "./assets/alley/ph_hidden_alley.blend",
        "output_dir":  "output/alley_scenario_test",
        "gap_mm":      37.5   # 相机阵列基线间距（毫米）
    },
    # 添加更多场景...
]
```

---

### `alley_cube.py` / `alley_parameter.py` — 单场景调试脚本

用于对单一场景进行快速参数验证。

| 脚本 | 特点 |
|---|---|
| `alley_cube.py` | 在相机正前方自动放置红色长方体作为深度参照物 |
| `alley_parameter.py` | 手动指定焦距和基线，方便参数对比实验 |

---

### `visualization.py` — RGB-D 数据提取

遍历 `./output/` 目录下所有场景的 `.hdf5` 文件，分别提取：
- `colors` 通道 → `output_colors/<场景名>_rgb/*.png`
- `distance` 通道 → `output_depths/<场景名>_depth/*.npy`

---

### `depth_visualization.py` — 深度图可视化

读取 `./output_depths/` 下所有 `.npy` 深度矩阵，以对数映射（LogNorm）方式生成 `plasma` 配色方案的伪彩色深度图，并自动过滤天空等无效无穷大值。

输出文件命名规则：`<原文件名>_vis.png`

---

## 快速开始

### 环境依赖

```bash
# 推荐使用 BlenderProc 官方环境
pip install blenderproc
# 其他依赖
pip install numpy matplotlib h5py
```

### 步骤一：批量渲染

```bash
blenderproc run batch.py
```

渲染完成后，`.hdf5` 数据保存于 `./output/<场景名>/`。

### 步骤二：提取 RGB-D 数据对

```bash
python visualization.py
```

### 步骤三：生成深度可视化图

```bash
python depth_visualization.py
```

---

## 相机阵列设计

系统采用本地坐标系矩阵乘法构建相机阵列，确保偏移量始终相对于主相机朝向，而非世界坐标轴。

```
┌─────────────────────────────────────┐
│  相机阵列示意（2 行 × 3 列）         │
│                                     │
│   [Cam 0]   [Cam 1]   [Cam 2]       │  ← 第 0 行
│                                     │
│   [Cam 3]   [Cam 4]   [Cam 5]       │  ← 第 1 行
│                                     │
│   ←──────── gap_mm ────────→        │
└─────────────────────────────────────┘
```

关键参数：

| 参数 | 说明 | 默认值 |
|---|---|---|
| `rows` | 阵列行数 | 2 |
| `cols` | 阵列列数 | 3 |
| `gap_mm` | 相邻相机水平间距（mm） | 37.5 |
| `focal_length` | 相机焦距（mm） | 继承自场景 |
| `resolution` | 渲染分辨率（px） | 1024 × 1024 |

---

## 可见性同步机制

BlenderProc 在加载 `.blend` 文件时会重置部分可见性状态，导致原作者隐藏的对象（如隐藏的建模参考、体积雾气等）被意外渲染。本系统实现了三级修复：

1. **集合层级同步**：从原 `.blend` 的 View Layer 中递归读取被排除/隐藏的 Collection 名单，并应用到当前场景所有关联物体。
2. **物体状态唤醒**：对灯光、集合实例等特殊类型执行针对性的节点与可见性修复。
3. **关键字过滤**：自动隐藏名称包含 `fog`、`atmosphere`、`volume`、`mist` 等关键字的体积对象。

---

## 输出格式

| 目录 | 内容 | 格式 |
|---|---|---|
| `output/<场景>/` | BlenderProc 原始渲染 | `.hdf5`（含 RGB + Distance） |
| `output_colors/<场景>_rgb/` | 全彩渲染图像 | `.png` |
| `output_depths/<场景>_depth/` | 深度距离矩阵 | `.npy`（float32，单位：米） |
| `output_depths/<场景>_depth/` | 深度伪彩色可视化 | `*_vis.png` |

---

## 已支持场景

| 场景 | 路径 | 特点 |
|---|---|---|
| Hidden Alley | `assets/alley/` | 城市窄巷，远近景深动态范围大 |
| Namaqualand | `assets/Namaqualand/` | 开阔自然地貌 |
| Pine Forest | `assets/pine_forest/` | 密集植被，遮挡复杂 |
| The Shed | `assets/the_shed/` | 室内外过渡场景 |
