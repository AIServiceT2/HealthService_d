// 전투 리플레이 (시안 'Replay'). F-06 / US-05
// API-048. 콤보 수 = 결과 카드 타격 수, 최대 30초, 건너뛰기 가능. 모션 감소 설정이면 결과 카드로 바로 이동 (DESIGN.md 6절)
// 공략 대상 이름·남은 체력 %는 리플레이 응답에 없어 넣지 않는다.
import { useEffect, useMemo, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, Image, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import Svg, { Path } from 'react-native-svg';
import { game } from '../../../src/auth/session';
import { BottomBar, Cta, DS, ErrorState, Loading, Page, ProgressBar, T } from '../../../src/design/kit';
import { REPLAY_MAX_SECONDS, scheduleHits } from '../../../src/game/rules';
import { useLoad } from '../../../src/game/useLoad';

export default function ReplayScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const toResult = () => router.replace({ pathname: '/submission/[id]/result', params: { id } });
  const { data, error, loading, reload } = useLoad(() => game.replay(id), [id]);
  const [combo, setCombo] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const done = useRef(false);
  const shake = useRef(new Animated.Value(0)).current;

  const times = useMemo(() => (data ? scheduleHits(data.events) : []), [data]);
  const total = times.length > 0 ? times[times.length - 1] + 600 : 0;

  useEffect(() => {
    if (!data) return;
    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];
    (async () => {
      const reduce = await AccessibilityInfo.isReduceMotionEnabled().catch(() => false);
      if (cancelled) return;
      if (reduce || data.hitCount === 0) { toResult(); return; }
      times.forEach((ms, i) => timers.push(setTimeout(() => setCombo(i + 1), ms)));
      const started = Date.now();
      const tick = setInterval(() => setElapsed(Date.now() - started), 200);
      timers.push(tick as unknown as ReturnType<typeof setTimeout>);
      timers.push(setTimeout(() => { if (!done.current) { done.current = true; toResult(); } }, total + 900));
    })();
    return () => { cancelled = true; timers.forEach((t) => { clearTimeout(t); clearInterval(t as unknown as ReturnType<typeof setInterval>); }); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  // 타격마다 보스가 짧게 흔들린다
  useEffect(() => {
    if (combo === 0) return;
    shake.setValue(1);
    Animated.timing(shake, { toValue: 0, duration: 220, useNativeDriver: true }).start();
  }, [combo, shake]);

  const skip = () => { done.current = true; toResult(); };

  if (!data && loading) return <Page>
    <Loading label="리플레이를 준비하는 중" />
    <BottomBar><Cta title="결과 카드 보기" variant="secondary" onPress={toResult} /></BottomBar>
  </Page>;
  if (!data) return <Page>
    <ErrorState message={error ?? '리플레이를 불러오지 못했어요'} onRetry={reload} />
    <BottomBar><Cta title="결과 카드 보기" variant="secondary" onPress={toResult} /></BottomBar>
  </Page>;

  const hits = times.length;
  const ratio = total > 0 ? Math.min(1, elapsed / total) : 0;
  const shakeX = shake.interpolate({ inputRange: [0, 1], outputRange: [0, 8] });

  return <Page>
    <View style={{ flex: 1, paddingHorizontal: 20, paddingTop: 4, paddingBottom: 16, gap: 20 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text accessibilityRole="header" style={{ fontSize: 14, color: DS.label2 }}>전투 리플레이</Text>
        <Cta title="건너뛰기" variant="secondary" height={56} style={{ paddingHorizontal: 16 }} onPress={skip} />
      </View>

      <View style={{ gap: 6 }}>
        <Text style={T.foot}>적 체력</Text>
        <ProgressBar ratio={hits > 0 ? 1 - combo / hits : 1} color={DS.warn} track={DS.bg3} height={10} />
      </View>

      <View style={{ flex: 1, borderRadius: 16, backgroundColor: DS.bg2, overflow: 'hidden', flexDirection: 'row', alignItems: 'flex-end',
        justifyContent: 'space-between', paddingHorizontal: 28, paddingBottom: 48 }}>
        <Image source={require('../../../assets/design/character-stomp.png')} accessibilityLabel="내 캐릭터가 충격파 스톰프 중"
          style={{ width: 150, height: 132, marginLeft: -14 }} resizeMode="contain" />
        <Animated.Image source={require('../../../assets/design/boss.png')} accessibilityLabel="적"
          style={{ width: 160, height: 186, marginRight: -14, transform: [{ translateX: shakeX }] }} resizeMode="contain" />
        <Svg width={340} height={40} viewBox="0 0 340 40" style={{ position: 'absolute', left: 25, bottom: 30 }}
          accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <Path d="M10 30 Q 90 0 170 30 T 330 30" stroke={DS.accent} strokeWidth={3} fill="none" strokeDasharray="10 8" opacity={combo > 0 ? 1 : 0.3} />
        </Svg>
        <View style={{ position: 'absolute', top: 40, left: 0, right: 0, alignItems: 'center', gap: 4 }}
          accessible accessibilityLiveRegion="polite" accessibilityLabel={`${combo} 콤보, 총 ${data.hitCount}`}>
          <Text style={[T.display, { fontSize: 64, lineHeight: 68, color: DS.accent }]}>{combo}</Text>
          <Text style={{ fontSize: 20, fontWeight: '600', letterSpacing: 4, color: DS.label }}>COMBO</Text>
        </View>
      </View>

      <View style={{ gap: 8 }}>
        <ProgressBar ratio={ratio} color={DS.label} track={DS.bg3} height={4} />
        <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
          <Text style={T.foot}>{combo} / {data.hitCount}타</Text>
          <Text style={T.foot}>최대 {REPLAY_MAX_SECONDS}초</Text>
        </View>
      </View>
    </View>
  </Page>;
}
