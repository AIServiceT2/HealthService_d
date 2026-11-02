import { ApiError } from './client';
import type { Submission } from './submissions';

export const MOCK_EXAMPLES = [
  { id: '00000000-0000-4000-8000-000000000001', label: '스쿼트 30회 · 계산 전' },
  { id: '00000000-0000-4000-8000-000000000002', label: '스쿼트 20회 · 계산 완료' },
  { id: '00000000-0000-4000-8000-000000000003', label: '스쿼트 15회 · 계산 오류' },
] as const;

function createRecords(): Record<string, Submission> {
  return Object.fromEntries(MOCK_EXAMPLES.map((item, index) => [item.id, {
    id: item.id, exercise_type: 'SQUAT', counted_reps: [30, 20, 15][index],
    status: index === 1 ? 'PREPARED' : 'SUBMITTED',
    snapshot: index === 1 ? { hit_count: 20 } : null,
  }]));
}
let records = createRecords();
export function resetMockSubmissions() { records = createRecords(); }

export async function mockSubmission(id: string, calculate = false, signal?: AbortSignal): Promise<Submission> {
  await new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); signal?.removeEventListener('abort', abort); reject(new ApiError('요청이 취소됐어요.')); };
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve(); }, 400);
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
  });
  const record = records[id];
  if (!record) throw new ApiError('기록을 찾을 수 없어요. 제출건 ID를 확인해 주세요.', 404);
  if (calculate) {
    if (record.status !== 'SUBMITTED') throw new ApiError('이미 처리된 기록이에요. 최신 상태를 다시 확인해 주세요.', 409);
    if (id === MOCK_EXAMPLES[2].id) throw new ApiError('목데이터 계산 오류 예시예요. 기록은 접수 상태로 유지됩니다.', 500);
    record.status = 'PREPARED'; record.snapshot = { hit_count: record.counted_reps };
  }
  return { ...record, snapshot: record.snapshot ? { ...record.snapshot } : null };
}
