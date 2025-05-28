import json
import re
from .timing import SimaiTimingPoint


class SimaiChart:
    """
    Main class to load, parse, and store data from a Simai chart file.
    """

    def __init__(self):
        self.metadata = {
            "title": "", "artist": "", "designer": "",
            "first_offset_sec": 0.0,  # from &first
            "levels": ["" for _ in range(7)],  # &lv_1 to &lv_7
            "other_commands_raw": ""  # Unparsed lines from metadata section
        }
        self.fumens_raw = ["" for _ in range(7)]  # Raw &inote_1 to &inote_7 strings

        # Processed data will be generated when to_dict() is called or via a dedicated process method
        self.processed_fumens_data = []

    def _get_value_from_line(self, line, prefix):
        """Helper to extract value from a 'prefix=value' string."""
        return line[len(prefix):].strip() if line.startswith(prefix) else ""

    def load_from_text(self, simai_text_content):
        """
        Parses the entire Simai chart from a string containing the file content.
        Populates metadata and raw fumen strings.
        """
        lines = simai_text_content.splitlines()

        current_fumen_index = -1
        reading_fumen_block = False
        temp_fumen_lines = []
        other_commands_buffer = []

        for i, line_orig in enumerate(lines):
            line = line_orig.strip()

            if reading_fumen_block:
                if line.startswith("&"):  # New metadata tag signals end of current fumen block
                    if current_fumen_index != -1:
                        self.fumens_raw[current_fumen_index] = "\n".join(temp_fumen_lines).strip()
                    reading_fumen_block = False
                    current_fumen_index = -1
                    temp_fumen_lines = []
                    # Fall through to process the new '&' tag
                else:
                    temp_fumen_lines.append(line_orig)  # Keep original formatting for fumen block
                    continue

                    # Process metadata tags (or if fall-through from fumen block end)
            if line.startswith("&title="):
                self.metadata["title"] = self._get_value_from_line(line, "&title=")
            elif line.startswith("&artist="):
                self.metadata["artist"] = self._get_value_from_line(line, "&artist=")
            elif line.startswith("&des="):
                self.metadata["designer"] = self._get_value_from_line(line, "&des=")
            elif line.startswith("&first="):
                try:
                    self.metadata["first_offset_sec"] = float(self._get_value_from_line(line, "&first="))
                except ValueError:
                    print(f"Warning: Could not parse &first value: {line}")
            elif line.startswith("&lv_"):  # e.g. &lv_4=12
                try:
                    # Extract index and value carefully
                    match = re.match(r"&lv_(\d+)=(.*)", line)
                    if match:
                        idx = int(match.group(1)) - 1
                        val = match.group(2).strip()
                        if 0 <= idx < 7:
                            self.metadata["levels"][idx] = val
                    else:
                        print(f"Warning: Could not parse &lv_ line: {line}")
                except Exception as e:
                    print(f"Warning: Error parsing &lv_ line '{line}': {e}")
            elif line.startswith("&inote_"):  # e.g. &inote_4=...
                try:
                    match = re.match(r"&inote_(\d+)=(.*)", line_orig.strip())  # Use line_orig for first line of fumen
                    if match:
                        idx = int(match.group(1)) - 1
                        first_fumen_line = match.group(2)  # This is the first line of the fumen data
                        if 0 <= idx < 7:
                            current_fumen_index = idx
                            temp_fumen_lines = [first_fumen_line]  # Start with this line
                            reading_fumen_block = True
                    else:
                        print(f"Warning: Could not parse &inote_ line: {line}")
                except Exception as e:
                    print(f"Warning: Error parsing &inote_ line '{line}': {e}")
            elif line.startswith("&"):  # Other known or unknown &commands
                other_commands_buffer.append(line_orig)
            elif line:  # Non-empty lines that are not metadata and not part of an active fumen block
                other_commands_buffer.append(line_orig)

        # If the file ends while reading a fumen block
        if reading_fumen_block and current_fumen_index != -1:
            self.fumens_raw[current_fumen_index] = "\n".join(temp_fumen_lines).strip()

        self.metadata["other_commands_raw"] = "\n".join(other_commands_buffer).strip()

        # After loading, immediately process the fumens
        self._process_all_fumens()

    def _process_all_fumens(self):
        """Processes all loaded raw fumen strings into structured data."""
        self.processed_fumens_data = []
        for i, fumen_raw_text in enumerate(self.fumens_raw):
            level_info = self.metadata["levels"][i] if i < len(self.metadata["levels"]) else ""
            if fumen_raw_text:
                note_evs, timing_evs_commas = self._parse_single_fumen(fumen_raw_text)
                self.processed_fumens_data.append({
                    "difficulty_index": i,
                    "level_info": level_info,
                    "note_events": [ne.to_dict() for ne in note_evs],
                    "timing_events_at_commas": [te.to_dict() for te in timing_evs_commas]
                })
            else:  # Fumen might be empty for this difficulty
                self.processed_fumens_data.append({
                    "difficulty_index": i,
                    "level_info": level_info,
                    "note_events": [],
                    "timing_events_at_commas": []
                })

    def _parse_single_fumen(self, fumen_text):
        """
        Parses a single fumen string (the content of one &inote_ block).
        Returns a list of note_events (SimaiTimingPoint with notes) and
        timing_events_at_commas (SimaiTimingPoint for each comma).
        """
        note_events_list = []
        timing_events_at_commas_list = []

        if not fumen_text:
            return note_events_list, timing_events_at_commas_list

        current_bpm = 0.0
        current_beats_per_bar = 4
        current_time_sec = self.metadata.get("first_offset_sec", 0.0)
        current_hspeed = 1.0

        char_idx = 0
        line_num = 0  # 0-indexed
        char_in_line = 0  # 0-indexed position within the current logical line being parsed

        note_buffer = ""  # Accumulates characters for a note group between commas

        while char_idx < len(fumen_text):
            char = fumen_text[char_idx]

            # 1. Handle comments: || ... \n (skip to end of physical line)
            if char == '|' and char_idx + 1 < len(fumen_text) and fumen_text[char_idx + 1] == '|':
                # Finalize any pending notes before the comment
                self._finalize_note_segment(note_buffer, current_time_sec, char_in_line, line_num, current_bpm,
                                            current_hspeed, note_events_list)
                note_buffer = ""

                start_of_comment_line = line_num
                while char_idx < len(fumen_text) and fumen_text[char_idx] != '\n':
                    char_idx += 1
                # After loop, char_idx is at \n or end of fumen_text
                if char_idx < len(fumen_text) and fumen_text[char_idx] == '\n':
                    # If comment was on its own line, line_num should advance.
                    # If comment was inline, line_num already reflects current logical line.
                    # This simple comment handling assumes comments effectively end the current "logical" line for parsing.
                    line_num += 1  # Advance to next line
                    char_in_line = 0
                    char_idx += 1  # Move past \n
                else:  # End of fumen
                    char_in_line = 0  # Reset for potential next (non-existent) line
                continue

            # 2. Handle BPM changes: (value)
            if char == '(':
                self._finalize_note_segment(note_buffer, current_time_sec, char_in_line, line_num, current_bpm,
                                            current_hspeed, note_events_list)
                note_buffer = ""
                bpm_str = ""
                char_idx += 1  # Skip '('
                # char_in_line will be updated by the loop
                temp_char_in_line = char_in_line + 1
                while char_idx < len(fumen_text) and fumen_text[char_idx] != ')':
                    bpm_str += fumen_text[char_idx]
                    char_idx += 1;
                    temp_char_in_line += 1
                try:
                    new_bpm = float(bpm_str)
                    if new_bpm > 0:
                        current_bpm = new_bpm
                    else:
                        print(f"Warning: Invalid BPM value (<=0) '{bpm_str}' at line {line_num + 1}")
                except ValueError:
                    print(f"Warning: Invalid BPM string '{bpm_str}' at line {line_num + 1}")
                if char_idx < len(fumen_text) and fumen_text[char_idx] == ')': char_idx += 1; temp_char_in_line += 1
                char_in_line = temp_char_in_line - 1  # char_in_line points to the last char processed in this block
                continue

            # 3. Handle beat signature changes: {value}
            if char == '{':
                self._finalize_note_segment(note_buffer, current_time_sec, char_in_line, line_num, current_bpm,
                                            current_hspeed, note_events_list)
                note_buffer = ""
                beats_str = ""
                char_idx += 1  # Skip '{'
                temp_char_in_line = char_in_line + 1
                while char_idx < len(fumen_text) and fumen_text[char_idx] != '}':
                    beats_str += fumen_text[char_idx]
                    char_idx += 1;
                    temp_char_in_line += 1
                try:
                    new_beats = int(beats_str)
                    if new_beats > 0:
                        current_beats_per_bar = new_beats
                    else:
                        print(f"Warning: Invalid beats value (<=0) '{beats_str}' at line {line_num + 1}")
                except ValueError:
                    print(f"Warning: Invalid beats string '{beats_str}' at line {line_num + 1}")
                if char_idx < len(fumen_text) and fumen_text[char_idx] == '}': char_idx += 1; temp_char_in_line += 1
                char_in_line = temp_char_in_line - 1
                continue

            # 4. Handle Hi-Speed changes: <Hvalue> or <HS*value>
            if char == '<':
                # Check if it's a Hi-Speed change
                if char_idx + 1 < len(fumen_text) and fumen_text[char_idx + 1] == 'H':
                    self._finalize_note_segment(note_buffer, current_time_sec, char_in_line, line_num, current_bpm,
                                                current_hspeed, note_events_list)
                    note_buffer = ""
                    hspeed_str = ""
                    char_idx += 2  # Skip '<' and 'H'
                    temp_char_in_line = char_in_line + 2

                    # Check for optional "S*" part
                    if char_idx < len(fumen_text) and fumen_text[char_idx] == 'S':
                        char_idx += 1
                        temp_char_in_line += 1
                        if char_idx < len(fumen_text) and fumen_text[char_idx] == '*':
                            char_idx += 1
                            temp_char_in_line += 1

                    # Read the Hi-Speed value until '>'
                    while char_idx < len(fumen_text) and fumen_text[char_idx] != '>':
                        hspeed_str += fumen_text[char_idx]
                        char_idx += 1
                        temp_char_in_line += 1

                    # Parse and set Hi-Speed value
                    try:
                        current_hspeed = float(hspeed_str)
                    except ValueError:
                        print(f"Warning: Invalid HSpeed value '{hspeed_str}' at line {line_num + 1}")

                    # Ensure closing '>' is present
                    if char_idx < len(fumen_text) and fumen_text[char_idx] == '>':
                        char_idx += 1
                        temp_char_in_line += 1

                    # Update character position
                    char_in_line = temp_char_in_line - 1
                    continue
                else:
                    # If not Hi-Speed, treat '<' as a normal character
                    note_buffer += char
                    char_idx += 1
                    char_in_line += 1
                    continue

            # 5. Handle newline (physical newline in the fumen string)
            if char == '\n':
                # Newlines can be part of note_buffer if multi-line notes are allowed before a comma.
                # Simai usually expects notes on one logical line then a comma.
                # If note_buffer can span newlines, add char to buffer.
                # The C# code implies newlines mainly affect Ycount for raw text position.
                note_buffer += char  # Add newline to buffer, it might be stripped later by SimaiTimingPoint or during _finalize
                line_num += 1
                char_in_line = 0
                char_idx += 1
                continue

            # 6. Handle comma (event separator)
            if char == ',':
                self._finalize_note_segment(note_buffer, current_time_sec, char_in_line, line_num, current_bpm,
                                            current_hspeed, note_events_list)
                note_buffer = ""  # Reset buffer for next segment

                # Add a generic timing event for the comma itself
                tp_comma = SimaiTimingPoint(current_time_sec, char_in_line, line_num, "", current_bpm, current_hspeed)
                timing_events_at_commas_list.append(tp_comma)

                # Advance time
                if current_bpm > 0 and current_beats_per_bar > 0:
                    time_increment = (60.0 / current_bpm) * (4.0 / current_beats_per_bar)
                    current_time_sec += time_increment
                else:
                    if current_bpm <= 0: print(
                        f"Warning: BPM is {current_bpm} at line {line_num + 1}, char {char_in_line + 1}. Time will not advance correctly.")

                char_idx += 1
                char_in_line += 1
                continue

            # 7. Accumulate other characters into note_buffer
            note_buffer += char
            char_idx += 1
            char_in_line += 1

        # After loop, process any remaining content in note_buffer (e.g., if fumen doesn't end with comma)
        self._finalize_note_segment(note_buffer, current_time_sec, char_in_line, line_num, current_bpm, current_hspeed,
                                    note_events_list)

        note_events_list.sort(key=lambda x: x.time)  # Sort by time, important if '`' pseudo notes are out of order
        timing_events_at_commas_list.sort(key=lambda x: x.time)

        return note_events_list, timing_events_at_commas_list

    def _finalize_note_segment(self, note_buffer_str, time_sec, x_pos, y_pos, bpm, hspeed, note_events_list_ref):
        """Helper to process a collected note segment string."""
        # Strip whitespace including newlines that might have been collected in note_buffer
        # Note: Simai notes are typically single line, but buffer might collect \n before a comma.
        # The .strip() here will remove those. If Simai allows meaningful newlines *within* a note group,
        # this needs adjustment. C# SimaiTimingPoint also does .Replace("\n","").Replace(" ","") on notesContent.
        processed_note_buffer_str = note_buffer_str.strip()
        if not processed_note_buffer_str:
            return

        # Handle pseudo-simultaneous notes with '`' (backtick)
        if '`' in processed_note_buffer_str:
            pseudo_parts = processed_note_buffer_str.split('`')
            # C# uses 1.875 / bpm for 128th note interval. (60 / bpm / 32)
            time_interval_pseudo = (60.0 / bpm / 32.0) if bpm > 0 else 0.001

            current_pseudo_time = time_sec
            for i, part in enumerate(pseudo_parts):
                part = part.strip()
                if part:  # Ensure part is not empty after strip
                    tp = SimaiTimingPoint(current_pseudo_time, x_pos, y_pos, part, bpm, hspeed)
                    tp.parse_notes_from_content()
                    if tp.notes:  # Only add if it resulted in actual notes
                        note_events_list_ref.append(tp)
                # Increment time for the next pseudo note, but not after the last one
                if i < len(pseudo_parts) - 1:
                    current_pseudo_time += time_interval_pseudo
        else:  # Regular note segment
            tp = SimaiTimingPoint(time_sec, x_pos, y_pos, processed_note_buffer_str, bpm, hspeed)
            tp.parse_notes_from_content()
            if tp.notes:  # Only add if it resulted in actual notes
                note_events_list_ref.append(tp)

    def to_json(self, indent=2):
        """Converts the entire parsed SimaiChart to a JSON string."""
        # Ensure fumens are processed before creating the dict
        if not self.processed_fumens_data and any(self.fumens_raw):
            self._process_all_fumens()

        chart_dict = {
            "metadata": self.metadata,
            "fumens_data": self.processed_fumens_data
        }
        return json.dumps(chart_dict, indent=indent)


# Example Usage:
if __name__ == '__main__':
    simai_content = """
&title=Test Song Title
&artist=Test Artist Name
&des=Chart Designer
&first=1.25
&lv_4=13+
&inote_4=
|| This is a comment line
(120) || BPM set to 120
1,2h[4:1], E1/3, || Some notes
{8} || 8 beats per measure from now on
<HS*2.5> || Hi-Speed 2.5x
A1b-2[8:1]$/Cfx, 4`5`6, 7,
8
"""

    chart = SimaiChart()
    chart.load_from_text(simai_content)

    # Output to JSON
    json_output = chart.to_json(indent=2)
    print(json_output)

    # You can also access parts of the chart:
    # print("\nMetadata:", chart.metadata)
    # if chart.processed_fumens_data and len(chart.processed_fumens_data) > 3:
    #     expert_fumen_data = chart.processed_fumens_data[3] # Index 3 for lv_4
    #     if expert_fumen_data["note_events"]:
    #         print("\nFirst note event of Expert fumen:", expert_fumen_data["note_events"][0])
