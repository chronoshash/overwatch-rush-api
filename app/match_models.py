"""Pydantic models for the self-reported match log (v1 match API)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MatchResult = Literal["win", "loss", "draw"]
PLAYER_PATTERN = re.compile(r"^[\w][\w .#\-']{0,47}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MatchCreate(StrictModel):
    """A single match, as reported by the player themselves."""

    player: str = Field(min_length=1, max_length=48, examples=["Arena#1234"])
    hero: str = Field(min_length=1, max_length=48, examples=["tracer"])
    mode: str = Field(min_length=1, max_length=48, examples=["4v4-pvp"])
    map: str | None = Field(default=None, max_length=48, examples=["narwhal-cove"])
    result: MatchResult
    kills: int = Field(default=0, ge=0, le=500)
    deaths: int = Field(default=0, ge=0, le=500)
    assists: int = Field(default=0, ge=0, le=500)
    damage: int | None = Field(default=None, ge=0, le=1_000_000)
    healing: int | None = Field(default=None, ge=0, le=1_000_000)
    duration_seconds: int | None = Field(default=None, ge=0, le=10_800)
    played_at: datetime | None = Field(default=None, description="ISO 8601; defaults to now (UTC).")
    client_match_id: str | None = Field(
        default=None,
        max_length=64,
        description="Optional idempotency key. Repeating the same id returns the stored match.",
    )
    notes: str = Field(default="", max_length=500)

    @field_validator("player")
    @classmethod
    def _valid_player(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not PLAYER_PATTERN.match(cleaned):
            raise ValueError("player must be 1-48 chars: letters, digits, space, dot, #, -, '")
        return cleaned

    @field_validator("hero", "mode", "map")
    @classmethod
    def _slugish(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().replace(" ", "-").lower()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("played_at")
    @classmethod
    def _aware_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError(
                "played_at must include a timezone offset, e.g. 2026-10-17T18:30:00+02:00"
            )
        return value


class Match(StrictModel):
    id: int
    client_match_id: str | None
    player: str
    player_key: str = Field(exclude=True, description="Internal lookup key; never serialized.")
    hero: str
    mode: str
    map: str | None
    result: MatchResult
    kills: int
    deaths: int
    assists: int
    damage: int | None
    healing: int | None
    duration_seconds: int | None
    played_at: str
    notes: str
    created_at: str


class HeroBreakdown(StrictModel):
    hero: str
    matches: int
    wins: int
    win_rate: float | None
    kills: int
    deaths: int
    assists: int


class ModeBreakdown(StrictModel):
    mode: str
    matches: int
    wins: int
    win_rate: float | None


class PlayerStats(StrictModel):
    player: str
    matches: int
    wins: int
    losses: int
    draws: int
    win_rate: float | None
    kills: int
    deaths: int
    assists: int
    kda: float | None
    kills_per_match: float | None
    deaths_per_match: float | None
    avg_duration_seconds: float | None
    total_damage: int | None
    total_healing: int | None
    first_played_at: str | None
    last_played_at: str | None
    per_hero: list[HeroBreakdown]
    per_mode: list[ModeBreakdown]


class PlayerSummary(StrictModel):
    player: str
    player_key: str
    matches: int
    last_played_at: str | None
