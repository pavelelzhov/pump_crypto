from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get('/api/health')
    assert response.status_code == 200
    assert 'running' in response.json()


def test_update_config_endpoint() -> None:
    client = TestClient(app)
    response = client.post('/api/config', json={'min_score': 0.72, 'min_move_pct': 4.0})
    assert response.status_code == 200
    body = response.json()
    assert body['config']['min_score'] == 0.72
    assert body['config']['min_move_pct'] == 4.0


def test_update_alerts_endpoint() -> None:
    client = TestClient(app)
    response = client.post('/api/alerts', json={'enabled': True, 'min_score_for_alert': 0.9})
    assert response.status_code == 200
    assert response.json()['enabled'] is True


def test_report_endpoint() -> None:
    client = TestClient(app)
    response = client.get('/api/report')
    assert response.status_code == 200
    body = response.json()
    assert 'signals_24h' in body
    assert 'avg_final_score' in body
