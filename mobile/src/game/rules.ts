// 화면에서 쓰는 순수 규칙. 화면 문구는 DESIGN.md 4절 [제안], 판단 기준은 backlog·API.md를 따른다.
import type { Frame, Keypoint, SubmissionStatus } from '../api/game';

export type Tone = 'lime' | 'warn' | 'danger' | 'muted';

// DESIGN.md 4절 '처리 상태와 행동' 화면 문구
export const STATUS_COPY: Record<SubmissionStatus, { chip: string; message: string; tone: Tone }> = {
  SUBMITTED: { chip: '계산 중', message: '운동 기록을 접수했어요. 보상을 계산 중이에요', tone: 'muted' },
  PREPARED: { chip: '계산 완료', message: '보상 미리보기 · 아직 지급 전이에요', tone: 'muted' },
  PENDING_REVIEW: { chip: '확인 대기', message: '확인자의 검토를 기다리고 있어요', tone: 'warn' },
  APPROVED: { chip: '승인', message: '승인됐어요. 보상을 반영 중이에요', tone: 'lime' },
  REWARDED: { chip: '지급 완료', message: '보상이 반영됐어요', tone: 'lime' },
  CANCELED: { chip: '취소됨', message: '제출이 취소됐어요', tone: 'muted' },
  REJECTED: { chip: '반려', message: '반려됐어요. 기록을 종료 중이에요', tone: 'danger' },
  CLOSED: { chip: '종료', message: '종료된 기록이에요', tone: 'muted' },
  REVOKED: { chip: '회수', message: '보상이 회수된 기록이에요', tone: 'danger' },
};

export const statusCopy = (status: string) =>
  STATUS_COPY[status as SubmissionStatus] ?? { chip: status, message: status, tone: 'muted' as Tone };

export const EXERCISE_NAMES: Record<string, string> = { SQUAT: '스쿼트' };
export const exerciseName = (code: string) => EXERCISE_NAMES[code] ?? code;

// 스쿼트 스킬 이름 (PRD 2절 '충격파 스톰프 ×30'). 다른 운동은 MVP 제외
export const skillName = (code: string) => (code === 'SQUAT' ? '충격파 스톰프' : exerciseName(code));

// 데모 던전 ID (backend battle/catalog.py DEMO_DUNGEON_ID: 앱이 target으로 그대로 쓰도록 고정) [가안]
export const DEMO_DUNGEON_ID = '3d1f6c2a-5b7e-4c1a-9f0e-2a8b6d4c1e70';

// 자동 승인 기준 0.90 (backend review/rules.py, PRD 미정 표: 미확정)
export const AUTO_APPROVAL_THRESHOLD = 0.9;

// 취소 가능: 승인 전 세 상태 (backlog US-06)
export const canCancel = (status: string) => status === 'SUBMITTED' || status === 'PREPARED' || status === 'PENDING_REVIEW';

// 확인 요청 가능: PREPARED이고 자동 승인 대상이 아님 (backlog US-03 (실패·거절), US-07, API-035)
export function needsReview(s: { status: string; confidence: number; livenessPassed: boolean | null }) {
  return s.status === 'PREPARED' && (s.confidence < AUTO_APPROVAL_THRESHOLD || s.livenessPassed !== true);
}

// 서버가 다음 단계로 넘길 때까지 다시 조회해야 하는 상태
export function isWaiting(s: { status: string; confidence: number; livenessPassed: boolean | null }) {
  return s.status === 'SUBMITTED' || s.status === 'APPROVED' || (s.status === 'PREPARED' && !needsReview(s));
}

// 상한 초과: 인정량은 있는데 보상 대상으로 예약된 양이 0 (backlog US-01 (실패·거절))
export const capExceeded = (s: { countedReps: number; reservedReps: number; status: string }) =>
  s.countedReps > 0 && s.reservedReps === 0 && s.status !== 'CANCELED' && s.status !== 'CLOSED';

// 무작위 동작 (backend workout_session/service.py LIVENESS_ACTIONS)
export const LIVENESS_LABELS: Record<string, { lead: string; accent: string }> = {
  RAISE_LEFT_HAND: { lead: '왼손을', accent: '머리 위로' },
  RAISE_RIGHT_HAND: { lead: '오른손을', accent: '머리 위로' },
  RAISE_BOTH_HANDS: { lead: '양손을', accent: '머리 위로' },
};
export const livenessLabel = (action: string) => LIVENESS_LABELS[action] ?? { lead: '화면의 동작을', accent: '따라 해' };

// ---- 카메라 연결 전 개발용 관절 좌표 ----
// MoveNet(COCO 17) 배열. 0~4번(코·눈·귀)은 서버로 보내지 않으므로 null (backlog US-01, 03 R11)
export const MOVENET_FACE_INDEXES = [0, 1, 2, 3, 4];
const BODY_17: [number, number][] = [
  [0, 0], [0, 0], [0, 0], [0, 0], [0, 0],
  [0.42, 0.3], [0.58, 0.3], [0.38, 0.45], [0.62, 0.45], [0.36, 0.58], [0.64, 0.58],
  [0.45, 0.6], [0.55, 0.6], [0.44, 0.75], [0.56, 0.75], [0.45, 0.92], [0.55, 0.92],
];

/** 렙 하나에 해당하는 가짜 프레임. depth 0(서 있음)~1(앉음)만큼 엉덩이·무릎을 내린다 */
export function devFrame(t: number, depth: number): Frame {
  const kp: Keypoint[] = BODY_17.map(([x, y], i) => {
    if (MOVENET_FACE_INDEXES.includes(i)) return null;
    const drop = i >= 11 && i <= 14 ? depth * 0.12 : i >= 5 && i <= 10 ? depth * 0.1 : 0;
    return [x, Math.min(1, y + drop), 0.9];
  });
  return { t, kp };
}

/** 프레임 배열을 서버 청크 크기(maxFrames)로 나눈다. 비어 있으면 서 있는 프레임 1개 */
export function toChunks(frames: Frame[], maxFrames: number, now = Date.now()): Frame[][] {
  const list = frames.length > 0 ? frames : [devFrame(now, 0)];
  const size = Math.max(1, maxFrames);
  const chunks: Frame[][] = [];
  for (let i = 0; i < list.length; i += size) chunks.push(list.slice(i, i + size));
  return chunks;
}

// 리플레이는 30초를 넘지 않는다 (backlog US-05 (정상) 2번째)
export const REPLAY_MAX_SECONDS = 30;

/** HIT 이벤트의 재생 시각(ms). 30초를 넘으면 비율대로 줄이고, 시각이 없으면 0.5초 간격으로 둔다 */
export function scheduleHits(events: { t: number; type: string }[]) {
  const hits = events.filter((e) => e.type === 'HIT');
  const raw = hits.some((e) => e.t > 0) ? hits.map((e) => e.t) : hits.map((_, i) => i * 0.5);
  const end = Math.max(0, ...raw);
  const scale = end > REPLAY_MAX_SECONDS ? REPLAY_MAX_SECONDS / end : 1;
  return raw.map((t) => t * scale * 1000);
}

// Idempotency-Key용 UUID v4 (Hermes에 crypto.randomUUID가 없을 수 있음)
export function uuidV4(random: () => number = Math.random) {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.floor(random() * 16);
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export const pct = (value: number) => `${Math.round(value * 100)}%`;
export const shortTime = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
};
