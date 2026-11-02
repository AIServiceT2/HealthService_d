import { test } from 'node:test';
import assert from 'node:assert/strict';
import { MOCK_EXAMPLES, mockSubmission, resetMockSubmissions } from '../src/api/mockSubmissions';

test('US-02 목데이터 3건: 계산 성공·완료·실패와 초기화', async () => {
  resetMockSubmissions();
  const [pending, prepared, failed] = MOCK_EXAMPLES;
  assert.equal((await mockSubmission(pending.id)).status, 'SUBMITTED');
  assert.equal((await mockSubmission(pending.id, true)).snapshot?.hit_count, 30);
  assert.equal((await mockSubmission(prepared.id)).snapshot?.hit_count, 20);
  await assert.rejects(mockSubmission(failed.id, true), /계산 오류/);
  assert.equal((await mockSubmission(failed.id)).status, 'SUBMITTED');
  resetMockSubmissions();
  assert.equal((await mockSubmission(pending.id)).snapshot, null);
});
