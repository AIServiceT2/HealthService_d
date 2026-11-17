// 조회 상태(로딩·오류·데이터)를 한곳에서 다룬다. 다시 조회할 때는 기존 데이터를 유지한다 (DESIGN.md 5절 공통 원칙).
import { useCallback, useEffect, useRef, useState } from 'react';
import { HttpError } from '../api/http';

export function errorMessage(error: unknown, fallback = '요청을 처리하지 못했어요.') {
  return error instanceof Error && error.message ? error.message : fallback;
}

export const isStatus = (error: unknown, status: number) => error instanceof HttpError && error.status === status;

export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reload = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      const value = await load();
      if (alive.current) { setData(value); setError(null); }
    } catch (e) {
      if (alive.current) setError(errorMessage(e, '불러오지 못했어요.'));
    } finally {
      if (alive.current) setLoading(false);
    }
  }, deps);

  useEffect(() => { void reload(); }, [reload]);
  return { data, error, loading, reload, setData };
}
