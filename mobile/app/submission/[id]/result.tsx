// 결과 카드·서사·교정 코멘트 (시안 'ResultCard', 상한 초과는 'StateDailyCap'). F-05·F-06·F-13 / US-04·05
// API-047. 수치는 결과 카드에만 두고, AI 글(L3 전투 이야기·L4 다음에 고칠 점)은 아래 카드로 영역을 나눈다.
// 몸 그림은 이번 운동 부위를 보여 주는 보조 그림이다. 회복률·피로도 %는 계산하지 않는다 (DESIGN.md 1절).
import { Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import Svg, { Circle, Rect } from 'react-native-svg';
import { game } from '../../../src/auth/session';
import { BottomBar, Cta, DS, ErrorState, Header, Loading, Page, T } from '../../../src/design/kit';
import { StateBody } from '../../../src/workout/StateView';
import { exerciseName, shortTime, skillName } from '../../../src/game/rules';
import { useLoad } from '../../../src/game/useLoad';

const PROTECT_MS = 24 * 60 * 60 * 1000;

export default function ResultScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { data, error, loading, reload } = useLoad(async () => {
    const [result, caps] = await Promise.all([game.result(id), game.dailyCaps().catch(() => null)]);
    return { result, caps };
  }, [id]);

  if (!data && loading) return <Page><Header /><Loading label="결과를 불러오는 중" /></Page>;
  if (!data) return <Page><Header /><ErrorState message={error ?? '결과를 불러오지 못했어요'} onRetry={reload} /></Page>;

  const { card, narrative, formComment } = data.result;
  const locked = card.drops.filter((d) => d.status === 'LOCKED').length;
  const releaseAt = new Date(new Date(card.rewardedAt).getTime() + PROTECT_MS).toISOString();
  const protecting = Date.now() < new Date(releaseAt).getTime();
  const overCap = card.dailyCapExceeded || card.hitCount === 0;
  const cap = data.caps?.items.find((c) => c.exerciseCode === card.exerciseCode);
  const home = () => router.replace('/home');

  if (overCap) return <Page>
    <ScrollView contentContainerStyle={{ flexGrow: 1 }}>
      <StateBody art="dailyCap" title="오늘 보상을 다 받았습니다"
        body={`방금 한 ${card.countedReps}회는 기록으로 남지만 보상과 공격은 없습니다.\n내일(KST 0시)부터 다시 받을 수 있습니다.`}
        tag={cap ? `오늘 보상 ${cap.reserved} / ${cap.cap}회` : null}
        primary={{ title: '홈으로', onPress: home }} />
    </ScrollView>
  </Page>;

  return <Page>
    <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 16, paddingBottom: 16, gap: 12 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <Text accessibilityRole="header" style={{ fontSize: 24, lineHeight: 32, fontWeight: '700', color: DS.label }}>전투 결과</Text>
        <Text style={T.cap}>{shortTime(card.rewardedAt)}</Text>
      </View>

      <View accessible accessibilityLabel={`${skillName(card.exerciseCode)} ${card.hitCount}타, ${exerciseName(card.exerciseCode)} ${card.countedReps}회 인정`}
        style={{ paddingVertical: 16, paddingHorizontal: 20, borderRadius: 16, backgroundColor: DS.accent, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <View style={{ gap: 2 }}>
          <Text style={{ fontSize: 13, fontWeight: '600', color: DS.onAccent }}>{skillName(card.exerciseCode)}</Text>
          <Text style={[T.display, { fontSize: 38, lineHeight: 42, color: DS.onAccent }]}>{card.hitCount}타</Text>
        </View>
        <Text style={{ fontSize: 13, fontWeight: '600', color: DS.onAccent }}>{exerciseName(card.exerciseCode)} {card.countedReps}회 인정</Text>
      </View>

      <View style={{ padding: 16, borderRadius: 16, backgroundColor: DS.bg2, flexDirection: 'row', gap: 14, alignItems: 'center' }}>
        <Svg width={86} height={172} viewBox="0 0 120 240" accessibilityLabel="이번 운동 부위: 하체">
          <Circle cx={60} cy={22} r={16} fill="#808080" />
          <Rect x={40} y={42} width={40} height={66} rx={14} fill="#808080" />
          <Rect x={44} y={110} width={32} height={30} rx={8} fill="#808080" />
          <Rect x={18} y={48} width={16} height={70} rx={8} fill="#808080" />
          <Rect x={86} y={48} width={16} height={70} rx={8} fill="#808080" />
          <Rect x={42} y={142} width={16} height={86} rx={8} fill={DS.accent} />
          <Rect x={62} y={142} width={16} height={86} rx={8} fill={DS.accent} />
          <Circle cx={50} cy={172} r={14} fill={DS.accent} opacity={0.25} />
          <Circle cx={50} cy={172} r={5} fill={DS.label} />
          <Circle cx={70} cy={196} r={14} fill={DS.accent} opacity={0.25} />
          <Circle cx={70} cy={196} r={5} fill={DS.label} />
        </Svg>
        <View style={{ flex: 1, gap: 8 }}>
          <Text style={{ fontSize: 13, color: DS.label2 }}>이번 운동 부위</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, paddingHorizontal: 14, borderRadius: 999, backgroundColor: DS.bg3 }}>
            <View style={{ width: 12, height: 12, borderRadius: 999, backgroundColor: DS.accent }} />
            <View>
              <Text style={{ fontSize: 13, fontWeight: '600', color: DS.label2 }}>하체</Text>
              <Text style={{ fontSize: 22, lineHeight: 26, fontWeight: '600', color: DS.label }}>{card.countedReps}회</Text>
            </View>
          </View>
          {['코어', '상체'].map((part) => <View key={part} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8, paddingHorizontal: 14,
            borderRadius: 999, borderWidth: 1, borderColor: DS.bg3 }}>
            <View style={{ width: 12, height: 12, borderRadius: 999, backgroundColor: DS.gray2 }} />
            <Text style={{ fontSize: 13, color: DS.label2 }}>{part} · 이번엔 없음</Text>
          </View>)}
          <Pressable accessibilityRole="link" onPress={() => router.push({ pathname: '/submission/[id]/body', params: { id } })}
            style={{ minHeight: 44, justifyContent: 'center' }}>
            <Text style={{ fontSize: 13, fontWeight: '600', color: DS.accent }}>몸 지도로 보기 →</Text>
          </Pressable>
        </View>
      </View>

      <View style={{ flexDirection: 'row', gap: 10 }}>
        <StatTile label="경험치" value={`+${card.exp}`} />
        <StatTile label="총 피해" value={String(card.totalDamage)} />
        <StatTile label="보상 상자" value={`${card.drops.length}개`} warn={locked > 0} />
      </View>

      <View style={{ paddingVertical: 16, paddingHorizontal: 18, borderRadius: 16, backgroundColor: DS.bg2, gap: 10 }}>
        <Text style={{ fontSize: 13, fontWeight: '600', color: DS.accent }}>전투 이야기{narrative.isFallback ? ' · 기본 문구' : ''}</Text>
        <Text style={{ fontSize: 14, lineHeight: 22, color: DS.label }}>{narrative.text}</Text>
        <View style={{ height: 1, backgroundColor: DS.bg3 }} />
        <Text style={{ fontSize: 13, fontWeight: '600', color: DS.accent }}>다음에 고칠 점{formComment.isFallback ? ' · 기본 문구' : ''}</Text>
        <Text style={{ fontSize: 14, lineHeight: 22, color: DS.label }}>{formComment.text}</Text>
      </View>

      {protecting && <Text style={{ fontSize: 13, lineHeight: 19, color: DS.label2 }}>
        얻은 아이템과 하체 경험치는 24시간 뒤 확정됩니다 ({shortTime(releaseAt)})
      </Text>}
    </ScrollView>
    <BottomBar>
      <Cta title="홈으로" height={56} onPress={home} />
      <Cta title="리플레이 다시 보기" variant="text" height={44} onPress={() => router.replace({ pathname: '/submission/[id]/replay', params: { id } })} />
    </BottomBar>
  </Page>;
}

function StatTile({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return <View style={{ flex: 1, paddingVertical: 12, paddingHorizontal: 14, borderRadius: 14, backgroundColor: DS.bg2, gap: 4 }}>
    <Text style={{ fontSize: 13, color: DS.label2 }}>{label}</Text>
    <Text numberOfLines={1} adjustsFontSizeToFit style={{ fontSize: 17, fontWeight: '600', color: DS.label }}>{value}</Text>
    {warn ? <Text style={{ fontSize: 11, color: DS.warn }}>잠김</Text> : null}
  </View>;
}
