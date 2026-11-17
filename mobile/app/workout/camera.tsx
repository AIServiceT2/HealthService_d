// 카메라 운동 (시안 'LivenessCheck'·'CameraSession'·'Submitting', 상태 화면 'StateInterrupted'·'StateRetry'·'StateDuplicate'). F-02·F-11 / US-01·03
// 세션 시작(API-020) → 무작위 동작 확인(021) → 관절 좌표 청크(022) → 제출(026). 일시중지·재개(023·024), 폐기(027).
//
// [임시] 카메라·자세 인식(VisionCamera + fast-tflite)이 아직 설치·선택되지 않아(STACK.md 확인할 것),
// 렙 판정은 '개발용 입력' 버튼으로 대신하고 관절 좌표는 MoveNet 17점 형식의 가짜 값(얼굴 null)을 보낸다.
// 확신도(aiConfidence)도 아직 앱이 정해서 보낸다 (API.md '노션 명세와 구현이 다른 곳': 서버 재계산 전 임시).
// 카메라 권한 거부 화면(시안 'StateCameraDenied')은 카메라 모듈이 붙을 때 권한 상태로 연결한다 (src/workout/StateView의 'cameraDenied' 그림).
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { ActivityIndicator, Alert, AppState, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import Svg, { Circle, G, Line, Path } from 'react-native-svg';
import { game } from '../../src/auth/session';
import type { Frame, Rep, StartedSession, Submission, Target } from '../../src/api/game';
import { HttpError } from '../../src/api/http';
import { Chip, Cta, DS, ErrorState, IconButton, Loading, Page, ProgressBar, T } from '../../src/design/kit';
import { StateBody } from '../../src/workout/StateView';
import { LIVENESS_LABELS, devFrame, exerciseName, statusCopy, toChunks, uuidV4 } from '../../src/game/rules';
import { errorMessage } from '../../src/game/useLoad';

type Phase = 'starting' | 'liveness' | 'counting' | 'submitting' | 'failed' | 'submitFailed' | 'duplicate';

const OTHER_ACTION: Record<string, string> = {
  RAISE_LEFT_HAND: 'RAISE_RIGHT_HAND', RAISE_RIGHT_HAND: 'RAISE_LEFT_HAND', RAISE_BOTH_HANDS: 'RAISE_LEFT_HAND',
};
const ACTIVE = ['SUBMITTED', 'PREPARED', 'PENDING_REVIEW', 'APPROVED'];
const SUBMIT_STEPS = ['기록 보내는 중 (얼굴 정보 제외)', '오늘 상한과 중복 확인', '보상 계산 중'];
const OVERLAY = 'rgba(0,0,0,0.65)';

const isDuplicate = (e: unknown) => e instanceof HttpError && e.code === 'DUPLICATE_SUBMISSION';

export default function Camera() {
  const router = useRouter();
  const params = useLocalSearchParams<{ exerciseCode?: string; reps?: string; sets?: string; targetType?: string; targetId?: string }>();
  const exerciseCode = params.exerciseCode ?? 'SQUAT';
  const goalReps = Math.max(1, Number(params.reps) || 30);
  const goalSets = Math.max(1, Number(params.sets) || 1);
  const totalGoal = goalReps * goalSets;

  const [phase, setPhase] = useState<Phase>('starting');
  const [session, setSession] = useState<StartedSession | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [livenessPassed, setLivenessPassed] = useState<boolean | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [reps, setReps] = useState<Rep[]>([]);
  const [confidence, setConfidence] = useState(0.95);
  const [paused, setPaused] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitStep, setSubmitStep] = useState(0);
  const [active, setActive] = useState<Submission | null>(null);
  const [checking, setChecking] = useState(false);

  const frames = useRef<Frame[]>([]);
  const idempotencyKey = useRef(uuidV4()); // 제출을 다시 보낼 때도 같은 키 (API-026)
  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  const start = useCallback(async () => {
    setStartError(null);
    setPhase('starting');
    try {
      const target: Target | undefined = (params.targetType === 'DUNGEON' || params.targetType === 'BOSS') && params.targetId
        ? { type: params.targetType, id: params.targetId } : undefined;
      const started = await game.startSession({ exerciseCode, goal: { reps: goalReps, sets: goalSets }, target });
      setSession(started);
      setSecondsLeft(started.liveness.timeoutSec);
      setPhase('liveness');
    } catch (e) {
      setStartError(errorMessage(e, '운동 세션을 시작하지 못했어요.'));
      setPhase(isDuplicate(e) ? 'duplicate' : 'failed');
    }
  }, [exerciseCode, params.targetId, params.targetType, goalReps, goalSets]);

  useEffect(() => { void start(); }, [start]);

  // 무작위 동작 제한 시간 표시 (판정은 서버 시각 기준, API-021)
  useEffect(() => {
    if (phase !== 'liveness' || paused) return;
    const timer = setInterval(() => setSecondsLeft((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(timer);
  }, [phase, paused]);

  // 앱이 백그라운드로 가면 촬영·추론을 멈추고 세션을 일시중지한다 (DESIGN.md 5절, API-023)
  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active' || !session) return;
      if (phaseRef.current !== 'liveness' && phaseRef.current !== 'counting') return;
      setPaused((already) => {
        if (!already) game.pauseSession(session.sessionId, 'APP_BACKGROUND').catch(() => undefined);
        return true;
      });
    });
    return () => sub.remove();
  }, [session]);

  // 중복 제출 거부: 처리 중인 내 기록을 찾아 바로 열 수 있게 한다 (API-029)
  useEffect(() => {
    if (phase !== 'duplicate') return;
    let alive = true;
    game.mySubmissions(20)
      .then((page) => { if (alive) setActive(page.items.find((s) => s.exerciseCode === exerciseCode && ACTIVE.includes(s.status)) ?? null); })
      .catch(() => undefined);
    return () => { alive = false; };
  }, [phase, exerciseCode]);

  const resume = async () => {
    if (!session) return;
    setBusy(true); setActionError(null);
    try { await game.resumeSession(session.sessionId); setPaused(false); }
    catch (e) { setActionError(errorMessage(e, '세션을 재개하지 못했어요.')); }
    finally { setBusy(false); }
  };

  // 처음부터 다시: 지금 세션을 폐기하고 새 세션을 시작한다 (불완전 기록은 제출하지 않음, DESIGN.md 5절)
  const restart = async () => {
    setBusy(true); setActionError(null);
    if (session) await game.discardSession(session.sessionId).catch(() => undefined);
    frames.current = [];
    idempotencyKey.current = uuidV4();
    setReps([]); setLivenessPassed(null); setPaused(false); setSession(null);
    setBusy(false);
    void start();
  };

  const sendLiveness = async (match: boolean) => {
    if (!session) return;
    const { challengeId, action } = session.liveness;
    setBusy(true); setActionError(null);
    try {
      const res = await game.sendLiveness(session.sessionId, {
        challengeId, detectedAction: match ? action : OTHER_ACTION[action] ?? 'NONE', score: match ? 0.95 : 0.4, detectedAt: new Date().toISOString(),
      });
      setLivenessPassed(res.passed);
      setPhase('counting');
    } catch (e) {
      setActionError(errorMessage(e, '동작 확인 결과를 보내지 못했어요.'));
    } finally { setBusy(false); }
  };

  const addRep = (counted: boolean) => {
    const now = Date.now();
    frames.current.push(devFrame(now - 600, 0), devFrame(now - 300, counted ? 1 : 0.5), devFrame(now, 0));
    setReps((prev) => [...prev, { repNo: prev.length + 1, ts: new Date(now).toISOString(), counted }]);
  };

  const countedCount = reps.filter((r) => r.counted).length;
  const missCount = reps.length - countedCount;

  const submit = async () => {
    if (!session) return;
    setPhase('submitting'); setSubmitStep(0); setActionError(null);
    try {
      // 같은 seq는 서버가 덮어쓰므로 다시 보내도 안전하다 (DATA-MODEL pose_chunk)
      const chunks = toChunks(frames.current, session.chunkSpec.maxFrames);
      for (let i = 0; i < chunks.length; i += 1) await game.uploadChunk(session.sessionId, i + 1, chunks[i]);
      setSubmitStep(1);
      const res = await game.submitSession(session.sessionId, idempotencyKey.current, {
        totalChunks: chunks.length, endedAt: new Date().toISOString(), clientRepCount: countedCount, reps, aiConfidence: confidence,
      });
      setSubmitStep(2);
      router.replace({ pathname: '/submission/[id]', params: { id: res.submissionId } });
    } catch (e) {
      // 결과가 불명확할 수 있으니 같은 키로 다시 보내게 한다 (DESIGN.md 5절: 이미 완료된 처리를 새로 만들지 않음)
      setActionError(errorMessage(e, '제출하지 못했어요. 같은 기록으로 다시 보내 주세요.'));
      setPhase(isDuplicate(e) ? 'duplicate' : 'submitFailed');
    }
  };

  // 응답을 잃었을 수 있으니 이 세션으로 접수된 기록이 있는지 먼저 확인한다 (DESIGN.md 5절)
  const checkSubmitted = async () => {
    if (!session) return;
    setChecking(true); setActionError(null);
    try {
      const page = await game.mySubmissions(20);
      const found = page.items.find((s) => s.sessionId === session.sessionId);
      if (found) { router.replace({ pathname: '/submission/[id]', params: { id: found.id } }); return; }
      setActionError('아직 접수된 기록이 없어요. 다시 보내 주세요.');
    } catch (e) {
      setActionError(errorMessage(e, '제출 상태를 확인하지 못했어요.'));
    } finally { setChecking(false); }
  };

  const quit = () => {
    const leave = async () => {
      if (session) await game.discardSession(session.sessionId).catch(() => undefined);
      if (router.canGoBack()) router.back(); else router.replace('/home');
    };
    if (!session || reps.length === 0) { void leave(); return; }
    Alert.alert('운동을 그만둘까요?', '지금까지 센 기록은 저장되지 않고 사라져요.', [
      { text: '계속하기', style: 'cancel' }, { text: '그만두기', style: 'destructive', onPress: () => void leave() },
    ]);
  };
  const leaveNow = async () => {
    if (session) await game.discardSession(session.sessionId).catch(() => undefined);
    router.replace('/home');
  };

  if (phase === 'starting') return <Page><Loading label="카메라와 세션을 준비하는 중" /></Page>;
  if (phase === 'failed') return <Page>
    <View style={{ paddingHorizontal: 8, height: 56, justifyContent: 'center' }}><IconButton name="close" label="닫기" onPress={quit} /></View>
    <ErrorState message={startError ?? '운동 세션을 시작하지 못했어요.'} onRetry={start} />
  </Page>;

  if (phase === 'duplicate') return <Page>
    <StateBody art="duplicate" title="이미 처리 중인 기록이 있습니다"
      body={'같은 시간대에 제출한 기록이 아직 처리 중이라\n새 기록을 받지 않았습니다.'}
      tag={active ? `처리 중인 기록 · ${statusCopy(active.status).chip}` : null}
      primary={active ? { title: '처리 중인 기록 보기', onPress: () => router.replace({ pathname: '/submission/[id]', params: { id: active.id } }) } : undefined}
      secondary={{ title: '홈으로', onPress: () => router.replace('/home') }} />
  </Page>;

  if (phase === 'submitFailed') return <Page>
    <StateBody art="retry" title="연결이 끊겨 보내지 못했습니다"
      body={'기록은 폰에 안전하게 남아 있습니다.\n다시 보내도 두 번 들어가지 않습니다.'}
      extra={actionError ? <Text accessibilityLiveRegion="polite" style={[T.foot, { color: DS.danger, textAlign: 'center' }]}>{actionError}</Text> : null}
      primary={{ title: '다시 보내기', onPress: submit, disabled: checking }}
      secondary={{ title: '제출 상태 확인', onPress: checkSubmitted, loading: checking }} />
  </Page>;

  if (paused) return <Page>
    <StateBody art="interrupted" title="운동이 잠시 멈췄습니다"
      body={'앱이 화면 밖으로 나가서 세기를 멈췄습니다.\n멈추기 전까지 센 횟수는 아직 제출되지 않았습니다.'}
      tag={phase === 'counting' ? `${countedCount} / ${totalGoal}회에서 멈춤` : null}
      primary={{ title: '처음부터 다시 하기', onPress: restart, loading: busy }}
      extra={<View style={{ alignItems: 'center', gap: 8 }}>
        <Cta title="이어서 하기" variant="outline" height={48} disabled={busy} onPress={resume} />
        {actionError ? <Text style={[T.foot, { color: DS.danger, textAlign: 'center' }]}>{actionError}</Text> : null}
      </View>}
      secondary={{ title: '그만하기', onPress: leaveNow, disabled: busy }} />
  </Page>;

  if (phase === 'submitting') return <Page>
    <View style={{ flex: 1, paddingTop: 72, paddingHorizontal: 20, gap: 32 }}>
      <View style={{ alignItems: 'center', gap: 14 }}>
        <Text style={[T.display, { fontSize: 72, lineHeight: 76, color: DS.accent }]}>{countedCount}</Text>
        <Text style={{ fontSize: 16, color: DS.label2 }}>회 인정 · {exerciseName(exerciseCode)}</Text>
      </View>
      <View accessibilityLiveRegion="polite" style={{ gap: 14, padding: 20, borderRadius: 16, backgroundColor: DS.bg2 }}>
        {SUBMIT_STEPS.map((label, i) => {
          const done = i < submitStep; const now = i === submitStep;
          return <View key={label} accessible accessibilityLabel={`${label}${done ? ', 완료' : now ? ', 진행 중' : ''}`}
            style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
            <View style={{ width: 22, height: 22, alignItems: 'center', justifyContent: 'center' }}>
              {done ? <StepCheck /> : now ? <ActivityIndicator size="small" color={DS.accent} />
                : <View style={{ width: 18, height: 18, borderRadius: 999, borderWidth: 2, borderColor: DS.gray2 }} />}
            </View>
            <Text style={{ fontSize: 14, color: done || now ? DS.label : DS.label2, fontWeight: now ? '600' : '400' }}>{label}</Text>
          </View>;
        })}
      </View>
      <Text style={{ fontSize: 13, lineHeight: 21, color: DS.label2, textAlign: 'center' }}>
        {'앱을 닫아도 기록은 안전하게 처리됩니다.\n연결이 끊기면 같은 기록으로 다시 보냅니다.'}
      </Text>
    </View>
  </Page>;

  const action = session?.liveness.action ?? '';
  const known = LIVENESS_LABELS[action];

  if (phase === 'liveness') return <Page bg={DS.bg} edges={['bottom']}>
    <View style={{ flex: 1, backgroundColor: DS.bg3 }}>
      <Page bg="transparent" edges={['top']} style={{ flex: 1, paddingHorizontal: 20, paddingTop: 8, paddingBottom: 20, justifyContent: 'space-between' }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <IconButton name="close" label="운동 그만두기" onPress={quit} style={{ borderRadius: 999, backgroundColor: 'rgba(0,0,0,0.6)' }} />
          <OverlayChip label="영상 저장 안 함" muted />
        </View>
        <View style={{ alignSelf: 'center', alignItems: 'center', gap: 10 }}>
          <LivenessFigure action={action} />
          <Text style={{ fontSize: 13, color: DS.label2 }}>얼굴은 인식하지 않습니다</Text>
        </View>
        <View />
      </Page>
    </View>
    <View style={{ paddingTop: 24, paddingHorizontal: 20, paddingBottom: 16, gap: 14 }}>
      <Text style={{ fontSize: 13, fontWeight: '600', color: DS.accent }}>시작 전 확인</Text>
      <Text accessibilityRole="header" style={{ fontSize: 24, lineHeight: 31, fontWeight: '700', color: DS.label }}>
        {known ? `${known.lead} ${known.accent}\n들어 주십시오` : '화면의 동작을\n따라 해 주십시오'}
      </Text>
      <Text style={{ marginTop: -6, fontSize: 14, lineHeight: 21, color: DS.label2 }}>실제 사람인지 확인하는 동작입니다. 매번 다른 동작이 나옵니다.</Text>
      <View accessible accessibilityLabel={secondsLeft > 0 ? `${secondsLeft}초 남음` : '시간이 지났어요'} style={{ gap: 6 }}>
        <ProgressBar ratio={session ? secondsLeft / session.liveness.timeoutSec : 0} track={DS.bg3} height={6} />
        <Text style={T.cap}>{secondsLeft > 0 ? `${secondsLeft}초 안에 해 주세요` : '시간이 지났어요. 지금 보내면 확인에 실패해요'}</Text>
      </View>
      {actionError ? <Text style={[T.foot, { color: DS.danger }]}>{actionError}</Text> : null}
      {/* 개발용 입력: 카메라·자세 모델이 붙으면 이 블록을 지운다 */}
      <DevPanel>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Cta title="지시 동작 함" height={44} loading={busy} style={{ flex: 1 }} onPress={() => sendLiveness(true)} />
          <Cta title="다른 동작" variant="secondary" height={44} disabled={busy} style={{ flex: 1 }} onPress={() => sendLiveness(false)} />
        </View>
      </DevPanel>
    </View>
  </Page>;

  // phase === 'counting'
  return <Page bg={DS.bg3}>
    <ScrollView contentContainerStyle={{ flexGrow: 1, paddingHorizontal: 20, paddingTop: 8, paddingBottom: 16, justifyContent: 'space-between', gap: 12 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <IconButton name="close" label="운동 그만두기" onPress={quit} style={{ borderRadius: 999, backgroundColor: OVERLAY }} />
        <OverlayChip label={`${exerciseName(exerciseCode)} · ${goalSets}세트`} />
        <View style={{ flex: 1 }} />
        <OverlayChip label="영상 저장 안 함" muted />
      </View>

      <View style={{ alignItems: 'center', gap: 4 }} accessible accessibilityLiveRegion="polite" accessibilityLabel={`인정 ${countedCount}회, 목표 ${totalGoal}회`}>
        <Text style={[T.display, { fontSize: 112, lineHeight: 116, color: DS.accent }]}>{countedCount}</Text>
        <Text style={{ fontSize: 18, fontWeight: '600', color: DS.label2 }}>/ {totalGoal}회</Text>
      </View>

      <View style={{ alignSelf: 'center' }}>
        <Svg width={170} height={200} viewBox="0 0 170 220" accessibilityLabel="관절선: 스쿼트 앉은 자세. 카메라 연결 전 자리 표시">
          <G stroke={DS.accent} strokeWidth={4} strokeLinecap="round" fill="none">
            <Line x1={70} y1={40} x2={80} y2={110} /><Line x1={72} y1={55} x2={120} y2={75} />
            <Line x1={80} y1={110} x2={130} y2={120} /><Line x1={130} y1={120} x2={125} y2={200} />
          </G>
          <G fill={DS.label}>{[[72, 55], [120, 75], [80, 110], [130, 120], [125, 200]].map(([x, y]) => <Circle key={`${x}-${y}`} cx={x} cy={y} r={5} />)}</G>
        </Svg>
      </View>

      <View style={{ gap: 12 }}>
        {livenessPassed === false && <Text style={[T.foot, { color: DS.warn, textAlign: 'center' }]}>
          시작 전 동작 확인에 실패했어요. 이 기록은 자동 승인되지 않고, 제출 뒤 확인 요청이 필요해요.
        </Text>}
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
          <View style={{ paddingVertical: 8, paddingHorizontal: 14, borderRadius: 999, backgroundColor: DS.accent }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: DS.onAccent }}>{countedCount}회 인정</Text>
          </View>
          {missCount > 0 && <View accessibilityLiveRegion="polite" style={{ paddingVertical: 8, paddingHorizontal: 14, borderRadius: 999, borderWidth: 1, borderColor: DS.warn, backgroundColor: OVERLAY }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: DS.warn }}>{missCount}회 미인정 · 더 깊이 앉기</Text>
          </View>}
        </View>
        {actionError ? <Text style={[T.foot, { color: DS.danger, textAlign: 'center' }]}>{actionError}</Text> : null}

        {/* 개발용 입력: 카메라·자세 모델이 붙으면 이 블록을 지운다 */}
        <DevPanel>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Cta title="인정 렙 +1" height={44} style={{ flex: 1 }} onPress={() => addRep(true)} />
            <Cta title="미인정 렙" variant="secondary" height={44} style={{ flex: 1 }} onPress={() => addRep(false)} />
          </View>
          <Text style={T.cap}>AI 판정 확신도 (서버 재계산 전 임시로 앱이 보냄)</Text>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Chip label="95% · 자동 승인" on={confidence === 0.95} onPress={() => setConfidence(0.95)} />
            <Chip label="70% · 확인 필요" on={confidence === 0.7} onPress={() => setConfidence(0.7)} />
          </View>
        </DevPanel>

        <Cta title="운동 끝내기" variant="secondary" height={56} style={{ backgroundColor: 'rgba(0,0,0,0.75)' }} onPress={submit} />
      </View>
    </ScrollView>
  </Page>;
}

