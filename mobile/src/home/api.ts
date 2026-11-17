// 홈 영역 전용 API (API.md에 '구현'으로 적혀 있으나 src/api에 클라이언트가 없는 것).
// 응답 필드는 서버 camelCase 그대로 (backend guild/schemas.py, reward/schemas.py, submission/router.py).
import type { Submission } from '../api/game';
import { http } from '../auth/session';

export type Guild = { id: string; name: string; leader: { userId: string; nickname: string }; memberCount: number };
export type GuildMember = { userId: string; nickname: string; role: 'LEADER' | 'MEMBER' };
export type Invitation = { inviteCode: string; expiresAt: string };
export type InventoryItem = { itemId: string; submissionId: string; status: 'LOCKED' | 'UNLOCKED' | string; unlockAt: string };
type Page<T> = { items: T[]; nextCursor: string | null };

const id = (value: string) => encodeURIComponent(value);

export const home = {
  // API-009 길드 생성 (이름 2~20자)
  createGuild: (name: string) =>
    http.request<{ guildId: string; name: string; leaderUserId: string }>('/guilds', { method: 'POST', body: { name } }),
  // API-010 길드 정보
  guild: (guildId: string) => http.request<Guild>(`/guilds/${id(guildId)}`),
  // API-011 길드원 목록 (최대 50명씩)
  members: (guildId: string, limit = 50) => http.request<Page<GuildMember>>(`/guilds/${id(guildId)}/members?limit=${limit}`),
  // API-012 초대 코드 발급 (길드장만)
  invite: (guildId: string) => http.request<Invitation>(`/guilds/${id(guildId)}/invitations`, { method: 'POST' }),
  // API-044 인벤토리
  inventory: async () => (await http.request<{ items: InventoryItem[] }>('/me/inventory')).items,

  // API-029 기간 지정 조회 (from·to는 KST 날짜, 둘 다 포함). 다음 쪽이 있으면 이어서 받는다 (최대 maxPages쪽)
  async submissionsBetween(from: string, to: string, maxPages = 6): Promise<{ items: Submission[]; complete: boolean }> {
    const items: Submission[] = [];
    let cursor: string | null = null;
    for (let page = 0; page < maxPages; page += 1) {
      const query: string = `/me/submissions?limit=50&from=${from}&to=${to}${cursor ? `&cursor=${id(cursor)}` : ''}`;
      const res: Page<Submission> = await http.request<Page<Submission>>(query);
      items.push(...res.items);
      cursor = res.nextCursor;
      if (!cursor) return { items, complete: true };
    }
    return { items, complete: false };
  },
};
