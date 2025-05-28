import json
import re
from collections import Counter
import fractions

class JsonSimaiConverter:
    """
    Converts Simai chart data from a JSON-like Python dictionary back to Simai text format.
    This version prioritizes event time and note content. It infers global BPM for metadata,
    ensures each fumen explicitly states its initial BPM, and calculates
    beat signature changes ({X}) using fractions for segments defined by comma timings,
    with refined line formatting to pack segments into "beats per line".
    """

    def __init__(self, chart_data_dict):
        """
        Initializes the converter with chart data.
        Args:
            chart_data_dict (dict): A Python dictionary representing the Simai chart.
        """
        self.chart_data = chart_data_dict
        self.metadata = self.chart_data.get("metadata", {})
        self.fumens_data = self.chart_data.get("fumens_data", [])

    @classmethod
    def from_json_file(cls, filepath, encoding='utf-8'):
        """
        Creates a JsonSimaiConverter instance from a JSON file.
        """
        with open(filepath, 'r', encoding=encoding) as f:
            data = json.load(f)
        return cls(data)
    
    @classmethod
    def from_json_text(cls, json_text):
        """
        Creates a JsonSimaiConverter instance from a json text string.
        """
        return cls(json.loads(json_text))
    
    def _format_number(self, num, precision=4):
        """Formats a number to an integer string if it's a whole number, else a float string."""
        if num is None:
            return "" 
        if isinstance(num, (int, float)) and float(num).is_integer():
            return str(int(num))
        
        formatted_num = f"{num:.{precision}f}".rstrip('0').rstrip('.')
        return formatted_num if formatted_num else "0"

    def _determine_chart_global_bpm(self):
        """
        Tries to determine a common starting BPM for metadata &wholebpm.
        """
        initial_bpms = []
        for fumen_item in self.fumens_data:
            events_to_check_bpm = fumen_item.get('note_events', [])
            if not events_to_check_bpm:
                events_to_check_bpm = fumen_item.get('timing_events_at_commas', [])
            
            if events_to_check_bpm: 
                first_event_bpm = events_to_check_bpm[0].get('current_bpm_at_event')
                if first_event_bpm is not None:
                    initial_bpms.append(first_event_bpm)
        
        if not initial_bpms: return None
        if len(set(initial_bpms)) == 1: return initial_bpms[0]
        
        if initial_bpms:
            bpm_counts = Counter(initial_bpms)
            most_common_bpm, count = bpm_counts.most_common(1)[0]
            if count > len(initial_bpms) / 2 or len(bpm_counts) == 1:
                 return most_common_bpm
        return None

    def _calculate_x_for_segment(self, segment_duration, bpm_at_segment_start):
        """Calculates the {X} value for a segment."""
        MAX_X = 256.0
        MIN_X = 0.0625
        
        if not all([segment_duration > 1e-6, 
                   bpm_at_segment_start and bpm_at_segment_start > 0]):
            return max(MIN_X, min(4.0, MAX_X))
        
        try:
            x_candidate = 240.0 / (segment_duration * bpm_at_segment_start)
            x_candidate = max(MIN_X, min(x_candidate, MAX_X))
            
            frac = fractions.Fraction(x_candidate).limit_denominator(256)
            x_val = float(frac)
            return max(MIN_X, min(x_val, MAX_X))
        except:
            return max(MIN_X, min(x_candidate if 'x_candidate' in locals() else 4.0, MAX_X))

    def to_simai_text(self):
        simai_output_lines = []
        # --- Metadata Section ---
        if self.metadata.get("title"): simai_output_lines.append(f"&title={self.metadata['title']}")
        if self.metadata.get("artist"): simai_output_lines.append(f"&artist={self.metadata['artist']}")
        if self.metadata.get("designer"): simai_output_lines.append(f"&des={self.metadata['designer']}")
        
        chart_global_bpm_for_metadata = self._determine_chart_global_bpm()
        if chart_global_bpm_for_metadata is not None:
            simai_output_lines.append(f"&wholebpm={self._format_number(chart_global_bpm_for_metadata)}")

        if "first_offset_sec" in self.metadata:
            first_offset = self.metadata['first_offset_sec']
            simai_output_lines.append(f"&first={self._format_number(first_offset)}")

        levels = self.metadata.get("levels", [])
        for i, lv_value in enumerate(levels):
            if lv_value: simai_output_lines.append(f"&lv_{i+1}={lv_value}")
        
        simai_output_lines.append("") 

        # --- Fumens Section ---
        for fumen_idx, fumen_item in enumerate(self.fumens_data):
            has_notes = bool(fumen_item.get('note_events'))
            has_commas = bool(fumen_item.get('timing_events_at_commas'))
            level_is_defined = fumen_idx < len(levels) and bool(levels[fumen_idx])

            if not has_notes and not has_commas and not level_is_defined: continue
            
            simai_output_lines.append(f"&inote_{fumen_idx+1}=")
            if not has_notes and not has_commas: 
                simai_output_lines.append("")
                continue

            fumen_lines_buffer = [] 
            notes_since_last_boundary = [] # Accumulates notes between significant timing boundaries
            
            active_bpm_for_fumen = None 
            active_hspeed_for_fumen = 1.0
            
            all_points = [] 
            if fumen_item.get('note_events'):
                for ne_idx, ne in enumerate(fumen_item['note_events']): all_points.append({'time': ne['time'], 'type': 'note', 'obj': ne, 'original_order': ne_idx})
            if fumen_item.get('timing_events_at_commas'):
                for te_idx, te in enumerate(fumen_item['timing_events_at_commas']): all_points.append({'time': te['time'], 'type': 'comma', 'obj': te, 'original_order': te_idx})
            
            all_points.sort(key=lambda x: (x['time'], x.get('original_order', 0), 0 if x['type'] == 'note' else 1))

            # Pre-calculate {X} for segments starting at each comma
            comma_times_and_x = {} # Store: comma_start_time -> calculated_X_for_segment_starting_at_this_time
            
            # Create a list of just comma events to find next comma easily
            comma_only_events = [p for p in all_points if p['type'] == 'comma']

            for i, current_comma_event_info in enumerate(comma_only_events):
                current_comma_time = current_comma_event_info['time']
                bpm_for_this_segment_x_calc = current_comma_event_info['obj'].get('current_bpm_at_event')
                
                next_comma_time = None
                if i + 1 < len(comma_only_events):
                    next_comma_time = comma_only_events[i+1]['time']
                
                calculated_x = None
                if next_comma_time is not None:
                    duration = next_comma_time - current_comma_time
                    calculated_x = self._calculate_x_for_segment(duration, bpm_for_this_segment_x_calc)
                else:
                    # 处理最后一个时间段
                    last_note_time = max(p['time'] for p in all_points) if all_points else current_comma_time
                    duration_to_last_note = last_note_time - current_comma_time
                    
                    # 如果持续时间过小（小于1拍），则扩展持续时间
                    if duration_to_last_note < (60.0 / bpm_for_this_segment_x_calc if bpm_for_this_segment_x_calc else 0.5):
                        duration_to_last_note = 60.0 / (bpm_for_this_segment_x_calc or 120)  # 默认1拍
                        
                    calculated_x = self._calculate_x_for_segment(duration_to_last_note, bpm_for_this_segment_x_calc)
                
                comma_times_and_x[current_comma_time] = calculated_x


            current_line_output_segments = [] 
            x_governing_current_line = None 
            segments_on_current_line = 0
            max_segments_this_line = 1 

            if all_points:
                first_event_obj = all_points[0]['obj']
                initial_bpm = first_event_obj.get('current_bpm_at_event')
                initial_hspeed = first_event_obj.get('hspeed_at_event', 1.0)

                if initial_bpm is not None:
                    fumen_lines_buffer.append(f"({self._format_number(initial_bpm)})")
                    active_bpm_for_fumen = initial_bpm
                
                if initial_hspeed != 1.0:
                    fumen_lines_buffer.append(f"<H{self._format_number(initial_hspeed)}>")
                active_hspeed_for_fumen = initial_hspeed
            
            def flush_current_line():
                nonlocal current_line_output_segments, x_governing_current_line, segments_on_current_line
                if current_line_output_segments: 
                    line_str = ""
                    if x_governing_current_line is not None:
                         line_str += f"{{{self._format_number(x_governing_current_line, precision=2)}}}"
                    line_str += "".join(current_line_output_segments)
                    if line_str.strip(): 
                        fumen_lines_buffer.append(line_str)
                current_line_output_segments = [] 
                x_governing_current_line = None
                segments_on_current_line = 0
            
            for event_info in all_points:
                event_obj = event_info['obj']
                point_bpm = event_obj.get('current_bpm_at_event')
                point_hspeed = event_obj.get('hspeed_at_event', 1.0) 
                current_event_time = event_info['time']

                if point_bpm is not None and active_bpm_for_fumen is not None and point_bpm != active_bpm_for_fumen:
                    flush_current_line()
                    if notes_since_last_boundary:
                        fumen_lines_buffer.append("".join(notes_since_last_boundary))
                    notes_since_last_boundary = []
                    fumen_lines_buffer.append(f"({self._format_number(point_bpm)})")
                    active_bpm_for_fumen = point_bpm
                
                if point_hspeed is not None:
                    hspeed_changed = False
                    if active_hspeed_for_fumen is None or point_hspeed != active_hspeed_for_fumen:
                        if point_hspeed != 1.0 or (active_hspeed_for_fumen is not None and active_hspeed_for_fumen != 1.0):
                            hspeed_changed = True
                    if hspeed_changed:
                        flush_current_line()
                        if notes_since_last_boundary:
                            fumen_lines_buffer.append("".join(notes_since_last_boundary))
                        notes_since_last_boundary = []
                        fumen_lines_buffer.append(f"<H{self._format_number(point_hspeed)}>")
                        active_hspeed_for_fumen = point_hspeed
                
                if event_info['type'] == 'note':
                    notes_since_last_boundary.append(event_obj['notes_content_raw'])
                elif event_info['type'] == 'comma':
                    current_small_segment_notes = "".join(notes_since_last_boundary)
                    notes_since_last_boundary = []
                    
                    current_small_segment_str = current_small_segment_notes + ","
                    x_for_this_segment = comma_times_and_x.get(current_event_time)

                    if not current_line_output_segments:
                        x_governing_current_line = x_for_this_segment
                        segments_on_current_line = 0
                        if x_governing_current_line and x_governing_current_line > 0:
                            max_segments_this_line = int(round(x_governing_current_line))
                        else: 
                            max_segments_this_line = 1
                        
                        current_line_output_segments.append(current_small_segment_str)
                        segments_on_current_line = 1
                    elif (x_for_this_segment == x_governing_current_line 
                          and segments_on_current_line < max_segments_this_line):
                        current_line_output_segments.append(current_small_segment_str)
                        segments_on_current_line += 1
                    else:
                        flush_current_line()
                        x_governing_current_line = x_for_this_segment
                        segments_on_current_line = 0
                        if x_governing_current_line and x_governing_current_line > 0:
                            max_segments_this_line = int(round(x_governing_current_line))
                        else:
                            max_segments_this_line = 1
                        current_line_output_segments.append(current_small_segment_str)
                        segments_on_current_line = 1
            
            flush_current_line() 
            if notes_since_last_boundary:
                 fumen_lines_buffer.append("".join(notes_since_last_boundary))
            
            if fumen_lines_buffer:
                simai_output_lines.append("\n".join(line for line in fumen_lines_buffer if line or line == ""))
            elif level_is_defined:
                 simai_output_lines.append("")

            is_last_meaningful_fumen = (fumen_idx == len(self.fumens_data) - 1) or \
                not any(
                    bool(self.fumens_data[next_f_idx].get('note_events')) or \
                    bool(self.fumens_data[next_f_idx].get('timing_events_at_commas')) or \
                    (next_f_idx < len(levels) and bool(levels[next_f_idx]))
                    for next_f_idx in range(fumen_idx + 1, len(self.fumens_data))
                )
            if not is_last_meaningful_fumen:
                 simai_output_lines.append("")

        while len(simai_output_lines) > 1 and \
              (simai_output_lines[-1] == "" or simai_output_lines[-1].isspace()) and \
              (simai_output_lines[-2] == "" or simai_output_lines[-2].isspace()):
            simai_output_lines.pop()
        
        if len(simai_output_lines) > 0 and (simai_output_lines[-1] == "" or simai_output_lines[-1].isspace()):
            if len(simai_output_lines) == 1 and simai_output_lines[0].startswith("&inote_"): pass
            elif len(simai_output_lines) > 1 and (simai_output_lines[-2].strip() if simai_output_lines[-2] else False):
                 simai_output_lines.pop()
            elif len(simai_output_lines) == 1: simai_output_lines.pop()

        final_output = "\n".join(simai_output_lines)
        if final_output and not final_output.endswith("\n"): final_output += "\n"
        elif len(simai_output_lines) == 1 and simai_output_lines[0].startswith("&inote_") and not final_output.endswith("\n"):
             final_output += "\n"
        
        return final_output

