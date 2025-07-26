import re
from typing import List


def parse_note_to_segments(note_content: str) -> List[str]:
    """
    Parses a complex slide string into a list of individual, calculable segments.
    Handles special cases like 'V' shapes.
    """
    base_content = re.sub(r'\[.*?\]', '', note_content).strip()
    if not base_content or not base_content[0].isdigit():
        return []

    # Pre-process V-shapes: aVbc is decomposed into two straight slides a-b and b-c.
    # A special separator '*' is used to handle chains.
    v_pattern = re.compile(r'(\d)V(\d)(\d)')
    base_content = v_pattern.sub(r'\1-\2*\2-\3', base_content)

    segments = []
    chains = base_content.split('*')

    for chain in chains:
        if not chain: continue
        last_end_pos_char = chain[0]
        remaining_content = chain[1:]

        while remaining_content:
            match = re.match(r'([pPqQ<>^w\-sSzZ]{1,2})(\d)', remaining_content)
            if not match:
                break

            shape = match.group(1)
            end_char = match.group(2)

            segment = f"{last_end_pos_char}{shape}{end_char}"
            segments.append(segment)

            last_end_pos_char = end_char
            remaining_content = remaining_content[len(shape) + 1:]

    return segments
