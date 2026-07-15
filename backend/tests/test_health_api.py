def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "medmemory-api",
    }


def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Welcome to MedMemory API",
        "docs": "/docs",
        "health": "/health",
    }


def test_metrics_endpoint(client):
    client.get("/health")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "medmemory_uptime_seconds" in response.text
    assert "medmemory_http_requests_total" in response.text
    assert "medmemory_http_request_duration_ms_total" in response.text
    assert "medmemory_clinician_agent_runs_total" in response.text
    assert "medmemory_access_audit_events_total" in response.text
    assert "medmemory_guardrail_events_total" in response.text
