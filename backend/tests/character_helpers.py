"""캐릭터 API 테스트 공통 도구. 실제 회원 가입(API-001)·로그인(API-002)으로 access token을 받는다."""

import uuid


def new_player(client) -> tuple[uuid.UUID, dict[str, str]]:
    """새 사용자를 가입·로그인시키고 (user_id, Authorization 헤더)를 돌려준다."""
    email = f"player-{uuid.uuid4().hex[:12]}@example.com"
    password = "example-password"
    signup = client.post(
        "/auth/signup",
        json={
            "provider": "EMAIL",
            "email": email,
            "password": password,
            "nickname": "플레이어",
            "birthDate": "2010-03-14",
        },
    )
    assert signup.status_code == 201, signup.json()
    login = client.post("/auth/login", json={"provider": "EMAIL", "email": email, "password": password})
    assert login.status_code == 200, login.json()
    return uuid.UUID(signup.json()["userId"]), {"Authorization": f"Bearer {login.json()['accessToken']}"}
