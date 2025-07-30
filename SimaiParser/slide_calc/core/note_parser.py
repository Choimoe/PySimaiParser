import re
from typing import List


def parse_note_to_segments(note_content: str) -> List[str]:
    """
    Parses a complex slide string into a list of individual, calculable segments.
    Handles special cases like 'V' shapes and '*' for branching slides.
    """
    # Remove timing/BPM markers, e.g., [4:1]
    base_content = re.sub(r'\[.*?\]', '', note_content).strip()
    if not base_content or not base_content[0].isdigit():
        return []

    # Record the global starting key for branching slides
    global_start_char = base_content[0]

    # Pre-process V-shapes: aVbc is decomposed into two continuous slides a-b and b-c.
    # The '*' here is used to separate continuous chains. e.g., 5V13 -> 5-1*1-3
    v_pattern = re.compile(r'(\d)V(\d)(\d)')
    base_content = v_pattern.sub(r'\1-\2*\2-\3', base_content)

    segments = []
    # Split the note into chains using '*' as a delimiter.
    chains = base_content.split('*')

    for chain in chains:
        if not chain:
            continue

        remaining_content: str
        last_end_pos_char: str

        # Check if the chain starts with a number.
        # If yes, it's a continuous chain (e.g., "1-3" or "3>5").
        # If no, it's a branch from the global start (e.g., "s5" in "1-3*s5").
        if chain[0].isdigit():
            last_end_pos_char = chain[0]
            remaining_content = chain[1:]
        else:
            last_end_pos_char = global_start_char
            remaining_content = chain

        # Process all segments within the current chain
        while remaining_content:
            # Match a shape (1-2 chars) followed by an end position (1 digit)
            match = re.match(r'([pPqQ<>^w\-sSzZ]{1,2})(\d)', remaining_content)
            if not match:
                # Could not parse the rest of the chain, stop processing it.
                break

            shape = match.group(1)
            end_char = match.group(2)

            segment = f"{last_end_pos_char}{shape}{end_char}"
            segments.append(segment)

            # The end of the current segment is the start of the next one in this chain
            last_end_pos_char = end_char
            remaining_content = remaining_content[len(match.group(0)):]

    return segments
