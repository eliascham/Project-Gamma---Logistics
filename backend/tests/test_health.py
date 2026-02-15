import pytest


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint_has_required_fields(client):
    response = await client.get("/api/v1/health")
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data
    assert "timestamp" in data
    assert "environment" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_health_endpoint_reports_version(client):
    response = await client.get("/api/v1/health")
    data = response.json()
    assert data["version"] == "0.1.0"
