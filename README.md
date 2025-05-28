[Read this document in English (阅读英文版)](README_en.md)

# PySimaiParser：Python Simai 谱面解析器

PySimaiParser 是一个 Python 库和命令行工具，用于解析某些音乐游戏中使用的 Simai 谱面文件（通常是 `maidata.txt` 或类似格式）。它将谱面数据，包括元数据和详细的音符信息，转换为结构化的 JSON 格式。这使得谱面数据更易于分析、处理或集成到其他应用程序和工具中。

## 特性

- **全面的元数据解析**: 提取谱面的关键信息，如标题 (`&title`)、艺术家 (`&artist`)、谱师 (`&des`)、初始偏移时间 (`&first`) 和难度等级 (`&lv_x`)。
- **详细的谱面数据解析**:
  - 处理 BPM 变化 `(value)`。
  - 处理节拍记号变化 `{value}`。
  - 解析变速调整 `<Hvalue>` 或 `<HS*value>`。
  - 基于以上参数精确计算音符时间。
- **精细的音符解释**:
  - 支持所有标准 Simai 音符类型：TAP、HOLD、SLIDE (支持 `-`, `^`, `v`, `<`, `>`, `V`, `p`, `q`, `s`, `z`, `w` 等多种路径记号)、TOUCH (A-E, C) 和 TOUCH_HOLD。
  - 解析复杂的音符修饰符和标志：BREAK 音符 (`b`)、EX 音符 (`x`)、烟花效果 (`f`)、无头滑条 (`!`, `?`)、强制星星显示 (`$`) 和伪旋转效果 (`$$`)。
  - 解释复杂的 HOLD/SLIDE 时值和 SLIDE 星星等待时间语法 (例如 `[拍号分母:拍数]`、`[BPM#拍号分母:拍数]`、`[#绝对秒数]` 以及 `[等待BPM#...]`、`[绝对等待秒数##持续秒数]`)。
  - 正确处理通过 `/` 分隔的同时音符、使用 `*` 的同头滑条以及使用 ``` 的伪同时音符（装饰音）。
- **结构化 JSON 输出**: 生成组织良好且易读的 JSON 对象，代表整个解析后的谱面，适合直接使用或进一步处理。
- **命令行接口 (CLI)**: 提供简单易用的命令行工具 (`cli.py`)，用于快速将 Simai 谱面文件转换为 JSON，并可指定输出文件和缩进。
- **Python 包**: 设计为 Python 包 (`SimaiParser`)，方便集成到其他 Python 项目中。

## 项目结构

```
PySimaiParser/
├── SimaiParser/
│   ├── __init__.py
│   ├── core.py                # 包含 SimaiChart 和解析器核心逻辑
│   ├── note.py                # 包含 SimaiNote 音符数据类
│   └── timing.py              # 包含 SimaiTimingPoint 时间点类
├── tests/                     # 单元测试
│   ├── __init__.py
│   └── test_core.py           # core.py 的测试文件
├── cli.py                     # 命令行接口脚本
├── LICENSE.txt                # LICENSE 文件
├── README_en.md               # 英文版 README
└── README.md                  # 中文版 README (本文档)
```

## 安装

1. **clone 仓库:**

   ```
   git clone https://github.com/Choimoe/PySimaiParser.git
   cd PySimaiParser
   ```

2. **安装包:** 建议在虚拟环境中安装。

   ```
   python -m venv venv
   source venv/bin/activate  # Windows 系统: venv\Scripts\activate
   ```

   然后，安装包 (如果您有 `setup.py` 或 `pyproject.toml` 文件):

   ```
   pip install .
   ```

   如果您还没有安装配置文件，可以通过确保 `PySimaiParser` 目录 (包含 `SimaiParser` 和 `cli.py` 的目录) 位于您的 `PYTHONPATH` 中，或者从该目录运行脚本来直接使用该包。

## 使用方法

### 作为 Python 库

```
from SimaiParser import SimaiChart

simai_file_content = """
&title=示例歌曲
&artist=某艺术家
&first=1.0
&lv_4=12
&inote_4=
(120)
1,2,
E1h[4:1],
"""

chart = SimaiChart()
chart.load_from_text(simai_file_content)
json_data = chart.to_json(indent=2)

print(json_data)

# 访问解析后的数据
# print(chart.metadata["title"])
# if chart.processed_fumens_data and chart.processed_fumens_data[3]["note_events"]:
#     first_note_time = chart.processed_fumens_data[3]["note_events"][0]["time"]
#     print(f"Expert 难度谱面的第一个音符时间: {first_note_time}")
```

### 作为命令行工具

`cli.py` 脚本允许您直接从终端解析 Simai 文件。

1. **导航到 `cli.py` 所在的目录。**

2. **运行脚本:**

   - 解析文件并将 JSON 打印到控制台：

     ```
     python cli.py path/to/your/chart.txt
     ```

   - 解析文件并将 JSON 保存到输出文件：

     ```
     python cli.py path/to/your/chart.txt -o path/to/output.json
     ```

   - 指定 JSON 缩进 (例如, 4个空格)：

     ```
     python cli.py path/to/your/chart.txt -i 4
     ```

   - 获取紧凑的 JSON 输出 (无额外空格的单行)：

     ```
     python cli.py path/to/your/chart.txt -i -1
     ```

   - 查看帮助信息：

     ```
     python cli.py -h
     ```

   - 查看版本号：

     ```
     python cli.py --version
     ```

## 运行测试

单元测试位于 `tests/` 目录中，并使用 Python 内置的 `unittest` 模块。

1. **导航到项目根目录 (`PySimaiParser/`)。**

2. **运行测试:**

   ```
   python -m unittest discover tests
   ```

   或者，运行特定的测试文件：

   ```
   python -m unittest tests.test_core
   ```

## 贡献

欢迎参与贡献！如果您想为项目做出贡献，请考虑以下几点：

- Fork 本仓库。
- 为您的新功能或错误修复创建一个新的分支。
- 为您的更改编写测试。
- 确保所有测试都通过。
- 提交一个 Pull Request，并清晰描述您的更改。

## 许可证

本项目采用 MIT 许可证。详情请参阅 `LICENSE` 文件。