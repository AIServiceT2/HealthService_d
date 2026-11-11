// 이름 단계의 '다음': 가입(API-001) → 로그인(API-002) → 캐릭터 생성(API-006).
// 중간에 실패해 다시 눌러도 이미 끝난 단계는 건너뛴다 (가입은 signedUp, 캐릭터는 409를 성공으로 본다).
import type { createAccountApi } from '../api/account';
import { HttpError } from '../api/http';
import type { Draft } from './draft';
import { signupErrorMessage } from './rules';

type Api = Pick<ReturnType<typeof createAccountApi>, 'signup' | 'login' | 'createCharacter'>;

export type CompleteResult =
  | { ok: true }
  | { ok: false; message: string; backTo?: 'signup' | 'birth' };

export async function completeSignup(api: Api, draft: Draft, markSignedUp: () => void): Promise<CompleteResult> {
  if (!draft.birthDate) return { ok: false, message: '생년월일을 다시 입력해 주세요.', backTo: 'birth' };
  try {
    if (!draft.signedUp) {
      await api.signup({
        email: draft.email, password: draft.password, nickname: draft.nickname.trim(),
        birthDate: draft.birthDate, gender: draft.gender,
      });
      markSignedUp();
    }
    await api.login(draft.email, draft.password);
    try {
      await api.createCharacter(draft.avatarId);
    } catch (error) {
      if (!(error instanceof HttpError && error.status === 409)) throw error; // 409 = 이미 있음
    }
    return { ok: true };
  } catch (error) {
    if (error instanceof HttpError && error.code === 'VALIDATION_FAILED') {
      return {
        ok: false, message: signupErrorMessage(error.reason),
        backTo: error.reason === 'EMAIL_ALREADY_USED' ? 'signup' : error.reason === 'UNDER_MIN_AGE' ? 'birth' : undefined,
      };
    }
    if (error instanceof HttpError && error.status === 401) {
      return { ok: false, message: '가입은 됐지만 로그인하지 못했어요. 로그인 화면에서 다시 시도해 주세요.' };
    }
    return { ok: false, message: error instanceof Error ? error.message : '잠시 뒤 다시 시도해 주세요.' };
  }
}