function OverlayChip({ label, muted }: { label: string; muted?: boolean }) {
  return <View style={{ paddingVertical: 8, paddingHorizontal: 14, borderRadius: 999, backgroundColor: OVERLAY }}>
    <Text style={{ fontSize: 13, fontWeight: muted ? '400' : '600', color: muted ? DS.label2 : DS.label }}>{label}</Text>
  </View>;
}

function DevPanel({ children }: { children: ReactNode }) {
  return <View style={{ gap: 8, padding: 12, borderRadius: 14, borderWidth: 1, borderStyle: 'dashed', borderColor: DS.gray2, backgroundColor: OVERLAY }}>
    <Text style={[T.cap, { color: DS.warn }]}>개발용 입력 (카메라 연결 전)</Text>
    {children}
  </View>;
}

function StepCheck() {
  return <Svg width={22} height={22} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no">
    <Path fill={DS.accent} fillRule="evenodd" d="M12 2c5.523 0 10 4.477 10 10s-4.477 10-10 10S2 17.523 2 12 6.477 2 12 2m0 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16m3.535 4.381a1 1 0 0 1 1.498 1.32l-.083.094-5.586 5.587a1.1 1.1 0 0 1-1.46.085l-.096-.085-2.758-2.758a1 1 0 0 1 1.32-1.498l.094.084 2.122 2.121 4.95-4.95Z" />
  </Svg>;
}

