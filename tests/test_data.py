from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.store import load_dataset

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_SUFFIXES = {".apk", ".xapk", ".apks", ".aab", ".obb"}
SKIP_DIRS = {".git", ".venv", "tmp", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}


@pytest.fixture(scope="module")
def dataset():
    return load_dataset()


def test_dataset_loads_and_validates(dataset) -> None:
    assert dataset.game.package_id == "com.blizzard.overwatch.rush"
    assert len(dataset.heroes) == 12


def test_every_hero_has_https_source_and_known_subclass(dataset) -> None:
    role_slugs = dataset.role_slugs()
    for hero in dataset.heroes:
        assert hero.sources, hero.slug
        assert all(url.startswith("https://") for url in hero.sources), hero.slug
        assert hero.subclass in role_slugs, hero.slug


def test_live_and_upcoming_split(dataset) -> None:
    live = [hero for hero in dataset.heroes if hero.status == "live"]
    upcoming = [hero for hero in dataset.heroes if hero.status == "upcoming"]
    assert len(live) == 9
    assert len(upcoming) == 3
    assert {hero.slug for hero in upcoming} == {"doomfist", "genji", "hanzo"}


def test_only_sourced_abilities_are_present(dataset) -> None:
    with_abilities = {hero.slug: hero.abilities for hero in dataset.heroes if hero.abilities}
    assert set(with_abilities) == {"brigitte"}
    assert {ability.name for ability in with_abilities["brigitte"]} == {
        "Shield Bash",
        "Whip Shot",
    }


def test_data_version_is_a_date(dataset) -> None:
    assert re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", dataset.game.data_version)
    assert dataset.game.data_version == dataset.game.updated_at.strftime("%Y.%m.%d")


def test_no_game_binaries_are_tracked() -> None:
    offenders = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"game binaries must never be committed: {offenders}"
