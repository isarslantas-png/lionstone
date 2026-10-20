"""Core data model.

Lionstone separates *deciding* from *rendering*: every agent writes structured
decisions into an :class:`EditPlan`; the renderer only executes that plan.
Plans are plain JSON, so they can be diffed, reviewed, versioned and undone.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PLAN_VERSION = "1.0"


@dataclass
class StreamInfo:
    index: int
    kind: str  # "video" | "audio"
    codec: str
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    avg_fps: float | None = None
    sample_rate: int | None = None
    channels: int | None = None


@dataclass
class MediaInfo:
    path: str
    duration: float
    format_name: str
    streams: list[StreamInfo] = field(default_factory=list)
    timecode: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def video(self) -> StreamInfo | None:
        return next((s for s in self.streams if s.kind == "video"), None)

    @property
    def audio(self) -> StreamInfo | None:
        return next((s for s in self.streams if s.kind == "audio"), None)


@dataclass
class Word:
    text: str
    start: float
    end: float
    confidence: float = 1.0
    speaker: str | None = None


@dataclass
class Interval:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class Cut:
    """A region of the *source* timeline that will be removed."""

    id: str
    start: float
    end: float
    kind: str  # silence | filler | repeat | false_start | manual | transcript
    reason: str
    confidence: float = 1.0
    enabled: bool = True  # set False to restore ("undo") a cut

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class Segment:
    """A region of the source that is *kept*, in output order."""

    id: str
    start: float
    end: float
    source: str = "main"  # camera / source id (multicam plugins add more)
    text: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class GraphicEvent:
    """A title / lower third / chapter card placed on the *output* timeline."""

    id: str
    effect: str  # effect id, e.g. "F01"
    at: float  # output-timeline seconds
    duration: float
    text: str
    subtext: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    layer: str = "titles"  # titles | lower_thirds | captions (captions are separate)
    reason: str = ""


@dataclass
class EditPlan:
    source: str
    duration: float
    intensity: str
    segments: list[Segment] = field(default_factory=list)
    cuts: list[Cut] = field(default_factory=list)
    graphics: list[GraphicEvent] = field(default_factory=list)
    words: list[Word] = field(default_factory=list)
    audio_profile: str = "youtube"
    color: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    version: str = PLAN_VERSION

    # ---- derived -------------------------------------------------------
    @property
    def output_duration(self) -> float:
        return sum(s.duration for s in self.segments)

    def source_to_output(self, t: float) -> float | None:
        """Map a source timestamp to the output timeline (None if cut)."""
        acc = 0.0
        for s in self.segments:
            if s.start <= t <= s.end:
                return acc + (t - s.start)
            acc += s.duration
        return None

    # ---- io ------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EditPlan:
        return cls(
            source=d["source"],
            duration=d["duration"],
            intensity=d.get("intensity", "balanced"),
            segments=[Segment(**s) for s in d.get("segments", [])],
            cuts=[Cut(**c) for c in d.get("cuts", [])],
            graphics=[GraphicEvent(**g) for g in d.get("graphics", [])],
            words=[Word(**w) for w in d.get("words", [])],
            audio_profile=d.get("audio_profile", "youtube"),
            color=d.get("color", {}),
            meta=d.get("meta", {}),
            version=d.get("version", PLAN_VERSION),
        )

    @classmethod
    def load(cls, path: str | Path) -> EditPlan:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class QAIssue:
    check: str
    severity: str  # critical | high | medium | low
    message: str
    at: float | None = None  # output-timeline seconds
    auto_fixable: bool = False


@dataclass
class QACheck:
    name: str
    group: str  # technical | editorial
    status: str  # passed | failed | skipped | warning
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class QAReport:
    file: str
    checks: list[QACheck] = field(default_factory=list)
    issues: list[QAIssue] = field(default_factory=list)

    @property
    def deliverable(self) -> bool:
        return not any(i.severity == "critical" for i in self.issues)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["deliverable"] = self.deliverable
        return d
