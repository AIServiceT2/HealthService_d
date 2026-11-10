"""LLM 입력·출력 규칙 (03-rules-states-llm.md 3-4, backlog US-02·05·07, 노션 API-049~051)."""

import re

# 출력 검사에 실패하면 다시 만들고, 이 횟수만큼 실패하면 기본 문구 (backlog US-05: 2번 실패하면 기본 문구)
MAX_ATTEMPTS = 2
# 출력 길이 상한 [제안·팀 확인 필요]. 한두 문장 (03 3-4)
MAX_OUTPUT_LENGTH = 200

DIGITS = re.compile(r"[0-9０-９]")

# ---- L3 전투 서사 ----

# 운동 종류별 스킬명. 스킬 카탈로그가 아직 없어 user-flows.md 5단계의 '충격파 스톰프'만 둔다 [가정]
SKILL_BY_EXERCISE: dict[str, str] = {"SQUAT": "충격파 스톰프"}
# 서사에 나오면 안 되는 아이템명. 아이템 카탈로그가 아직 없어 비어 있다 (노션 ERD '아직 정하지 못한 것')
ITEM_NAMES: tuple[str, ...] = ()

# ---- L4 자세 교정 코멘트 ----

# 기본 문구: DESIGN.md 5절 'LLM 결과 표시'의 교정 기본 문구 예시 [제안·팀 확인 필요 — PRD 미정 표]
FALLBACK_FORM_TIP = "교정 안내를 불러오지 못했어요. 다음 운동 전 판정 기준을 확인해 주세요."
# 진단·처방처럼 들리는 표현. 거를 기준은 미정 (backlog US-05 미확정, PRD 미정 표) → 우선 아래 낱말이 있으면 탈락 [제안]
MEDICAL_WORDS: tuple[str, ...] = (
    "진단", "처방", "치료", "질환", "질병", "병원", "의사", "복용", "약물", "재활", "부상입니다", "손상",
)
# poseSummary로 받는 관절 각도 통계 [제안: 입력 계약 미정 — 노션 API-050]
POSE_SUMMARY_MAX_JOINTS = 10

# ---- L1 기록 요약·L2 이상치 설명 ----

# 이상치는 규칙이 찾고(종류·렙 번호), LLM은 설명 문장만 쓴다 (03 3-4 L2: 규칙 검사 결과 + 렙 간격 통계).
# 기준값은 근거가 없는 가정이다 [가정·팀 확인 필요]. ai/ 엔진의 anomaly.py와 맞출지 팀이 정한다
MIN_REP_INTERVAL_SEC = 1.0  # 이보다 짧은 렙 간격은 TEMPO_TOO_FAST
UNIFORM_TEMPO_STD_SEC = 0.05  # 렙 간격 표준편차가 이보다 작으면 UNIFORM_TEMPO (영상 재생 의심, 03 3-4 L2 예)
UNIFORM_TEMPO_MIN_REPS = 10  # 렙이 이만큼은 있어야 고른 간격을 의심한다

# LLM이 실패하면 규칙 검사 결과만 보여 준다 (03 3-4 L2) → 종류별 고정 설명 [제안]
FALLBACK_ANOMALY_DESCRIPTIONS: dict[str, str] = {
    "TEMPO_TOO_FAST": "렙 사이 간격이 매우 짧은 구간이 있어요.",
    "UNIFORM_TEMPO": "렙 간격이 처음부터 끝까지 거의 같아요.",
}
