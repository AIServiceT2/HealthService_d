export class ApiError extends Error {
  constructor(message: string, public status?: number) { super(message); }
}

export async function request(path: string, method = 'GET', signal?: AbortSignal): Promise<unknown> {
  const base = process.env.EXPO_PUBLIC_API_URL?.trim().replace(/\/$/, '');
  if (!base) throw new ApiError('서버 주소가 설정되지 않았어요. EXPO_PUBLIC_API_URL을 확인해 주세요.');
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener('abort', abort);
  if (signal?.aborted) controller.abort();
  const timeout = setTimeout(abort, 15000);
  try {
    const response = await fetch(`${base}${path}`, { method, signal: controller.signal });
    if (!response.ok) {
      const messages: Record<number, string> = {
        404: '기록을 찾을 수 없어요. 제출건 ID를 확인해 주세요.',
        409: '이미 처리된 기록이에요. 최신 상태를 다시 확인해 주세요.',
        500: '서버에서 계산 또는 조회에 실패했어요. 상태를 다시 확인해 주세요.',
      };
      throw new ApiError(messages[response.status] ?? '요청을 처리하지 못했어요.', response.status);
    }
    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) throw new ApiError('응답을 기다리는 시간이 길어졌어요. 다시 조회해 처리 결과를 확인해 주세요.');
    throw new ApiError('서버에 연결할 수 없어요. 네트워크와 서버 주소를 확인해 주세요.');
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}
