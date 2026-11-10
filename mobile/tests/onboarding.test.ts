// F-01 가입·로그인 (US 번호가 없는 MVP 전제 기능이라 F-01로 적음, 백엔드 test_f01_*와 같은 방식)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { HttpError } from '../src/api/http';
import { completeSignup } from '../src/onboarding/complete';
import type { Draft } from '../src/onboarding/draft';
import { ageOn, daysInMonth, isEmail, isInviteCode, isName, isPassword, kstToday, toIsoDate } from '../src/onboarding/rules';

test('F-01 만 나이는 생일 전날까지 한 살 적다 (14세 미만 가입 불가)', () => {
  const today = { year: 2026, month: 11, day: 11 };
  assert.equal(ageOn({ year: 2012, month: 11, day: 11 }, today), 14);
  assert.equal(ageOn({ year: 2012, month: 11, day: 12 }, today), 13);
  assert.equal(ageOn({ year: 2012, month: 12, day: 1 }, today), 13);
});
test('F-01 오늘 날짜는 KST로 센다', () => {
  assert.deepEqual(kstToday(new Date('2026-11-10T15:30:00Z')), { year: 2026, month: 11, day: 11 });
  assert.deepEqual(kstToday(new Date('2026-11-10T14:59:00Z')), { year: 2026, month: 11, day: 10 });
});
test('F-01 날짜 계산과 서버로 보내는 형식', () => {
  assert.equal(daysInMonth(2024, 2), 29);
  assert.equal(daysInMonth(2026, 2), 28);
  assert.equal(toIsoDate({ year: 2007, month: 4, day: 5 }), '2007-04-05');
});
test('F-01 입력 규칙: 이메일·비밀번호 8~64자·이름 2~10자·초대 코드 6자', () => {
  assert.ok(isEmail(' you@example.com '));
  assert.ok(!isEmail('you@example'));
  assert.ok(isPassword('12345678') && !isPassword('1234567') && !isPassword('x'.repeat(65)));
  assert.ok(isName(' 민규 ') && isName('가'.repeat(10)));
  assert.ok(!isName('가') && !isName('가'.repeat(11)) && !isName('   '));
  assert.ok(isInviteCode(' a7k2qx ') && !isInviteCode('A7K2Q'));
});

const DRAFT: Draft = {
  birthDate: '2007-04-15', gender: 'FEMALE', email: 'you@example.com', password: 'example-password',
  avatarId: 'AVATAR_SKIRT', nickname: ' 민규 ', signedUp: false,
};

function fakeApi(fail: Partial<Record<'signup' | 'login' | 'createCharacter', Error>> = {}) {
  const calls: [string, unknown][] = [];
  const step = (name: 'signup' | 'login' | 'createCharacter') => async (...args: unknown[]) => {
    calls.push([name, args.length === 1 ? args[0] : args]);
    if (fail[name]) throw fail[name];
    return undefined as never;
  };
  return { calls, api: { signup: step('signup'), login: step('login'), createCharacter: step('createCharacter') } };
}

test('F-01 이름 단계: 가입 → 로그인 → 캐릭터 생성 순서, 성별·고른 모습을 보낸다', async () => {
  const { api, calls } = fakeApi();
  let marked = false;
  const result = await completeSignup(api, DRAFT, () => { marked = true; });
  assert.deepEqual(result, { ok: true });
  assert.ok(marked);
  assert.deepEqual(calls.map((c) => c[0]), ['signup', 'login', 'createCharacter']);
  assert.deepEqual(calls[0][1], { email: 'you@example.com', password: 'example-password', nickname: '민규', birthDate: '2007-04-15', gender: 'FEMALE' });
  assert.equal(calls[2][1], 'AVATAR_SKIRT');
});
test('F-01 이미 가입된 뒤 다시 누르면 가입을 건너뛰고, 캐릭터가 이미 있으면(409) 성공으로 본다', async () => {
  const { api, calls } = fakeApi({ createCharacter: new HttpError('이미 캐릭터가 있습니다.', 409, 'INVALID_STATE') });
  const result = await completeSignup(api, { ...DRAFT, signedUp: true }, () => assert.fail('다시 가입하면 안 됨'));
  assert.deepEqual(result, { ok: true });
  assert.deepEqual(calls.map((c) => c[0]), ['login', 'createCharacter']);
});
test('F-01 이메일 중복이면 이메일 단계로 돌려보내고 가입됨으로 표시하지 않는다', async () => {
  const { api } = fakeApi({ signup: new HttpError('입력값이 올바르지 않습니다.', 400, 'VALIDATION_FAILED', 'EMAIL_ALREADY_USED') });
  let marked = false;
  const result = await completeSignup(api, DRAFT, () => { marked = true; });
  assert.equal(result.ok, false);
  assert.equal(!result.ok && result.backTo, 'signup');
  assert.ok(!marked);
});
test('F-01 생년월일이 없으면(14세 미만으로 지워짐) 서버에 보내지 않는다', async () => {
  const { api, calls } = fakeApi();
  const result = await completeSignup(api, { ...DRAFT, birthDate: null }, () => undefined);
  assert.equal(!result.ok && result.backTo, 'birth');
  assert.equal(calls.length, 0);
});
test('F-01 네트워크 오류는 그 문구를 보여 주고, 가입이 끝났으면 가입됨으로 남긴다', async () => {
  const { api } = fakeApi({ login: new HttpError('서버에 연결할 수 없어요.', undefined) });
  let marked = false;
  const result = await completeSignup(api, DRAFT, () => { marked = true; });
  assert.deepEqual(result, { ok: false, message: '서버에 연결할 수 없어요.' });
  assert.ok(marked);
});
