import os
import sys
import pytest
from unittest.mock import patch, MagicMock

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(THIS_DIR)
sys.path.insert(0, THIS_DIR)


@pytest.fixture
def app_mod(monkeypatch):
    monkeypatch.chdir(PARENT)
    import app as app_module
    app_module.ASSETS.clear()
    app_module.PLATFORMS.clear()
    app_module.DELIVERY_JOBS.clear()
    app_module.load_seed_data()
    return app_module


@pytest.fixture
def client(app_mod):
    app_mod.app.config["TESTING"] = True
    with app_mod.app.test_client() as c:
        yield c


def valid_asset_payload(**overrides):
    payload = {
        "title": "New Show - S01E01",
        "format": "MOV",
        "codec": "H264",
        "resolution": "4K",
        "duration_sec": 1800,
        "file_size_gb": 12.5,
        "territory": "US",
        "languages": ["en"],
        "has_captions": False,
    }
    payload.update(overrides)
    return payload


def test_app_starts_and_loads_seed_data(app_mod):
    assert len(app_mod.ASSETS) == 12
    assert len(app_mod.PLATFORMS) == 5


def test_get_assets_returns_all_12(client):
    resp = client.get("/api/assets")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 12
    assert len(data["assets"]) == 12


def test_get_assets_filter_qc_passed_returns_9(client):
    resp = client.get("/api/assets?status=qc_passed")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 9
    assert all(a["status"] == "qc_passed" for a in data["assets"])


def test_get_assets_search_is_case_insensitive(client):
    lower = client.get("/api/assets?search=northern").get_json()
    upper = client.get("/api/assets?search=NORTHERN").get_json()
    mixed = client.get("/api/assets?search=NoRtHeRn").get_json()

    assert lower["total"] >= 1
    assert lower["total"] == upper["total"] == mixed["total"]
    assert all("northern" in a["title"].lower() for a in lower["assets"])


def test_get_asset_unknown_returns_404(client):
    resp = client.get("/api/assets/DOES-NOT-EXIST")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Asset not found"}


def test_post_assets_creates_with_auto_fields(client):
    resp = client.post("/api/assets", json=valid_asset_payload())
    assert resp.status_code == 201
    data = resp.get_json()
    assert data.get("id")
    assert data.get("status") == "ingested"
    assert data.get("created_at")
    assert data.get("updated_at")


def test_post_assets_missing_fields_returns_400(client):
    resp = client.post("/api/assets", json={"title": "Only title"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "missing_fields" in data
    assert isinstance(data["missing_fields"], list)
    assert len(data["missing_fields"]) > 0


def test_route_returns_400_when_not_qc_passed(client):
    # ASSET-004 is "ingested", not qc_passed
    resp = client.post("/api/assets/ASSET-004/route")
    assert resp.status_code == 400


def test_route_asset_001_creates_2_jobs(client, app_mod):
    resp = client.post("/api/assets/ASSET-001/route")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["jobs"]) == 2

    routed_platform_ids = {
        j["platform_id"] for j in app_mod.DELIVERY_JOBS if j["asset_id"] == "ASSET-001"
    }
    routed_platform_names = {
        next(p["name"] for p in app_mod.PLATFORMS if p["id"] == pid)
        for pid in routed_platform_ids
    }
    assert routed_platform_names == {"AppleTV+ Global", "iTunes US Store"}


def test_route_asset_002_creates_3_jobs(client, app_mod):
    resp = client.post("/api/assets/ASSET-002/route")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["jobs"]) == 3

    routed_platform_ids = {
        j["platform_id"] for j in app_mod.DELIVERY_JOBS if j["asset_id"] == "ASSET-002"
    }
    routed_platform_names = {
        next(p["name"] for p in app_mod.PLATFORMS if p["id"] == pid)
        for pid in routed_platform_ids
    }
    assert routed_platform_names == {
        "AppleTV+ Global",
        "iTunes US Store",
        "VOD Asia Pacific",
    }


