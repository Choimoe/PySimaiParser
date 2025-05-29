import json
import re
from collections import Counter
import fractions
import math

class JsonSimaiConverter:
    """
    Converts chart data from a JSON format to a simai-like text format.

    The class handles metadata, timing events (fumens), note events, BPM changes,
    and high-speed (HSpeed) modifications to generate a simai chart.
    It attempts to standardize note segment durations (X values) and adjust BPM
    to maintain timing accuracy when necessary.
    """
    def __init__(self, chart_data_dict):
        """
        Initializes the JsonSimaiConverter with chart data.

        Args:
            chart_data_dict (dict): A dictionary containing the chart data,
                                    expected to have 'metadata' and 'fumens_data'.
        """
        self.chart_data = chart_data_dict
        self.metadata = self.chart_data.get("metadata", {})
        self.fumens_data = self.chart_data.get("fumens_data", [])
        # A comprehensive list of standard X values, including those divisible by 3, 5, 7.
        # These represent the number of notes of a certain type that fit into a whole note.
        # For example, X=4.0 means quarter notes.
        self.standard_x_values = sorted([
            1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0,  # Common simple divisions
            10.0, 12.0, 14.0, 15.0, 16.0, 20.0, 24.0, 28.0, 30.0, 32.0, # Further divisions
            40.0, 48.0, 56.0, 60.0, 64.0, # Higher density divisions
            96.0, 128.0, 192.0, 256.0 # Very high density, often for specific patterns
        ])

    @classmethod
    def from_json_file(cls, filepath, encoding='utf-8'):
        """
        Creates a JsonSimaiConverter instance from a JSON file.

        Args:
            filepath (str): The path to the JSON file.
            encoding (str, optional): The encoding of the file. Defaults to 'utf-8'.

        Returns:
            JsonSimaiConverter: An instance of the converter.
        """
        with open(filepath, 'r', encoding=encoding) as f:
            data = json.load(f)
        return cls(data)

    @classmethod
    def from_json_text(cls, json_text):
        """
        Creates a JsonSimaiConverter instance from a JSON string.

        Args:
            json_text (str): The JSON string containing chart data.

        Returns:
            JsonSimaiConverter: An instance of the converter.
        """
        return cls(json.loads(json_text))

    def _format_number(self, num, precision=4):
        """
        Formats a number for simai output.
        If it's an integer, returns the integer string.
        Otherwise, formats to a specified precision, removing trailing zeros.

        Args:
            num (int | float | None): The number to format.
            precision (int, optional): The maximum number of decimal places for floats.
                                       Defaults to 4.

        Returns:
            str: The formatted number as a string, or an empty string if num is None.
        """
        if num is None: return ""
        if isinstance(num, (int, float)) and float(num).is_integer():
            return str(int(num))
        # Round to a reasonable number of decimal places to avoid overly long numbers.
        # For example, up to 4 places, then remove trailing zeros.
        formatted_num = f"{num:.{precision}f}".rstrip('0').rstrip('.')
        return formatted_num if formatted_num else "0" # Return "0" if formatting results in empty string (e.g. "0.00" -> "")

    def _determine_chart_global_bpm(self):
        """
        Determines the primary BPM for the chart.
        It checks the initial BPM of each fumen. If they are consistent, that BPM is used.
        If not, it uses the most common BPM if it's significantly prevalent.
        Falls back to metadata 'wholebpm' or the first BPM found if no clear primary BPM.

        Returns:
            float | None: The determined global BPM, or None if not found.
        """
        initial_bpms = []
        for fumen_item in self.fumens_data:
            if not fumen_item: continue # Skip if fumen_item is None or empty
            # Prioritize note_events for BPM, then timing_events_at_commas
            events_to_check_bpm = fumen_item.get('note_events', [])
            if not events_to_check_bpm:
                events_to_check_bpm = fumen_item.get('timing_events_at_commas', [])

            if events_to_check_bpm:
                # Get BPM from the first event in the fumen
                first_event_bpm = events_to_check_bpm[0].get('current_bpm_at_event')
                if first_event_bpm is not None:
                    initial_bpms.append(first_event_bpm)

        if not initial_bpms:
            return self.metadata.get('wholebpm')  # Fallback to metadata if no BPMs found in events

        if len(set(initial_bpms)) == 1:
            return initial_bpms[0]  # All fumens start with the same BPM

        # If multiple starting BPMs, find the most common one
        bpm_counts = Counter(initial_bpms)
        most_common_bpm, count = bpm_counts.most_common(1)[0]

        # Use most common if it's a clear majority or the only one (already handled)
        if count > len(initial_bpms) / 2 or len(bpm_counts) == 1:
            return most_common_bpm

        # Fallback strategy if no clear majority
        return self.metadata.get('wholebpm', initial_bpms[0])

    def _calculate_x_for_segment(self, segment_duration, bpm_at_segment_start):
        """
        Calculates the 'X' value for a note segment based on its duration and BPM.
        X represents how many notes of this type fit into a whole note.
        Formula: X = (240 / BPM) / segment_duration

        Args:
            segment_duration (float): The duration of the segment in seconds.
            bpm_at_segment_start (float): The BPM at the start of this segment.

        Returns:
            float: The calculated X value. Defaults to 4.0 (quarter note) if
                   duration or BPM is invalid.
        """
        if not (segment_duration > 1e-6 and bpm_at_segment_start and bpm_at_segment_start > 0):
            # Default to {4} (quarter note equivalent) if duration or BPM is invalid or too small
            return 4.0
        try:
            # X = (Number of this note type that fits into a Whole Note)
            # Whole note duration = (60 seconds / BPM) * 4 beats
            # X = Whole note duration / segment_duration
            # X = (240 / BPM) / segment_duration = 240 / (BPM * segment_duration)
            x_candidate = 240.0 / (segment_duration * bpm_at_segment_start)
            return x_candidate  # Return raw X value; transformation to standard X happens later
        except ZeroDivisionError:
            # Should be caught by the initial check, but as a safeguard
            return 4.0

    def _find_closest_standard_x(self, x_val):
        """
        Finds the closest standard X value to a given calculated X value.
        It prioritizes standard values if `x_val` is close.
        It also considers if `x_val` itself is a "good" simple fraction.

        Args:
            x_val (float | None): The calculated X value.

        Returns:
            float | None: The closest or most appropriate standard/simple X value,
                          or None if input is None.
        """
        if x_val is None: return None

        # Find the arithmetically closest standard value
        closest_std = min(self.standard_x_values, key=lambda std: abs(std - x_val))

        # If x_val is very close to a standard value, use that standard value
        # A tolerance of 2% is used here.
        if math.isclose(x_val, closest_std, rel_tol=0.02, abs_tol=0.02):
            return closest_std

        # If x_val is not close to a standard value, check if x_val itself is a "good" number
        # (e.g., an integer or a simple fraction).
        # Try to limit the denominator of the fraction to keep it simple (e.g., up to 64).
        try:
            frac = fractions.Fraction(x_val).limit_denominator(64)
            limited_x = float(frac)
            # If limiting the denominator didn't significantly change the value
            if math.isclose(x_val, limited_x, rel_tol=1e-4):
                # Check if this limited_x is one of the standard values
                if any(math.isclose(limited_x, std_val) for std_val in self.standard_x_values):
                    return limited_x
                # If the limited_x is not standard, but is a "simple" integer (e.g., 10.0, 15.0),
                # it can be kept if it's within a reasonable range (e.g., <= 256).
                if limited_x.is_integer() and limited_x > 0:
                    if limited_x <= 256:  # Upper limit for X values
                        return limited_x
        except Exception:
            # If there's an error working with fractions (e.g., x_val is too complex),
            # fall back to using the closest standard value.
            pass

        # If no "good" simple value was found, return the closest standard value.
        return closest_std

    def to_simai_text(self):
        """
        Converts the loaded chart data into a simai text format.

        Returns:
            str: A string representing the chart in simai format.
        """
        simai_output_lines = []

        # --- Metadata Section ---
        # Add metadata like title, artist, designer if they exist.
        if self.metadata.get("title"): simai_output_lines.append(f"&title={self.metadata['title']}")
        if self.metadata.get("artist"): simai_output_lines.append(f"&artist={self.metadata['artist']}")
        if self.metadata.get("designer"): simai_output_lines.append(f"&des={self.metadata['designer']}")

        # Determine and add the global BPM for the chart.
        # Use 'wholebpm' from metadata if available, otherwise determine it from fumen events.
        chart_global_bpm_for_metadata = self.metadata.get('wholebpm', self._determine_chart_global_bpm())
        if chart_global_bpm_for_metadata is not None:
            simai_output_lines.append(f"&wholebpm={self._format_number(chart_global_bpm_for_metadata)}")
        else:
            # If BPM is still undefined, set a default (e.g., 120) for consistency.
            chart_global_bpm_for_metadata = 120.0
            simai_output_lines.append(f"&wholebpm={self._format_number(chart_global_bpm_for_metadata)}")

        # Add first offset if specified in metadata.
        if "first_offset_sec" in self.metadata:
            simai_output_lines.append(f"&first={self._format_number(self.metadata['first_offset_sec'])}")

        # Add difficulty levels if specified.
        levels = self.metadata.get("levels", [])
        for i, lv_value in enumerate(levels):
            if lv_value: simai_output_lines.append(f"&lv_{i + 1}={lv_value}")
        simai_output_lines.append("") # Add a blank line after metadata

        # --- Fumens Section ---
        # Process each fumen (timing/note section).
        for fumen_idx, fumen_item in enumerate(self.fumens_data):
            if not fumen_item: continue # Skip if fumen data is missing

            # Check if the fumen has any content or if its level is defined.
            has_notes = bool(fumen_item.get('note_events'))
            has_commas = bool(fumen_item.get('timing_events_at_commas'))
            level_is_defined = fumen_idx < len(levels) and bool(levels[fumen_idx])

            # If the fumen is completely empty and its level isn't defined, skip it.
            if not has_notes and not has_commas and not level_is_defined: continue

            simai_output_lines.append(f"&inote_{fumen_idx + 1}=") # Fumen header
            if not has_notes and not has_commas:
                # If the fumen is defined by a level but has no events, add an empty line.
                simai_output_lines.append("")
                continue

            fumen_lines_buffer = [] # Buffer for lines within the current fumen
            notes_since_last_boundary = [] # Buffer for notes between commas or timing changes
            active_bpm_for_fumen = chart_global_bpm_for_metadata # Initialize fumen BPM with global BPM
            active_hspeed_for_fumen = 1.0 # Default HSpeed

            # Collect all note and comma events into a single list to sort by time.
            all_points = []
            if fumen_item.get('note_events'):
                for ne_idx, ne in enumerate(fumen_item['note_events']):
                    all_points.append({'time': ne['time'], 'type': 'note', 'obj': ne, 'original_order': ne_idx})
            if fumen_item.get('timing_events_at_commas'):
                for te_idx, te in enumerate(fumen_item['timing_events_at_commas']):
                    all_points.append({'time': te['time'], 'type': 'comma', 'obj': te, 'original_order': te_idx})

            # Sort events by time. If times are equal, notes come before commas.
            # 'original_order' is used as a secondary sort key for stability if times and types are identical.
            all_points.sort(key=lambda x: (x['time'], 0 if x['type'] == 'note' else 1, x.get('original_order', 0)))

            comma_times_and_x = {} # Dictionary to store calculated X values for segments starting at comma times
            comma_only_events = [p for p in all_points if p['type'] == 'comma']

            # Pre-calculate X for each segment defined by comma events.
            for i, current_comma_event_info in enumerate(comma_only_events):
                current_comma_time = current_comma_event_info['time']
                # BPM for X calculation is taken from the comma event itself if present,
                # otherwise, the active fumen BPM is used.
                bpm_for_this_segment_x_calc = current_comma_event_info['obj'].get('current_bpm_at_event', active_bpm_for_fumen)
                if bpm_for_this_segment_x_calc is None: bpm_for_this_segment_x_calc = active_bpm_for_fumen

                next_comma_time = None
                if i + 1 < len(comma_only_events):
                    next_comma_time = comma_only_events[i + 1]['time']

                calculated_x = 4.0 # Default X
                if next_comma_time is not None: # Segment between two commas
                    duration = next_comma_time - current_comma_time
                    if duration > 1e-6: # Avoid division by zero or very small values
                        calculated_x = self._calculate_x_for_segment(duration, bpm_for_this_segment_x_calc)
                else:  # Last segment (from the last comma to the end of notes in that segment)
                    # Find the time of the last event (note or 'E') after the current comma.
                    last_event_time_in_segment = current_comma_time
                    notes_after_this_comma = [p['time'] for p in all_points if
                                              p['time'] >= current_comma_time and p['type'] == 'note']
                    if notes_after_this_comma:
                        last_event_time_in_segment = max(last_event_time_in_segment, max(notes_after_this_comma))

                    # If no notes after the last comma, but there's an 'E' (end marker), use its time.
                    if not notes_after_this_comma:
                        e_events = [p['time'] for p in all_points if
                                    p['time'] >= current_comma_time and p['type'] == 'note' and p['obj'].get(
                                        'notes_content_raw', '').strip() == 'E']
                        if e_events:
                            last_event_time_in_segment = max(last_event_time_in_segment, max(e_events))

                    duration_to_last = last_event_time_in_segment - current_comma_time

                    # If the duration of the last segment (to the last note/E) is very small or zero,
                    # assume it's a segment of 1 beat at the current BPM to avoid infinite X.
                    # This is crucial if the last comma and last note are at the same time.
                    # A threshold (e.g., less than 1/16th of a beat) is used to detect this.
                    beat_duration_threshold = (60.0 / (bpm_for_this_segment_x_calc or 120.0)) * 0.25
                    if duration_to_last < beat_duration_threshold:
                        is_final_e_segment = any(
                            p['obj'].get('notes_content_raw', '').strip() == 'E' for p in all_points if
                            p['time'] >= current_comma_time and p['type'] == 'note')
                        has_non_e_notes_in_segment = any(
                            p['obj'].get('notes_content_raw', '').strip() != 'E' for p in all_points if
                            p['time'] >= current_comma_time and p['type'] == 'note')

                        if not has_non_e_notes_in_segment and is_final_e_segment:  # Only 'E' in this segment
                            calculated_x = 4.0  # Or another standard X for 'E,' segments
                        elif duration_to_last < 1e-5:  # If it's like "1," with no subsequent notes, assume 1 beat long
                            duration_to_last = 60.0 / (bpm_for_this_segment_x_calc or 120.0)  # Duration of 1 beat
                            calculated_x = self._calculate_x_for_segment(duration_to_last, bpm_for_this_segment_x_calc) # Should result in X=4
                        else:  # If there are notes but the segment is short
                            calculated_x = self._calculate_x_for_segment(duration_to_last, bpm_for_this_segment_x_calc)
                    elif duration_to_last > 1e-6:
                        calculated_x = self._calculate_x_for_segment(duration_to_last, bpm_for_this_segment_x_calc)

                comma_times_and_x[current_comma_time] = calculated_x

            current_line_output_segments = [] # Buffer for segments on the current simai line
            x_governing_current_line = None # The X value that defines the current line's structure
            segments_on_current_line = 0 # Counter for segments on the current line
            # Default to 1 segment per line if X is not defined or <=1.
            # This is later updated based on the actual X value.
            max_segments_this_line = 1

            # Set initial BPM and HSpeed for the fumen based on the first event.
            if all_points:
                first_event_obj = all_points[0]['obj']
                initial_bpm = first_event_obj.get('current_bpm_at_event', active_bpm_for_fumen)
                initial_hspeed = first_event_obj.get('hspeed_at_event', 1.0)

                if initial_bpm is not None and not math.isclose(initial_bpm, active_bpm_for_fumen):
                    active_bpm_for_fumen = initial_bpm
                # Always output the BPM at the beginning of the fumen.
                fumen_lines_buffer.append(f"({self._format_number(active_bpm_for_fumen)})")

                if not math.isclose(initial_hspeed, 1.0): # Output HSpeed only if it's not the default 1.0
                    fumen_lines_buffer.append(f"<H{self._format_number(initial_hspeed)}>")
                    active_hspeed_for_fumen = initial_hspeed
            elif active_bpm_for_fumen is not None: # If no events, but there's an active BPM (e.g., from metadata)
                fumen_lines_buffer.append(f"({self._format_number(active_bpm_for_fumen)})")


            def flush_current_line():
                """
                Helper function to format and append the current line of simai notes
                to the fumen buffer. It handles X value standardization and BPM adjustments
                to maintain segment durations.
                """
                nonlocal current_line_output_segments, x_governing_current_line, segments_on_current_line, active_bpm_for_fumen

                if not current_line_output_segments: return # Nothing to flush

                line_str = ""
                x_val_original = x_governing_current_line # Original calculated X for this line

                if x_val_original is not None and active_bpm_for_fumen is not None and active_bpm_for_fumen > 0:
                    # Check if the original X is already a standard value (within a small tolerance)
                    is_std = any(math.isclose(x_val_original, std_val, rel_tol=0.01, abs_tol=0.01) for std_val in self.standard_x_values)

                    if not is_std:
                        # If X is not standard, find the closest standard X.
                        # This is for debugging/logging purposes.
                        # print(f"[DEBUG REBUILD V3] Non-standard X: {x_val_original:.4f} at BPM: {active_bpm_for_fumen:.2f}")
                        target_x = self._find_closest_standard_x(x_val_original)
                        # print(f"[DEBUG REBUILD V3] Closest standard X chosen: {target_x}")

                        if target_x is not None and not math.isclose(target_x, x_val_original):
                            # If a different standard X is chosen, adjust BPM to preserve segment duration.
                            # Original duration = k / (original_X * original_BPM)
                            # New duration = k / (target_X * new_BPM)
                            # To keep duration same: original_X * original_BPM = target_X * new_BPM
                            # So, new_BPM = (original_X / target_X) * original_BPM
                            new_bpm = active_bpm_for_fumen * (x_val_original / target_x)
                            new_bpm_formatted_str = self._format_number(new_bpm, precision=2) # Format new BPM

                            # Add the BPM change command *before* this line with the new {X}.
                            # This BPM change applies to the current segment and subsequent ones
                            # until another explicit BPM change occurs.
                            fumen_lines_buffer.append(f"({new_bpm_formatted_str})")
                            # print(f"[DEBUG REBUILD V3] BPM Change: ({active_bpm_for_fumen:.2f} -> {new_bpm_formatted_str}) for X: {x_val_original:.2f} -> {target_x}")
                            active_bpm_for_fumen = float(new_bpm_formatted_str) # Update the active BPM

                            line_str += f"{{{self._format_number(target_x, precision=2)}}}"
                        else:
                            # If target_x is the same or couldn't be found, use the original (possibly rounded).
                            line_str += f"{{{self._format_number(x_val_original, precision=2)}}}"
                    else:
                        # If X is already standard, use it directly.
                        line_str += f"{{{self._format_number(x_val_original, precision=2)}}}"
                elif x_val_original is not None: # If BPM is not defined, but X exists (less common scenario)
                    line_str += f"{{{self._format_number(x_val_original, precision=2)}}}"

                line_str += "".join(current_line_output_segments) # Append the note segments
                if line_str.strip(): # Add the line to buffer if it's not empty
                    fumen_lines_buffer.append(line_str)

                # Reset for the next line
                current_line_output_segments = []
                x_governing_current_line = None
                segments_on_current_line = 0

            # --- Main Event Loop for processing notes and commas within a fumen ---
            for event_idx, event_info in enumerate(all_points):
                event_obj = event_info['obj']
                point_bpm = event_obj.get('current_bpm_at_event') # BPM at this specific event point
                point_hspeed = event_obj.get('hspeed_at_event', 1.0) # HSpeed at this event point

                # Handle BPM changes
                if point_bpm is not None and not math.isclose(point_bpm, active_bpm_for_fumen):
                    flush_current_line() # Output any pending line before BPM change
                    if notes_since_last_boundary: # If there are notes buffered before this BPM change
                        fumen_lines_buffer.append("".join(notes_since_last_boundary))
                    notes_since_last_boundary = []
                    fumen_lines_buffer.append(f"({self._format_number(point_bpm)})") # Output BPM change
                    active_bpm_for_fumen = point_bpm # Update active BPM

                # Handle HSpeed changes
                if not math.isclose(point_hspeed, active_hspeed_for_fumen):
                    flush_current_line() # Output any pending line before HSpeed change
                    if notes_since_last_boundary:
                        fumen_lines_buffer.append("".join(notes_since_last_boundary))
                    notes_since_last_boundary = []
                    # Output HSpeed change only if it's not 1.0, or if changing back to 1.0 from non-1.0
                    if not math.isclose(point_hspeed, 1.0) or \
                       (math.isclose(point_hspeed, 1.0) and not math.isclose(active_hspeed_for_fumen, 1.0)):
                        fumen_lines_buffer.append(f"<H{self._format_number(point_hspeed)}>")
                    active_hspeed_for_fumen = point_hspeed # Update active HSpeed

                # Process notes and commas
                if event_info['type'] == 'note':
                    notes_since_last_boundary.append(event_obj['notes_content_raw']) # Buffer note content
                elif event_info['type'] == 'comma': # Comma indicates end of a small segment
                    current_small_segment_notes = "".join(notes_since_last_boundary)
                    notes_since_last_boundary = []
                    current_small_segment_str = current_small_segment_notes + "," # Append comma

                    # Get the pre-calculated X value for the segment ending with this comma.
                    x_for_this_segment = comma_times_and_x.get(event_info['time'])
                    if x_for_this_segment is None: x_for_this_segment = 4.0 # Safe default

                    # The BPM associated with a comma event might affect the X calculation for *its* segment.
                    # However, active_bpm_for_fumen used by flush_current_line should be the BPM *during*
                    # the segment being flushed. If a comma event also carries a BPM change, that change
                    # typically applies *after* the comma, for the *next* segment.
                    # The logic for BPM changes above should handle explicit BPM events.
                    # If BPM is embedded within the comma event itself and intended to affect the *current*
                    # segment's X, that was handled during `comma_times_and_x` calculation.

                    # Determine how many segments can fit on one line with the current X value.
                    # If X is not an integer (e.g., {3.5}), floor it (e.g., 3 segments per line).
                    # If X < 1, then 1 segment per line.
                    max_segments_this_line = math.floor(x_for_this_segment) if x_for_this_segment >= 1 else 1

                    if not current_line_output_segments:  # Starting a new simai line
                        x_governing_current_line = x_for_this_segment
                        current_line_output_segments.append(current_small_segment_str)
                        segments_on_current_line = 1
                    # If the X for this segment is close enough to the X governing the current line,
                    # and we haven't exceeded the max segments for this line, append to current line.
                    elif (x_governing_current_line is not None and
                          math.isclose(x_for_this_segment, x_governing_current_line, rel_tol=0.01, abs_tol=0.01)) and \
                            segments_on_current_line < max_segments_this_line:
                        current_line_output_segments.append(current_small_segment_str)
                        segments_on_current_line += 1
                    else:  # X value changed significantly or max segments reached, flush old line, start new.
                        flush_current_line()
                        x_governing_current_line = x_for_this_segment
                        current_line_output_segments.append(current_small_segment_str)
                        segments_on_current_line = 1

            flush_current_line()  # Flush any remaining segments at the end of all events
            if notes_since_last_boundary:  # Flush any remaining notes (typically the 'E' marker)
                fumen_lines_buffer.append("".join(notes_since_last_boundary))

            # Add the processed fumen lines to the main output.
            if fumen_lines_buffer:
                simai_output_lines.append("\n".join(line for line in fumen_lines_buffer if line or line == "")) # Preserve empty lines from buffer
            elif level_is_defined: # If level was defined but fumen was empty, ensure an empty line for it
                simai_output_lines.append("")

            # Add a blank line between fumens, unless it's the last meaningful fumen.
            is_last_meaningful_fumen = (fumen_idx == len(self.fumens_data) - 1) or \
                                       not any(
                                           self.fumens_data[next_f_idx] and ( # Check next fumen is not None
                                                   bool(self.fumens_data[next_f_idx].get('note_events')) or \
                                                   bool(self.fumens_data[next_f_idx].get('timing_events_at_commas')) or \
                                                   (next_f_idx < len(levels) and bool(levels[next_f_idx])) # And has content or defined level
                                           )
                                           for next_f_idx in range(fumen_idx + 1, len(self.fumens_data))
                                       )
            if not is_last_meaningful_fumen:
                simai_output_lines.append("")

        # --- Final Output Cleaning ---
        # Remove excessive trailing blank lines. Keep at most one.
        while len(simai_output_lines) > 1 and \
                (simai_output_lines[-1] == "" or simai_output_lines[-1].isspace()) and \
                (simai_output_lines[-2] == "" or simai_output_lines[-2].isspace()):
            simai_output_lines.pop()

        # Remove the very last blank line if it's not needed for separation or for an empty fumen definition.
        if len(simai_output_lines) > 0 and (simai_output_lines[-1] == "" or simai_output_lines[-1].isspace()):
            # Don't remove if it's the only line and it's a fumen header like "&inote_X="
            if len(simai_output_lines) == 1 and simai_output_lines[0].startswith("&inote_"):
                pass
            # Don't remove if the second to last line has content (i.e., the blank line is a separator)
            elif len(simai_output_lines) > 1 and (simai_output_lines[-2].strip() if simai_output_lines[-2] else False):
                pass
            elif len(simai_output_lines) == 1: # If it's the only line and it's blank (and not an &inote header)
                simai_output_lines.pop()

        final_output = "\n".join(simai_output_lines)
        # Ensure there's a single trailing newline if there's content.
        if final_output and not final_output.endswith("\n"):
            final_output += "\n"
        # If output is just "&inote_X=" ensure it has a newline.
        elif len(simai_output_lines) == 1 and simai_output_lines[0].startswith("&inote_") and not final_output.endswith("\n"):
            final_output += "\n"

        return final_output

