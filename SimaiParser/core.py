import json
import re
from enum import Enum


class SimaiNoteType(Enum):
    """Enumeration for different types of Simai notes."""
    TAP = 1
    SLIDE = 2
    HOLD = 3
    TOUCH = 4
    TOUCH_HOLD = 5


class SimaiNote:
    """
    Represents a single musical note or action in a Simai chart.
    Contains properties like type, position, duration, and various gameplay modifiers.
    """

    def __init__(self):
        self.note_type = None
        self.start_position = None  # 1-8 for regular, or derived for touch (e.g., A1 -> 1)
        self.touch_area = None  # A-E for touch areas, C for center touch
        self.hold_time = 0.0  # Duration in seconds for hold notes
        self.slide_time = 0.0  # Duration in seconds for slide notes
        self.slide_start_time_offset = 0.0  # Time offset from the timing point's time for star appearance
        self.is_break = False  # Break note flag
        self.is_ex = False  # EX note flag (often a stronger visual/sound)
        self.is_hanabi = False  # 'f' flag, typically for "fireworks" visual effect
        self.is_slide_no_head = False  # '!' or '?' flag, slide starts without a visible tap head
        self.is_force_star = False  # '$' flag, forces a star visual for slides
        self.is_fake_rotate = False  # '$$' flag, specific visual effect
        self.is_slide_break = False  # 'b' flag on a slide segment, indicating a break during the slide
        self.raw_note_text = ""  # Original text for this note, for debugging or reference

    def to_dict(self):
        """Converts the SimaiNote object to a dictionary for JSON serialization."""
        return {
            "note_type": self.note_type.name if self.note_type else None,
            "start_position": self.start_position,
            "touch_area": self.touch_area,
            "hold_time": self.hold_time,
            "slide_time": self.slide_time,
            "slide_start_time_offset": self.slide_start_time_offset,
            "is_break": self.is_break,
            "is_ex": self.is_ex,
            "is_hanabi": self.is_hanabi,
            "is_slide_no_head": self.is_slide_no_head,
            "is_force_star": self.is_force_star,
            "is_fake_rotate": self.is_fake_rotate,
            "is_slide_break": self.is_slide_break,
            "raw_note_text": self.raw_note_text
        }


