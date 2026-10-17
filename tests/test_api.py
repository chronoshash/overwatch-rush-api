from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["counts"] == {"heroes": 12, "roles": 5, "modes": 4, "maps": 3}


def test_meta_exposes_sources_and_disclaimer(client: TestClient) -> None:
    response = client.get("/v1/meta")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["package_id"] == "com.blizzard.overwatch.rush"
    assert data["soft_launch"]["regions"] == ["ID", "MY", "PH"]
    assert data["sources"]
    assert "keine Spieldateien" in data["disclaimer"]
    assert "APK" not in data["disclaimer"]


def test_heroes_default_order_and_count(client: TestClient) -> None:
    response = client.get("/v1/heroes")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 12
    statuses = [hero["status"] for hero in body["data"]]
    assert statuses == sorted(statuses)  # "live" sorts before "upcoming"


def test_hero_filter_by_subclass(client: TestClient) -> None:
    response = client.get("/v1/heroes", params={"subclass": "vanguard"})
    assert response.status_code == 200
    slugs = [hero["slug"] for hero in response.json()["data"]]
    assert slugs == ["brigitte", "reinhardt"]


def test_hero_filter_by_status(client: TestClient) -> None:
    response = client.get("/v1/heroes", params={"status": "upcoming"})
    assert response.status_code == 200
    slugs = [hero["slug"] for hero in response.json()["data"]]
    assert slugs == ["doomfist", "genji", "hanzo"]


def test_unknown_subclass_is_a_400_with_valid_options(client: TestClient) -> None:
    response = client.get("/v1/heroes", params={"subclass": "tank"})
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "unknown_subclass"
    assert "vanguard" in error["detail"]["valid"]


def test_hero_by_slug_and_alias(client: TestClient) -> None:
    canonical = client.get("/v1/heroes/soldier-76")
    assert canonical.status_code == 200
    assert canonical.json()["data"]["name"] == "Soldier: 76"

    alias = client.get("/v1/heroes/s76")
    assert alias.status_code == 200
    assert alias.json()["data"]["slug"] == "soldier-76"


def test_hero_404_envelope(client: TestClient) -> None:
    response = client.get("/v1/heroes/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "hero_not_found"
    assert "tracer" in error["detail"]["available"]


def test_pagination(client: TestClient) -> None:
    response = client.get("/v1/heroes", params={"limit": 3, "offset": 9})
    body = response.json()
    assert body["meta"] == {
        **body["meta"],
        "total": 12,
        "limit": 3,
        "offset": 9,
        "returned": 3,
    }
    assert len(body["data"]) == 3


def test_pagination_validation(client: TestClient) -> None:
    response = client.get("/v1/heroes", params={"limit": 0})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_roles_modes_maps(client: TestClient) -> None:
    assert len(client.get("/v1/roles").json()["data"]) == 5
    modes = client.get("/v1/modes").json()["data"]
    assert {mode["slug"] for mode in modes} == {
        "3v3-control",
        "4v4-pvp",
        "duo-free-for-all",
        "solo-free-for-all",
    }
    maps = client.get("/v1/maps").json()["data"]
    assert {item["slug"] for item in maps} == {
        "hydronet-gardens",
        "mansion-portero",
        "narwhal-cove",
    }


def test_search_across_collections(client: TestClient) -> None:
    body = client.get("/v1/search", params={"q": "dora"}).json()
    assert [item["slug"] for item in body["data"]["maps"]] == ["mansion-portero"]

    body = client.get("/v1/search", params={"q": "brig"}).json()
    assert body["data"]["heroes"][0]["slug"] == "brigitte"


def test_search_rejects_blank_query(client: TestClient) -> None:
    response = client.get("/v1/search", params={"q": "   "})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_query"


def test_etag_revalidation(client: TestClient) -> None:
    first = client.get("/v1/heroes")
    etag = first.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')
    assert first.headers["cache-control"] == "public, max-age=60"

    second = client.get("/v1/heroes")
    assert second.headers["etag"] == etag

    revalidated = client.get("/v1/heroes", headers={"If-None-Match": etag})
    assert revalidated.status_code == 304
    assert revalidated.content == b""


def test_etag_differs_per_resource(client: TestClient) -> None:
    heroes = client.get("/v1/heroes").headers["etag"]
    roles = client.get("/v1/roles").headers["etag"]
    assert heroes != roles


def test_cors_is_open_for_reads(client: TestClient) -> None:
    response = client.get("/v1/heroes", headers={"Origin": "https://example.com"})
    assert response.headers["access-control-allow-origin"] == "*"


def test_openapi_schema_is_served(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "Overwatch Rush API"
    assert "/v1/heroes/{slug}" in schema["paths"]
