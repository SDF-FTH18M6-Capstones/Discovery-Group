def test_health_returns_200(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json["database"] == "ok"


def test_unknown_route_returns_json_404(client):
    response = client.get("/api/nothing-here")

    assert response.status_code == 404
    assert response.json["error"]["code"] == 404


def test_swagger_docs_are_served(client):
    assert "/api/health" in client.get("/api/openapi.json").json["paths"]
    assert client.get("/api/docs").status_code == 200
