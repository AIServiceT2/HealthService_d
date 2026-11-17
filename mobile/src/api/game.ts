// 운동·제출·결과·확인 요청 API (API-007·017·018~030·032·034~040·045~048).
// 응답 필드는 서버 camelCase 그대로 쓴다 (backend/app/modules/*/schemas.py).
// /internal API(031·033·041·049~051)는 SYSTEM 전용이라 앱에서 부르지 않는다.
import type { createHttp } from './http';

type Http = ReturnType<typeof createHttp>;

export type SubmissionStatus =
  | 'SUBMITTED' | 'PREPARED' | 'PENDING_REVIEW' | 'APPROVED' | 'REWARDED'
  | 'REJECTED' | 'CLOSED' | 'CANCELED' | 'REVOKED';

export type MyCharacter = {
  userId: string; avatarId: string | null; level: number;
  exp: { confirmed: number; pending: number }; lockedItemCount: number;
};
export type Exercise = {
  code: string; name: string; dailyCap: number;
  criteria: { kneeAngleMax: number | null }; recommendedCameraAngle: string | null; tutorialUrl: string | null;
};
export type DailyCap = { exerciseCode: string; cap: number; reserved: number; remaining: number };
export type Dungeon = { id: string; name: string; enemy: { name: string; hpMax: number; hp: number }; myProgress: { totalDamage: number } };
export type GuildBoss = { bossId: string; status: string; hpMax: number; hp: number; guildTotalDamage: number; weekStart: string; weekEnd: string };

export type Target = { type: 'DUNGEON' | 'BOSS'; id: string };
export type StartedSession = {
  sessionId: string; status: string; catalogVersion: string; remainingDailyCap: number;
  liveness: { challengeId: string; action: string; timeoutSec: number };
  chunkSpec: { maxFrames: number; maxBytes: number };
};
export type Keypoint = [number, number, number] | null;
export type Frame = { t: number; kp: Keypoint[] };
export type Rep = { repNo: number; ts: string; counted: boolean };

export type Submission = {
  id: string; sessionId: string; exerciseCode: string; status: SubmissionStatus; version: number;
  approvalPath: 'AI_AUTO' | 'REVIEWER' | null; startedAt: string; endedAt: string;
  countedReps: number; reservedReps: number; confidence: number; livenessPassed: boolean | null;
};
export type SnapshotValues = {
  catalogVersion: string; hitCount: number; exp: number; totalDamage: number; weaknessMultiplier: number; dropCount: number;
};
export type AiText = { level: string; text: string; isFallback: boolean };
// API-032: 200이면 snapshot이 있고, 계산 전이면 202 { status: 'SUBMITTED', retryAfterSec }
export type RewardPreview =
  | { status: SubmissionStatus; snapshot: SnapshotValues; narrative: AiText }
  | { status: 'SUBMITTED'; retryAfterSec: number; snapshot?: undefined };

export type ResultCard = {
  exerciseCode: string; countedReps: number; hitCount: number; exp: number; totalDamage: number;
  drops: { itemId: string; status: string }[]; rewardedAt: string; dailyCapExceeded: boolean;
};
export type Result = { card: ResultCard; narrative: AiText; formComment: AiText };
export type ReplayEvent = { repIndex: number; t: number; type: 'HIT' | 'MISS'; damage: number | null; reason: string | null };
export type Replay = { hitCount: number; events: ReplayEvent[]; skeletonUrl: string | null };

export type Acquaintance = { userId: string; nickname: string; relation: 'GUILD_LEADER' | 'GUILD_MEMBER' | string };
export type Anomaly = { type: string; repNos: number[]; description: string };
export type SharePreview = { skeletonReplayUrl: string | null; summary: string | null; anomalies: Anomaly[]; painNotice: string | null };
export type ReceivedReview = {
  submissionId: string; requester: { userId: string; nickname: string };
  exerciseCode: string; countedReps: number; requestedAt: string;
};
export type ReviewMaterial = {
  submissionId: string; status: SubmissionStatus; version: number; requester: { nickname: string };
  exerciseCode: string; countedReps: number; confidence: number;
  skeletonReplayUrl: string | null; summary: string | null; anomalies: Anomaly[]; painNotice: string | null;
};
export type RejectReason = { code: string; label: string };
type Page<T> = { items: T[]; nextCursor: string | null };

const id = (value: string) => encodeURIComponent(value);
const ifMatch = (version: number) => ({ 'If-Match': `"${version}"` });

