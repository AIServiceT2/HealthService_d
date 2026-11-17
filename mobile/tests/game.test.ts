// MVP 화면의 규칙과 API 요청 형식 (backlog US-01·03·05·06·07, API.md 공통 규칙)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHttp, type TokenStore } from '../src/api/http';
import { createGameApi } from '../src/api/game';
import {
  MOVENET_FACE_INDEXES, canCancel, capExceeded, devFrame, isWaiting, needsReview, scheduleHits, toChunks, uuidV4,
} from '../src/game/rules';

const base = { confidence: 0.95, livenessPassed: true as boolean | null };

test('US-03 확신도 90% 이상이고 동작 확인을 통과한 PREPARED 건은 확인 요청 대상이 아니다', () => {
  assert.equal(needsReview({ ...base, status: 'PREPARED' }), false);
  assert.equal(needsReview({ ...base, status: 'PREPARED', confidence: 0.9 }), false);
});

test('US-03 확신도 기준 미만이거나 동작 확인 실패면 PREPARED 건에 확인 요청 버튼이 나온다', () => {
  assert.equal(needsReview({ ...base, status: 'PREPARED', confidence: 0.7 }), true);
  assert.equal(needsReview({ ...base, status: 'PREPARED', livenessPassed: false }), true);
  assert.equal(needsReview({ ...base, status: 'PREPARED', livenessPassed: null }), true);
});

test('US-07 이미 APPROVED된 건에는 확인 요청 버튼이 없다', () => {
  assert.equal(needsReview({ ...base, status: 'APPROVED', confidence: 0.5 }), false);
});

test('US-06 승인 전 세 상태만 취소할 수 있다', () => {
  for (const s of ['SUBMITTED', 'PREPARED', 'PENDING_REVIEW']) assert.equal(canCancel(s), true, s);
  for (const s of ['APPROVED', 'REWARDED', 'CANCELED', 'REJECTED', 'CLOSED']) assert.equal(canCancel(s), false, s);
});

test('서버가 다음 단계로 넘길 때까지 다시 조회하는 상태', () => {
  assert.equal(isWaiting({ ...base, status: 'SUBMITTED' }), true);
  assert.equal(isWaiting({ ...base, status: 'APPROVED' }), true);
  assert.equal(isWaiting({ ...base, status: 'PREPARED' }), true); // 자동 승인 대기
  assert.equal(isWaiting({ ...base, status: 'PREPARED', confidence: 0.7 }), false); // 사람 확인 필요
  assert.equal(isWaiting({ ...base, status: 'REWARDED' }), false);
});

test('US-01 상한 초과: 인정량은 있지만 예약량이 0이면 상한 초과로 본다', () => {
  assert.equal(capExceeded({ countedReps: 30, reservedReps: 0, status: 'REWARDED' }), true);
  assert.equal(capExceeded({ countedReps: 30, reservedReps: 30, status: 'REWARDED' }), false);
  assert.equal(capExceeded({ countedReps: 0, reservedReps: 0, status: 'SUBMITTED' }), false);
});

test('US-01 개발용 관절 좌표는 MoveNet 17점이고 얼굴 자리(0~4번)는 null이다', () => {
  const frame = devFrame(1000, 1);
  assert.equal(frame.kp.length, 17);
  for (const i of MOVENET_FACE_INDEXES) assert.equal(frame.kp[i], null);
  assert.ok(frame.kp.slice(5).every((p) => Array.isArray(p) && p.length === 3));
});

test('청크는 서버가 준 최대 프레임 수로 나누고, 프레임이 없으면 1개를 보낸다', () => {
  const frames = Array.from({ length: 7 }, (_, i) => devFrame(i, 0));
  assert.deepEqual(toChunks(frames, 3).map((c) => c.length), [3, 3, 1]);
  assert.equal(toChunks([], 300).length, 1);
});

test('US-05 리플레이는 30초를 넘지 않고, 타격 수만큼 재생한다', () => {
  const events = Array.from({ length: 40 }, (_, i) => ({ t: i * 2, type: i % 10 === 9 ? 'MISS' : 'HIT' }));
  const times = scheduleHits(events);
  assert.equal(times.length, 36);
  assert.ok(Math.max(...times) <= 30_000);
  assert.deepEqual(scheduleHits([{ t: 0, type: 'HIT' }, { t: 0, type: 'HIT' }]), [0, 500]);
});

test('Idempotency-Key는 UUID v4 형식이다', () => {
  assert.match(uuidV4(), /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

// ---- 요청 형식 ----
type Call = { url: string; init: RequestInit };
function setup() {
  const calls: Call[] = [];
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
  const store: TokenStore = { get: async () => ({ accessToken: 'a', refreshToken: 'r' }), set: async () => undefined, clear: async () => undefined };
  const game = createGameApi(createHttp(store, () => 'http://api.test'));
  return { calls, game };
}
const header = (call: Call, name: string) => (call.init.headers as Record<string, string>)[name];

test('US-06 취소는 제출건 version을 If-Match에 넣는다', async () => {
  const { calls, game } = setup();
  await game.cancel('s1', 3);
  assert.equal(calls[0].url, 'http://api.test/submissions/s1/cancel');
  assert.equal(calls[0].init.method, 'POST');
  assert.equal(header(calls[0], 'If-Match'), '"3"');
  assert.equal(header(calls[0], 'Authorization'), 'Bearer a');
});

test('US-01 제출은 Idempotency-Key를 넣고, 같은 키를 다시 쓸 수 있다', async () => {
  const { calls, game } = setup();
  const body = { totalChunks: 1, endedAt: '2026-11-12T00:00:00Z', clientRepCount: 1, reps: [], aiConfidence: 0.95 };
  await game.submitSession('sess', 'key-1', body);
  await game.submitSession('sess', 'key-1', body);
  assert.equal(calls[0].url, 'http://api.test/workout-sessions/sess/submit');
  assert.equal(header(calls[0], 'Idempotency-Key'), 'key-1');
  assert.equal(header(calls[1], 'Idempotency-Key'), 'key-1');
  assert.deepEqual(JSON.parse(String(calls[0].init.body)), body);
});

test('US-07 확인 요청은 미리보기를 확인했다는 값과 If-Match를 보낸다', async () => {
  const { calls, game } = setup();
  await game.requestReview('s1', 2, 'u2');
  assert.equal(header(calls[0], 'If-Match'), '"2"');
  assert.deepEqual(JSON.parse(String(calls[0].init.body)), { reviewerUserId: 'u2', sharePreviewConfirmed: true });
});

test('US-08 반려는 사유 코드와 설명을 함께 보낸다', async () => {
  const { calls, game } = setup();
  await game.rejectReview('s1', 4, 'RECORD_ANOMALY', '간격이 이상함');
  assert.equal(calls[0].url, 'http://api.test/review-requests/s1/reject');
  assert.equal(header(calls[0], 'If-Match'), '"4"');
  assert.deepEqual(JSON.parse(String(calls[0].init.body)), { reasonCode: 'RECORD_ANOMALY', reasonText: '간격이 이상함' });
});
