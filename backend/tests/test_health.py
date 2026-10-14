def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_unknown_api_route_returns_404(client):
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
