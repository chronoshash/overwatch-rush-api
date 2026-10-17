"""FastAPI application exposing verified Overwatch Rush reference data."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict

from app.cache import make_etag
from app.models import GameMeta, Hero, MapFeature, Mode, Subclass
from app.store import get_dataset

APP_VERSION = "0.1.0"
CACHE_CONTROL = "public, max-age=60"

app = FastAPI(
    title="Overwatch Rush API",
    version=APP_VERSION,
    summary="Community-Datenset zu Overwatch Rush (Blizzard) – quellenbasiert, ohne Spieldateien.",
    description=(
        "Read-only API mit verifizierten Stammdaten zu Overwatch Rush.\n\n"
        "Jeder Datensatz nennt seine Quellen. Es werden **keine** APK/XAPK-Dateien "
        "verteilt. Felder ohne belastbare Quelle bleiben leer statt geraten zu werden."
    ),
    license_info={"name": "MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Response envelopes
# --------------------------------------------------------------------------- #
class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_version: str
    updated_at: date
    total: int | None = None
    limit: int | None = None
    offset: int | None = None
    returned: int | None = None


class GameEnvelope(BaseModel):
    data: GameMeta
    meta: ResponseMeta


class HeroEnvelope(BaseModel):
    data: Hero
    meta: ResponseMeta


class HeroListEnvelope(BaseModel):
    data: list[Hero]
    meta: ResponseMeta


class RoleListEnvelope(BaseModel):
    data: list[Subclass]
    meta: ResponseMeta


class ModeListEnvelope(BaseModel):
    data: list[Mode]
    meta: ResponseMeta


class MapListEnvelope(BaseModel):
    data: list[MapFeature]
    meta: ResponseMeta


class SearchResults(BaseModel):
    heroes: list[Hero]
    modes: list[Mode]
    maps: list[MapFeature]


class SearchEnvelope(BaseModel):
    data: SearchResults
    meta: ResponseMeta


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app_version: str
    data_version: str
    updated_at: date
    counts: dict[str, int]


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: Any | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def base_meta(extra: dict[str, Any] | None = None) -> ResponseMeta:
    dataset = get_dataset()
    payload: dict[str, Any] = {
        "data_version": dataset.game.data_version,
        "updated_at": dataset.game.updated_at,
    }
    if extra:
        payload.update(extra)
    return ResponseMeta(**payload)


def fail(status_code: int, code: str, message: str, detail: Any | None = None) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "detail": detail},
    )


def sort_heroes(heroes: list[Hero]) -> list[Hero]:
    return sorted(heroes, key=lambda h: (0 if h.status == "live" else 1, h.name.casefold()))


def matches(query: str, *values: str) -> bool:
    needle = query.casefold()
    return any(needle in value.casefold() for value in values if value)


# --------------------------------------------------------------------------- #
# Middleware: caching headers for immutable dataset reads
# --------------------------------------------------------------------------- #
@app.middleware("http")
async def cache_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    is_json = response.headers.get("content-type", "").startswith("application/json")
    if request.method == "GET" and response.status_code == 200 and is_json:
        dataset = get_dataset()
        etag = make_etag(
            dataset.game.data_version,
            dataset.game.updated_at.isoformat(),
            request.url.path,
            list(request.query_params.multi_items()),
        )
        response.headers["etag"] = etag
        response.headers["cache-control"] = CACHE_CONTROL
        if request.headers.get("if-none-match") == etag:
            return Response(
                status_code=304,
                headers={"etag": etag, "cache-control": CACHE_CONTROL},
            )
    return response


# --------------------------------------------------------------------------- #
# Error handling
# --------------------------------------------------------------------------- #
@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        body = ErrorBody(
            code=detail.get("code", "error"),
            message=detail.get("message", ""),
            detail=detail.get("detail"),
        )
    else:
        body = ErrorBody(code="error", message=str(detail), detail=None)
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(ErrorEnvelope(error=body)),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    body = ErrorBody(
        code="invalid_request",
        message="Request validation failed.",
        detail=jsonable_encoder(exc.errors()),
    )
    return JSONResponse(status_code=422, content=jsonable_encoder(ErrorEnvelope(error=body)))


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
def root() -> HTMLResponse:
    dataset = get_dataset()
    live = sum(1 for hero in dataset.heroes if hero.status == "live")
    upcoming = len(dataset.heroes) - live
    cards = "".join(
        f'<a class="card" href="{href}"><strong>{label}</strong><span>{desc}</span></a>'
        for href, label, desc in (
            ("/docs", "OpenAPI-Dokumentation", "Interaktiv alle Endpunkte testen"),
            ("/v1/heroes", "Helden", f"{live} spielbar, {upcoming} angekündigt"),
            ("/v1/modes", "Spielmodi", f"{len(dataset.modes)} Formate"),
            ("/v1/maps", "Maps", f"{len(dataset.maps)} Arenen"),
            ("/v1/roles", "Subklassen", f"{len(dataset.roles)} Rollen"),
            ("/v1/meta", "Spiel-Metadaten", "Soft Launch, Anforderungen, Quellen"),
            ("/health", "Health", "Status und Datenversion"),
        )
    )
    html = f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Overwatch Rush API</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; min-height: 100vh; display: grid; place-items: center;
         font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
         background: radial-gradient(1200px 600px at 20% -10%, #1f3a5f 0%, #0b1220 55%, #070b12 100%);
         color: #e6edf7; padding: 32px 20px; }}
  main {{ width: min(860px, 100%); }}
  .badge {{ display: inline-block; font-size: 12px; letter-spacing: .14em; text-transform: uppercase;
            color: #8fd3ff; border: 1px solid #2b4a6b; border-radius: 999px; padding: 4px 12px; }}
  h1 {{ font-size: clamp(28px, 5vw, 44px); margin: 16px 0 8px; }}
  p.lead {{ color: #9fb0c6; margin: 0 0 28px; max-width: 62ch; line-height: 1.6; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
  .card {{ display: flex; flex-direction: column; gap: 4px; padding: 16px 18px; text-decoration: none;
           color: inherit; background: rgba(255,255,255,.04); border: 1px solid #22314a;
           border-radius: 14px; transition: .15s border-color, .15s transform; }}
  .card:hover {{ border-color: #3d6ea0; transform: translateY(-2px); }}
  .card strong {{ font-size: 15px; }}
  .card span {{ font-size: 13px; color: #8fa1b8; }}
  footer {{ margin-top: 28px; font-size: 12px; color: #6f819a; line-height: 1.6; }}
  code {{ background: rgba(255,255,255,.06); padding: 1px 6px; border-radius: 6px; }}
</style>
</head>
<body>
<main>
  <span class="badge">v{APP_VERSION} · data {dataset.game.data_version}</span>
  <h1>Overwatch Rush API</h1>
  <p class="lead">Quellenbasierte Stammdaten zu Overwatch Rush. Read-only, kein Login.
     Dieses Projekt verteilt keine Spieldateien.</p>
  <div class="grid">{cards}</div>
  <footer>
    Kurztest: <code>curl {"/v1/heroes?subclass=vanguard"}</code> ·
    Fehler kommen als <code>{{"error": {{"code": ...}}}}</code> ·
    Jede JSON-Antwort trägt <code>ETag</code>.
  </footer>
</main>
</body>
</html>"""
    return HTMLResponse(html)


