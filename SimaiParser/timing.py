import re
from .note import SimaiNote, SimaiNoteType

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