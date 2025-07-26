import re


def _calculate_relative_distance(start: int, end: int, shape: str) -> int:
    """Calculates the relative distance between two buttons on an 8-button circle."""
    if start == end: return 8

    # This custom logic appears to mirror the slide path based on the starting button.
    if shape in ('>', 'p', 'pp'):  # Clockwise shapes
        if start in (3, 4, 5, 6):
            return (start - end + 8) % 8
        else:
            return (end - start + 8) % 8
    elif shape in ('<', 'q', 'qq'):  # Counter-clockwise shapes
        if start in (3, 4, 5, 6):
            return (end - start + 8) % 8
        else:
            return (start - end + 8) % 8
    elif shape == '^':  # Shortest path
        clockwise = (end - start + 8) % 8
        counter_clockwise = (start - end + 8) % 8
        return min(clockwise, counter_clockwise)
    else:  # Straight, V, S, Z shapes
        return abs(end - start)


def _get_shape_type(shape_char: str) -> str:
    """Returns the base name for a prefab based on the shape character."""
    if '-' in shape_char: return "Star_Line"
    if any(s in shape_char for s in ['>', '<', '^']): return "Star_Circle"
    if 'v' in shape_char.lower(): return "Star_V"
    if 'p' in shape_char.lower() and 'pp' not in shape_char.lower(): return "Star_pq"
    if 'q' in shape_char.lower() and 'qq' not in shape_char.lower(): return "Star_pq"
    if 's' in shape_char.lower() or 'z' in shape_char.lower(): return "Star_S"
    if 'pp' in shape_char.lower() or 'qq' in shape_char.lower(): return "Star_ppqq"
    if 'w' in shape_char.lower(): return "Slide_Wifi"
    raise ValueError(f"Unknown shape character: '{shape_char}'")


def map_segment_to_prefab(segment: str) -> str:
    """
    Maps a slide segment string to its corresponding .prefab file name.
    e.g., "2-4" -> "Star_Line_3.prefab"
    """
    start_pos = int(segment[0])
    shape_char = re.sub(r'[\d]', '', segment)
    end_pos = int(segment[-1])

    relative_distance = _calculate_relative_distance(start_pos, end_pos, shape_char)

    # All prefabs are designed as if starting from button 1.
    # The final button number in the prefab name is 1 + relative_distance.
    prefab_end_num = 1 + relative_distance
    if prefab_end_num > 8:
        prefab_end_num %= 8
        if prefab_end_num == 0: prefab_end_num = 8

    shape_type = _get_shape_type(shape_char)

    if shape_type in ["Star_S", "Slide_Wifi"]:
        return f"{shape_type}.prefab"
    else:
        return f"{shape_type}_{prefab_end_num}.prefab"
