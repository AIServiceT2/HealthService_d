// 가입 화면 입력 규칙. 서버 규칙(API-001)과 같거나 더 좁게 둔다.

// 만 14세 미만 가입 불가 (PRD 1절, API-001 UNDER_MIN_AGE). 나이는 KST 오늘 기준.
export const MIN_SIGNUP_AGE = 14;

export function kstToday(now = new Date()): { year: number; month: number; day: number } {
  const kst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  return { year: kst.getUTCFullYear(), month: kst.getUTCMonth() + 1, day: kst.getUTCDate() };
}

export function ageOn(birth: { year: number; month: number; day: number }, today = kstToday()): number {
  const beforeBirthday = today.month < birth.month || (today.month === birth.month && today.day < birth.day);
  return today.year - birth.year - (beforeBirthday ? 1 : 0);
}

export function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

export function toIsoDate({ year, month, day }: { year: number; month: number; day: number }): string {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

// 이메일은 서버와 같은 기본 형식만 (API-001 EMAIL_PATTERN), 비밀번호 8~64자 (API-001)
export const isEmail = (value: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.trim()) && value.trim().length <= 254;
export const isPassword = (value: string) => value.length >= 8 && value.length <= 64;

// 캐릭터 이름 = 닉네임. 시안대로 2~10자 (서버는 2~12자, 2026-11-11 팀 결정으로 앱이 더 좁게)
export const NAME_MIN = 2;
export const NAME_MAX = 10;
export const isName = (value: string) => {
  const length = [...value.trim()].length;
  return length >= NAME_MIN && length <= NAME_MAX;
};

// 초대 코드: 영문·숫자 6자, 소문자도 받음 (API-013)
export const normalizeInviteCode = (value: string) => value.trim().toUpperCase();
export const isInviteCode = (value: string) => /^[A-Z0-9]{6}$/.test(normalizeInviteCode(value));

// 서버 오류 사유를 화면 문구로
export function signupErrorMessage(reason?: string): string {
  if (reason === 'EMAIL_ALREADY_USED') return '이미 가입된 이메일이에요. 로그인하거나 다른 이메일을 써 주세요.';
  if (reason === 'UNDER_MIN_AGE') return '만 14세부터 가입할 수 있어요.';
  return '입력한 내용을 다시 확인해 주세요.';
}
