// 생년월일 (시안 '생년월일 (가입 1단계)'). 만 14세 미만이면 저장하지 않고 안내 화면으로 보낸다.
import { useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useDraft } from '../../src/onboarding/draft';
import { MIN_SIGNUP_AGE, ageOn, daysInMonth, kstToday, toIsoDate } from '../../src/onboarding/rules';
import { Accent, BodyHero, FadeToBlack, OB, PillButton, ProgressDots, Screen, Sub, Title } from '../../src/onboarding/ui';
import { ITEM_H, WheelColumn } from '../../src/onboarding/WheelColumn';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DEFAULT = { year: 2007, month: 4, day: 15 }; // 시안 예시 값

export default function Birth() {
  const router = useRouter();
  const { draft, update } = useDraft();
  const thisYear = kstToday().year;
  const years = useMemo(() => Array.from({ length: 100 }, (_, i) => String(thisYear - 99 + i)), [thisYear]);
  const initial = draft.birthDate
    ? { year: +draft.birthDate.slice(0, 4), month: +draft.birthDate.slice(5, 7), day: +draft.birthDate.slice(8, 10) }
    : DEFAULT;
  const [date, setDate] = useState(initial);
  const days = useMemo(() => Array.from({ length: daysInMonth(date.year, date.month) }, (_, i) => String(i + 1)), [date.year, date.month]);

  const set = (patch: Partial<typeof date>) => setDate((prev) => {
    const next = { ...prev, ...patch };
    return { ...next, day: Math.min(next.day, daysInMonth(next.year, next.month)) };
  });

  const next = () => {
    if (ageOn(date) < MIN_SIGNUP_AGE) {
      update({ birthDate: null }); // 14세 미만은 생년월일을 남기지 않는다 (시안 '입력한 생년월일은 저장하지 않았습니다')
      router.push('/onboarding/under-age');
      return;
    }
    update({ birthDate: toIsoDate(date) });
    router.push('/onboarding/gender');
  };

  return <Screen>
    <View style={styles.hero} pointerEvents="none"><BodyHero width={330} height={529} /></View>
    <FadeToBlack top={250} height={300} />
    <View style={styles.top}><ProgressDots count={4} active={1} /></View>
    <View style={styles.body}>
      <View style={styles.text}>
        <Title>생년월일을 입력하세요</Title>
        <Sub><Accent>만 14세</Accent>부터 가입할 수 있습니다.</Sub>
      </View>
      <View style={styles.wheel}>
        <View style={styles.band} pointerEvents="none" />
        <WheelColumn label="월" width={64} values={MONTHS} index={date.month - 1} onChange={(i) => set({ month: i + 1 })} />
        <WheelColumn label="일" width={48} values={days} index={date.day - 1} onChange={(i) => set({ day: i + 1 })} />
        <WheelColumn label="연도" width={72} values={years} index={years.indexOf(String(date.year))} onChange={(i) => set({ year: +years[i] })} />
      </View>
    </View>
    <View style={styles.bottom}><PillButton title="계속하기" onPress={next} /></View>
  </Screen>;
}

const styles = StyleSheet.create({
  hero: { position: 'absolute', left: 150, top: 24 },
  top: { paddingHorizontal: 24, paddingTop: 12 },
  body: { flex: 1, justifyContent: 'flex-end', paddingHorizontal: 24, gap: 12 },
  text: { gap: 8, maxWidth: 300 },
  wheel: { flexDirection: 'row', justifyContent: 'center', gap: 8, marginBottom: 16 },
  band: { position: 'absolute', left: 30, right: 30, top: ITEM_H * 2, height: ITEM_H, borderRadius: 12, backgroundColor: OB.surface },
  bottom: { paddingHorizontal: 24, paddingBottom: 24 },
});
