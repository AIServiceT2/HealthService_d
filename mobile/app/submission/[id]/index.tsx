// 제출 상세·보상 미리보기 (시안 'Preview'·'HoldPreview'·'HoldApproved', 상태 화면 'StateDailyCap'). F-02·F-03·F-04·F-05 / US-02·03·04·06
// 제출 상태(API-028), 보상 미리보기(API-032), 취소(API-030), 일일 상한(API-019). 상태의 기준은 서버 응답이다 (DESIGN.md 4절).
import { useCallback, useEffect, useState } from 'react';
import { Alert, RefreshControl, ScrollView, Text, View } from 'react-native';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { game } from '../../../src/auth/session';
import type { DailyCap, RewardPreview, Submission } from '../../../src/api/game';
import { BottomBar, Cta, DS, Divider, ErrorState, Header, Icon, Loading, Page, T, Tag } from '../../../src/design/kit';
import { StateBody } from '../../../src/workout/StateView';
import {
  AUTO_APPROVAL_THRESHOLD, canCancel, capExceeded, exerciseName, isWaiting, needsReview, pct, skillName, statusCopy, type Tone,
} from '../../../src/game/rules';
import { errorMessage, isStatus, useLoad } from '../../../src/game/useLoad';

const POLL_MS = 3000;
const HAS_PREVIEW = ['PREPARED', 'PENDING_REVIEW', 'APPROVED', 'REWARDED'];
const TAG_TONE: Record<Tone, 'accent' | 'warn' | 'danger' | 'muted'> = { lime: 'accent', warn: 'warn', danger: 'danger', muted: 'muted' };

