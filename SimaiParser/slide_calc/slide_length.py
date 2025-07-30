import os
import sys
import json
from typing import Dict

from core.note_parser import parse_note_to_segments
from core.slide_rules import map_segment_to_prefab


class SimaiSlideCalculator:
    """
    Orchestrates the process of calculating the total physical length of a Simai
    slide note by reading pre-calculated lengths from a config file.
    """

    def __init__(self, config_path: str = "Assets/prefab_lengths.json"):
        """
        Initializes the calculator by loading prefab lengths from a JSON config file.
        """
        self.config_path = config_path
        self._length_cache = self._load_lengths_from_config()

    def _load_lengths_from_config(self) -> Dict[str, float]:
        """
        Loads the prefab name to length mapping from the specified JSON file.
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Prefab length configuration file not found at '{self.config_path}'.\n"
                f"Please run 'tools/abstract.py' first to generate it."
            )
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            raise ValueError(f"Error decoding JSON from '{self.config_path}'. The file may be corrupt.")

    def get_total_physical_length(self, note_content: str) -> float:
        """
        Calculates the total physical length for a complete Simai slide string.
        """
        total_length = 0.0
        segments = parse_note_to_segments(note_content)

        print("-" * 30)
        print(f"Parsing Note: '{note_content}'")
        print(f"Parsed Segments: {segments}")

        for segment in segments:
            try:
                # Special handling for 'w' shape as per game rules
                if 'w' in segment:
                    print(f"  Segment '{segment}' -> Special 'w' shape handling")
                    len1 = self._get_single_prefab_length("Star_Line_5.prefab")
                    print(f"    -> Calculating Star_Line_5.prefab length: {len1:.4f}")
                    len2 = self._get_single_prefab_length("Star_Line_4.prefab")
                    print(f"    -> Calculating Star_Line_4.prefab length: {len2:.4f}")
                    total_length += len1 + len2
                    continue

                prefab_name = map_segment_to_prefab(segment)
                print(f"  Segment '{segment}' -> Mapped to Prefab '{prefab_name}'")

                segment_length = self._get_single_prefab_length(prefab_name)
                print(f"    -> Fetched Length: {segment_length:.4f}")

                total_length += segment_length
            except (KeyError, ValueError) as e:
                print(f"  Error processing segment '{segment}': {e}", file=sys.stderr)
                continue

        print("-" * 30)
        return total_length

    def _get_single_prefab_length(self, prefab_name: str) -> float:
        """
        Retrieves the length of a single prefab from the pre-loaded cache.
        """
        try:
            return self._length_cache[prefab_name]
        except KeyError:
            # This error occurs if the rules map to a prefab name that wasn't
            # found or processed by abstract.py.
            raise KeyError(
                f"Prefab '{prefab_name}' not found in the configuration file. "
                f"Ensure it exists and 'tools/abstract.py' has been run."
            )


def main():
    """
    Main application entry point.
    """
    try:
        # The calculator now uses the generated config file.
        calculator = SimaiSlideCalculator()

        test_strings = [
            "1s5*z1",
            "2-4",
            "1>3",
            "2>4",
            "8^6<4",
            "5V13",
            "1pp2",
            "2qq4",
            "3p5",
            "6q8",
            "1-3[4:1]>5[4:1]",
            "2w6",
            "1-3>5V13<1"
        ]

        for note_str in test_strings:
            final_length = calculator.get_total_physical_length(note_str)
            print(f">>> Total calculated length for '{note_str}' is: {final_length:.4f}\n")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()