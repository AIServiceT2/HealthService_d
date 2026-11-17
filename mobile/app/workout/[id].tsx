// 개발용 보상 미리보기 (첫 기능 US-02 화면, src/api/submissions 목데이터 지원). 디자인 키트로 모양만 맞춤.
import { useEffect, useRef, useState } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import { IS_MOCK_MODE, getSubmission, isSubmissionId, prepareSubmission, Submission } from '../../src/api/submissions';
import { Cta, DS, Divider, Header, Page, T, Tag } from '../../src/design/kit';

export default function Preview() {
  const params = useLocalSearchParams<{ id: string }>(); const id = params.id;
  const [record, setRecord] = useState<Submission | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const active = useRef<AbortController | null>(null);
  const load = async (calculate = false) => {
    if (active.current) return;
    if (typeof id !== 'string' || !isSubmissionId(id)) { setError('올바른 제출건 ID가 아니에요.'); return; }
    const controller = new AbortController(); active.current = controller;
    setBusy(true); setError('');
    try {
      const result = await (calculate ? prepareSubmission(id, controller.signal) : getSubmission(id, controller.signal));
      if (!controller.signal.aborted) { setRecord(result); setNeedsRefresh(false); }
    } catch (cause) {
      if (!controller.signal.aborted) {
        setError(cause instanceof Error ? cause.message : '기록을 확인하지 못했어요.');
        // POST 응답 유실 시 계산 재요청보다 서버 상태 조회를 먼저 수행한다.
        setNeedsRefresh(true);
      }
    } finally {
      if (active.current === controller) { active.current = null; setBusy(false); }
    }
  };
  useEffect(() => {
    setRecord(null); setNeedsRefresh(false); void load();
    return () => { active.current?.abort(); active.current = null; };
  }, [id]);
  const prepared = record?.status === 'PREPARED';
  return <Page>
    <Header title="보상 미리보기" />
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={styles.kicker}>{IS_MOCK_MODE ? '목데이터 · 실제 기록이 아니에요' : '운동 기록 · 보상 미리보기'}</Text>
      <Text accessibilityRole="header" style={styles.heading}>운동이 쌓인 만큼,{'\n'}공격도 강해져요.</Text>
      {busy && <View accessibilityLiveRegion="polite" style={styles.row}><ActivityIndicator color={DS.accent} /><Text style={T.foot}>기록을 확인하고 있어요…</Text></View>}
      {!!error && <View accessibilityRole="alert" style={styles.card}><Text style={styles.error}>{error}</Text><Text style={T.foot}>처리 결과가 불확실하면 다시 조회해 주세요.</Text></View>}
      {record && <>
        <View style={styles.row}><Tag label={STATUS_TEXT[record.status] ?? record.status} tone={prepared ? 'solid' : 'muted'} /><Text style={T.foot}>{record.exercise_type === 'SQUAT' ? '스쿼트' : record.exercise_type}</Text></View>
        <View style={styles.card}>
          <Text style={T.foot}>인정된 운동</Text>
          <Text style={styles.count}>{record.counted_reps}<Text style={styles.unit}> 회</Text></Text>
          <Divider />
          <Text style={T.foot}>예상 타격 수</Text>
          <Text style={[styles.count, { color: DS.accent }]}>{prepared ? record.snapshot?.hit_count : '—'}<Text style={styles.unit}>{prepared ? ' 타' : ''}</Text></Text>
          <Text style={T.sub}>{prepared ? (IS_MOCK_MODE ? '목데이터 계산 예시예요. 실제 보상은 지급되지 않아요.' : '서버에서 계산한 미리보기예요. 승인과 보상 지급은 아직이에요.') : record.status === 'SUBMITTED' ? '계산이 끝나면 타격 수를 보여드려요.' : '이 기록은 미리보기 단계를 벗어났어요. 현재 상태만 표시합니다.'}</Text>
        </View>
        {record.status === 'SUBMITTED' && <>
          <Text style={T.foot}>{IS_MOCK_MODE ? '목데이터의 보상 계산을 실행합니다.' : '개발 시연용 · 서버의 보상 계산을 수동 실행합니다.'}</Text>
          <Cta title="보상 계산 실행" disabled={busy || needsRefresh} onPress={() => void load(true)} />
          {needsRefresh && <Text style={T.foot}>다시 조회한 뒤 계산을 재시도할 수 있어요.</Text>}
        </>}
      </>}
      {!busy && !record && !error && <Text style={T.foot}>표시할 운동 기록이 없어요.</Text>}
      <Cta title="상태 다시 조회" variant="outline" disabled={busy} onPress={() => void load()} />
      <Text selectable style={T.cap}>기록 ID{'\n'}{id}</Text>
    </ScrollView>
  </Page>;
}
// DESIGN.md 4절 화면 문구 [제안]
const STATUS_TEXT: Record<string, string> = {
  SUBMITTED: '운동 기록을 접수했어요. 보상을 계산 중이에요',
  PREPARED: '보상 미리보기 · 아직 지급 전이에요',
  PENDING_REVIEW: '확인자의 검토를 기다리고 있어요',
  APPROVED: '승인됐어요. 보상을 반영 중이에요',
  REWARDED: '보상이 반영됐어요',
  CANCELED: '제출이 취소됐어요',
  REJECTED: '반려됐어요. 기록을 종료 중이에요',
  CLOSED: '종료된 기록이에요',
};
const styles = StyleSheet.create({
  page: { paddingHorizontal: 20, paddingBottom: 32, gap: 18 },
  kicker: { fontSize: 13, fontWeight: '600', color: DS.accent, marginTop: 8 },
  heading: { fontSize: 24, lineHeight: 32, fontWeight: '800', color: DS.label },
  card: { backgroundColor: DS.bg2, borderRadius: 16, padding: 20, gap: 8 },
  row: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8 },
  count: { fontSize: 48, lineHeight: 56, fontWeight: '800', color: DS.label }, unit: { fontSize: 16, fontWeight: '400', color: DS.label2 },
  error: { fontSize: 16, lineHeight: 24, color: DS.danger },
});
