// 캐릭터 모습 선택 (시안 'CharacterCreate', 'CharacterCreate2'). 옆으로 넘기거나 눌러서 고른다. 3번째는 잠긴 캐릭터.
// ?existing=1: 이미 로그인했지만 캐릭터가 없는 계정 → 여기서 바로 캐릭터를 만든다 (API-006).
import { useRef, useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions, type ScrollViewInstance } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { api } from '../../src/auth/session';
import { HttpError } from '../../src/api/http';
import { Cta, DS, Icon, Page } from '../../src/design/kit';
import { AVATARS, useDraft } from '../../src/onboarding/draft';
import { CharacterRing, ErrorLine, StepHeading } from '../../src/onboarding/parts';

const ITEM_W = 225; // 시안: 가운데 캐릭터와 옆 캐릭터의 중심 간격
const SLOTS = [...AVATARS.map((a) => ({ ...a, locked: false })), { id: 'LOCKED', label: '잠긴 캐릭터', image: AVATARS[0].image, locked: true }];

export default function Avatar() {
  const router = useRouter();
  const { existing } = useLocalSearchParams<{ existing?: string }>();
  const { draft, update } = useDraft();
  const { width } = useWindowDimensions();
  const scroller = useRef<ScrollViewInstance>(null);
  const [index, setIndex] = useState(Math.max(0, AVATARS.findIndex((a) => a.id === draft.avatarId)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const slot = SLOTS[index];
  const side = (width - ITEM_W) / 2;

  const goTo = (i: number) => { setIndex(i); scroller.current?.scrollTo({ x: i * ITEM_W, animated: true }); };

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

  return <Page>
    <View style={styles.ring}>
      <CharacterRing ratio={index === 0 ? 1 / 3 : 2 / 3} label={`가입 진행 ${index === 0 ? 1 : 2}/3단계`} />
    </View>
    <View style={styles.heading}>
      <StepHeading center title={'캐릭터 모습을 선택해 주십시오.\n어느 쪽이 마음에 드십니까?'} />
    </View>
    <ScrollView ref={scroller} horizontal showsHorizontalScrollIndicator={false} snapToInterval={ITEM_W} decelerationRate="fast"
      contentOffset={{ x: index * ITEM_W, y: 0 }}
      contentContainerStyle={{ paddingHorizontal: side, alignItems: 'center' }} style={{ flexGrow: 0, height: 370 }}
      onMomentumScrollEnd={(e) => setIndex(Math.max(0, Math.min(SLOTS.length - 1, Math.round(e.nativeEvent.contentOffset.x / ITEM_W))))}>
      {SLOTS.map((s, i) => {
        const on = i === index;
        return <Pressable key={s.id} onPress={() => goTo(i)} style={{ width: ITEM_W, height: 370, alignItems: 'center', justifyContent: 'center' }}
          accessibilityRole="button" accessibilityState={{ selected: on }}
          accessibilityLabel={`선택지 ${i + 1}: ${s.label}${on ? ' (선택됨)' : ''}`}>
          <Image source={s.image} resizeMode="contain"
            style={[{ width: on ? 232 : 192, height: on ? 362 : 320 }, !on && { opacity: 0.45 }, s.locked && { tintColor: '#2E2E2E', opacity: 1 }]} />
          {s.locked && <View style={styles.lock} pointerEvents="none"><Icon name="lock" size={26} color={DS.label2} /></View>}
        </Pressable>;
      })}
    </ScrollView>
    <View style={styles.dots} accessible accessibilityLabel={`캐릭터 ${SLOTS.length}개 중 ${index + 1}번째`}>
      {SLOTS.map((s, i) => <View key={s.id} style={[styles.dot, i === index && { backgroundColor: DS.accent }]} />)}
    </View>
    <View style={styles.caption}>
      <Text style={styles.captionText}>{slot.locked ? '아직 잠긴 캐릭터예요.\n다른 모습을 골라 주세요.' : '고른 모습이 전투에서\n나의 캐릭터로 등장합니다.'}</Text>
      <ErrorLine>{error}</ErrorLine>
    </View>
    <View style={styles.bottom}>
      <Cta title="선택" onPress={choose} disabled={slot.locked} loading={busy} />
    </View>
  </Page>;
}

const styles = StyleSheet.create({
  ring: { alignItems: 'center', marginTop: 16 },
  heading: { paddingHorizontal: 20, marginTop: 24, marginBottom: 8 },
  lock: { position: 'absolute', alignItems: 'center', justifyContent: 'center' },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 10, marginTop: 16 },
  dot: { width: 8, height: 8, borderRadius: 999, backgroundColor: DS.dot },
  caption: { paddingHorizontal: 20, marginTop: 17, gap: 8, alignItems: 'center' },
  captionText: { color: DS.label2, fontSize: 14, lineHeight: 18, textAlign: 'center' },
  bottom: { marginTop: 'auto', paddingHorizontal: 20, paddingTop: 12, paddingBottom: 16 },
});
