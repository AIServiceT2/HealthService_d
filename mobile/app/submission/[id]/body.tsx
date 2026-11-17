// 몸 지도 (시안 'BodyMap'·'BodyDetail'). 결과 카드의 '몸 지도로 보기'에서 들어온다. F-06 / US-05
// 결과(API-047)의 인정 횟수와 일일 상한(API-019)만 숫자로 쓴다. 그림은 스쿼트가 쓰는 부위를 보여 주는 보조 그림이고,
// 회복률·피로도 %는 계산하지 않는다 (DESIGN.md 1절 '실루엣과 선택 UI').
import { useState } from 'react';
import { Image, Pressable, Text, View, useWindowDimensions } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Cta, DS, ErrorState, Header, Icon, Loading, Page, ProgressBar, T } from '../../../src/design/kit';
import { game } from '../../../src/auth/session';
import { exerciseName } from '../../../src/game/rules';
import { useLoad } from '../../../src/game/useLoad';

type Side = 'front' | 'back';
type Part = 'QUAD' | 'GLUTE';

// 시안 좌표(그림 300×500 기준)의 빛나는 점
const SPOTS: Record<Side, { part: Part; label: string; points: [number, number][] }> = {
  front: { part: 'QUAD', label: '허벅지 앞', points: [[107, 300], [156, 300]] },
  back: { part: 'GLUTE', label: '엉덩이', points: [[113, 246], [152, 246]] },
};
const MUSCLES: { part: Part | 'HAM'; label: string; role: string; color: string }[] = [
  { part: 'QUAD', label: '허벅지 앞', role: '주력', color: DS.accent },
  { part: 'GLUTE', label: '엉덩이', role: '주력', color: DS.accent700 },
  { part: 'HAM', label: '허벅지 뒤', role: '보조', color: DS.gray2 },
];

