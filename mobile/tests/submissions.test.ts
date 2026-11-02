import { test } from 'node:test';
import assert from 'node:assert/strict';
import { getSubmission, parseSubmission, prepareSubmission } from '../src/api/submissions';
const ID = '00000000-0000-4000-8000-000000000001';
const submitted = { id: ID, status: 'SUBMITTED', exercise_type: 'SQUAT', counted_reps: 30, snapshot: null };

test('US-02 계산 전 타격 수를 만들지 않고 서버의 30타 결과를 보존한다', () => {
  assert.equal(parseSubmission(submitted).snapshot, null);
  assert.equal(parseSubmission({ ...submitted, status: 'PREPARED', snapshot: { hit_count: 30 } }).snapshot?.hit_count, 30);
});
test('US-02 잘못된 계산 결과를 0타로 표시하지 않는다', () => {
  for (const snapshot of [null, {}, { hit_count: -1 }, { hit_count: '30' }]) {
    assert.throws(() => parseSubmission({ ...submitted, status: 'PREPARED', snapshot }));
  }
});
test('US-02 실제 서버 계약의 조회와 계산 경로·방식을 사용한다', async () => {
  const original = globalThis.fetch; const oldUrl = process.env.EXPO_PUBLIC_API_URL;
  process.env.EXPO_PUBLIC_API_URL = 'http://localhost:8000';
  const calls: [string, string][] = [];
  globalThis.fetch = async (url, options) => {
    calls.push([String(url), options?.method ?? 'GET']);
    return new Response(JSON.stringify(submitted), { status: 200 });
  };
  try {
    await getSubmission(ID); await prepareSubmission(ID);
    assert.deepEqual(calls, [[`http://localhost:8000/submissions/${ID}`, 'GET'], [`http://localhost:8000/submissions/${ID}/prepare`, 'POST']]);
    globalThis.fetch = async () => new Response('{}', { status: 500 });
    await assert.rejects(prepareSubmission(ID), /실패/);
    globalThis.fetch = async () => new Response('{}', { status: 404 });
    await assert.rejects(getSubmission(ID), /찾을 수 없어요/);
  } finally {
    globalThis.fetch = original;
    if (oldUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = oldUrl;
  }
});
