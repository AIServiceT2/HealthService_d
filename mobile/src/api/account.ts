// 회원·캐릭터·길드 API (API-001·002·004·005·006·013, 추천 길드 [추가]).
// 응답 필드는 서버 camelCase 그대로 쓴다.
import type { createHttp, Tokens } from './http';

type Http = ReturnType<typeof createHttp>;

export type Gender = 'MALE' | 'FEMALE';
export type SignupInput = { email: string; password: string; nickname: string; birthDate: string; gender: Gender | null };
export type Me = { id: string; nickname: string; guildId: string | null; isGuildLeader: boolean; hasCharacter: boolean };
export type RecommendedGuild = { guildId: string; name: string; memberCount: number };
type LoginResponse = Tokens & { accessTokenExpiresIn: number; user: { id: string; nickname: string; guildId: string | null } };

export function createAccountApi(http: Http, saveTokens: (tokens: Tokens) => Promise<void>) {
  return {
    signup: (input: SignupInput) =>
      http.request<{ userId: string }>('/auth/signup', { method: 'POST', auth: false, body: { provider: 'EMAIL', ...input } }),
    async login(email: string, password: string) {
      const data = await http.request<LoginResponse>('/auth/login', {
        method: 'POST', auth: false, body: { provider: 'EMAIL', email, password },
      });
      await saveTokens({ accessToken: data.accessToken, refreshToken: data.refreshToken });
      return data.user;
    },
    logout: (refreshToken: string) =>
      http.request<void>('/auth/logout', { method: 'POST', body: { refreshToken } }),
    me: () => http.request<Me>('/me'),
    createCharacter: (avatarId: string) =>
      http.request<{ userId: string; avatarId: string | null }>('/characters', { method: 'POST', body: { avatarId } }),
    recommendedGuilds: async () => (await http.request<{ items: RecommendedGuild[] }>('/guilds/recommended')).items,
    joinGuildByCode: (inviteCode: string) =>
      http.request<{ guildId: string }>('/guilds/join', { method: 'POST', body: { inviteCode } }),
    joinGuild: (guildId: string) =>
      http.request<{ guildId: string }>(`/guilds/${encodeURIComponent(guildId)}/members/me`, { method: 'POST' }),
  };
}
