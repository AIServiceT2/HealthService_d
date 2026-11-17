// 확인자 화면 · 승인 / 반려 (시안 ReviewerView·HoldReviewer·RejectReason). F-04 / US-07·08
// 자료(API-037), 승인(API-038), 반려 사유 목록(API-040), 반려(API-039). 모두 If-Match version.
// AI 요약·설명(L1·L2)은 표시만 하고, 승인·반려는 확인자가 직접 누른다. 신청자의 얼굴·나이·길드명은 받지도 보여 주지도 않는다.
import { useCallback, useState } from 'react';
import { Alert, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { game } from '../../src/auth/session';
import { BottomBar, Cta, DS, ErrorState, Loading, Page, T, Tag } from '../../src/design/kit';
import { RejectForm } from '../../src/review/RejectForm';
import { ANOMALY_TEXT, InfoPill, JointFigure, Notice, Panel, TitleBar, WarnButton } from '../../src/review/ui';
import { exerciseName, pct, statusCopy } from '../../src/game/rules';
import { errorMessage, isStatus, useLoad } from '../../src/game/useLoad';

export default function ReviewDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [mode, setMode] = useState<'view' | 'reject'>('view');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const closeReject = useCallback(() => setMode('view'), []);

  const { data, error, loading, reload } = useLoad(async () => {
    const [material, reasons] = await Promise.all([game.reviewMaterial(id), game.rejectReasons()]);
    return { material, reasons };
  }, [id]);

  if (!data && loading) return <Page><Loading label="확인 자료를 불러오는 중" /></Page>;
  if (!data) return <Page>
    <View style={{ paddingHorizontal: 20 }}><TitleBar title="확인 요청" /></View>
    <ErrorState message={error?.includes('권한') || error?.includes('확인자') ? '이 기록을 볼 수 없어요' : error ?? '확인 자료를 불러오지 못했어요'} onRetry={reload} />
  </Page>;

  const { material: m, reasons } = data;
  const open = m.status === 'PENDING_REVIEW';
  const handleError = (e: unknown, fallback: string) => {
    setActionError(isStatus(e, 412) || isStatus(e, 409) ? '이미 처리됐거나 상태가 바뀐 요청이에요. 최신 상태를 확인해 주세요.' : errorMessage(e, fallback));
    void reload();
  };

  const approve = () => Alert.alert('승인할까요?', '승인하면 신청자에게 보상이 지급돼요.', [
    { text: '돌아가기', style: 'cancel' },
    { text: '승인', onPress: async () => {
      setBusy(true); setActionError(null);
      try { await game.approveReview(m.submissionId, m.version); router.back(); }
      catch (e) { handleError(e, '승인하지 못했어요.'); }
      finally { setBusy(false); }
    } },
  ]);

  const reject = async (reasonCode: string, reasonText: string) => {
    setBusy(true); setActionError(null);
    try { await game.rejectReview(m.submissionId, m.version, reasonCode, reasonText); router.back(); }
    catch (e) { handleError(e, '반려하지 못했어요.'); }
    finally { setBusy(false); }
  };

  if (mode === 'reject' && open) return <Page>
    <RejectForm reasons={reasons} busy={busy} error={actionError} onBack={closeReject} onSubmit={reject} />
  </Page>;

  const copy = statusCopy(m.status);
  return <Page>
    <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 8, paddingBottom: 24, gap: 14 }}>
      <TitleBar />
      <View style={{ gap: 4 }}>
        <Text style={{ color: open ? DS.warn : DS.label2, fontSize: 13, fontWeight: '600' }}>{open ? '확인 요청이 왔습니다' : `이미 처리된 요청이에요 · ${copy.chip}`}</Text>
        <Text accessibilityRole="header" style={[T.display, { fontSize: 24, lineHeight: 32 }]}>이 기록을 확인해 주십시오</Text>
      </View>

      <View style={{ height: 250, borderRadius: 16, backgroundColor: DS.bg2, alignItems: 'center', justifyContent: 'center' }}>
        <JointFigure width={140} height={190} dots label="관절선 예시 그림. 신청자의 실제 기록이 아니에요. 얼굴 없음" />
        <Tag label={m.skeletonReplayUrl ? '예시 그림' : '예시 그림 · 리플레이 준비 중'} style={{ position: 'absolute', left: 14, bottom: 14 }} />
      </View>

      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        <InfoPill label={`${m.requester.nickname}님`} />
        <InfoPill label={`${exerciseName(m.exerciseCode)} · ${m.countedReps}회`} />
        <InfoPill label={`AI 확신도 ${pct(m.confidence)}`} />
      </View>

      {(m.summary || m.anomalies.length > 0) && <Panel style={{ gap: 8 }}>
        <Text style={{ color: DS.accent, fontSize: 13, fontWeight: '600' }}>AI 요약 (참고용)</Text>
        {m.summary ? <Text style={{ color: DS.label, fontSize: 13, lineHeight: 21 }}>{m.summary}</Text> : null}
        {m.anomalies.map((a, i) => <Text key={`${a.type}-${i}`} style={{ color: ANOMALY_TEXT, fontSize: 13, lineHeight: 21 }}>{a.description}</Text>)}
      </Panel>}
      {m.painNotice ? <Notice>{m.painNotice}</Notice> : null}
      <Notice>AI 요약은 참고용이에요. 승인·반려는 직접 정해요.</Notice>
      <Notice>신청자의 얼굴·나이·길드명은 보이지 않습니다.</Notice>
      {!open && <Notice>{copy.message}</Notice>}
      {actionError && <Notice tone="danger">{actionError}</Notice>}
    </ScrollView>
    {open && <BottomBar style={{ flexDirection: 'row', gap: 10 }}>
      <WarnButton title="반려" disabled={busy} onPress={() => { setActionError(null); setMode('reject'); }} style={{ flex: 1 }} />
      <Cta title="승인" height={56} loading={busy} onPress={approve} style={{ flex: 1 }} />
    </BottomBar>}
  </Page>;
}
