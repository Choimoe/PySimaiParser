import unittest
import json
from SimaiParser import SimaiChart


class TestSimaiParserCore(unittest.TestCase):

    def _parse_simai(self, simai_content_str):
        chart = SimaiChart()
        chart.load_from_text(simai_content_str)
        return json.loads(chart.to_json())

    def test_metadata_parsing(self):
        content = """
&title=My Awesome Song
&artist=The Best Artist
&des=Chart Master
&first=1.5
&lv_1=1
&lv_4=10+
&lv_5=12
&uot_other=some_value
"""
        parsed_chart = self._parse_simai(content)
        metadata = parsed_chart["metadata"]
        self.assertEqual(metadata["title"], "My Awesome Song")
        self.assertEqual(metadata["artist"], "The Best Artist")
        self.assertEqual(metadata["designer"], "Chart Master")
        self.assertAlmostEqual(metadata["first_offset_sec"], 1.5)
        self.assertEqual(metadata["levels"][0], "1")
        self.assertEqual(metadata["levels"][3], "10+")
        self.assertEqual(metadata["levels"][4], "12")
        self.assertEqual(metadata["levels"][1], "")  # Unspecified levels should be empty
        self.assertIn("&uot_other=some_value", metadata["other_commands_raw"])

    def test_empty_fumen(self):
        content = "&inote_1=\n"  # Completely empty fumen
        parsed_chart = self._parse_simai(content)
        fumen_data = parsed_chart["fumens_data"][0]
        self.assertEqual(fumen_data["difficulty_index"], 0)
        self.assertEqual(len(fumen_data["note_events"]), 0)
        self.assertEqual(len(fumen_data["timing_events_at_commas"]), 0)

    def test_simple_tap_and_bpm(self):
        content = """
&first=0.5
&inote_1=
(120)
1,
2,
"""
        parsed_chart = self._parse_simai(content)
        fumen_data = parsed_chart["fumens_data"][0]

        self.assertEqual(len(fumen_data["note_events"]), 2)
        self.assertEqual(len(fumen_data["timing_events_at_commas"]), 2)

        # First note event (for "1")
        event1_notes = fumen_data["note_events"][0]
        self.assertAlmostEqual(event1_notes["time"], 0.5)
        self.assertAlmostEqual(event1_notes["current_bpm_at_event"], 120.0)
        self.assertEqual(len(event1_notes["notes"]), 1)
        note1 = event1_notes["notes"][0]
        self.assertEqual(note1["note_type"], "TAP")
        self.assertEqual(note1["start_position"], 1)

        # First comma event
        event1_comma = fumen_data["timing_events_at_commas"][0]
        self.assertAlmostEqual(event1_comma["time"], 0.5)

        # Second note event (for "2")
        # Time = 0.5 (first) + (60/120) * (4/4) = 0.5 + 0.5 = 1.0
        event2_notes = fumen_data["note_events"][1]
        self.assertAlmostEqual(event2_notes["time"], 1.0)
        self.assertAlmostEqual(event2_notes["current_bpm_at_event"], 120.0)
        self.assertEqual(len(event2_notes["notes"]), 1)
        note2 = event2_notes["notes"][0]
        self.assertEqual(note2["note_type"], "TAP")
        self.assertEqual(note2["start_position"], 2)

        # Second comma event
        event2_comma = fumen_data["timing_events_at_commas"][1]
        self.assertAlmostEqual(event2_comma["time"], 1.0)

    def test_hold_note_basic_duration(self):
        content = """
&first=0
&inote_1=
(60)
1h[4:1], 
"""  # Hold for 1 beat at 60 BPM = 1 second duration. 1 beat = (60/60 * 4/4 * 1)
        parsed_chart = self._parse_simai(content)
        fumen_data = parsed_chart["fumens_data"][0]
        self.assertEqual(len(fumen_data["note_events"]), 1)
        note_event = fumen_data["note_events"][0]
        self.assertAlmostEqual(note_event["time"], 0.0)
        self.assertEqual(len(note_event["notes"]), 1)
        hold_note = note_event["notes"][0]
        self.assertEqual(hold_note["note_type"], "HOLD")
        self.assertEqual(hold_note["start_position"], 1)
        self.assertAlmostEqual(hold_note["hold_time"], 1.0)  # (60/60) * (4/4) * 1 = 1s

    def test_hold_note_custom_bpm_duration(self):
        content = """
&first=0
&inote_1=
(60) 
1h[120#4:1], 
"""  # Duration calculated at 120 BPM: (60/120) * (4/4) * 1 = 0.5s
        parsed_chart = self._parse_simai(content)
        note_event = parsed_chart["fumens_data"][0]["note_events"][0]
        hold_note = note_event["notes"][0]
        self.assertEqual(hold_note["note_type"], "HOLD")
        self.assertAlmostEqual(hold_note["hold_time"], 0.5)

    def test_hold_note_absolute_time_duration(self):
        content = """
&first=0
&inote_1=
(100)
1h[#2.5],
"""
        parsed_chart = self._parse_simai(content)
        hold_note = parsed_chart["fumens_data"][0]["note_events"][0]["notes"][0]
        self.assertEqual(hold_note["note_type"], "HOLD")
        self.assertAlmostEqual(hold_note["hold_time"], 2.5)

    def test_slide_note_duration_and_star_wait(self):
        content = """
&first=0
&inote_1=
(120)
1-4[4:1], 
"""  # Star wait: 1 beat at 120BPM = 0.5s. Slide duration: 1 beat at 120BPM = 0.5s.
        parsed_chart = self._parse_simai(content)
        slide_note = parsed_chart["fumens_data"][0]["note_events"][0]["notes"][0]
        self.assertEqual(slide_note["note_type"], "SLIDE")
        self.assertAlmostEqual(slide_note["slide_start_time_offset"], 0.5)
        self.assertAlmostEqual(slide_note["slide_time"], 0.5)

    def test_slide_note_custom_bpm_star_and_duration(self):
        content = """
&first=0
&inote_1=
(100) 
1V[120#8:1], 
"""  # Star wait uses 120BPM: (60/120)=0.5s. Duration uses 120BPM: (60/120)*(4/8)*1 = 0.25s
        parsed_chart = self._parse_simai(content)
        slide_note = parsed_chart["fumens_data"][0]["note_events"][0]["notes"][0]
        self.assertEqual(slide_note["note_type"], "SLIDE")
        self.assertAlmostEqual(slide_note["slide_start_time_offset"], 0.5)
        self.assertAlmostEqual(slide_note["slide_time"], 0.25)

    def test_slide_note_absolute_star_wait_no_hash_and_duration(self):
        content = """
&first=0
&inote_1=
(100)
1<[0.2##0.75], 
"""  # Star wait: 0.2s (no #). Duration: 0.75s
        parsed_chart = self._parse_simai(content)
        slide_note = parsed_chart["fumens_data"][0]["note_events"][0]["notes"][0]
        self.assertEqual(slide_note["note_type"], "SLIDE")
        self.assertAlmostEqual(slide_note["slide_start_time_offset"], 0.2)
        self.assertAlmostEqual(slide_note["slide_time"], 0.75)

    def test_touch_note(self):
        content = """
&first=0
&inote_1=
(120)
A1/C,E4h[4:1],
"""
        parsed_chart = self._parse_simai(content)
        notes_at_event = parsed_chart["fumens_data"][0]["note_events"][0]["notes"]

        self.assertEqual(len(notes_at_event), 2)

        touch_a1 = notes_at_event[0]
        self.assertEqual(touch_a1["note_type"], "TOUCH")
        self.assertEqual(touch_a1["touch_area"], "A")
        self.assertEqual(touch_a1["start_position"], 1)

        touch_c = notes_at_event[1]
        self.assertEqual(touch_c["note_type"], "TOUCH")
        self.assertEqual(touch_c["touch_area"], "C")
        self.assertEqual(touch_c["start_position"], 8)  # Convention for C

        notes_at_event = parsed_chart["fumens_data"][0]["note_events"][1]["notes"]

        self.assertEqual(len(notes_at_event), 1)

        touch_e4h = notes_at_event[0]
        self.assertEqual(touch_e4h["note_type"], "TOUCH_HOLD")
        self.assertEqual(touch_e4h["touch_area"], "E")
        self.assertEqual(touch_e4h["start_position"], 4)
        self.assertAlmostEqual(touch_e4h["hold_time"], 0.5)  # 1 beat at 120 BPM

    def test_modifiers(self):
        content = """
&first=0
&inote_1=
(120)
1bfx$,
2h[4:1]b!,
"""
        parsed_chart = self._parse_simai(content)
        fumen_data = parsed_chart["fumens_data"][0]

        note1_event = fumen_data["note_events"][0]
        note1 = note1_event["notes"][0]
        self.assertEqual(note1["note_type"],
                         "TAP")  # $ implies slide, but no path. Parser might make it TAP or SLIDE. Current makes it TAP.
        self.assertTrue(note1["is_break"])
        self.assertTrue(note1["is_hanabi"])
        self.assertTrue(note1["is_ex"])
        self.assertTrue(note1["is_force_star"])

        note2_event = fumen_data["note_events"][1]  # Time = 0.5s
        note2 = note2_event["notes"][0]
        self.assertEqual(note2["note_type"], "HOLD")
        self.assertTrue(note2["is_break"])  # 'b' on hold
        # '!' is for slides, typically ignored on non-slides or might be an error by charter.
        # self.assertTrue(note2["is_slide_no_head"]) # This would be false for a HOLD

    def test_slide_modifiers(self):
        content = """
&first=0
&inote_1=
(120)
1b-2[4:1]x!$$,
"""
        # 1b: break on tap part of slide
        # -2[4:1]: slide path and duration
        # x: EX
        # !: no head (though head '1' is given, '!' takes precedence for visual)
        # $$: fake rotate
        parsed_chart = self._parse_simai(content)
        fumen_data = parsed_chart["fumens_data"][0]
        note_event = fumen_data["note_events"][0]
        note = note_event["notes"][0]

        self.assertEqual(note["note_type"], "SLIDE")
        self.assertTrue(note["is_break"])  # Break on the star/tap part
        self.assertFalse(note["is_slide_break"])  # Not a break on the slide segment itself
        self.assertTrue(note["is_ex"])
        self.assertTrue(note["is_slide_no_head"])
        self.assertTrue(note["is_force_star"])  # $$ implies $
        self.assertTrue(note["is_fake_rotate"])
        self.assertAlmostEqual(note["slide_time"], 0.5)
        self.assertAlmostEqual(note["slide_start_time_offset"], 0.5)

    def test_slide_break_on_segment(self):
        content = """
&first=0
&inote_1=
(120)
1-b[4:1], 
"""  # 'b' after '-' and before '[' should be a slide_break
        parsed_chart = self._parse_simai(content)
        note = parsed_chart["fumens_data"][0]["note_events"][0]["notes"][0]
        self.assertEqual(note["note_type"], "SLIDE")
        self.assertTrue(note["is_slide_break"])
        self.assertFalse(note["is_break"])  # Not a break on the star

    def test_simultaneous_notes_slash(self):
        content = """
&first=0
&inote_1=
(60)
1/8/Ch[4:1],
"""
        parsed_chart = self._parse_simai(content)
        notes_at_event = parsed_chart["fumens_data"][0]["note_events"][0]["notes"]
        self.assertEqual(len(notes_at_event), 3)

        self.assertEqual(notes_at_event[0]["note_type"], "TAP")
        self.assertEqual(notes_at_event[0]["start_position"], 1)
        self.assertEqual(notes_at_event[1]["note_type"], "TAP")
        self.assertEqual(notes_at_event[1]["start_position"], 8)
        self.assertEqual(notes_at_event[2]["note_type"], "TOUCH_HOLD")
        self.assertEqual(notes_at_event[2]["touch_area"], "C")
        self.assertAlmostEqual(notes_at_event[2]["hold_time"], 1.0)

    def test_pseudo_simultaneous_backtick(self):
        content = """
&first=1.0
&inote_1=
(60)
1`2h[4:1]`A3,
"""
        # Event 1: "1" at time 1.0
        # Event 2: "2h[4:1]" at time 1.0 + (60/60/32) = 1.0 + 0.03125
        # Event 3: "A3" at time 1.0 + 0.03125 + 0.03125
        parsed_chart = self._parse_simai(content)
        note_events = parsed_chart["fumens_data"][0]["note_events"]
        self.assertEqual(len(note_events), 3)

        time_interval_pseudo = (60.0 / 60.0 / 32.0)  # 0.03125

        note1_tp = note_events[0]
        self.assertAlmostEqual(note1_tp["time"], 1.0)
        self.assertEqual(note1_tp["notes"][0]["note_type"], "TAP")
        self.assertEqual(note1_tp["notes"][0]["start_position"], 1)

        note2_tp = note_events[1]
        self.assertAlmostEqual(note2_tp["time"], 1.0 + time_interval_pseudo)
        self.assertEqual(note2_tp["notes"][0]["note_type"], "HOLD")
        self.assertEqual(note2_tp["notes"][0]["start_position"], 2)
        self.assertAlmostEqual(note2_tp["notes"][0]["hold_time"], 1.0)  # 1 beat at 60 BPM

        note3_tp = note_events[2]
        self.assertAlmostEqual(note3_tp["time"], 1.0 + 2 * time_interval_pseudo)
        self.assertEqual(note3_tp["notes"][0]["note_type"], "TOUCH")
        self.assertEqual(note3_tp["notes"][0]["touch_area"], "A")
        self.assertEqual(note3_tp["notes"][0]["start_position"], 3)

    def test_comment_handling(self):
        content = """
&first=0
&inote_1=
(120) || BPM set
1, || Note 1
|| Standalone comment
2, || Note 2
"""
        parsed_chart = self._parse_simai(content)
        fumen_data = parsed_chart["fumens_data"][0]
        self.assertEqual(len(fumen_data["note_events"]), 2)
        self.assertAlmostEqual(fumen_data["note_events"][0]["notes"][0]["start_position"], 1)
        self.assertAlmostEqual(fumen_data["note_events"][1]["notes"][0]["start_position"], 2)
        self.assertAlmostEqual(fumen_data["note_events"][0]["time"], 0.0)
        self.assertAlmostEqual(fumen_data["note_events"][1]["time"], 0.5)  # 0.0 + 1 beat at 120 BPM

    def test_beat_signature_change(self):
        content = """
&first=0
&inote_1=
(60)
1, 
{8} || 8 beats per bar now
2, 
{2} || 2 beats per bar now
3,
"""
        # Event 1 ("1"): time 0.0. BPM 60, Beats 4. Increment = (60/60)*(4/4)=1.0
        # Event 2 ("2"): time 1.0. BPM 60, Beats 8. Increment = (60/60)*(4/8)=0.5
        # Event 3 ("3"): time 1.5. BPM 60, Beats 2. Increment = (60/60)*(4/2)=2.0
        parsed_chart = self._parse_simai(content)
        note_events = parsed_chart["fumens_data"][0]["note_events"]

        self.assertEqual(len(note_events), 3)
        self.assertAlmostEqual(note_events[0]["time"], 0.0)
        self.assertAlmostEqual(note_events[1]["time"], 1.0)
        self.assertAlmostEqual(note_events[2]["time"], 1.5)

    def test_hspeed_change(self):
        content = """
&first=0
&inote_1=
(60)
<H2.5>
1,
<HS*0.5>
2,
"""
        parsed_chart = self._parse_simai(content)
        note_events = parsed_chart["fumens_data"][0]["note_events"]

        self.assertEqual(len(note_events), 2)
        self.assertAlmostEqual(note_events[0]["hspeed_at_event"], 2.5)
        self.assertAlmostEqual(note_events[1]["hspeed_at_event"], 0.5)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

