import { useEffect, useRef, useState } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import { getSubmission, isSubmissionId, prepareSubmission, Submission } from '../../src/api/submissions';
import { ActionButton } from '../../src/components/ActionButton';
import { COLORS, SPACE } from '../../src/theme/tokens';

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
  return <ScrollView contentContainerStyle={styles.page}>
    <Text style={styles.kicker}>WORKOUT / PREVIEW</Text>
    <Text style={styles.heading}>운동이 쌓인 만큼,\n공격도 강해져요.</Text>
    {busy && <View accessibilityLiveRegion="polite" style={styles.row}><ActivityIndicator color={COLORS.primary} /><Text style={styles.muted}>기록을 확인하고 있어요…</Text></View>}
    {!!error && <View accessibilityRole="alert" style={styles.card}><Text style={styles.error}>{error}</Text><Text style={styles.muted}>처리 결과가 불확실하면 다시 조회해 주세요.</Text></View>}
    {record && <>
      <View style={styles.row}><Text style={styles.pill}>{prepared ? '계산 완료' : record.status === 'SUBMITTED' ? '접수 완료' : record.status}</Text><Text style={styles.muted}>{record.exercise_type === 'SQUAT' ? '스쿼트' : record.exercise_type}</Text></View>
      <View style={styles.card}>
        <Text style={styles.muted}>인정된 운동</Text>
        <Text style={styles.count}>{record.counted_reps}<Text style={styles.unit}> 회</Text></Text>
        <View style={styles.divider} />
        <Text style={styles.muted}>예상 타격 수</Text>
        <Text style={[styles.count, { color: COLORS.primary }]}>{prepared ? record.snapshot?.hit_count : '—'}<Text style={styles.unit}>{prepared ? ' 타' : ''}</Text></Text>
        <Text style={styles.body}>{prepared ? '서버에서 계산한 미리보기예요. 아직 승인·보상 지급 전입니다.' : record.status === 'SUBMITTED' ? '아직 보상이 계산되지 않았어요. 계산이 완료되면 타격 수를 보여드려요.' : '이 기록은 미리보기 단계를 벗어났어요. 현재 상태만 표시합니다.'}</Text>
      </View>
      {record.status === 'SUBMITTED' && <>
        <Text style={styles.muted}>개발 시연용 · 서버의 보상 계산을 수동 실행합니다.</Text>
        <ActionButton title="보상 계산 실행" disabled={busy || needsRefresh} onPress={() => void load(true)} />
        {needsRefresh && <Text style={styles.muted}>다시 조회한 뒤 계산을 재시도할 수 있어요.</Text>}
      </>}
    </>}
    {!busy && !record && !error && <Text style={styles.muted}>표시할 운동 기록이 없어요.</Text>}
    <ActionButton title="상태 다시 조회" secondary disabled={busy} onPress={() => void load()} />
    <Text selectable style={styles.identifier}>기록 ID{ '\n' }{id}</Text>
  </ScrollView>;
}
const styles = StyleSheet.create({
  page: { padding: SPACE.large, gap: SPACE.large, paddingBottom: 48 },
  kicker: { color: COLORS.primary, fontSize: 12, letterSpacing: 2, marginTop: 16 },
  heading: { color: COLORS.text, fontSize: 30, lineHeight: 42, fontWeight: '800' },
  card: { backgroundColor: COLORS.surface, borderRadius: 12, padding: SPACE.large, gap: SPACE.medium },
  row: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: SPACE.medium },
  pill: { color: COLORS.background, backgroundColor: COLORS.primary, borderRadius: 999, paddingHorizontal: 16, paddingVertical: 8, fontWeight: '700' },
  count: { color: COLORS.text, fontSize: 56, fontWeight: '800' }, unit: { fontSize: 20 },
  divider: { height: 1, backgroundColor: COLORS.border, marginVertical: 8 },
  muted: { color: COLORS.muted, fontSize: 14, lineHeight: 22 }, body: { color: COLORS.muted, fontSize: 16, lineHeight: 25 },
  error: { color: COLORS.danger, fontSize: 16, lineHeight: 24 }, identifier: { color: COLORS.muted, fontSize: 12, lineHeight: 20 },
});
