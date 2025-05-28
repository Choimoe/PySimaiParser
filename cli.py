# cli.py
# Command-line interface for the Simai Parser

import argparse
import json
import os
import sys

# Attempt to import the package and its version
try:
    from SimaiParser import SimaiChart, __version__ as pkg_version
except ImportError:
    # This block allows running cli.py directly for development
    # without the package being installed, assuming SimaiParser
    # is in a directory that Python can find (e.g., PYTHONPATH or sibling).
    pkg_version = "0.0.0-dev (package not installed)"
    # Attempt to add the parent directory to sys.path if SimaiParser is a sibling
    # This is a common pattern for local development.
    # Get the directory containing cli.py
    # cli_dir = os.path.dirname(os.path.abspath(__file__))
    # project_root = os.path.dirname(cli_dir) # If cli.py is in a 'scripts' or 'bin' folder
    # Or if cli.py is at project root and SimaiParser is a subdir:
    # project_root = cli_dir
    # sys.path.insert(0, project_root)
    # try:
    # from SimaiParser import SimaiChart # Try importing again
    # except ImportError as e:
    # print(f"Development Warning: Could not import SimaiChart. Ensure SimaiParser is in PYTHONPATH or accessible. Error: {e}", file=sys.stderr)
    # SimaiChart = None # Define it as None or a mock if essential for script structure
    # For this script, if SimaiChart cannot be imported, main() will fail later, which is acceptable.
    # We will rely on the direct import at the top if the package is properly structured and accessible.
    pass  # Keep pkg_version as dev, SimaiChart might fail later if not found by the top-level import


# If the above try-except for SimaiChart itself is problematic,
# ensure SimaiChart is imported after potentially modifying sys.path,
# or rely on the initial import succeeding if PYTHONPATH is set correctly.
# For simplicity, we'll assume the initial `from SimaiParser import SimaiChart` works
# if the package is structured correctly and the script is run from the project root
# or the package is installed.

def main():
    """
    Main function to handle command-line arguments and process the Simai file.
    """
    # Ensure SimaiChart is available; if not, it's a critical error for the CLI's purpose.
    # The try-except at the top handles' pkg_version for the --version flag.
    # If SimaiChart itself failed to import, we should indicate that.
    try:
        from SimaiParser import SimaiChart
    except ImportError:
        print("Error: Could not import SimaiChart from SimaiParser.", file=sys.stderr)
        print("Please ensure the package is installed or your PYTHONPATH is configured correctly.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Parse a Simai chart file (.txt) and convert it to JSON."
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Path to the input Simai chart file (.txt)."
    )
    parser.add_argument(
        "-o", "--output_file",
        type=str,
        help="Optional. Path to save the output JSON file. "
             "If not provided, JSON will be printed to standard output."
    )
    parser.add_argument(
        "-i", "--indent",
        type=int,
        default=2,
        help="Indentation level for the output JSON. Default is 2. Use a negative value for compact output."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s (SimaiParser {pkg_version})",  # Use the imported or default version
        help="Show program's version number and exit."
    )

    args = parser.parse_args()

    input_filepath = args.input_file
    output_filepath = args.output_file
    json_indent = args.indent if args.indent >= 0 else None  # Compact output if indent is negative

    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found at '{input_filepath}'", file=sys.stderr)
        sys.exit(1)

    if not input_filepath.lower().endswith(".txt"):  # Basic check, Simai often uses .txt
        print(f"Warning: Input file '{input_filepath}' does not seem to be a .txt file. Proceeding anyway.",
              file=sys.stderr)

    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            simai_content = f.read()
    except Exception as e:
        print(f"Error reading input file '{input_filepath}': {e}", file=sys.stderr)
        sys.exit(1)

    try:
        chart = SimaiChart()
        chart.load_from_text(simai_content)
        json_output = chart.to_json(indent=json_indent)
    except Exception as e:
        print(f"Error parsing Simai content: {e}", file=sys.stderr)
        sys.exit(1)

    if output_filepath:
        try:
            with open(output_filepath, 'w', encoding='utf-8') as f:
                f.write(json_output)
            print(f"Successfully parsed Simai file and saved JSON to '{output_filepath}'")
        except Exception as e:
            print(f"Error writing output JSON file '{output_filepath}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Print to standard output if no output file is specified
        print(json_output)


if __name__ == "__main__":
    # The version import logic is now at the top of the file.
    # The main concern here is ensuring that 'SimaiParser' can be found
    # when running cli.py directly for development.
    # If cli.py is at the project root and 'SimaiParser' is a subdirectory,
    # Python's default import mechanism should work when running `python cli.py ...`
    # from the project root.
    # If the package is installed (e.g., `pip install .`), it will also be found.
    main()
