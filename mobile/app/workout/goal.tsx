// 목표 설정 (시안 'GoalSetupCard'). F-02·F-10 / US-01
// 일일 상한(API-019), 공략 대상(API-045·046). 공략 대상 선택은 시안에 없지만 세션 시작(API-020)에 쓰므로 카드 아래에 둔다.
import { useState } from 'react';
import { Image, Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { api, game } from '../../src/auth/session';
import { BottomBar, Chip, Cta, DS, ErrorState, Header, Icon, Loading, Page, T } from '../../src/design/kit';
import { DEMO_DUNGEON_ID, exerciseName } from '../../src/game/rules';
import { useLoad } from '../../src/game/useLoad';

type TargetChoice = 'DUNGEON' | 'BOSS' | 'NONE';

export default function GoalSetup() {
  const router = useRouter();
  const params = useLocalSearchParams<{ exerciseCode?: string }>();
  const code = params.exerciseCode ?? 'SQUAT';
  const [reps, setReps] = useState(30);
  const [sets, setSets] = useState(1);
  const [target, setTarget] = useState<TargetChoice>('DUNGEON');

  const { data, error, loading, reload } = useLoad(async () => {
    const [caps, me] = await Promise.all([game.dailyCaps(), api.me()]);
    // 공략 대상 조회가 실패해도 운동은 시작할 수 있게 따로 처리
    const [dungeon, boss] = await Promise.all([
      game.dungeon(DEMO_DUNGEON_ID).catch(() => null),
      me.guildId ? game.guildBoss(me.guildId).catch(() => null) : Promise.resolve(null),
    ]);
    return { caps: caps.items, dungeon, boss };
  }, []);

  if (!data && loading) return <Page><Header /><Loading label="목표 설정을 준비하는 중" /></Page>;
  if (!data) return <Page><Header /><ErrorState message={error ?? '설정을 불러오지 못했어요'} onRetry={reload} /></Page>;

  const cap = data.caps.find((c) => c.exerciseCode === code);
  const effectiveTarget: TargetChoice = target === 'DUNGEON' && !data.dungeon ? 'NONE' : target === 'BOSS' && !data.boss ? 'NONE' : target;

  const start = () => {
    const targetId = effectiveTarget === 'DUNGEON' ? data.dungeon?.id : effectiveTarget === 'BOSS' ? data.boss?.bossId : undefined;
    router.push({
      pathname: '/workout/camera',
      params: { exerciseCode: code, reps: String(reps), sets: String(sets), targetType: targetId ? effectiveTarget : '', targetId: targetId ?? '' },
    });
  };

  return <Page>
    <Header />
    <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 16, gap: 20 }}>
      <View style={{ gap: 8 }}>
        <Text accessibilityRole="header" style={[T.display, { fontSize: 24, lineHeight: 32 }]}>목표 설정</Text>
        <Text style={{ fontSize: 14, color: DS.label2 }}>오늘 할 횟수와 세트를 정합니다</Text>
      </View>

      <View style={{ alignItems: 'center' }}>
        <View style={{ width: 230, height: 330, borderRadius: 22, borderWidth: 2, borderColor: DS.accent, overflow: 'hidden', backgroundColor: DS.bg2 }}>
          <Image source={require('../../assets/design/muscle-legs.png')} style={{ width: '100%', height: 200, backgroundColor: DS.bg }} resizeMode="cover"
            accessibilityIgnoresInvertColors />
          <View style={{ position: 'absolute', right: 12, top: 12, width: 30, height: 30, borderRadius: 999, backgroundColor: DS.accent, alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="check" size={16} color={DS.onAccent} />
          </View>
          <View style={{ flex: 1, paddingVertical: 12, paddingHorizontal: 14, alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <Text style={[T.display, { fontSize: 17 }]}>{exerciseName(code)}</Text>
            <Text style={{ fontSize: 13, color: DS.label2 }}>{reps}회 / {sets}세트</Text>
            <Text style={{ fontSize: 13, color: DS.label2 }}>하체 · 허벅지 앞</Text>
          </View>
        </View>
      </View>

      <View style={{ gap: 10 }}>
        <Stepper label="횟수" unit="회" value={reps} onChange={setReps} max={200} />
        <Stepper label="세트" unit="세트" value={sets} onChange={setSets} max={10} />
        {cap && <Text style={{ fontSize: 13, lineHeight: 18, color: cap.remaining === 0 ? DS.warn : DS.label2 }}>
          오늘 {exerciseName(cap.exerciseCode)} 상한 {cap.reserved} / {cap.cap}회{cap.remaining === 0 ? ' · 오늘은 보상이 더 쌓이지 않아요' : ''}
        </Text>}
      </View>

      <View style={{ gap: 10 }}>
        <Text style={{ fontSize: 14, color: DS.label2 }}>공략 대상</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          <Chip label={data.dungeon ? `던전 · ${data.dungeon.enemy.name}` : '던전 · 불러오지 못함'} on={effectiveTarget === 'DUNGEON'}
            disabled={!data.dungeon} onPress={() => setTarget('DUNGEON')} />
          <Chip label="길드 주간 보스" on={effectiveTarget === 'BOSS'} disabled={!data.boss} onPress={() => setTarget('BOSS')} />
          <Chip label="선택 안 함" on={effectiveTarget === 'NONE'} onPress={() => setTarget('NONE')} />
        </View>
        {!data.boss && <Text style={T.foot}>길드에 가입하면 길드 주간 보스를 공략할 수 있어요.</Text>}
      </View>
    </ScrollView>
    <BottomBar>
      <Cta title="운동 시작" onPress={start} />
    </BottomBar>
  </Page>;
}

function Stepper({ label, unit, value, onChange, min = 1, max }: {
  label: string; unit: string; value: number; onChange: (v: number) => void; min?: number; max: number;
}) {
  const btn = { width: 44, height: 44, borderRadius: 999, borderWidth: 1.5, borderColor: DS.gray2, alignItems: 'center', justifyContent: 'center' } as const;
  return <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 12, paddingHorizontal: 16, borderRadius: 16, backgroundColor: DS.bg2 }}>
    <Text style={{ fontSize: 14, color: DS.label2 }}>{label}</Text>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
      <Pressable accessibilityRole="button" accessibilityLabel={`${label} 줄이기`} accessibilityState={{ disabled: value <= min }}
        disabled={value <= min} onPress={() => onChange(Math.max(min, value - 1))} style={[btn, value <= min && { opacity: 0.4 }]}>
        <Text style={{ color: DS.label, fontSize: 20 }}>−</Text>
      </Pressable>
      <Text accessibilityLabel={`${label} ${value}${unit}`} style={[T.display, { minWidth: 54, textAlign: 'center', fontSize: 22 }]}>
        {value}<Text style={{ fontSize: 13, color: DS.label2, fontWeight: '400' }}> {unit}</Text>
      </Text>
      <Pressable accessibilityRole="button" accessibilityLabel={`${label} 늘리기`} accessibilityState={{ disabled: value >= max }}
        disabled={value >= max} onPress={() => onChange(Math.min(max, value + 1))} style={[btn, value >= max && { opacity: 0.4 }]}>
        <Text style={{ color: DS.label, fontSize: 20 }}>+</Text>
      </Pressable>
    </View>
  </View>;
}
