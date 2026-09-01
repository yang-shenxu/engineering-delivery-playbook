"""pytest 接口测试：三类 REST 接口 + 两种报表模式。"""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["points"] >= 1


def test_list_points_pagination():
    resp = client.get("/points", params={"page": 1, "size": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert len(body["items"]) == 5
    assert "point_id" in body["items"][0]


def test_point_values():
    resp = client.get(
        "/points/point_001/values",
        params={"start": "2026-07-01", "end": "2026-07-02"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["point_id"] == "point_001"
    assert body["total"] > 0
    assert "ts" in body["data"][0] and "value" in body["data"][0]


def test_point_values_404():
    resp = client.get(
        "/points/point_999/values",
        params={"start": "2026-07-01", "end": "2026-07-02"},
    )
    assert resp.status_code == 404


def test_report_monthly_batch():
    resp = client.get(
        "/reports/monthly",
        params={"points": "point_001,point_002", "start": "2026-07-01", "end": "2026-07-05", "mode": "batch"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "batch"
    assert body["query_count"] == 1
    # 表头 = 测点列 + 5 天
    assert len(body["rows"][0]) == 6
    assert len(body["rows"]) == 3  # 表头 + 2 测点


def test_report_monthly_n1_query_count():
    resp = client.get(
        "/reports/monthly",
        params={"points": "point_001,point_002", "start": "2026-07-01", "end": "2026-07-05", "mode": "n1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "n1"
    # N+1 模式查询次数 = 测点数 × 天数
    assert body["query_count"] == 2 * 5
