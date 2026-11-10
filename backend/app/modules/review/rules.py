"""확인 요청·승인·반려 기준값."""

# AI 판정 확신도 자동 승인 기준 (PRD 2절·backlog US-03). 90%와 계산 방법은 미확정 (PRD 미정 표)
AUTO_APPROVAL_THRESHOLD = 0.90

# 반려 사유 코드 (노션 API-040, ERD REJECT_REASON). 노션 ERD는 테이블이지만 값을 바꾸는 API가 없어 코드 상수로 둔다
# [제안·팀 확인 필요]. 이름은 backlog US-08의 `기록이상` / `본인확인실패` / `도용의심`, 코드는 노션 예시 값
REJECT_REASONS: dict[str, str] = {
    "RECORD_ANOMALY": "기록 이상",
    "IDENTITY_FAILED": "본인 확인 실패",
    "SUSPECTED_THEFT": "도용 의심",
}
