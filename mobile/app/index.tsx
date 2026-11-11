// 시작 화면 (시안 '시작 화면'). 저장된 로그인이 살아 있으면 바로 홈(또는 캐릭터 만들기)으로 보낸다.
import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import Svg, { G, Path } from 'react-native-svg';
import { api, tokenStore } from '../src/auth/session';
import { HttpError } from '../src/api/http';
import { BodyHero, FadeToBlack, OB, PillButton, ProgressDots, Screen } from '../src/onboarding/ui';

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

  return <Screen>
    <Svg width={390} height={420} style={styles.lines} pointerEvents="none">
      <G stroke="#2E2E2E" strokeWidth={1} fill="none">
        <Path d="M-20 40 C 80 120, 140 20, 220 110 S 360 60, 420 150" />
        <Path d="M-10 160 C 60 90, 150 200, 240 130 S 330 230, 410 180" />
        <Path d="M40 -10 C 70 80, 20 160, 90 240" />
        <Path d="M330 -10 C 300 90, 370 170, 310 260" />
      </G>
    </Svg>
    <View style={styles.top}><ProgressDots count={3} active={0} /></View>
    <View style={styles.heading}>
      <Text style={styles.kicker}>전지적 운동 시점</Text>
      <Text accessibilityRole="header" style={styles.h1}>운동한 만큼{'\n'}<Text style={{ color: OB.accent }}>캐릭터가 싸운다</Text></Text>
    </View>
    <View style={styles.hero}>
      <BodyHero width={300} height={481} feet label="카메라가 관절 위치를 인식해 몸 위에 관절선을 그린 모습. 얼굴은 인식하지 않음" />
      <FadeToBlack top={360} height={160} />
    </View>
    <View style={styles.bottom}>
      {checking
        ? <ActivityIndicator color={OB.accent} accessibilityLabel="로그인 상태 확인 중" />
        : <>
          <PillButton title="시작하기" arrow onPress={() => router.push('/onboarding/birth')} />
          <PillButton title="이미 계정이 있습니다" variant="text" onPress={() => router.push('/login')} />
        </>}
    </View>
  </Screen>;
}

const styles = StyleSheet.create({
  lines: { position: 'absolute', left: 0, top: 0 },
  top: { paddingHorizontal: 28, paddingTop: 12 },
  heading: { alignItems: 'center', marginTop: 20, gap: 2 },
  kicker: { fontSize: 14, fontWeight: '600', letterSpacing: 2, color: OB.mutedStrong },
  h1: { marginTop: 6, fontSize: 32, fontWeight: '600', lineHeight: 40, letterSpacing: -0.5, color: '#F7F7F7', textAlign: 'center' },
  hero: { flex: 1, alignItems: 'center', justifyContent: 'flex-start', marginTop: 8 },
  bottom: { paddingHorizontal: 24, paddingBottom: 24, gap: 4 },
});