def test_route_asset_010_creates_no_jobs_with_skips(client):
    resp = client.post("/api/assets/ASSET-010/route")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["jobs"]) == 0
    assert len(data["platforms_skipped"]) > 0


def test_job_status_invalid_value_returns_400(client):
    route_resp = client.post("/api/assets/ASSET-001/route")
    job_id = route_resp.get_json()["jobs"][0]

    resp = client.put(f"/api/jobs/{job_id}/status", json={"status": "bogus"})
    assert resp.status_code == 400


def test_job_status_disallowed_transition_returns_400(client):
    route_resp = client.post("/api/assets/ASSET-001/route")
    job_id = route_resp.get_json()["jobs"][0]

    # queued -> delivered is not a valid transition
    resp = client.put(f"/api/jobs/{job_id}/status", json={"status": "delivered"})
    assert resp.status_code == 400


def test_job_status_terminal_fires_webhook(client, app_mod):
    route_resp = client.post("/api/assets/ASSET-001/route")
    job_id = route_resp.get_json()["jobs"][0]

    with patch.object(app_mod, "requests") as mock_requests:
        mock_requests.post.return_value = MagicMock(status_code=200)
        mock_requests.exceptions = __import__("requests").exceptions

        r1 = client.put(f"/api/jobs/{job_id}/status", json={"status": "processing"})
        assert r1.status_code == 200

        r2 = client.put(f"/api/jobs/{job_id}/status", json={"status": "delivered"})
        assert r2.status_code == 200

        assert mock_requests.post.called
        called_url = mock_requests.post.call_args.args[0] if mock_requests.post.call_args.args else mock_requests.post.call_args.kwargs.get("url")
        platform = next(p for p in app_mod.PLATFORMS if p["id"] == "PLAT-001")
        assert called_url == platform.get("webhook_url")


def test_stats_updates_after_routing_and_status_changes(client):
    initial = client.get("/api/stats").get_json()
    assert initial["assets"]["total"] == 12
    assert initial["assets"]["by_status"]["qc_passed"] == 9
    assert initial["jobs"]["total"] == 0

    client.post("/api/assets/ASSET-001/route")
    after_route = client.get("/api/stats").get_json()
    assert after_route["jobs"]["total"] == 2
    assert after_route["jobs"]["by_status"]["queued"] == 2

    route_resp = client.post("/api/assets/ASSET-002/route")
    job_id = route_resp.get_json()["jobs"][0]
    client.put(f"/api/jobs/{job_id}/status", json={"status": "processing"})

    after_transition = client.get("/api/stats").get_json()
    assert after_transition["jobs"]["by_status"]["processing"] == 1


def test_stats_delivery_rate_null_when_no_terminal_jobs(client):
    resp = client.get("/api/stats")
    data = resp.get_json()
    assert data["delivery_rate"] is None

    client.post("/api/assets/ASSET-001/route")
    data = client.get("/api/stats").get_json()
    assert data["delivery_rate"] is None


def test_all_endpoints_return_json_content_type(client):
    responses = [
        client.get("/api/assets"),
        client.get("/api/assets/ASSET-001"),
        client.get("/api/assets/DOES-NOT-EXIST"),
        client.post("/api/assets", json=valid_asset_payload()),
        client.post("/api/assets", json={}),
        client.post("/api/assets/ASSET-001/route"),
        client.post("/api/assets/ASSET-004/route"),
        client.get("/api/stats"),
    ]
    for resp in responses:
        assert "application/json" in resp.content_type, (
            f"non-json content type: {resp.content_type} for {resp.request.path}"
        )


def test_server_does_not_crash_on_malformed_or_empty_body(client):
    malformed = client.post(
        "/api/assets",
        data="{not valid json",
        content_type="application/json",
    )
    assert malformed.status_code < 500

    empty = client.post(
        "/api/assets",
        data="",
        content_type="application/json",
    )
    assert empty.status_code < 500

    no_content_type = client.post("/api/assets", data="")
    assert no_content_type.status_code < 500
