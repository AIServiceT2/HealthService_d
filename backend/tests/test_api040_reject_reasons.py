"""API-040 반려 사유 코드 목록 — backlog US-08: 사유 코드 `기록이상` / `본인확인실패` / `도용의심`."""


def test_us08_api040_lists_three_reasons_without_login(client):
    res = client.get("/reject-reasons")

    assert res.status_code == 200
    assert res.json() == {
        "items": [
            {"code": "RECORD_ANOMALY", "label": "기록 이상"},
            {"code": "IDENTITY_FAILED", "label": "본인 확인 실패"},
            {"code": "SUSPECTED_THEFT", "label": "도용 의심"},
        ]
    }