export default function BodyMap() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const [side, setSide] = useState<Side>('front');
  const [detail, setDetail] = useState<Part | null>(null);
  const { data, error, loading, reload } = useLoad(async () => {
    const [result, caps] = await Promise.all([game.result(id), game.dailyCaps().catch(() => null)]);
    return { card: result.card, cap: caps?.items.find((c) => c.exerciseCode === result.card.exerciseCode) ?? null };
  }, [id]);

  if (!data && loading) return <Page><Header /><Loading /></Page>;
  if (!data) return <Page><Header /><ErrorState message={error ?? '결과를 불러오지 못했어요'} onRetry={reload} /></Page>;
  const { card, cap } = data;
  const back = () => (router.canGoBack() ? router.back() : router.replace({ pathname: '/submission/[id]/result', params: { id } }));

  if (detail) return <Page edges={['top']}>
    <Image source={require('../../../assets/design/bodymap-legs.png')} resizeMode="contain"
      accessibilityLabel="하체 확대: 허벅지 앞과 엉덩이는 초록, 허벅지 뒤는 진한 초록"
      style={{ position: 'absolute', left: width - 240, top: 48, width: 340, height: 534 }} />
    <Header onBack={() => setDetail(null)} />
    <View style={{ paddingHorizontal: 28, paddingTop: 16, gap: 8, width: 260 }}>
      <Text style={{ fontSize: 14, color: DS.label2 }}>하체 · {exerciseName(card.exerciseCode)} {card.countedReps}회</Text>
      <Text accessibilityRole="header" style={{ fontSize: 24, lineHeight: 31, fontWeight: '700', color: DS.label }}>{'이번 운동에서\n많이 쓴 근육'}</Text>
    </View>
    <View style={{ paddingHorizontal: 20, marginTop: 40, gap: 14, width: 240 }}>
      {MUSCLES.map((m) => {
        const on = m.part === detail;
        return <View key={m.part} accessible accessibilityLabel={`${m.label} ${m.role}`}
          style={{ height: 76, paddingHorizontal: 22, borderRadius: 999, backgroundColor: on ? DS.bg2 : DS.bg3, flexDirection: 'row', alignItems: 'center', gap: 18 }}>
          <View style={{ width: 18, height: 18, borderRadius: 999, backgroundColor: m.color }} />
          <View>
            <Text style={{ fontSize: 13, fontWeight: '600', color: DS.label2 }}>{m.label}</Text>
            <Text style={{ fontSize: 20, lineHeight: 23, fontWeight: '700', color: on ? DS.label : DS.label2 }}>{m.role}</Text>
          </View>
        </View>;
      })}
    </View>
    <View style={{ flex: 1 }} />
    <Page edges={['bottom']} bg={DS.bg3} style={{ flex: 0, borderTopLeftRadius: 16, borderTopRightRadius: 28, paddingTop: 24, paddingHorizontal: 20, paddingBottom: 20, gap: 16 }}>
      <Text style={{ fontSize: 16, fontWeight: '600', color: DS.label, textAlign: 'center' }}>오늘 하체 운동량</Text>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16 }}>
        <View style={{ flex: 1, gap: 8 }}>
          {cap ? <>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <Text style={{ fontSize: 13, fontWeight: '600', color: DS.label2 }}>{cap.reserved}회</Text>
              <Text style={{ fontSize: 13, fontWeight: '600', color: DS.label2 }}>상한 {cap.cap}회</Text>
            </View>
            <View accessible accessibilityLabel={`오늘 ${cap.reserved}회, 상한 ${cap.cap}회`}>
              <ProgressBar ratio={cap.cap > 0 ? cap.reserved / cap.cap : 0} track={DS.bg2} />
            </View>
          </> : <Text style={{ fontSize: 13, fontWeight: '600', color: DS.label2 }}>이번 운동 {card.countedReps}회</Text>}
        </View>
        <Cta title="결과 카드로" height={56} style={{ paddingHorizontal: 18 }} onPress={back} />
      </View>
    </Page>
  </Page>;

  const spot = SPOTS[side];
  return <Page>
    <Header onBack={back} />
    <View style={{ alignItems: 'center', gap: 8, paddingHorizontal: 20 }}>
      <Text accessibilityRole="header" style={{ fontSize: 24, lineHeight: 31, fontWeight: '700', color: DS.label, textAlign: 'center' }}>{'이번 운동으로\n단련한 부위'}</Text>
      <Text style={[T.sub, { textAlign: 'center' }]}>{'빛나는 부위를 누르면\n어떤 근육을 썼는지 볼 수 있습니다'}</Text>
    </View>
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
      <View style={{ width: 300, height: 500 }}>
        <Image source={side === 'front' ? require('../../../assets/design/bodymap-front.png') : require('../../../assets/design/bodymap-back.png')}
          resizeMode="contain" style={{ width: 300, height: 500 }}
          accessibilityLabel={side === 'front' ? '앞모습 근육 지도: 허벅지 앞이 초록으로 강조됨' : '뒷모습 근육 지도: 엉덩이는 초록, 허벅지 뒤는 진한 초록으로 강조됨'} />
        {spot.points.map(([x, y]) => <Pressable key={`${x}-${y}`} accessibilityRole="button" accessibilityLabel={`${spot.label} 자세히 보기`}
          onPress={() => setDetail(spot.part)}
          style={{ position: 'absolute', left: x - 4, top: y - 4, width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }}>
          <View style={{ width: 36, height: 36, borderRadius: 999, backgroundColor: 'rgba(185, 253, 80, 0.28)', alignItems: 'center', justifyContent: 'center' }}>
            <View style={{ width: 10, height: 10, borderRadius: 999, backgroundColor: DS.label }} />
          </View>
        </Pressable>)}
      </View>
    </View>
    <Pressable accessibilityRole="button" accessibilityLabel={side === 'front' ? '뒷모습으로 돌려 보기' : '앞모습으로 돌려 보기'}
      onPress={() => setSide(side === 'front' ? 'back' : 'front')}
      style={{ alignSelf: 'center', paddingVertical: 8, paddingHorizontal: 16, alignItems: 'center', gap: 8, marginBottom: 16 }}>
      <Icon name="rotate" color={DS.label2} />
      <Text style={{ fontSize: 14, fontWeight: '600', color: DS.label }}>앞 · 뒤 돌려 보기</Text>
    </Pressable>
  </Page>;
}