@app.get("/v1", include_in_schema=False)
def api_index() -> dict[str, Any]:
    return {
        "service": "overwatch-rush-api",
        "version": APP_VERSION,
        "docs": "/docs",
        "endpoints": [
            "/health",
            "/v1/meta",
            "/v1/heroes",
            "/v1/heroes/{slug}",
            "/v1/roles",
            "/v1/modes",
            "/v1/maps",
            "/v1/search?q=",
        ],
        "notice": "Read-only. No game binaries are distributed by this service.",
    }


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    dataset = get_dataset()
    return HealthResponse(
        status="ok",
        app_version=APP_VERSION,
        data_version=dataset.game.data_version,
        updated_at=dataset.game.updated_at,
        counts={
            "heroes": len(dataset.heroes),
            "roles": len(dataset.roles),
            "modes": len(dataset.modes),
            "maps": len(dataset.maps),
        },
    )


@app.get(
    "/v1/meta",
    response_model=GameEnvelope,
    tags=["game"],
    responses={304: {"description": "Not modified"}},
)
def get_meta() -> GameEnvelope:
    dataset = get_dataset()
    return GameEnvelope(data=dataset.game, meta=base_meta())


@app.get(
    "/v1/heroes",
    response_model=HeroListEnvelope,
    tags=["heroes"],
    responses={304: {"description": "Not modified"}},
)
def list_heroes(
    subclass: Annotated[
        str | None, Query(description="Filter by Rush subclass slug, e.g. `vanguard`.")
    ] = None,
    status: Annotated[
        Literal["live", "upcoming"] | None, Query(description="Filter by availability.")
    ] = None,
    q: Annotated[
        str | None, Query(description="Free-text match on name, slug and aliases.")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HeroListEnvelope:
    dataset = get_dataset()
    heroes = dataset.heroes

    if subclass is not None:
        valid = sorted(dataset.role_slugs())
        if subclass not in valid:
            fail(
                400,
                "unknown_subclass",
                f"Unknown subclass {subclass!r}.",
                {"valid": valid},
            )
        heroes = [hero for hero in heroes if hero.subclass == subclass]

    if status is not None:
        heroes = [hero for hero in heroes if hero.status == status]

    if q is not None:
        heroes = [
            hero for hero in heroes if matches(q, hero.name, hero.slug, hero.notes, *hero.aliases)
        ]

    ordered = sort_heroes(heroes)
    total = len(ordered)
    page = ordered[offset : offset + limit]
    return HeroListEnvelope(
        data=page,
        meta=base_meta({"total": total, "limit": limit, "offset": offset, "returned": len(page)}),
    )


@app.get(
    "/v1/heroes/{slug}",
    response_model=HeroEnvelope,
    tags=["heroes"],
    responses={
        304: {"description": "Not modified"},
        404: {"model": ErrorEnvelope, "description": "Unknown hero"},
    },
)
def get_hero(
    slug: str = Path(description="Hero slug or alias, e.g. `soldier-76`."),
) -> HeroEnvelope:
    dataset = get_dataset()
    needle = slug.casefold()
    for hero in dataset.heroes:
        if hero.slug == needle or needle in {alias.casefold() for alias in hero.aliases}:
            return HeroEnvelope(data=hero, meta=base_meta())
    fail(
        404,
        "hero_not_found",
        f"No hero matches {slug!r}.",
        {"available": [hero.slug for hero in sort_heroes(dataset.heroes)]},
    )
    raise AssertionError("unreachable")  # pragma: no cover


@app.get(
    "/v1/roles",
    response_model=RoleListEnvelope,
    tags=["game"],
    responses={304: {"description": "Not modified"}},
)
def list_roles() -> RoleListEnvelope:
    dataset = get_dataset()
    roles = sorted(dataset.roles, key=lambda role: role.name.casefold())
    return RoleListEnvelope(
        data=roles,
        meta=base_meta({"total": len(roles), "returned": len(roles)}),
    )


@app.get(
    "/v1/modes",
    response_model=ModeListEnvelope,
    tags=["game"],
    responses={304: {"description": "Not modified"}},
)
def list_modes() -> ModeListEnvelope:
    dataset = get_dataset()
    modes = sorted(dataset.modes, key=lambda mode: mode.name.casefold())
    return ModeListEnvelope(
        data=modes,
        meta=base_meta({"total": len(modes), "returned": len(modes)}),
    )


@app.get(
    "/v1/maps",
    response_model=MapListEnvelope,
    tags=["game"],
    responses={304: {"description": "Not modified"}},
)
def list_maps() -> MapListEnvelope:
    dataset = get_dataset()
    maps = sorted(dataset.maps, key=lambda item: item.name.casefold())
    return MapListEnvelope(
        data=maps,
        meta=base_meta({"total": len(maps), "returned": len(maps)}),
    )


@app.get(
    "/v1/search",
    response_model=SearchEnvelope,
    tags=["search"],
    responses={
        304: {"description": "Not modified"},
        400: {"model": ErrorEnvelope, "description": "Empty query"},
    },
)
def search(
    q: Annotated[str, Query(min_length=1, description="Search term, at least one character.")],
) -> SearchEnvelope:
    if not q.strip():
        fail(400, "empty_query", "Query parameter `q` must not be blank.")

    dataset = get_dataset()
    heroes = [hero for hero in dataset.heroes if matches(q, hero.name, hero.slug, *hero.aliases)]
    modes = [mode for mode in dataset.modes if matches(q, mode.name, mode.slug, mode.description)]
    maps = [
        item
        for item in dataset.maps
        if matches(q, item.name, item.slug, item.inspired_by or "", item.setting or "")
    ]

    results = SearchResults(
        heroes=sort_heroes(heroes),
        modes=sorted(modes, key=lambda mode: mode.name.casefold()),
        maps=sorted(maps, key=lambda item: item.name.casefold()),
    )
    total = len(results.heroes) + len(results.modes) + len(results.maps)
    return SearchEnvelope(data=results, meta=base_meta({"total": total, "returned": total}))


@app.get("/v1/version", tags=["system"], include_in_schema=True)
def version() -> dict[str, Any]:
    dataset = get_dataset()
    return {
        "app_version": APP_VERSION,
        "data_version": dataset.game.data_version,
        "data_updated_at": dataset.game.updated_at,
        "license": "MIT",
    }
