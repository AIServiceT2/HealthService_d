// F-01 로그인 토큰을 붙이는 HTTP 클라이언트 (API.md 공통 규칙: 오류 본문, access 만료 시 재발급 API-003)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { HttpError, createHttp, type TokenStore, type Tokens } from '../src/api/http';

function memoryStore(initial: Tokens | null): TokenStore & { value: Tokens | null } {
  const store = {
    value: initial,
    get: async () => store.value,
    set: async (t: Tokens) => { store.value = t; },
    clear: async () => { store.value = null; },
  };
  return store;
}

type Call = { url: string; init: RequestInit };
function mockFetch(responses: ((call: Call) => Response)[]) {
  const calls: Call[] = [];
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    const call = { url, init };
    calls.push(call);
    const next = responses.shift();
    if (!next) throw new Error('예상하지 못한 요청');
    return next(call);
  }) as typeof fetch;
  return calls;
}
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const BASE = () => 'http://server.test/';

test('F-01 저장된 access 토큰을 Bearer로 붙이고 JSON 본문을 보낸다', async () => {
  const calls = mockFetch([() => json(201, { guildId: 'g1' })]);
  const http = createHttp(memoryStore({ accessToken: 'A1', refreshToken: 'R1' }), BASE);
  const data = await http.request<{ guildId: string }>('/guilds/join', { method: 'POST', body: { inviteCode: 'A7K2QX' } });
  assert.equal(data.guildId, 'g1');
  assert.equal(calls[0].url, 'http://server.test/guilds/join');
  const headers = calls[0].init.headers as Record<string, string>;
  assert.equal(headers.Authorization, 'Bearer A1');
  assert.equal(calls[0].init.body, JSON.stringify({ inviteCode: 'A7K2QX' }));
});
test('F-01 로그인 없이 부르는 API(auth:false)에는 토큰을 붙이지 않는다', async () => {
  const calls = mockFetch([() => json(201, { userId: 'u1' })]);
  const http = createHttp(memoryStore({ accessToken: 'A1', refreshToken: 'R1' }), BASE);
  await http.request('/auth/signup', { method: 'POST', auth: false, body: {} });
  assert.equal((calls[0].init.headers as Record<string, string>).Authorization, undefined);
});
test('F-01 access가 만료돼 401이면 refresh로 새 토큰을 받아 한 번 다시 보낸다', async () => {
  const store = memoryStore({ accessToken: 'OLD', refreshToken: 'R1' });
  const calls = mockFetch([
    () => json(401, { code: 'UNAUTHENTICATED', message: '로그인이 필요합니다.', details: null }),
    () => json(200, { accessToken: 'NEW', accessTokenExpiresIn: 1800, refreshToken: 'R2' }),
    () => json(200, { nickname: '민규' }),
  ]);
  const http = createHttp(store, BASE);
  const me = await http.request<{ nickname: string }>('/me');
  assert.equal(me.nickname, '민규');
  assert.equal(calls[1].url, 'http://server.test/auth/refresh');
  assert.equal(calls[1].init.body, JSON.stringify({ refreshToken: 'R1' }));
  assert.equal((calls[2].init.headers as Record<string, string>).Authorization, 'Bearer NEW');
  assert.deepEqual(store.value, { accessToken: 'NEW', refreshToken: 'R2' });
});
test('F-01 refresh도 실패하면 토큰을 지우고 401 오류를 돌려준다', async () => {
  const store = memoryStore({ accessToken: 'OLD', refreshToken: 'R1' });
  mockFetch([
    () => json(401, { code: 'UNAUTHENTICATED', message: '로그인이 필요합니다.', details: null }),
    () => json(401, { code: 'UNAUTHENTICATED', message: '다시 로그인해 주세요.', details: null }),
  ]);
  const http = createHttp(store, BASE);
  await assert.rejects(http.request('/me'), (e: unknown) => e instanceof HttpError && e.status === 401);
  assert.equal(store.value, null);
});
test('F-01 오류 본문 { code, message, details.reason }을 그대로 넘긴다', async () => {
  mockFetch([() => json(400, { code: 'VALIDATION_FAILED', message: '입력값이 올바르지 않습니다.', details: { reason: 'EMAIL_ALREADY_USED' } })]);
  const http = createHttp(memoryStore(null), BASE);
  await assert.rejects(http.request('/auth/signup', { method: 'POST', auth: false, body: {} }), (e: unknown) =>
    e instanceof HttpError && e.status === 400 && e.code === 'VALIDATION_FAILED' && e.reason === 'EMAIL_ALREADY_USED');
});
test('F-01 입력 형식 오류의 details가 배열이어도 reason 없이 처리한다', async () => {
  mockFetch([() => json(400, { code: 'VALIDATION_FAILED', message: '입력값이 올바르지 않습니다.', details: [{ field: 'email' }] })]);
  const http = createHttp(memoryStore(null), BASE);
  await assert.rejects(http.request('/x', { auth: false }), (e: unknown) => e instanceof HttpError && e.reason === undefined);
});
test('F-01 연결 실패는 네트워크 안내 문구로 바꾼다', async () => {
  globalThis.fetch = (async () => { throw new TypeError('Network request failed'); }) as typeof fetch;
  const http = createHttp(memoryStore(null), BASE);
  await assert.rejects(http.request('/me'), /서버에 연결할 수 없어요/);
});
