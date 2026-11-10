"""지급 규칙 상수."""

from datetime import timedelta

# 지급 뒤 보호 기간: 아이템 LOCKED·경험치 확정 대기 (backlog US-04, 03 R7)
PROTECTION_PERIOD = timedelta(hours=24)
