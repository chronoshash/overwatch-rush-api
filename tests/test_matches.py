from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

BASE = {
    "player": "Arena#1234",
    "hero": "tracer",
    "mode": "4v4-pvp",
    "map": "narwhal-cove",
    "result": "win",
    "kills": 12,
    "deaths": 4,
    "assists": 3,
    "duration_seconds": 280,
}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "test.sqlite3"))
    db.init_db()
    with TestClient(app) as test_client:
        yield test_client


def test_create_and_read_match(client: TestClient) -> None:
    created = client.post("/v1/matches", json=BASE)
    assert created.status_code == 201
    body = created.json()["data"]
    assert body["player"] == "Arena#1234"
    assert body["hero"] == "tracer"
    assert body["result"] == "win"

    fetched = client.get(f"/v1/matches/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["kills"] == 12


def test_player_name_is_normalized(client: TestClient) -> None:
    client.post("/v1/matches", json={**BASE, "player": "  arena#1234  "})
    stats = client.get("/v1/players/Arena%231234/stats")
    assert stats.status_code == 200
    assert stats.json()["data"]["matches"] == 1


def test_unknown_hero_is_rejected(client: TestClient) -> None:
    response = client.post("/v1/matches", json={**BASE, "hero": "winston"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_hero"


def test_upcoming_hero_cannot_be_logged(client: TestClient) -> None:
    response = client.post("/v1/matches", json={**BASE, "hero": "genji"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "hero_not_playable"


def test_unknown_map_and_mode(client: TestClient) -> None:
    assert client.post("/v1/matches", json={**BASE, "map": "ilios"}).json()["error"]["code"] == (
        "unknown_map"
    )
    assert client.post("/v1/matches", json={**BASE, "mode": "5v5"}).json()["error"]["code"] == (
        "unknown_mode"
    )


def test_negative_stats_are_rejected(client: TestClient) -> None:
    response = client.post("/v1/matches", json={**BASE, "kills": -1})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_naive_datetime_is_rejected(client: TestClient) -> None:
    response = client.post("/v1/matches", json={**BASE, "played_at": "2026-10-17T18:00:00"})
    assert response.status_code == 422


def test_idempotent_client_match_id(client: TestClient) -> None:
    payload = {**BASE, "client_match_id": "abc-1"}
    first = client.post("/v1/matches", json=payload)
    second = client.post("/v1/matches", json=payload)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.headers["x-idempotent-replay"] == "true"
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    assert client.get("/v1/matches").json()["meta"]["total"] == 1


def test_filters_and_pagination(client: TestClient) -> None:
    client.post("/v1/matches", json=BASE)
    client.post("/v1/matches", json={**BASE, "hero": "mercy", "result": "loss", "kills": 0})
    client.post("/v1/matches", json={**BASE, "hero": "reinhardt", "mode": "3v3-control"})

    assert client.get("/v1/matches?result=loss").json()["meta"]["total"] == 1
    assert client.get("/v1/matches?hero=mercy").json()["data"][0]["hero"] == "mercy"
    assert client.get("/v1/matches?mode=3v3-control").json()["meta"]["total"] == 1
    assert client.get("/v1/matches?limit=2").json()["meta"]["returned"] == 2
    assert client.get("/v1/matches?offset=2").json()["meta"]["returned"] == 1


def test_aggregated_stats(client: TestClient) -> None:
    client.post("/v1/matches", json={**BASE, "result": "win", "kills": 10, "deaths": 2})
    client.post("/v1/matches", json={**BASE, "result": "win", "kills": 6, "deaths": 2})
    client.post(
        "/v1/matches",
        json={**BASE, "result": "loss", "hero": "mercy", "kills": 2, "deaths": 6, "healing": 4000},
    )

    data = client.get("/v1/players/Arena%231234/stats").json()["data"]
    assert data["matches"] == 3
    assert data["wins"] == 2
    assert data["losses"] == 1
    assert data["win_rate"] == pytest.approx(0.6667, abs=1e-4)
    assert data["kills"] == 18
    assert data["deaths"] == 10
    assert data["assists"] == 9
    assert data["kda"] == pytest.approx(2.7)
    assert data["total_healing"] == 4000

    heroes = {row["hero"]: row for row in data["per_hero"]}
    assert heroes["tracer"]["matches"] == 2
    assert heroes["tracer"]["win_rate"] == 1.0
    assert heroes["mercy"]["win_rate"] == 0.0
    assert data["per_mode"][0]["mode"] == "4v4-pvp"


def test_unknown_player_returns_404(client: TestClient) -> None:
    response = client.get("/v1/players/nobody%239999/stats")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "player_not_found"


def test_players_list(client: TestClient) -> None:
    client.post("/v1/matches", json=BASE)
    client.post("/v1/matches", json={**BASE, "player": "Second#1"})
    rows = client.get("/v1/players").json()["data"]
    assert {row["player"] for row in rows} == {"Arena#1234", "Second#1"}


def test_delete_match(client: TestClient) -> None:
    match_id = client.post("/v1/matches", json=BASE).json()["data"]["id"]
    assert client.delete(f"/v1/matches/{match_id}").status_code == 204
    assert client.get(f"/v1/matches/{match_id}").status_code == 404
    assert client.delete(f"/v1/matches/{match_id}").status_code == 404


def test_write_token_protects_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(db.DB_PATH_ENV, str(tmp_path / "tok.sqlite3"))
    monkeypatch.setenv("OWR_WRITE_TOKEN", "s3cret")
    db.init_db()
    with TestClient(app) as test_client:
        assert test_client.post("/v1/matches", json=BASE).status_code == 401
        ok = test_client.post("/v1/matches", json=BASE, headers={"Authorization": "Bearer s3cret"})
        assert ok.status_code == 201
        assert test_client.get("/v1/matches").status_code == 200  # reads stay open


def test_etag_changes_after_write(client: TestClient) -> None:
    first = client.get("/v1/matches")
    etag_before = first.headers["etag"]

    client.post("/v1/matches", json=BASE)

    second = client.get("/v1/matches")
    assert second.headers["etag"] != etag_before
    revalidated = client.get("/v1/matches", headers={"If-None-Match": etag_before})
    assert revalidated.status_code == 200
    assert revalidated.json()["meta"]["total"] == 1
