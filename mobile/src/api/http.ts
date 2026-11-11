// 로그인이 필요한 API용 HTTP 클라이언트 (API.md 공통 규칙).
// - 오류 본문 { code, message, details }를 ApiError로 바꾼다 (details.reason이 있으면 reason)
// - access 토큰이 만료돼 401이면 refresh 토큰으로 한 번 재발급(API-003)하고 다시 보낸다
// 토큰 저장소는 주입한다: 앱은 SecureStore(src/auth/session.ts), 테스트는 메모리.
import { ApiError } from './client';

export type Tokens = { accessToken: string; refreshToken: string };
export type TokenStore = {
  get(): Promise<Tokens | null>;
  set(tokens: Tokens): Promise<void>;
  clear(): Promise<void>;
};

export class HttpError extends ApiError {
  constructor(message: string, status: number | undefined, public code?: string, public reason?: string) {
    super(message, status);
  }
}

type Options = { method?: string; body?: unknown; auth?: boolean; signal?: AbortSignal };

const TIMEOUT_MS = 15000;
const NETWORK_MESSAGE = '서버에 연결할 수 없어요. 네트워크와 서버 주소를 확인해 주세요.';
const TIMEOUT_MESSAGE = '응답을 기다리는 시간이 길어졌어요. 잠시 뒤 다시 시도해 주세요.';

export function createHttp(store: TokenStore, baseUrl = () => process.env.EXPO_PUBLIC_API_URL) {
  let refreshing: Promise<boolean> | null = null;

  async function send(path: string, { method = 'GET', body, auth = true, signal }: Options, token?: string) {
    const base = baseUrl()?.trim().replace(/\/$/, '');
    if (!base) throw new HttpError('서버 주소가 설정되지 않았어요. EXPO_PUBLIC_API_URL을 확인해 주세요.', undefined);
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort);
    if (signal?.aborted) controller.abort();
    const timer = setTimeout(abort, TIMEOUT_MS);
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (auth && token) headers.Authorization = `Bearer ${token}`;
    try {
      return await fetch(`${base}${path}`, {
        method, headers, signal: controller.signal, body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new HttpError(controller.signal.aborted ? TIMEOUT_MESSAGE : NETWORK_MESSAGE, undefined);
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
    }
  }

  // 동시에 여러 요청이 401을 받아도 재발급은 한 번만 한다 (refresh 토큰은 한 번 쓰면 폐기됨, API-003)
  async function refresh(): Promise<boolean> {
    refreshing ??= (async () => {
      const saved = await store.get();
      if (!saved) return false;
      const res = await send('/auth/refresh', { method: 'POST', auth: false, body: { refreshToken: saved.refreshToken } });
      if (!res.ok) { await store.clear(); return false; }
      const data = await res.json() as Tokens;
      await store.set({ accessToken: data.accessToken, refreshToken: data.refreshToken });
      return true;
    })().finally(() => { refreshing = null; });
    return refreshing;
  }

  async function request<T>(path: string, options: Options = {}): Promise<T> {
    const auth = options.auth ?? true;
    let res = await send(path, options, auth ? (await store.get())?.accessToken : undefined);
    if (auth && res.status === 401 && await refresh()) {
      res = await send(path, options, (await store.get())?.accessToken);
    }
    if (!res.ok) throw await toError(res);
    if (res.status === 204) return undefined as T;
    return await res.json() as T;
  }

  return { request, refresh };
}

async function toError(res: Response): Promise<HttpError> {
  let body: { code?: string; message?: string; details?: unknown } = {};
  try { body = await res.json(); } catch { /* 본문이 JSON이 아님 */ }
  const details = body.details;
  const reason = details && typeof details === 'object' && !Array.isArray(details)
    ? (details as { reason?: unknown }).reason : undefined;
  const fallback = res.status === 401 ? '다시 로그인해 주세요.' : '요청을 처리하지 못했어요.';
  return new HttpError(body.message ?? fallback, res.status, body.code, typeof reason === 'string' ? reason : undefined);
}
