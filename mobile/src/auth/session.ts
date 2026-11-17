// 앱 전체가 쓰는 API 객체. 토큰은 기기의 보안 저장소(expo-secure-store)에만 둔다
// (STACK.md '추가 검증 항목': 안전한 토큰 저장. 저장 방식 최종 결정은 팀 확인 필요).
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { createAccountApi } from '../api/account';
import { createGameApi } from '../api/game';
import { createHttp, type TokenStore, type Tokens } from '../api/http';

const KEY = 'jeonunsi.tokens';

// 웹 미리보기(npx expo start --web) 전용: expo-secure-store는 웹 구현이 없어 localStorage에 둔다.
// 웹은 배포하지 않으므로(STACK.md) 화면 확인용으로만 쓴다. Android는 아래 SecureStore를 쓴다.
const webStore: TokenStore = {
  async get() {
    const raw = globalThis.localStorage?.getItem(KEY);
    if (!raw) return null;
    try { return JSON.parse(raw) as Tokens; } catch { return null; }
  },
  set: async (tokens) => { globalThis.localStorage?.setItem(KEY, JSON.stringify(tokens)); },
  clear: async () => { globalThis.localStorage?.removeItem(KEY); },
};

export const tokenStore: TokenStore = Platform.OS === 'web' ? webStore : {
  async get() {
    const raw = await SecureStore.getItemAsync(KEY);
    if (!raw) return null;
    try { return JSON.parse(raw) as Tokens; } catch { return null; }
  },
  set: (tokens) => SecureStore.setItemAsync(KEY, JSON.stringify(tokens)),
  clear: () => SecureStore.deleteItemAsync(KEY),
};

export const http = createHttp(tokenStore);
export const api = createAccountApi(http, tokenStore.set);
export const game = createGameApi(http);

export async function logout() {
  const saved = await tokenStore.get();
  if (saved) await api.logout(saved.refreshToken).catch(() => undefined); // 서버 실패와 관계없이 기기에서는 지운다
  await tokenStore.clear();
}
