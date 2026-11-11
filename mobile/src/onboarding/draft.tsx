// 가입 단계에서 모은 값. 이름 단계에서 한꺼번에 가입(API-001)·로그인(API-002)·캐릭터 생성(API-006)한다.
// 화면을 오가도 유지되도록 앱 메모리에만 둔다 (기기에 저장하지 않음. 14세 미만이면 생년월일을 지운다).
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import type { Gender } from '../api/account';

export const AVATARS = [
  { id: 'AVATAR_PANTS', label: '바지를 입은 초록 머리 캐릭터', image: require('../../assets/onboarding/avatar-pants.png') },
  { id: 'AVATAR_SKIRT', label: '치마를 입은 초록 머리 캐릭터', image: require('../../assets/onboarding/avatar-skirt.png') },
] as const;
export type AvatarId = (typeof AVATARS)[number]['id'];

export type Draft = {
  birthDate: string | null;
  gender: Gender | null;
  email: string;
  password: string;
  avatarId: AvatarId;
  nickname: string;
  // 재시도 때 이미 끝난 단계를 다시 하지 않게 표시 (가입은 됐는데 로그인이 실패한 경우 등)
  signedUp: boolean;
};

const EMPTY: Draft = { birthDate: null, gender: null, email: '', password: '', avatarId: 'AVATAR_PANTS', nickname: '', signedUp: false };

type Ctx = { draft: Draft; update: (patch: Partial<Draft>) => void; reset: () => void };
const DraftContext = createContext<Ctx | null>(null);

export function DraftProvider({ children }: { children: ReactNode }) {
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const value = useMemo<Ctx>(() => ({
    draft,
    update: (patch) => setDraft((prev) => ({ ...prev, ...patch })),
    reset: () => setDraft(EMPTY),
  }), [draft]);
  return <DraftContext.Provider value={value}>{children}</DraftContext.Provider>;
}

export function useDraft(): Ctx {
  const ctx = useContext(DraftContext);
  if (!ctx) throw new Error('DraftProvider 밖에서 useDraft를 썼습니다.');
  return ctx;
}

export const avatarOf = (id: AvatarId) => AVATARS.find((a) => a.id === id) ?? AVATARS[0];
