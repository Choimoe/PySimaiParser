from dataclasses import dataclass
from typing import Optional

@dataclass
class SimaiNote:
    note_type: str
    note_id: int
    timing: float
    position: Optional[str] = None
    slide_to: Optional[str] = None
    slide_duration: Optional[float] = None
    is_break: bool = False
    is_star: bool = False
    star_pitch: Optional[float] = None
    highlight: bool = False
    delay: float = 0.0
    judgement: bool = False 