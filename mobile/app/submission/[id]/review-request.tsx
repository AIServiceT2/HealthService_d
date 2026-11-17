// 확인 요청 보내기 (시안 ReviewRequest·HoldRequest). F-04 / US-07
// 보낼 내용(API-034)을 먼저 보여 주고, 확인자 1명(API-017 지인 목록)을 고른 뒤에만 보낸다(API-035, If-Match).
// 보내기 성공 전까지 상태는 PREPARED 그대로다. '제출 취소'는 API-030 (US-06).
import { useState } from 'react';
import { Alert, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { game } from '../../../src/auth/session';
import type { Submission } from '../../../src/api/game';
import { BottomBar, Cta, DS, ErrorState, Loading, Page } from '../../../src/design/kit';
import { ANOMALY_TEXT, ChoiceRow, JointFigure, Notice, Panel, TitleBar } from '../../../src/review/ui';
import { canCancel, exerciseName, needsReview } from '../../../src/game/rules';
import { errorMessage, isStatus, useLoad } from '../../../src/game/useLoad';

const relationLabel = (relation: string) => (relation === 'GUILD_LEADER' ? '길드장' : relation === 'GUILD_MEMBER' ? '길드원' : '지인');

export default function ReviewRequest() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [picked, setPicked] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const { data, error, loading, reload } = useLoad(async () => {
    const [submission, preview, people] = await Promise.all([game.submission(id), game.sharePreview(id), game.acquaintances()]);
    return { submission, preview, people };
  }, [id]);

  if (!data && loading) return <Page><Loading label="보낼 내용을 준비하는 중" /></Page>;
  if (!data) return <Page>
    <View style={{ paddingHorizontal: 20 }}><TitleBar title="확인 요청 보내기" /></View>
    <ErrorState message={error ?? '보낼 내용을 불러오지 못했어요'} onRetry={reload} />
  </Page>;

  const { submission, preview, people } = data;
  const allowed = needsReview(submission);
  const busy = sending || canceling;

  const send = async () => {
    if (!picked) return;
    setSending(true); setSendError(null);
    try {
      await game.requestReview(submission.id, submission.version, picked);
      router.back();
    } catch (e) {
      // 결과가 불명확하면 상태부터 다시 확인한다 (DESIGN.md 5절)
      setSendError(isStatus(e, 412) || isStatus(e, 409)
        ? '기록 상태가 바뀌어서 보내지 못했어요. 다시 확인해 주세요.'
        : errorMessage(e, '보내지 못했어요.'));
      void reload();
    } finally { setSending(false); }
  };

  const doCancel = async (current: Submission) => {
    setCanceling(true); setSendError(null);
    try {
      await game.cancel(current.id, current.version);
      router.back();
    } catch (e) {
      // 승인과 동시에 오면 먼저 처리된 쪽만 반영된다 (backlog US-06)
      setSendError(isStatus(e, 412) || isStatus(e, 409)
        ? '다른 처리가 먼저 끝나서 취소하지 못했어요. 최신 상태를 확인해 주세요.'
        : errorMessage(e, '취소하지 못했어요.'));
      void reload();
    } finally { setCanceling(false); }
  };
  const cancel = () => Alert.alert('제출을 취소할까요?', '취소하면 이 기록은 보상을 받지 않고, 오늘 상한에서도 빠져요.', [
    { text: '돌아가기', style: 'cancel' },
    { text: '제출 취소', style: 'destructive', onPress: () => void doCancel(submission) },
  ]);

  return <Page>
    <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 8, paddingBottom: 24, gap: 16 }}>
      <TitleBar title="확인 요청 보내기" />

      <Text style={st.section}>보낼 내용 미리보기</Text>
      <Panel style={{ flexDirection: 'row', alignItems: 'center', gap: 16 }}>
        <View style={{ width: 110, height: 150, borderRadius: 14, backgroundColor: DS.bg3, alignItems: 'center', justifyContent: 'center' }}>
          <JointFigure width={80} height={120} label="보낼 관절선 모양을 보여 주는 예시 그림. 얼굴 없음" />
        </View>
        <View style={{ flex: 1, gap: 8 }}>
          <Text style={st.meta}>관절선 (얼굴 없음)</Text>
          <Text style={st.meta}>운동 종류 · {exerciseName(submission.exerciseCode)}</Text>
          <Text style={st.meta}>인정 {submission.countedReps}회</Text>
          <Text style={st.meta}>얼굴·나이·길드명은 보내지 않습니다</Text>
        </View>
      </Panel>
      {!preview.skeletonReplayUrl && <Notice>왼쪽 그림은 예시 모양이에요. 관절선 리플레이는 아직 준비 중이에요.</Notice>}

      {(preview.summary || preview.anomalies.length > 0) && <Panel style={{ gap: 8 }}>
        <Text style={{ color: DS.accent, fontSize: 13, fontWeight: '600' }}>AI 요약 (참고용)</Text>
        {preview.summary ? <Text style={st.ai}>{preview.summary}</Text> : null}
        {preview.anomalies.map((a, i) => <Text key={`${a.type}-${i}`} style={[st.ai, { color: ANOMALY_TEXT }]}>{a.description}</Text>)}
      </Panel>}
      {preview.painNotice ? <Notice>{preview.painNotice}</Notice> : null}

      <Text style={st.section} nativeID="reviewer-label">누구에게 보내시겠습니까? (1명)</Text>
      <View accessibilityRole="radiogroup" accessibilityLabelledBy="reviewer-label" style={{ gap: 10 }}>
        {people.length === 0
          ? <Panel style={{ gap: 4 }}>
            <Text style={{ color: DS.label, fontSize: 14, fontWeight: '600' }}>확인을 부탁할 사람이 없어요</Text>
            <Notice>지금은 내 길드의 길드장에게만 보낼 수 있어요. 길드에 가입해 주세요.</Notice>
          </Panel>
          : people.map((p) => <ChoiceRow key={p.userId} selected={picked === p.userId} onPress={() => setPicked(p.userId)}
            disabled={!allowed || busy} label={p.nickname} hint={relationLabel(p.relation)}
            leading={<View style={{ width: 40, height: 40, borderRadius: 999, backgroundColor: DS.bg3 }} />} />)}
      </View>
      {!allowed && <Notice tone="warn">이 기록은 지금 확인 요청을 보낼 수 없는 상태예요.</Notice>}
      {sendError && <Notice tone="danger">{sendError}</Notice>}
    </ScrollView>
    <BottomBar style={{ gap: 10 }}>
      <Cta title="확인 요청 보내기" height={56} loading={sending} disabled={!picked || !allowed || canceling} onPress={send} />
      {canCancel(submission.status)
        ? <Cta title="제출 취소" variant="secondary" height={56} loading={canceling} disabled={sending} onPress={cancel} />
        : <Cta title="돌아가기" variant="secondary" height={56} onPress={() => router.back()} />}
    </BottomBar>
  </Page>;
}

const st = {
  section: { color: DS.label, fontSize: 14, fontWeight: '600' },
  meta: { color: DS.label2, fontSize: 13, lineHeight: 20 },
  ai: { color: DS.label, fontSize: 13, lineHeight: 21 },
} as const;
