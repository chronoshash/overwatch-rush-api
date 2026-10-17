"""Match-log routes: write your own results, read your own aggregates.

Everything here is *self-reported* data. Nothing is scraped from Blizzard and
nothing about other players is asserted; the API only stores what the caller
sends for a player name they choose.
"""

from __future__ import annotations

import os
import secrets
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, Query, Response
from pydantic import BaseModel, ConfigDict

from app import db
from app.match_models import Match, MatchCreate, PlayerStats, PlayerSummary
from app.store import get_dataset

router = APIRouter(prefix="/v1", tags=["player stats"])

WRITE_TOKEN_ENV = "OWR_WRITE_TOKEN"


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_version: str
    updated_at: date
    total: int | None = None
    limit: int | None = None
    offset: int | None = None
    returned: int | None = None
    replayed: bool | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: Any | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class MatchEnvelope(BaseModel):
    data: Match
    meta: Meta


class MatchListEnvelope(BaseModel):
    data: list[Match]
    meta: Meta


class PlayerListEnvelope(BaseModel):
    data: list[PlayerSummary]
    meta: Meta


class PlayerStatsEnvelope(BaseModel):
    data: PlayerStats
    meta: Meta


def _meta(**extra: Any) -> Meta:
    dataset = get_dataset()
    return Meta(
        data_version=dataset.game.data_version,
        updated_at=dataset.game.updated_at,
        **extra,
    )


def _fail(status_code: int, code: str, message: str, detail: Any | None = None) -> None:
    from fastapi import HTTPException

    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "detail": detail},
    )


def _check_write_access(authorization: str | None) -> None:
    """Optional bearer protection for writes.

    Enabled only when OWR_WRITE_TOKEN is set, so local/preview use stays
    frictionless while a deployed instance can be locked down.
    """
    expected = os.environ.get(WRITE_TOKEN_ENV)
    if not expected:
        return
    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not secrets.compare_digest(supplied, expected):
        _fail(
            401,
            "unauthorized",
            "Write access requires a bearer token.",
            {"header": "Authorization: Bearer <OWR_WRITE_TOKEN>"},
        )


def _validate_references(payload: MatchCreate) -> None:
    dataset = get_dataset()
    heroes = {hero.slug: hero for hero in dataset.heroes}
    modes = {mode.slug for mode in dataset.modes}
    maps = {item.slug for item in dataset.maps}

    hero = heroes.get(payload.hero)
    if hero is None:
        _fail(
            422,
            "unknown_hero",
            f"Unknown hero {payload.hero!r}.",
            {"valid": sorted(heroes)},
        )
    if hero is not None and hero.status == "upcoming":
        _fail(
            422,
            "hero_not_playable",
            f"Hero {payload.hero!r} is announced but not playable yet.",
            {
                "status": hero.status,
                "live": sorted(h.slug for h in dataset.heroes if h.status == "live"),
            },
        )
    if payload.mode not in modes:
        _fail(422, "unknown_mode", f"Unknown mode {payload.mode!r}.", {"valid": sorted(modes)})
    if payload.map is not None and payload.map not in maps:
        _fail(422, "unknown_map", f"Unknown map {payload.map!r}.", {"valid": sorted(maps)})


@router.post(
    "/matches",
    response_model=MatchEnvelope,
    status_code=201,
    responses={
        200: {"description": "Idempotent replay of an existing client_match_id"},
        401: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
    },
    summary="Log one match (self-reported)",
)
def create_match(
    payload: MatchCreate,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
) -> MatchEnvelope:
    _check_write_access(authorization)
    _validate_references(payload)

    row, replayed = db.insert_match(payload.model_dump())
    if replayed:
        response.status_code = 200
        response.headers["X-Idempotent-Replay"] = "true"
    return MatchEnvelope(data=Match(**row), meta=_meta(replayed=replayed))


@router.get(
    "/matches",
    response_model=MatchListEnvelope,
    responses={304: {"description": "Not modified"}},
    summary="List logged matches",
)
def list_matches(
    player: Annotated[str | None, Query(max_length=48)] = None,
    hero: Annotated[str | None, Query(max_length=48)] = None,
    mode: Annotated[str | None, Query(max_length=48)] = None,
    result: Annotated[str | None, Query(pattern="^(win|loss|draw)$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MatchListEnvelope:
    rows, total = db.list_matches(
        player=player, hero=hero, mode=mode, result=result, limit=limit, offset=offset
    )
    return MatchListEnvelope(
        data=[Match(**row) for row in rows],
        meta=_meta(total=total, limit=limit, offset=offset, returned=len(rows)),
    )


@router.get(
    "/matches/{match_id}",
    response_model=MatchEnvelope,
    responses={404: {"model": ErrorEnvelope}},
    summary="Fetch one match",
)
def read_match(match_id: int = Path(ge=1)) -> MatchEnvelope:
    row = db.get_match(match_id)
    if row is None:
        _fail(404, "match_not_found", f"No match with id {match_id}.", None)
    return MatchEnvelope(data=Match(**row), meta=_meta())


@router.delete(
    "/matches/{match_id}",
    status_code=204,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
    summary="Delete one match",
)
def remove_match(
    match_id: int = Path(ge=1),
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    _check_write_access(authorization)
    if not db.delete_match(match_id):
        _fail(404, "match_not_found", f"No match with id {match_id}.", None)
    return Response(status_code=204)


@router.get(
    "/players",
    response_model=PlayerListEnvelope,
    responses={304: {"description": "Not modified"}},
    summary="List players that have logged matches",
)
def list_players() -> PlayerListEnvelope:
    rows = db.list_players()
    return PlayerListEnvelope(
        data=[PlayerSummary(**row) for row in rows],
        meta=_meta(total=len(rows), returned=len(rows)),
    )


@router.get(
    "/players/{player}/stats",
    response_model=PlayerStatsEnvelope,
    responses={
        304: {"description": "Not modified"},
        404: {"model": ErrorEnvelope},
    },
    summary="Aggregated stats for one player",
)
def player_stats(
    player: str = Path(min_length=1, max_length=48, description="Player name, case-insensitive."),
) -> PlayerStatsEnvelope:
    stats = db.player_stats(player)
    if stats is None:
        _fail(
            404,
            "player_not_found",
            f"No matches logged for {player!r}.",
            {"hint": "POST /v1/matches first."},
        )
    return PlayerStatsEnvelope(data=PlayerStats(**stats), meta=_meta())
