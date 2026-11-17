// 운동 선택 (시안 'WorkoutSelectCard'). F-02·F-10 / US-01
// 운동 목록(API-018). MVP 운동은 스쿼트 1종이라 나머지 카드는 잠금·'준비 중'으로 보여 주고 고를 수 없다 (mvp-scope.md 제외 표).
// 다음: 튜토리얼(/workout/tutorial) → 목표 설정(/workout/goal) → 카메라(/workout/camera)
import { useMemo, useRef, useState } from 'react';
import { Image, Pressable, ScrollView, Text, View, useWindowDimensions, type NativeScrollEvent, type NativeSyntheticEvent, type ScrollViewInstance } from 'react-native';
import { useRouter } from 'expo-router';
import { game } from '../../src/auth/session';
import { BottomBar, Cta, DS, ErrorState, Header, Icon, Loading, Page, T } from '../../src/design/kit';
import { useLoad } from '../../src/game/useLoad';

type Group = 'LOWER' | 'UPPER' | 'CORE';
type Card = { key: string; name: string; part: string | null; code: string | null };

const TABS: { id: Group; label: string }[] = [
  { id: 'LOWER', label: '하체 운동' }, { id: 'UPPER', label: '상체 운동' }, { id: 'CORE', label: '코어 운동' },
];
const CARD_W = 216;
const GAP = 18;

export default function WorkoutSelect() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const [group, setGroup] = useState<Group>('LOWER');
  const [index, setIndex] = useState(1);
  const scroller = useRef<ScrollViewInstance>(null);
  const { data, error, loading, reload } = useLoad(() => game.exercises(), []);

  const squat = data?.items.find((e) => e.code === 'SQUAT') ?? null;
  // 잠금 카드는 이름만 보여 준다. 난이도·목표 값은 정해지지 않아 넣지 않는다.
  const cards = useMemo<Card[]>(() => ({
    LOWER: [
      { key: 'lunge', name: '런지', part: '허벅지', code: null },
      { key: 'squat', name: '스쿼트', part: '허벅지 앞', code: squat ? squat.code : null },
      { key: 'rope', name: '줄넘기', part: '종아리', code: null },
    ],
    UPPER: [{ key: 'pushup', name: '푸시업', part: null, code: null }],
    CORE: [{ key: 'plank', name: '플랭크', part: null, code: null }],
  }[group]), [group, squat]);

  const side = Math.max(16, (width - CARD_W) / 2);
  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    setIndex(Math.max(0, Math.min(cards.length - 1, Math.round(e.nativeEvent.contentOffset.x / (CARD_W + GAP)))));
  };
  const pickTab = (g: Group) => {
    setGroup(g);
    const start = g === 'LOWER' ? 1 : 0;
    setIndex(start);
  };

  if (!data && loading) return <Page><Header /><Loading label="운동 목록을 불러오는 중" /></Page>;
  if (!data) return <Page><Header /><ErrorState message={error ?? '운동 목록을 불러오지 못했어요'} onRetry={reload} /></Page>;

  const next = () => {
    if (!squat) return;
    router.push({ pathname: '/workout/tutorial', params: { exerciseCode: squat.code } });
  };

  return <Page>
    <Header />
    <View accessibilityRole="tablist" style={{ height: 68, flexDirection: 'row', justifyContent: 'space-around', alignItems: 'center',
      paddingHorizontal: 16, borderBottomWidth: 1, borderBottomColor: DS.bg2 }}>
      {TABS.map((t) => {
        const on = t.id === group;
        return <Pressable key={t.id} accessibilityRole="tab" accessibilityState={{ selected: on }} onPress={() => pickTab(t.id)}
          style={{ minHeight: 44, paddingHorizontal: 4, alignItems: 'center', justifyContent: 'center', gap: 6 }}>
          <Text style={{ fontSize: 16, fontWeight: on ? '700' : '500', color: on ? DS.label : DS.gray }}>{t.label}</Text>
          <View style={{ width: on ? 60 : 28, height: 3, borderRadius: 999, backgroundColor: on ? DS.accent : 'transparent' }} />
        </Pressable>;
      })}
    </View>

    <View style={{ marginHorizontal: 32, marginTop: 20, height: 44, borderRadius: 12, backgroundColor: DS.bg2, alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ fontSize: 13, fontWeight: '700', color: DS.label }}>한 번에 하나만 선택할 수 있습니다</Text>
    </View>

    <ScrollView ref={scroller} key={group} horizontal showsHorizontalScrollIndicator={false} snapToInterval={CARD_W + GAP} decelerationRate="fast"
      onLayout={() => scroller.current?.scrollTo({ x: (group === 'LOWER' ? 1 : 0) * (CARD_W + GAP), animated: false })} onMomentumScrollEnd={onScroll}
      contentContainerStyle={{ paddingHorizontal: side, gap: GAP, alignItems: 'center' }} style={{ flexGrow: 0, marginTop: 32 }}>
      {cards.map((c) => <ExerciseCard key={c.key} card={c} selected={c.code != null} />)}
    </ScrollView>

    <View accessibilityLabel={`${TABS.find((t) => t.id === group)?.label} ${cards.length}개 중 ${index + 1}번째`}
      style={{ flexDirection: 'row', justifyContent: 'center', gap: 8, marginTop: 20 }}>
      {cards.map((c, i) => <View key={c.key} style={{ width: i === index ? 22 : 8, height: 8, borderRadius: 999, backgroundColor: i === index ? DS.accent : '#48484A' }} />)}
    </View>

    <View style={{ flex: 1 }} />
    <BottomBar>
      <Cta title="튜토리얼로 넘어가기" disabled={!squat} onPress={next} />
    </BottomBar>
  </Page>;
}

