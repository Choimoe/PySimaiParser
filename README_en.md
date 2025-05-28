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

1. **Clone the repository (if applicable):**

   ```
   git clone https://github.com/Choimoe/PySimaiParser.git
   cd PySimaiParser
   ```

2. **Install the package:** It's recommended to install in a virtual environment.

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

   Then, install the package (if you have a `setup.py` or `pyproject.toml`):

   ```
   pip install .
   ```

   If you don't have a setup file yet, you can use the package directly by ensuring the `PySimaiParser` directory (the one containing `SimaiParser` and `cli.py`) is in your `PYTHONPATH` or you run scripts from this directory.

## Usage

### As a Python Library

```
from SimaiParser import SimaiChart

simai_file_content = """
&title=Example Song
&artist=An Artist
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

# Access parsed data
# print(chart.metadata["title"])
# if chart.processed_fumens_data and chart.processed_fumens_data[3]["note_events"]:
#     first_note_time = chart.processed_fumens_data[3]["note_events"][0]["time"]
#     print(f"First note time of Expert fumen: {first_note_time}")
```

### As a Command-Line Tool

The `cli.py` script allows you to parse Simai files directly from your terminal.

1. **Navigate to the project directory where `cli.py` is located.**

2. **Run the script:**

   - Parse a file and print JSON to console:

     ```
     python cli.py path/to/your/chart.txt
     ```

   - Parse a file and save JSON to an output file:

     ```
     python cli.py path/to/your/chart.txt -o path/to/output.json
     ```

   - Specify JSON indentation (e.g., 4 spaces):

     ```
     python cli.py path/to/your/chart.txt -i 4
     ```

   - Get compact JSON output:

     ```
     python cli.py path/to/your/chart.txt -i -1
     ```

   - View help message:

     ```
     python cli.py -h
     ```

   - Check version:

     ```
     python cli.py --version
     ```

## Running Tests

Unit tests are located in the `tests/` directory and use Python's built-in `unittest` module.

1. **Navigate to the project root directory (`PySimaiParser/`).**

2. **Run tests:**

   ```
   python -m unittest discover tests
   ```

   Or, to run a specific test file:

   ```
   python -m unittest tests.test_core
   ```

## Contributing

Contributions are welcome! If you'd like to contribute, please consider the following:

- Fork the repository.
- Create a new branch for your feature or bug fix.
- Write tests for your changes.
- Ensure all tests pass.
- Submit a pull request with a clear description of your changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.