from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SimaiNoteType(Enum):
    """Enumeration for different types of Simai notes."""
    TAP = 1
    SLIDE = 2
    HOLD = 3
    TOUCH = 4
    TOUCH_HOLD = 5


@dataclass
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
