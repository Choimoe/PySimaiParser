# main.py
import os
import sys
from typing import Dict

from core.note_parser import parse_note_to_segments
from core.slide_rules import map_segment_to_prefab
from utils.prefab_reader import calculate_length_from_content


class SimaiSlideCalculator:
    """
    Orchestrates the process of calculating the total physical length of a Simai slide note.
    """

    def __init__(self, prefab_directory: str = "Assets/SlidePrefab"):
        self.prefab_directory = prefab_directory
        if not os.path.isdir(self.prefab_directory):
            raise FileNotFoundError(
                f"Prefab directory not found at '{self.prefab_directory}'.\n"
                f"Please ensure the script is in the same parent directory as the 'Assets' folder."
            )
        self._length_cache: Dict[str, float] = {}

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
                print(f"    -> Calculated Length: {segment_length:.4f}")

                total_length += segment_length
            except (FileNotFoundError, ValueError, IOError) as e:
                print(f"  Error processing segment '{segment}': {e}", file=sys.stderr)
                continue

        print("-" * 30)
        return total_length

    def _get_single_prefab_length(self, prefab_name: str) -> float:
        """
        Retrieves the length of a single prefab, using a cache to avoid redundant file reads.
        """
        if prefab_name in self._length_cache:
            return self._length_cache[prefab_name]

        prefab_path = os.path.join(self.prefab_directory, prefab_name)

        with open(prefab_path, 'r', encoding='utf-8') as f:
            content = f.read()

        length = calculate_length_from_content(content)
        self._length_cache[prefab_name] = length
        return length


def main():
    """
    Main application entry point.
    """
    try:
        calculator = SimaiSlideCalculator()

        test_strings = [
            "1-3",
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
