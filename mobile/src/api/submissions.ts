import { mockSubmission } from './mockSubmissions';
import { ApiError, request } from './client';

export const IS_MOCK_MODE = process.env.EXPO_PUBLIC_USE_MOCK === 'true';

export type Submission = {
  id: string; status: string; exercise_type: string; counted_reps: number;
  snapshot: { hit_count?: number } | null;
};
export const isSubmissionId = (value: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);

export function parseSubmission(value: unknown): Submission {
  if (!value || typeof value !== 'object') throw new ApiError('서버 응답 형식을 확인해 주세요.');
  const data = value as Submission;
  if (typeof data.id !== 'string' || typeof data.status !== 'string' || typeof data.exercise_type !== 'string'
    || !Number.isInteger(data.counted_reps) || data.counted_reps < 0
    || (data.snapshot !== null && (typeof data.snapshot !== 'object' || Array.isArray(data.snapshot)))) {
    throw new ApiError('서버 응답 형식을 확인해 주세요.');
  }
  if (data.snapshot?.hit_count !== undefined && (!Number.isInteger(data.snapshot.hit_count) || data.snapshot.hit_count < 0)) {
    throw new ApiError('타격 수 응답을 확인해 주세요.');
  }
  if (data.status === 'PREPARED' && data.snapshot?.hit_count === undefined) throw new ApiError('계산 결과에 타격 수가 없어요. 다시 조회해 주세요.');
  return data;
}

// API.md의 미정 항목은 현재 backend submission/router.py·service.py 구현에 맞춘다.
export async function getSubmission(id: string, signal?: AbortSignal) {
  if (IS_MOCK_MODE) return parseSubmission(await mockSubmission(id, false, signal));
  return parseSubmission(await request(`/submissions/${encodeURIComponent(id)}`, 'GET', signal));
}
export async function prepareSubmission(id: string, signal?: AbortSignal) {
  if (IS_MOCK_MODE) return parseSubmission(await mockSubmission(id, true, signal));
  return parseSubmission(await request(`/submissions/${encodeURIComponent(id)}/prepare`, 'POST', signal));
}