function ExerciseCard({ card, selected }: { card: Card; selected: boolean }) {
  const locked = card.code == null;
  return <View accessible accessibilityLabel={locked ? `${card.name}, 준비 중` : `${card.name}, 선택됨`}
    accessibilityState={{ selected, disabled: locked }}
    style={{ width: CARD_W, height: 404, borderRadius: 26, borderWidth: 2, borderColor: selected ? DS.accent : '#48484A',
      overflow: 'hidden', backgroundColor: '#F7F7F7', opacity: locked ? 0.6 : 1 }}>
    <View style={{ height: 248, alignItems: 'center', justifyContent: 'flex-end', paddingBottom: 14 }}>
      <Image source={locked ? require('../../assets/onboarding/avatar-skirt.png') : require('../../assets/onboarding/avatar-pants.png')}
        style={{ width: 150, height: 200 }} resizeMode="contain" />
    </View>
    <View style={{ position: 'absolute', right: 12, top: 12, width: 30, height: 30, borderRadius: 999, alignItems: 'center', justifyContent: 'center',
      backgroundColor: locked ? '#D1D1D6' : DS.accent }}>
      <Icon name={locked ? 'lock' : 'check'} size={locked ? 14 : 15} color={locked ? '#3A3A3C' : DS.onAccent} />
    </View>
    <View style={{ flex: 1, marginTop: -14, borderTopLeftRadius: 26, borderTopRightRadius: 26, backgroundColor: DS.bg,
      paddingTop: 16, paddingHorizontal: 12, paddingBottom: 14, alignItems: 'center', gap: 8 }}>
      <Text style={[T.display, { fontSize: 17 }]}>{card.name}</Text>
      {locked
        ? <View style={{ height: 24, paddingHorizontal: 10, borderRadius: 999, backgroundColor: DS.bg3, justifyContent: 'center' }}>
          <Text style={{ fontSize: 13, color: DS.label }}>준비 중</Text>
        </View>
        : <Text style={{ fontSize: 13, color: DS.label }}>30회 / 1세트</Text>}
      {card.part ? <Text style={{ fontSize: 13, color: DS.label }}>단련 부위 · {card.part}</Text> : null}
    </View>
  </View>;
}
