# pokemonle_solver

宝可梦猜谜游戏（[Pokemonle](https://github.com/QuantAskk/pokemonle)）辅助求解工具。

**核心设计原则**：直接读取并复用原游戏的图鉴数据文件（`serve/src/data/pokemon/` 下的单个 JSON 文件），无需将全部图鉴整合到单一文件，也无需二次处理数据。

---

## 使用方法

### 准备数据

克隆原游戏仓库以获取图鉴数据：

```bash
git clone https://github.com/QuantAskk/pokemonle.git
```

数据目录位于：`pokemonle/serve/src/data/pokemon/`

> **注意**：数据文件由 [QuantAskk/pokemonle](https://github.com/QuantAskk/pokemonle) 项目提供。如果该仓库不可访问，可使用任何包含同等格式单个宝可梦 JSON 文件的目录。

### 运行求解器

```bash
python solver.py --data-dir /path/to/pokemonle/serve/src/data/pokemon
```

求解器会根据每次猜测后游戏给出的反馈逐步缩小候选范围，最终给出答案。

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--data-dir` | 原游戏 `serve/src/data/pokemon/` 目录路径 | （必填） |
| `--top` | 每轮显示的候选宝可梦数量 | 10 |

---

## 反馈格式说明

每次猜测后，根据游戏显示的颜色输入对应反馈：

| 游戏显示 | 输入值 |
|----------|--------|
| 🟩 绿色（完全匹配） | `True` 或 `equiv` |
| 🟨 黄色（接近/相邻） | `near`（数值类）|
| ⬜ 灰色（不匹配） | `False` 或 `low`/`high` |

数值比较（种族值、速度、世代、捕获率）：
- `equiv`：与目标完全相同
- `low`：猜测值低于目标（答案更高）
- `high`：猜测值高于目标（答案更低）

---

## 数据文件格式

求解器直接读取游戏仓库中 `serve/src/data/pokemon/` 目录下的单个宝可梦 JSON 文件（如 `0001-妙蛙种子.json`），无需任何预处理或合并步骤。每个文件包含该宝可梦的完整图鉴信息（属性、种族值、特性、进化方式、蛋组等）。世代信息由文件内 `flavor_texts` 字段的第一条记录自动推导。

## 依赖

仅使用 Python 标准库，无需安装额外依赖。需要 Python 3.8+。