/** 무작위 동작 안내 관절선. 시안은 오른손 자세이고, 왼손·양손은 같은 선을 좌우로 바꿔 그린다 */
function LivenessFigure({ action }: { action: string }) {
  const right = action === 'RAISE_RIGHT_HAND' || action === 'RAISE_BOTH_HANDS';
  const left = action === 'RAISE_LEFT_HAND' || action === 'RAISE_BOTH_HANDS';
  const lHand: [number, number] = left ? [38, 22] : [40, 110];
  const rHand: [number, number] = right ? [112, 22] : [110, 110];
  const label = LIVENESS_LABELS[action] ? `관절선: ${LIVENESS_LABELS[action].lead} ${LIVENESS_LABELS[action].accent} 든 자세` : '관절선: 선 자세';
  return <Svg width={150} height={260} viewBox="0 0 150 260" accessibilityLabel={label}>
    <G stroke={DS.accent} strokeWidth={4} strokeLinecap="round" fill="none">
      <Line x1={75} y1={60} x2={75} y2={140} />
      <Line x1={75} y1={70} x2={lHand[0]} y2={lHand[1]} />
      <Line x1={75} y1={70} x2={rHand[0]} y2={rHand[1]} />
      <Line x1={75} y1={140} x2={55} y2={240} /><Line x1={75} y1={140} x2={95} y2={240} />
    </G>
    <G fill={DS.label}>
      {[[75, 70], lHand, rHand, [75, 140], [55, 240], [95, 240]].map(([x, y]) => <Circle key={`${x}-${y}`} cx={x} cy={y} r={5} />)}
    </G>
  </Svg>;
}
