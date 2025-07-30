import os
import re
import math
import json
import sys
from typing import List, Tuple, Dict


# --- Core Prefab Parsing Logic (migrated from prefab_reader.py) ---

def _extract_data_from_content(content: str) -> Tuple[Dict[int, str], Dict[int, Dict], set]:
    """
    Extracts GameObject, Transform, and root children data from prefab content.
    """
    gameobjects = {}
    transforms = {}
    root_child_ids = set()

    documents = content.split('--- ')
    for doc in documents:
        if not doc.strip():
            continue

        go_match = re.search(r"!u!1 &(\d+)\s*GameObject:[\s\S]*?m_Name: (.*?)\r?\n", doc)
        if go_match:
            gameobjects[int(go_match.group(1))] = go_match.group(2)

        tr_match = re.search(
            r"!u!4 &(\d+)\s*Transform:[\s\S]*?m_GameObject: {fileID: (\d+)}[\s\S]*?m_LocalPosition: {x: ([-\d.]+), y: ([-\d.]+)",
            doc)
        if tr_match:
            tr_id = int(tr_match.group(1))
            go_id = int(tr_match.group(2))
            x = float(tr_match.group(3))
            y = float(tr_match.group(4))
            transforms[tr_id] = {'go_id': go_id, 'pos': (x, y)}

            if 'm_Father: {fileID: 0}' in doc:
                children_block_match = re.search(r"m_Children:\s*([\s\S]*?)(?:\s*m_Father|\s*m_LocalEulerAnglesHint)",
                                                 doc)
                if children_block_match:
                    children_block = children_block_match.group(1)
                    found_ids = re.findall(r'- {fileID: (.*?)}', children_block)
                    root_child_ids.update([int(i) for i in found_ids])

    return gameobjects, transforms, root_child_ids


def calculate_length_from_content(content: str) -> float:
    """
    Calculates the physical length of a slide from the raw text content of a .prefab file.
    """
    gameobjects, transforms, root_child_ids = _extract_data_from_content(content)

    slide_segments = []
    for child_id in root_child_ids:
        if child_id in transforms:
            go_id = transforms[child_id]['go_id']
            name = gameobjects.get(go_id, '')
            if name.startswith("Slide_"):
                slide_segments.append({
                    'name': name,
                    'pos': transforms[child_id]['pos']
                })

    # Sort segments by the number in their name, e.g., Slide_01 (1), Slide_01 (2), etc.
    slide_segments.sort(
        key=lambda x: int(re.search(r'\((\d+)\)', x['name']).group(1)) if re.search(r'\((\d+)\)', x['name']) else 0)

    slide_points = [seg['pos'] for seg in slide_segments]

    if len(slide_points) < 2:
        return 0.0

    total_length = 0.0
    for i in range(len(slide_points) - 1):
        p1 = slide_points[i]
        p2 = slide_points[i + 1]
        total_length += math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

    return total_length


# --- Main Abstraction Logic ---

def create_length_config(prefab_dir: str, output_path: str):
    """
    Reads all .prefab files in a directory, calculates their slide lengths,
    and saves the results to a JSON configuration file.
    """
    print(f"Starting prefab processing from: '{prefab_dir}'")

    if not os.path.isdir(prefab_dir):
        print(f"Error: Prefab directory not found at '{prefab_dir}'.", file=sys.stderr)
        sys.exit(1)

    prefab_lengths = {}

    for filename in os.listdir(prefab_dir):
        if filename.endswith(".prefab"):
            print(f"  Processing '{filename}'...")
            file_path = os.path.join(prefab_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                length = calculate_length_from_content(content)
                prefab_lengths[filename] = length
            except Exception as e:
                print(f"    Could not process file {filename}: {e}", file=sys.stderr)

    # Ensure the target directory exists
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(prefab_lengths, f, indent=4)

    print(f"\nSuccessfully generated length configuration file at: '{output_path}'")


def main():
    """
    Main script entry point.
    """
    # Assuming the script is run from the project root directory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    prefab_directory = os.path.join(project_root, "Assets", "SlidePrefab")
    config_output_path = os.path.join(project_root, "Assets", "prefab_lengths.json")

    create_length_config(prefab_directory, config_output_path)


if __name__ == "__main__":
    main()
