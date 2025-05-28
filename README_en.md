[阅读中文版 (Read this document in Chinese)](README.md)

# PySimaiParser: A Python Simai Chart Parser

PySimaiParser is a Python library and command-line tool designed to parse Simai chart files (typically `maidata.txt` or similar formats) used in rhythm games. It converts the chart data, including metadata and detailed note information, into a structured JSON format. This makes the chart data more accessible for analysis, processing, or integration into other applications and tools.

## Features

- **Comprehensive Metadata Parsing**: Extracts key chart information such as title, artist, designer, first beat offset (`&first`), and difficulty levels (`&lv_x`).
- **Detailed Fumen (Chart Data) Parsing**:
  - Accurately processes BPM (Beats Per Minute) changes `(value)`.
  - Handles beat signature modifications `{value}`.
  - Parses Hi-Speed (HS) adjustments `Hvalue>` or `HS*value>`.
  - Calculates precise note timings based on the above parameters.
- **Granular Note Interpretation**:
  - Supports all standard Simai note types: TAP, HOLD, SLIDE (with various path notations like `-`, `^`, `v`, `<`, `>`, `V`, `p`, `q`, `s`, `z`, `w`), TOUCH (A-E, C), and TOUCH_HOLD.
  - Deciphers complex note modifiers and flags: break notes (`b`), EX notes (`x`), hanabi/fireworks (`f`), slides without a visible head (`!`, `?`), forced star visuals (`$`), and fake rotation effects (`$$`).
  - Interprets intricate duration syntax for holds/slides (e.g., `[beat_division:num_beats]`, `[bpm#beat_division:num_beats]`, `[#absolute_time]`) and star-wait time calculations for slides (e.g., `[wait_bpm#...]`, `[wait_abs_time##duration]`).
  - Correctly handles simultaneous notes separated by `/`, same-head slides using `*`, and pseudo-simultaneous "flam" notes using ` `.
- **Structured JSON Output**: Generates a well-organized and human-readable JSON object representing the entire parsed chart, suitable for direct use or further processing.
- **Command-Line Interface (CLI)**: Includes an easy-to-use CLI tool (`cli.py`) for quick conversion of Simai chart files to JSON, with options for output file and indentation.
- **Python Package**: Designed as a Python package (`SimaiParser`) for straightforward integration into other Python projects.

## Project Structure

```
PySimaiParser/
├── SimaiParser/
│   ├── __init__.py
│   ├── core.py          # Contains SimaiChart and parser core logic
│   ├── note.py          # SimaiNote data class
│   └── timing.py        # SimaiTimingPoint timing class
├── tests/
│   ├── __init__.py
│   └── test_core.py           # Tests for core.py
├── cli.py                     # Command-line interface script
├── LICENSE.txt                # LICENSE file
├── README_en.md               # This file
└── README.md                  # README in Chinese
```

## Installation

1. **Install with pip** (recommended):

   ```bash
   # Install directly from GitHub
   pip install git+https://github.com/Choimoe/PySimaiParser.git

   # Or clone and install locally
   git clone https://github.com/Choimoe/PySimaiParser.git
   cd PySimaiParser
   pip install .
   ```

2. **Verify installation**:

   ```bash
   pysimaiparser-cli --version
   # Should output 0.1.0
   ```

Recommended to install in a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install .
```

## Usage

### As a Python Library

```