class SimaiTimingPoint:
    """
    Represents a specific point in time within the chart, typically marked by a comma in Simai.
    It contains notes that occur at this time, and the active BPM/HSpeed.
    """

    def __init__(self, time, raw_text_pos_x=0, raw_text_pos_y=0, notes_content="", bpm=0.0, hspeed=1.0):
        self.time = time  # Absolute time in seconds from the start of the song
        self.raw_text_pos_x = raw_text_pos_x  # Original X character position in fumen text
        self.raw_text_pos_y = raw_text_pos_y  # Original Y line position in fumen text
        self.notes_content_raw = notes_content  # The raw string of notes at this timing point (e.g., "1/2h[4:1]")
        self.current_bpm = bpm  # BPM active at this timing point
        self.hspeed = hspeed  # Hi-Speed multiplier active at this timing point
        self.notes = []  # List of SimaiNote objects parsed from notes_content_raw

    def parse_notes_from_content(self):
        """
        Parses the raw note string (self.notes_content_raw) into a list of SimaiNote objects.
        This method replicates the detailed note parsing logic from the C# version.
        """
        if not self.notes_content_raw:
            return

        content = self.notes_content_raw.replace("\n", "").replace(" ", "")
        if not content:
            return

        # Handle "连写数字" (e.g., "12") - two separate taps if no other modifiers suggest otherwise
        if len(content) == 2 and content.isdigit() and \
                not self._is_slide_char_present(content) and \
                not self._is_hold_char_present(content) and \
                not self._is_touch_note_char(content[0]):  # Ensure it's not like "A1"
            self.notes.append(self._parse_single_note_token(content[0]))
            self.notes.append(self._parse_single_note_token(content[1]))
            return

        # Handle '/' for simultaneous notes (e.g., "1/2/E1")
        if '/' in content:
            note_tokens = content.split('/')
            for token in note_tokens:
                token = token.strip()
                if not token: continue
                if '*' in token:  # Same head slide group like "1*V[4:1]"
                    self.notes.extend(self._parse_same_head_slide(token))
                else:
                    self.notes.append(self._parse_single_note_token(token))
            return

        # Handle '*' for same head slide (if not already handled by '/')
        if '*' in content:
            self.notes.extend(self._parse_same_head_slide(content))
            return

        # Single note token if none of the above
        self.notes.append(self._parse_single_note_token(content))

    def _is_slide_char_present(self, note_text):
        """Checks if any standard slide characters are present in the note text."""
        slide_marks = "-^v<>Vpqszw"  # Standard Simai slide path characters
        return any(mark in note_text for mark in slide_marks)

    def _is_hold_char_present(self, note_text):
        """Checks if the hold character 'h' is present."""
        return 'h' in note_text

    def _parse_same_head_slide(self, content_token):
        """
        Parses same-head slide groups (e.g., "1*V[4:1]*<[4:1]").
        The first part defines the head, subsequent parts are headless slides from that same head.
        """
        parsed_notes = []
        parts = content_token.split('*')
        if not parts or not parts[0].strip(): return []

        first_note_text = parts[0].strip()
        first_note = self._parse_single_note_token(first_note_text)
        parsed_notes.append(first_note)

        # Determine the head indicator (e.g., "1", "A3") from the first note
        head_indicator = ""
        if first_note.touch_area:
            head_indicator = first_note.touch_area
            if first_note.touch_area != 'C' and first_note.start_position is not None:
                head_indicator += str(first_note.start_position)
        elif first_note.start_position is not None:
            head_indicator = str(first_note.start_position)

        for i in range(1, len(parts)):
            slide_path_part = parts[i].strip()
            if not slide_path_part: continue

            # Reconstruct the note text for the subsequent slide part using the determined head
            reconstructed_note_text = head_indicator + slide_path_part

            slide_segment_note = self._parse_single_note_token(reconstructed_note_text)
            slide_segment_note.is_slide_no_head = True  # Subsequent parts of '*' are headless
            parsed_notes.append(slide_segment_note)
        return parsed_notes

    def _parse_single_note_token(self, note_text_orig):
        """
        Parses a single note token string (e.g., "1b", "A2h[4:1]", "3-4[8:1]bx") into a SimaiNote object.
        This is a complex method due to the many possible modifiers and syntaxes.
        """
        note = SimaiNote()
        note.raw_note_text = note_text_orig

        # Work with a mutable copy for parsing, but refer to note_text_orig for context sensitive parsing
        note_text_parser = note_text_orig

        # 1. Identify base note type and position (TAP, TOUCH)
        if self._is_touch_note_char(note_text_parser[0]):
            note.note_type = SimaiNoteType.TOUCH  # Default, may become TOUCH_HOLD
            note.touch_area = note_text_parser[0]
            temp_note_text = note_text_parser[1:]
            if note.touch_area == 'C':  # Center touch
                note.start_position = 8  # Convention from C# (or could be None/special value)
            elif temp_note_text and temp_note_text[0].isdigit():
                note.start_position = int(temp_note_text[0])
                temp_note_text = temp_note_text[1:]
            note_text_parser = temp_note_text  # Remaining string after touch area and optional digit
        elif note_text_parser[0].isdigit():
            note.note_type = SimaiNoteType.TAP  # Default, may change to HOLD or SLIDE
            note.start_position = int(note_text_parser[0])
            note_text_parser = note_text_parser[1:]  # Remaining string after position digit
        else:
            # This case implies a malformed note or a note starting with a modifier (e.g. slide path)
            # which usually means it's part of a same-head slide or an error.
            # For now, we assume position is parsed first.
            pass

        # 2. Parse flags and refine note type (Hold, Slide, Modifiers)
        # Order of parsing modifiers can be important.

        # Hanabi 'f'
        if 'f' in note_text_orig: note.is_hanabi = True

        # Hold 'h'
        if 'h' in note_text_orig:  # Check original string for 'h'
            if note.note_type == SimaiNoteType.TOUCH:
                note.note_type = SimaiNoteType.TOUCH_HOLD
            elif note.note_type == SimaiNoteType.TAP or note.note_type is None:  # Or if type is still undetermined
                note.note_type = SimaiNoteType.HOLD

            # Calculate hold time using the original full token for context
            note.hold_time = self._get_time_from_beats_duration(note_text_orig)
            if note.hold_time == 0 and '[' not in note_text_orig and note_text_orig.strip().endswith('h'):
                pass  # Duration is 0, often means "until next note on same lane" or editor-defined.

        # Slide (various characters) - check after hold because a hold can also be a slide start
        slide_chars = "-^v<>Vpqszw"
        is_slide_path_present = any(sc in note_text_orig for sc in slide_chars)

        if is_slide_path_present:
            note.note_type = SimaiNoteType.SLIDE  # Override TAP/HOLD if slide path exists
            note.slide_time = self._get_time_from_beats_duration(note_text_orig)
            note.slide_start_time_offset = self._get_star_wait_time(note_text_orig)

            if '!' in note_text_orig: note.is_slide_no_head = True
            if '?' in note_text_orig: note.is_slide_no_head = True

        # Break 'b'
        if 'b' in note_text_orig:
            if note.note_type == SimaiNoteType.SLIDE:
                # Complex logic for 'b' in slides from C#
                # Iterate over all 'b' occurrences
                for b_match in re.finditer('b', note_text_orig):
                    b_idx = b_match.start()
                    is_segment_break_for_this_b = False
                    if b_idx < len(note_text_orig) - 1:
                        if note_text_orig[b_idx + 1] == '[':  # 'b[' indicates break on the slide path itself
                            is_segment_break_for_this_b = True
                        else:  # 'b' followed by something else (e.g. slide char) is break on star
                            note.is_break = True  # Break on the tap/star part of the slide
                    else:  # 'b' is the last character of the note token
                        is_segment_break_for_this_b = True

                    if is_segment_break_for_this_b:
                        note.is_slide_break = True
            else:  # TAP, HOLD, TOUCH, TOUCH_HOLD
                note.is_break = True

        # EX 'x'
        if 'x' in note_text_orig: note.is_ex = True

        # Star '$', '$$'
        if '$' in note_text_orig:
            note.is_force_star = True
            if note_text_orig.count('$') == 2:
                note.is_fake_rotate = True

        return note

    def _is_touch_note_char(self, char):
        """Checks if a character is a Simai touch area designator."""
        return char in "ABCDE"  # C is handled as a special case for position

    def _get_time_from_beats_duration(self, note_text_token):
        """
        Parses duration from Simai's beat notation like "[4:1]", "[bpm#N:D]", "[#abs_time]", etc.
        This is used for hold times and slide times.
        Returns duration in seconds.
        """
        total_duration = 0.0

        for match in re.finditer(r'\[([^]]+)]', note_text_token):  # Find all [...] sections
            inner_content = match.group(1)

            # Default time for one beat at current BPM for this segment's calculation
            time_one_beat_for_segment = (60.0 / self.current_bpm) if self.current_bpm > 0 else 0

            # Case 1: Absolute time specified like "[#1.5]" (seconds)
            # C# format: "[#abs_time_val]" (if no other '#' and no ':')
            if inner_content.startswith('#') and inner_content.count('#') == 1 and ':' not in inner_content:
                try:
                    total_duration += float(inner_content[1:])
                    continue
                except ValueError:
                    print(f"Warning: Malformed absolute time duration '{inner_content}' in '{note_text_token}'")

            # Case 2: Formats with multiple '#' or specific BPM
            # C# format: "[wait_time##duration_val]" -> parts[2] is duration
            if inner_content.count('#') == 2:
                parts = inner_content.split('#')
                if len(parts) == 3 and parts[2]:  # Ensure parts[2] is not empty
                    try:
                        total_duration += float(parts[2])
                        continue
                    except ValueError:
                        print(
                            f"Warning: Malformed duration in '[##val]' format: '{inner_content}' in '{note_text_token}'")

            # C# format: "[custom_bpm#...]"
            if inner_content.count('#') == 1:
                parts = inner_content.split('#')
                custom_bpm_str, timing_str = parts[0], parts[1]

                if custom_bpm_str:  # Custom BPM for this segment's calculation
                    try:
                        custom_bpm = float(custom_bpm_str)
                        if custom_bpm > 0:
                            time_one_beat_for_segment = 60.0 / custom_bpm
                    except ValueError:
                        print(f"Warning: Malformed custom BPM '{custom_bpm_str}' in '{note_text_token}'")

                # Now parse timing_str which can be "N:D" or "abs_time_val_for_this_bpm"
                if ':' in timing_str:  # Format "N:D"
                    try:
                        num_str, den_str = timing_str.split(':')
                        beat_division = int(num_str)  # e.g., 4 for 1/4 notes
                        num_beats = int(den_str)  # number of such beats
                        if beat_division > 0:
                            total_duration += time_one_beat_for_segment * (4.0 / beat_division) * num_beats
                        continue
                    except ValueError:
                        print(f"Warning: Malformed 'N:D' timing '{timing_str}' in '{note_text_token}'")
                else:  # C# implies this is "absolute time value" for this (potentially custom) BPM segment
                    # This means times[1] is already in seconds if it doesn't contain ':'.
                    try:
                        total_duration += float(timing_str)
                        continue
                    except ValueError:
                        print(
                            f"Warning: Malformed absolute time value '{timing_str}' in BPM override segment '{note_text_token}'")

            # Default case: "[N:D]" (no BPM override in this segment)
            if ':' in inner_content:
                try:
                    num_str, den_str = inner_content.split(':')
                    beat_division = int(num_str)
                    num_beats = int(den_str)
                    if beat_division > 0:
                        total_duration += time_one_beat_for_segment * (4.0 / beat_division) * num_beats
                except ValueError:
                    print(f"Warning: Malformed default 'N:D' duration '{inner_content}' in '{note_text_token}'")
            elif not inner_content.startswith('#') and not inner_content.count(
                    '#') > 0:  # e.g. "[abs_time_val]" without #
                try:
                    total_duration += float(inner_content)
                except ValueError:
                    print(f"Warning: Malformed simple absolute time duration '{inner_content}' in '{note_text_token}'")

        return total_duration

    def _get_star_wait_time(self, note_text_token):
        """
        Parses wait time for a slide's star visual, from notations like "[wait_bpm#N:D]" or "[#wait_abs_time#...]".
        Default Simai star wait time is one beat at the current chart BPM.
        Returns wait time in seconds.
        """
        # Default wait time: one beat at the timing point's current BPM
        default_wait_time = (60.0 / self.current_bpm) if self.current_bpm > 0 else 0.001

        match = re.search(r'\[([^\]]+)\]', note_text_token)  # Look for the first [...]
        if not match:
            return default_wait_time

        inner_content = match.group(1)

        # C# format: "[abs_wait_time##...]" -> parts[0] is wait time
        if inner_content.count('#') == 2:
            parts = inner_content.split('#')
            if parts[0]:
                try:
                    return float(parts[0])
                except ValueError:
                    print(f"Warning: Malformed absolute star wait time in '[val##...]' format: '{inner_content}'")

        # C# format: "[wait_bpm_override#...]" -> parts[0] is BPM for 1-beat calculation
        # If no ':', the second part is ignored for wait time calc, only BPM matters for the 1-beat default.
        effective_bpm_for_wait = self.current_bpm
        if inner_content.count('#') == 1:
            parts = inner_content.split('#')
            if parts[0]:  # Custom BPM for wait time calculation
                try:
                    custom_wait_bpm = float(parts[0])
                    if custom_wait_bpm > 0:
                        effective_bpm_for_wait = custom_wait_bpm
                except ValueError:
                    print(f"Warning: Malformed BPM for star wait time: '{parts[0]}'")

        return (60.0 / effective_bpm_for_wait) if effective_bpm_for_wait > 0 else 0.001

    def to_dict(self):
        """Converts the SimaiTimingPoint object to a dictionary."""
        return {
            "time": self.time,
            "raw_text_pos_x": self.raw_text_pos_x,
            "raw_text_pos_y": self.raw_text_pos_y,
            "notes_content_raw": self.notes_content_raw,
            "current_bpm_at_event": self.current_bpm,
            "hspeed_at_event": self.hspeed,
            "notes": [note.to_dict() for note in self.notes]
        }


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
