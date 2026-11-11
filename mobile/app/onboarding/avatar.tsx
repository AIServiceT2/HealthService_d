// 캐릭터 모습 선택 (시안 'F-01 캐릭터 생성', '캐릭터 선택 (2번째 선택)'). 3번째는 잠긴 캐릭터.
// ?existing=1: 이미 로그인했지만 캐릭터가 없는 계정 → 여기서 바로 캐릭터를 만든다 (API-006).
import { useState } from 'react';
import { Image, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { api } from '../../src/auth/session';
import { HttpError } from '../../src/api/http';
import { AVATARS, useDraft } from '../../src/onboarding/draft';
import { ErrorText, OB, PillButton, Screen, StepRing, Sub, Title } from '../../src/onboarding/ui';

const ITEM_W = 245;
const SLOTS = [...AVATARS.map((a) => ({ ...a, locked: false })), { id: 'LOCKED', label: '잠긴 캐릭터', image: AVATARS[0].image, locked: true }];

export default function Avatar() {
  const router = useRouter();
  const { existing } = useLocalSearchParams<{ existing?: string }>();
  const { draft, update } = useDraft();
  const { width } = useWindowDimensions();
  const [index, setIndex] = useState(Math.max(0, AVATARS.findIndex((a) => a.id === draft.avatarId)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const slot = SLOTS[index];
  const side = (width - ITEM_W) / 2;

  const choose = async () => {
    if (slot.locked) return;
    const avatarId = AVATARS[index].id;
    update({ avatarId });
    if (existing !== '1') { router.push('/onboarding/name'); return; }
    setBusy(true); setError(null);
    try {
      await api.createCharacter(avatarId);
    } catch (e) {
      if (!(e instanceof HttpError && e.status === 409)) { // 409 = 이미 캐릭터가 있음 → 그대로 진행
        setError(e instanceof Error ? e.message : '캐릭터를 만들지 못했어요.');
        setBusy(false);
        return;
      }
    }
    try {
      const me = await api.me();
      router.replace(me.guildId ? '/home' : '/onboarding/guild');
    } catch {
      router.replace('/home');
    }
  };

  return <Screen>
    <View style={styles.ring}><StepRing step={index === 0 ? 1 : 2} total={3} /></View>
    <View style={styles.heading}><Title size={24} center>캐릭터 모습을 선택해 주십시오.{'\n'}어느 쪽이 마음에 드십니까?</Title></View>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} snapToInterval={ITEM_W} decelerationRate="fast"
      contentContainerStyle={{ paddingHorizontal: side, alignItems: 'center' }} style={{ flexGrow: 0, height: 380 }}
      onMomentumScrollEnd={(e) => setIndex(Math.max(0, Math.min(SLOTS.length - 1, Math.round(e.nativeEvent.contentOffset.x / ITEM_W))))}>
      {SLOTS.map((s, i) => {
        const on = i === index;
        return <View key={s.id} style={{ width: ITEM_W, alignItems: 'center' }}
          accessible accessibilityLabel={`선택지 ${i + 1}: ${s.label}${on ? ' (선택됨)' : ''}`}>
          <Image source={s.image} resizeMode="contain"
            style={[{ width: on ? 232 : 192, height: on ? 362 : 320 }, !on && { opacity: 0.45 }, s.locked && { tintColor: '#2E2E2E', opacity: 1 }]} />
        </View>;
      })}
    </ScrollView>
    <View style={styles.dots} accessibilityLabel={`캐릭터 ${SLOTS.length}개 중 ${index + 1}번째`}>
      {SLOTS.map((s, i) => <View key={s.id} style={[styles.dot, i === index && { backgroundColor: OB.accent }]} />)}
    </View>
    <View style={styles.caption}>
      <Sub center>{slot.locked ? '아직 잠긴 캐릭터예요.\n다른 모습을 골라 주세요.' : '고른 모습이 전투에서\n나의 캐릭터로 등장합니다.'}</Sub>
      <ErrorText>{error}</ErrorText>
    </View>
    <View style={styles.bottom}>
      <PillButton title="선택" onPress={choose} disabled={slot.locked} loading={busy} />
    </View>
  </Screen>;
}

const styles = StyleSheet.create({
  ring: { alignItems: 'center', marginTop: 16 },
  heading: { paddingHorizontal: 24, marginTop: 20, marginBottom: 12 },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 10, marginTop: 12 },
  dot: { width: 8, height: 8, borderRadius: 999, backgroundColor: OB.dot },
  caption: { paddingHorizontal: 24, marginTop: 16, gap: 8, alignItems: 'center' },
  bottom: { marginTop: 'auto', paddingHorizontal: 24, paddingBottom: 24 },
});
