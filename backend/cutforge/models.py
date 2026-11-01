from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Settings(StrictModel):
    threshold_db: float = Field(default=-35, ge=-90, le=-5)
    min_silence: float = Field(default=0.7, ge=0.1, le=30)
    padding: float = Field(default=0.15, ge=0, le=2)


class Metadata(StrictModel):
    duration_ticks: int = Field(gt=0)
    rate: str  # exact frames/second for video, samples/second for audio
    has_video: bool = False
    has_audio: bool = True
    video_codec: str | None = None
    audio_codec: str | None = None
    width: int | None = None
    height: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    channel_layout: str | None = None
    warnings: list[str] = Field(default_factory=list)


Decision = Literal["pending", "accepted", "rejected"]


class Cut(StrictModel):
    id: str
    start: int
    end: int
    current: bool = True
    decision: Decision = "pending"
    adjusted: bool = False


class CutState(StrictModel):
    decision: Decision
    start: int
    end: int
    adjusted: bool = False


class Project(StrictModel):
    schema_version: Literal[1, 2] = 2
    id: str
    name: str
    media_name: str
    media_size: int
    metadata: Metadata
    settings: Settings = Field(default_factory=Settings)
    cuts: list[Cut] = Field(default_factory=list)
    # Legacy decision-only snapshots remain readable without rewriting projects.
    history: list[dict[str, Decision | CutState]] = Field(default_factory=list)
    future: list[dict[str, Decision | CutState]] = Field(default_factory=list)
    revision: int = 0
    analyzed: bool = False


class ReviewRequest(StrictModel):
    revision: int = Field(ge=0)
    action: Literal["accept", "reject", "restore", "accept_all", "reject_all", "undo", "redo", "adjust"]
    cut_id: str | None = None
    start: int | None = Field(default=None, ge=0, strict=True)
    end: int | None = Field(default=None, ge=0, strict=True)


class AnalysisRequest(StrictModel):
    revision: int = Field(ge=0)
    settings: Settings
