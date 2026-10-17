"""Pydantic models for the Overwatch Rush dataset.

All models forbid extra keys on purpose: a typo in a data file must fail loudly
at startup instead of silently shipping wrong data.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Confidence = Literal["high", "medium", "low"]
OverwatchClass = Literal["tank", "damage", "support"]
HeroStatus = Literal["live", "upcoming"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_sources(value: list[str]) -> list[str]:
    if not value:
        raise ValueError("at least one source is required")
    for url in value:
        if not url.startswith("https://"):
            raise ValueError(f"source must be an https URL: {url!r}")
    return value


class SourcedModel(StrictModel):
    sources: list[str] = Field(min_length=1)
    verified_at: date

    _validate_sources = field_validator("sources")(_check_sources)


class Ability(StrictModel):
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: str = "ability"


class Hero(SourcedModel):
    slug: str = Field(min_length=1, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    subclass: str = Field(min_length=1)
    overwatch_class: OverwatchClass
    status: HeroStatus
    first_playable: date | None = None
    abilities: list[Ability] = Field(default_factory=list)
    notes: str = ""
    confidence: Confidence


class Subclass(SourcedModel):
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    playstyle: str = Field(min_length=1)


class Mode(SourcedModel):
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    team_size: int | None = Field(default=None, ge=1)
    teams: int | None = Field(default=None, ge=2)
    objective: str = Field(min_length=1)
    description: str = Field(min_length=1)
    confidence: Confidence


class MapFeature(SourcedModel):
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    inspired_by: str | None = None
    built_from_scratch: bool
    setting: str | None = None
    confidence: Confidence


class SoftLaunch(StrictModel):
    started: date
    regions: list[str] = Field(min_length=1)
    platforms: list[str] = Field(min_length=1)


class MinRequirements(StrictModel):
    android_ram_gb: float = Field(gt=0)
    android_min_device: str
    android_chipsets: list[str] = Field(min_length=1)
    ios_min_device: str
    ios_min_chip: str


class GameMeta(StrictModel):
    name: str
    package_id: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
    developer: str
    publisher: str
    genre: str
    perspective: str
    price_model: str
    platforms: list[str] = Field(min_length=1)
    release_stage: str
    soft_launch: SoftLaunch
    match_formats: list[str] = Field(min_length=1)
    controller_support: bool
    party_support: bool
    party_support_note: str
    approximate_download_gb: float = Field(gt=0)
    min_requirements: MinRequirements
    progression: str
    global_release_date: date | None = None
    global_release_note: str
    data_version: str = Field(min_length=1)
    updated_at: date
    disclaimer: str
    sources: list[str] = Field(min_length=1)

    _validate_sources = field_validator("sources")(_check_sources)


class Dataset(StrictModel):
    game: GameMeta
    heroes: list[Hero]
    roles: list[Subclass]
    modes: list[Mode]
    maps: list[MapFeature]

    def role_slugs(self) -> set[str]:
        return {role.slug for role in self.roles}

    def validate_references(self) -> None:
        """Cross-collection integrity checks that pydantic cannot express."""
        for name, items in (
            ("heroes", self.heroes),
            ("roles", self.roles),
            ("modes", self.modes),
            ("maps", self.maps),
        ):
            slugs = [item.slug for item in items]  # type: ignore[attr-defined]
            if len(slugs) != len(set(slugs)):
                raise ValueError(f"duplicate slug in {name}: {slugs}")

        roles = self.role_slugs()
        for hero in self.heroes:
            if hero.subclass not in roles:
                raise ValueError(
                    f"hero {hero.slug!r} references unknown subclass {hero.subclass!r}"
                )
