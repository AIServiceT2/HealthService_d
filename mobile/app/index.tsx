// 시작 화면 (시안 'Start'). 저장된 로그인이 살아 있으면 바로 홈(또는 캐릭터 만들기)으로 보낸다.
// 시안의 '시작하기'는 소개 화면(Intro1)으로 가지만 소개 화면은 MVP 밖이라 바로 생년월일 단계로 간다.
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import Svg, { G, Path } from 'react-native-svg';
import { api, tokenStore } from '../src/auth/session';
import { HttpError } from '../src/api/http';
import { DS, Page } from '../src/design/kit';
import { BodyHero, FadeToBlack } from '../src/onboarding/ui';
import { QuietButton, StepDots } from '../src/onboarding/parts';

const ARROW = 'm14.707 5.636 5.657 5.657a1 1 0 0 1 0 1.414l-5.657 5.657a1 1 0 0 1-1.414-1.414l3.95-3.95H4a1 1 0 1 1 0-2h13.243l-3.95-3.95a1 1 0 1 1 1.414-1.414Z';

export default function Start() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        if (await tokenStore.get()) {
          const me = await api.me();
          if (!alive) return;
          router.replace(me.hasCharacter ? '/home' : { pathname: '/onboarding/avatar', params: { existing: '1' } });
          return;
        }
      } catch (error) {
        // 토큰이 만료·폐기됐으면 지우고 시작 화면을 보여 준다. 네트워크 오류면 토큰은 둔다
        if (error instanceof HttpError && error.status === 401) await tokenStore.clear();
      }
      if (alive) setChecking(false);
    })();
    return () => { alive = false; };
  }, [router]);

  return <Page>
    <Svg width={390} height={420} style={styles.lines} pointerEvents="none">
      <G stroke="#2E2E2E" strokeWidth={1} fill="none">
        <Path d="M-20 40 C 80 120, 140 20, 220 110 S 360 60, 420 150" />
        <Path d="M-10 160 C 60 90, 150 200, 240 130 S 330 230, 410 180" />
        <Path d="M40 -10 C 70 80, 20 160, 90 240" />
        <Path d="M330 -10 C 300 90, 370 170, 310 260" />
      </G>
    </Svg>
    <View style={styles.top}><StepDots count={3} active={0} /></View>
    <View style={styles.heading}>
      <Text style={styles.kicker}>전지적 운동 시점</Text>
      <Text accessibilityRole="header" style={styles.h1}>운동한 만큼{'\n'}<Text style={{ color: DS.accent }}>캐릭터가 싸운다</Text></Text>
    </View>
    <View style={styles.hero}>
      <BodyHero width={300} height={481} feet label="카메라가 관절 위치를 인식해 몸 위에 관절선을 그린 모습. 얼굴은 인식하지 않음" />
      <FadeToBlack top={360} height={160} />
    </View>
    <View style={styles.bottom}>
      {checking
        ? <ActivityIndicator color={DS.accent} accessibilityLabel="로그인 상태 확인 중" style={{ height: 60 }} />
        : <>
          <Pressable accessibilityRole="button" accessibilityLabel="시작하기" onPress={() => router.push('/onboarding/birth')} style={styles.start}>
            <Text style={styles.startText}>시작하기</Text>
            <View style={styles.arrow}>
              <Svg width={18} height={18} viewBox="0 0 24 24" fill="none"><Path fill={DS.accent} fillRule="evenodd" d={ARROW} /></Svg>
            </View>
          </Pressable>
          {/* 시안 시작 화면에는 없지만 기존 계정으로 들어갈 길이 필요해 남겨 둔다 [팀 확인 필요] */}
          <QuietButton title="이미 계정이 있습니다" onPress={() => router.push('/login')} />
        </>}
    </View>
  </Page>;
}

const styles = StyleSheet.create({
  lines: { position: 'absolute', left: 0, top: 0 },
  top: { paddingHorizontal: 28, paddingTop: 12 },
  heading: { alignItems: 'center', marginTop: 24, gap: 2 },
  kicker: { fontSize: 14, fontWeight: '600', letterSpacing: 2, color: '#CCCCCC' },
  h1: { marginTop: 6, fontSize: 30, lineHeight: 38, fontWeight: '800', letterSpacing: -0.5, color: '#F7F7F7', textAlign: 'center' },
  hero: { flex: 1, alignItems: 'center', marginTop: 16 },
  bottom: { paddingHorizontal: 24, paddingBottom: 16, gap: 4 },
  start: { height: 60, borderRadius: 999, backgroundColor: DS.accent, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingLeft: 28, paddingRight: 10 },
  startText: { color: DS.onAccent, fontSize: 17, fontWeight: '800' },
  arrow: { width: 40, height: 40, borderRadius: 999, backgroundColor: '#000', alignItems: 'center', justifyContent: 'center' },
});