export default function SubmissionDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [actionError, setActionError] = useState<string | null>(null);
  const [canceling, setCanceling] = useState(false);
  const [waitedMs, setWaitedMs] = useState(0);

  const { data, error, loading, reload } = useLoad(async () => {
    const submission = await game.submission(id);
    let preview: RewardPreview | null = null;
    if (HAS_PREVIEW.includes(submission.status)) preview = await game.rewardPreview(id).catch(() => null);
    let cap: DailyCap | null = null;
    if (capExceeded(submission)) {
      const caps = await game.dailyCaps().catch(() => null);
      cap = caps?.items.find((c) => c.exerciseCode === submission.exerciseCode) ?? null;
    }
    return { submission, preview, cap };
  }, [id]);

  useFocusEffect(useCallback(() => { void reload(); }, [reload]));

  // 서버가 다음 단계로 넘길 때까지 다시 조회 (계산·자동 승인·지급은 서버가 한다)
  const waiting = data ? isWaiting(data.submission) : false;
  useEffect(() => {
    if (!waiting) { setWaitedMs(0); return; }
    const timer = setInterval(() => { setWaitedMs((v) => v + POLL_MS); void reload(); }, POLL_MS);
    return () => clearInterval(timer);
  }, [waiting, reload]);

  if (!data && loading) return <Page><Header /><Loading /></Page>;
  if (!data) {
    const notFound = error?.includes('찾을 수 없') ?? false;
    return <Page><Header />
      <ErrorState message={notFound ? '기록을 찾을 수 없어요' : error ?? '기록을 불러오지 못했어요'} onRetry={reload} />
      {notFound && <BottomBar><Cta title="홈으로" variant="secondary" onPress={() => router.replace('/home')} /></BottomBar>}
    </Page>;
  }

  const { submission: sub, preview, cap } = data;
  const copy = statusCopy(sub.status);
  const snap = preview?.snapshot;
  const narrative = preview && 'narrative' in preview ? preview.narrative : null;
  const review = needsReview(sub);
  const overCap = capExceeded(sub);
  const ended = sub.status === 'CANCELED' || sub.status === 'CLOSED' || sub.status === 'REJECTED';
  const approved = sub.status === 'APPROVED' || sub.status === 'REWARDED';
  const byReviewer = approved && sub.approvalPath === 'REVIEWER';
  const autoApproved = approved && sub.approvalPath === 'AI_AUTO';
  const calculating = sub.status === 'SUBMITTED';

  const cancel = () => {
    Alert.alert('제출을 취소할까요?', '취소하면 이 기록은 보상을 받지 않고, 오늘 상한에서도 빠져요.', [
      { text: '돌아가기', style: 'cancel' },
      { text: '제출 취소', style: 'destructive', onPress: () => void doCancel(sub) },
    ]);
  };
  const doCancel = async (current: Submission) => {
    setCanceling(true); setActionError(null);
    try {
      await game.cancel(current.id, current.version);
    } catch (e) {
      // 승인과 동시에 오면 먼저 처리된 쪽만 반영된다. 최신 상태를 다시 읽고 이유를 알려 준다 (DESIGN.md 4절)
      setActionError(isStatus(e, 412) || isStatus(e, 409)
        ? '다른 처리가 먼저 끝나서 취소하지 못했어요. 최신 상태를 확인해 주세요.'
        : errorMessage(e, '취소하지 못했어요.'));
    } finally {
      setCanceling(false);
      void reload();
    }
  };

  const openResult = () => router.push({ pathname: overCap ? '/submission/[id]/result' : '/submission/[id]/replay', params: { id: sub.id } });

  const footer = <BottomBar>
    {sub.status === 'REWARDED' && <Cta title="전투 결과 보기" height={56} onPress={openResult} />}
    {review && <Cta title="확인 요청 보내기" height={56} onPress={() => router.push({ pathname: '/submission/[id]/review-request', params: { id: sub.id } })} />}
    {waiting && <Cta title="승인 확인 중…" variant="secondary" disabled onPress={() => undefined} />}
    {ended && <Cta title="새 운동 시작" onPress={() => router.replace('/workout/setup')} />}
    {canCancel(sub.status) && <Cta title="제출 취소" variant="secondary" height={56} loading={canceling} onPress={cancel} />}
    {(byReviewer || overCap) && <Cta title="홈으로" variant="secondary" height={56} onPress={() => router.replace('/home')} />}
  </BottomBar>;

  const refresh = <RefreshControl refreshing={loading && !waiting} onRefresh={reload} tintColor={DS.accent} />;
  const errorLine = actionError ? <Text accessibilityLiveRegion="polite" style={[T.foot, { color: DS.danger }]}>{actionError}</Text> : null;
  const slowCard = waiting && waitedMs >= 15000 ? <View style={{ gap: 6, padding: 16, borderRadius: 14, borderWidth: 1, borderColor: DS.warn }}>
    <Text style={{ fontSize: 15, fontWeight: '600', color: DS.warn }}>처리가 평소보다 오래 걸리고 있어요</Text>
    <Text style={T.foot}>기록은 안전하게 접수됐어요. 홈으로 갔다가 나중에 다시 확인해도 돼요.</Text>
  </View> : null;

  // 일일 상한 초과 (시안 'StateDailyCap'): 리플레이 대신 전용 안내 (DESIGN.md 4절)
  if (overCap) return <Page>
    <Header right={<Tag label={copy.chip} tone={TAG_TONE[copy.tone]} />} />
    <ScrollView contentContainerStyle={{ flexGrow: 1 }} refreshControl={refresh}>
      <StateBody art="dailyCap" title="오늘 보상을 다 받았습니다"
        body={`방금 한 ${sub.countedReps}회는 기록으로 남지만 보상과 공격은 없습니다.\n내일(KST 0시)부터 다시 받을 수 있습니다.`}
        tag={cap ? `오늘 보상 ${cap.reserved} / ${cap.cap}회` : null}
        extra={<View style={{ gap: 8, alignItems: 'center' }}><Text style={T.cap}>{copy.message}</Text>{errorLine}</View>} />
    </ScrollView>
    {footer}
  </Page>;

  // 확인자 승인 (시안 'HoldApproved'). 확인자 닉네임·보류 렙 수는 응답에 없어 넣지 않는다.
  if (byReviewer) return <Page>
    <Header />
    <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 8, paddingBottom: 24, gap: 20 }} refreshControl={refresh}>
      <View style={{ width: 72, height: 72, borderRadius: 999, backgroundColor: DS.bg2, alignItems: 'center', justifyContent: 'center' }}>
        <Icon name="check" size={34} color={DS.accent} />
      </View>
      <View style={{ gap: 8 }}>
        <Text style={{ fontSize: 14, fontWeight: '600', color: DS.accent }}>확인자 승인</Text>
        <Text accessibilityRole="header" style={{ fontSize: 24, lineHeight: 31, fontWeight: '700', color: DS.label }}>{copy.message}</Text>
      </View>
      <View style={{ padding: 20, borderRadius: 16, backgroundColor: DS.bg2, gap: 16 }}>
        <ApprovedRow label="인정 횟수" value={`${sub.countedReps}회`} accent />
        <Divider />
        {snap && <ApprovedRow label="경험치" value={`+${snap.exp}`} />}
        {snap && <ApprovedRow label={skillName(sub.exerciseCode)} value={`${snap.hitCount}타`} />}
      </View>
      <Text style={{ fontSize: 14, lineHeight: 21, color: DS.label2 }}>추가로 반영된 능력치는 24시간 뒤 확정됩니다.</Text>
      {slowCard}
      {errorLine}
    </ScrollView>
    {footer}
  </Page>;

  // 보상 미리보기 (시안 'Preview'·'HoldPreview')
  const tag = autoApproved ? <Tag label="자동 승인" tone="solid" />
    : review ? <Tag label="확인 필요" tone="warn" />
      : calculating ? <Tag label="계산 중" tone="muted" />
        : <Tag label={copy.chip} tone={TAG_TONE[copy.tone]} />;

  return <Page>
    <Header />
    <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 24, gap: 18 }} refreshControl={refresh}>
      <View style={{ gap: 6 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
          <Text accessibilityRole="header" style={{ fontSize: 24, lineHeight: 32, fontWeight: '700', color: DS.label }}>보상 미리보기</Text>
          {tag}
        </View>
        <Text style={T.foot}>{copy.message}</Text>
      </View>

      <View accessible accessibilityLabel={snap ? `${exerciseName(sub.exerciseCode)} ${sub.countedReps}회, ${skillName(sub.exerciseCode)} ${snap.hitCount}타` : undefined}
        style={{ padding: 24, borderRadius: 16, backgroundColor: DS.bg2, alignItems: 'center', gap: 10 }}>
        <Text style={{ fontSize: 14, color: DS.label2 }}>{exerciseName(sub.exerciseCode)} {sub.countedReps}회가 이렇게 바뀝니다</Text>
        <Text style={{ fontSize: 20, fontWeight: '600', color: DS.accent }}>{skillName(sub.exerciseCode)}</Text>
        {snap
          ? <Text style={[T.display, { fontSize: 64, lineHeight: 68, color: DS.accent }]}>×{snap.hitCount}</Text>
          : <Text style={{ fontSize: 17, fontWeight: '600', color: DS.label2 }}>{ended ? '보상 없음' : '계산 중'}</Text>}
      </View>

      {snap && <View style={{ flexDirection: 'row', gap: 10 }}>
        <StatTile label="경험치" value={`+${snap.exp}`} />
        <StatTile label="총 피해" value={String(snap.totalDamage)} />
        <StatTile label="보상 상자" value={`${snap.dropCount}개`} />
      </View>}

      {autoApproved && <Text style={styles.note}>AI가 바로 승인했습니다. 얻은 아이템은 24시간 동안 잠겨 있다가 사용할 수 있습니다.</Text>}
      {review && <>
        <Text style={styles.note}>
          {sub.livenessPassed !== true
            ? '시작 전 동작 확인을 통과하지 못했어요. 지인이나 길드장에게 확인을 요청하면 승인받을 수 있습니다. 얼굴은 보내지 않습니다.'
            : 'AI가 확신하지 못했습니다. 지인이나 길드장에게 확인을 요청하면 승인받을 수 있습니다. 얼굴은 보내지 않습니다.'}
        </Text>
        <View style={{ padding: 16, borderRadius: 14, backgroundColor: DS.bg2, gap: 10 }}>
          <KV label="AI 판정 확신도" value={pct(sub.confidence)} warn />
          <KV label="자동 승인 기준" value={`${pct(AUTO_APPROVAL_THRESHOLD)} (미확정)`} />
        </View>
      </>}
      {calculating && <Text style={styles.note}>보상을 계산하고 있습니다. 승인 전에는 취소할 수 있습니다.</Text>}
      {ended && <Text style={styles.note}>이 기록에는 보상과 리플레이가 없어요. 다시 운동하려면 새로 시작해 주세요.</Text>}
      {slowCard}

      {narrative && <View style={{ padding: 16, borderRadius: 16, backgroundColor: DS.bg2, gap: 8 }}>
        <Text style={{ fontSize: 13, fontWeight: '600', color: DS.accent }}>AI 전투 서사{narrative.isFallback ? ' · 기본 문구' : ''}</Text>
        <Text style={{ fontSize: 14, lineHeight: 22, color: DS.label }}>{narrative.text}</Text>
      </View>}
      {snap && <Text style={T.cap}>경험치·피해는 이 기록이 계산될 때 고정돼요. 나중에 보상 기준이 바뀌어도 그대로예요.{'\n'}AI 판정 확신도 {pct(sub.confidence)} · {snap.catalogVersion}</Text>}
      {errorLine}
    </ScrollView>
    {footer}
  </Page>;
}

const styles = { note: { fontSize: 13, lineHeight: 21, color: DS.label2 } } as const;

function StatTile({ label, value }: { label: string; value: string }) {
  return <View style={{ flex: 1, padding: 14, borderRadius: 14, backgroundColor: DS.bg2, gap: 6 }}>
    <Text style={{ fontSize: 13, color: DS.label2 }}>{label}</Text>
    <Text numberOfLines={1} adjustsFontSizeToFit style={{ fontSize: 17, fontWeight: '600', color: DS.label }}>{value}</Text>
  </View>;
}

function KV({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}>
    <Text style={{ fontSize: 14, color: DS.label2 }}>{label}</Text>
    <Text style={{ fontSize: 16, fontWeight: '600', color: warn ? DS.warn : DS.label }}>{value}</Text>
  </View>;
}

function ApprovedRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
    <Text style={{ fontSize: 14, color: DS.label2 }}>{label}</Text>
    <Text style={{ fontSize: 20, fontWeight: '700', color: accent ? DS.accent : DS.label }}>{value}</Text>
  </View>;
}