export function createGameApi(http: Http) {
  return {
    myCharacter: () => http.request<MyCharacter>('/characters/me'),

    exercises: () => http.request<{ catalogVersion: string; items: Exercise[] }>('/exercises'),
    dailyCaps: () => http.request<{ date: string; items: DailyCap[] }>('/me/daily-caps'),
    dungeon: (dungeonId: string) => http.request<Dungeon>(`/dungeons/${id(dungeonId)}`),
    guildBoss: (guildId: string) => http.request<GuildBoss>(`/guilds/${id(guildId)}/boss`),

    // 운동 세션 (API-020~027)
    startSession: (input: { exerciseCode: string; goal?: { reps: number; sets: number }; target?: Target }) =>
      http.request<StartedSession>('/workout-sessions', { method: 'POST', body: input }),
    sendLiveness: (sessionId: string, body: { challengeId: string; detectedAction: string; score: number; detectedAt: string }) =>
      http.request<{ passed: boolean; retryAllowed: boolean }>(`/workout-sessions/${id(sessionId)}/liveness`, { method: 'POST', body }),
    uploadChunk: (sessionId: string, seq: number, frames: Frame[]) =>
      http.request<{ received: number[] }>(`/workout-sessions/${id(sessionId)}/pose-chunks/${seq}`, { method: 'PUT', body: { seq, frames } }),
    pauseSession: (sessionId: string, reason: 'CAMERA_LOST' | 'APP_BACKGROUND') =>
      http.request<{ sessionId: string; status: string }>(`/workout-sessions/${id(sessionId)}/pause`, {
        method: 'POST', body: { reason, at: new Date().toISOString() },
      }),
    resumeSession: (sessionId: string) =>
      http.request<{ sessionId: string; status: string; receivedChunks: number[] }>(`/workout-sessions/${id(sessionId)}/resume`, { method: 'POST' }),
    discardSession: (sessionId: string) =>
      http.request<void>(`/workout-sessions/${id(sessionId)}`, { method: 'DELETE' }),
    // 같은 제출을 다시 보낼 때는 같은 idempotencyKey를 써야 중복 제출건이 생기지 않는다 (API-026)
    submitSession: (sessionId: string, idempotencyKey: string, body: {
      totalChunks: number; endedAt: string; clientRepCount: number; reps: Rep[]; aiConfidence: number;
    }) => http.request<{ submissionId: string; status: string; countedReps: number; reservedReps: number; version: number }>(
      `/workout-sessions/${id(sessionId)}/submit`, { method: 'POST', body, headers: { 'Idempotency-Key': idempotencyKey } }),

    // 제출건 (API-028~030·032)
    submission: (submissionId: string) => http.request<Submission>(`/submissions/${id(submissionId)}`),
    mySubmissions: (limit = 20) => http.request<Page<Submission>>(`/me/submissions?limit=${limit}`),
    cancel: (submissionId: string, version: number) =>
      http.request<{ submissionId: string; status: string; releasedReps: number; version: number }>(
        `/submissions/${id(submissionId)}/cancel`, { method: 'POST', headers: ifMatch(version) }),
    rewardPreview: (submissionId: string) => http.request<RewardPreview>(`/submissions/${id(submissionId)}/reward-preview`),

    // 결과 (API-047·048)
    result: (submissionId: string) => http.request<Result>(`/submissions/${id(submissionId)}/result`),
    replay: (submissionId: string) => http.request<Replay>(`/submissions/${id(submissionId)}/replay`),

    // 확인 요청 (API-017·034~040)
    acquaintances: async () => (await http.request<{ items: Acquaintance[] }>('/me/acquaintances')).items,
    sharePreview: (submissionId: string) => http.request<SharePreview>(`/submissions/${id(submissionId)}/review-share-preview`),
    requestReview: (submissionId: string, version: number, reviewerUserId: string) =>
      http.request<{ submissionId: string; submissionStatus: string; version: number }>(
        `/submissions/${id(submissionId)}/review-requests`,
        { method: 'POST', headers: ifMatch(version), body: { reviewerUserId, sharePreviewConfirmed: true } }),
    receivedReviews: (limit = 20) => http.request<Page<ReceivedReview>>(`/me/review-requests?limit=${limit}`),
    reviewMaterial: (submissionId: string) => http.request<ReviewMaterial>(`/review-requests/${id(submissionId)}`),
    approveReview: (submissionId: string, version: number) =>
      http.request<{ submissionStatus: string; version: number }>(`/review-requests/${id(submissionId)}/approve`, {
        method: 'POST', headers: ifMatch(version),
      }),
    rejectReview: (submissionId: string, version: number, reasonCode: string, reasonText: string) =>
      http.request<{ submissionStatus: string; version: number }>(`/review-requests/${id(submissionId)}/reject`, {
        method: 'POST', headers: ifMatch(version), body: { reasonCode, reasonText },
      }),
    rejectReasons: async () => (await http.request<{ items: RejectReason[] }>('/reject-reasons', { auth: false })).items,
  };
}
