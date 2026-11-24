"""길드 채팅 실시간 연결 목록 (노션 API-075).

서버 인스턴스 1개 기준이다. 연결 목록은 이 프로세스 메모리에만 있어서 인스턴스가 늘면 다른 인스턴스의
연결에는 전달되지 않는다 (인스턴스 사이 전달 방법은 명세 미정. STACK.md는 Redis를 넣지 않기로 함).

API(동기 함수, 스레드풀)에서 부르면 각 연결의 이벤트 루프에 있는 큐로 넘기고, 연결마다 쓰기 작업 하나가
큐에서 꺼내 순서대로 보낸다. 한 연결에 여러 스레드가 동시에 쓰지 않게 하려고.
"""

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

# 연결을 닫으라는 표시. 큐에 (CLOSE, code)로 넣는다
CLOSE = "__close__"


@dataclass(eq=False)
class Connection:
    guild_id: uuid.UUID
    user_id: uuid.UUID
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    def put(self, item: Any) -> None:
        """어느 스레드에서 불러도 된다. 연결의 루프가 이미 끝났으면 버린다."""
        try:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, item)
        except RuntimeError:
            pass


class ChatHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_guild: dict[uuid.UUID, set[Connection]] = {}

    def register(self, conn: Connection) -> None:
        with self._lock:
            self._by_guild.setdefault(conn.guild_id, set()).add(conn)

    def unregister(self, conn: Connection) -> None:
        with self._lock:
            conns = self._by_guild.get(conn.guild_id)
            if conns is not None:
                conns.discard(conn)
                if not conns:
                    del self._by_guild[conn.guild_id]

    def _connections(self, guild_id: uuid.UUID) -> list[Connection]:
        with self._lock:
            return list(self._by_guild.get(guild_id, ()))

    def broadcast(self, guild_id: uuid.UUID, event: dict[str, Any]) -> None:
        """그 길드의 모든 연결에 보낸다."""
        for conn in self._connections(guild_id):
            conn.put(event)

    def close_user(self, guild_id: uuid.UUID, user_id: uuid.UUID, code: int) -> None:
        """그 길드에서 그 사용자의 연결을 모두 닫는다 (탈퇴·내보내기 → 4403)."""
        for conn in self._connections(guild_id):
            if conn.user_id == user_id:
                conn.put((CLOSE, code))

    def connection_count(self, guild_id: uuid.UUID) -> int:
        return len(self._connections(guild_id))


hub = ChatHub()
