// 성별 (시안 'GenderStep'). 선택하지 않아도 된다. '밝히지 않음'은 서버에 null로 보낸다.
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import type { Gender } from '../../src/api/account';
import { useDraft } from '../../src/onboarding/draft';
import { Cta, DS, Page } from '../../src/design/kit';
import { BodyHero, FadeToBlack } from '../../src/onboarding/ui';
import { Lime, StepDots, StepHeading } from '../../src/onboarding/parts';

type Choice = Gender | 'NONE';
const OPTIONS: { value: Choice; label: string }[] = [
  { value: 'MALE', label: '남성' }, { value: 'FEMALE', label: '여성' }, { value: 'NONE', label: '밝히지 않음' },
];

export default function GenderStep() {
  const router = useRouter();
  const { draft, update } = useDraft();
  const [choice, setChoice] = useState<Choice | null>(draft.gender);

  const next = () => {
    update({ gender: choice === 'MALE' || choice === 'FEMALE' ? choice : null });
    router.push('/onboarding/signup');
  };

  return <Page>
    <View style={styles.hero} pointerEvents="none"><BodyHero width={330} height={529} /></View>
    <FadeToBlack top={250} height={300} />
    <View style={styles.top}><StepDots count={4} active={2} /></View>
    <View style={styles.body}>
      <View style={{ maxWidth: 290 }}>
        <StepHeading title="성별을 선택해 주십시오" sub={<><Lime>선택하지 않아도</Lime> 가입할 수 있습니다.</>} />
      </View>
      <View accessibilityRole="radiogroup" accessibilityLabel="성별" style={{ gap: 14 }}>
        {OPTIONS.map((o) => {
          const on = choice === o.value;
          return <Pressable key={o.value} accessibilityRole="radio" accessibilityState={{ checked: on }} accessibilityLabel={o.label}
            onPress={() => setChoice(on ? null : o.value)} style={[styles.pill, on && { borderColor: DS.accent }]}>
            <View style={[styles.radio, on && { borderColor: DS.accent }]}><View style={[styles.radioDot, on && { backgroundColor: DS.accent }]} /></View>
            <Text style={styles.pillText}>{o.label}</Text>
          </Pressable>;
        })}
      </View>
    </View>
    <View style={styles.bottom}><Cta title="계속하기" onPress={next} /></View>
  </Page>;
}

const styles = StyleSheet.create({
  hero: { position: 'absolute', left: 150, top: 24 },
  top: { paddingHorizontal: 20, paddingTop: 12 },
  body: { flex: 1, justifyContent: 'flex-end', paddingHorizontal: 20, gap: 24, paddingBottom: 32 },
  pill: { alignSelf: 'flex-start', height: 48, paddingLeft: 14, paddingRight: 20, borderRadius: 999, borderWidth: 1.5, borderColor: DS.gray2, flexDirection: 'row', alignItems: 'center', gap: 10 },
  radio: { width: 18, height: 18, borderRadius: 999, borderWidth: 1.5, borderColor: DS.gray2, alignItems: 'center', justifyContent: 'center' },
  radioDot: { width: 8, height: 8, borderRadius: 999, backgroundColor: DS.gray2 },
  pillText: { color: DS.label, fontSize: 16, fontWeight: '600' },
  bottom: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 16 },
});
