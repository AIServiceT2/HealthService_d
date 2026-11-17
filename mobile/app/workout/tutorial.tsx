// 스쿼트 튜토리얼 (시안 'Tutorial'). F-10 / US-01
// 판정 기준·촬영 각도는 운동 목록(API-018) 값을 쓴다. 값이 없으면 그 부분을 빼고 보여 준다 (시안의 [팀 확정 전] 자리).
import { ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import Svg, { Circle, Line, Path, Rect } from 'react-native-svg';
import { game } from '../../src/auth/session';
import { BottomBar, Cta, DS, ErrorState, Header, Loading, Page, T } from '../../src/design/kit';
import { exerciseName } from '../../src/game/rules';
import { useLoad } from '../../src/game/useLoad';

export default function Tutorial() {
  const router = useRouter();
  const params = useLocalSearchParams<{ exerciseCode?: string }>();
  const code = params.exerciseCode ?? 'SQUAT';
  const { data, error, loading, reload } = useLoad(() => game.exercises(), []);

  if (!data && loading) return <Page><Header /><Loading label="판정 기준을 불러오는 중" /></Page>;
  if (!data) return <Page><Header /><ErrorState message={error ?? '판정 기준을 불러오지 못했어요'} onRetry={reload} /></Page>;

  const exercise = data.items.find((e) => e.code === code) ?? null;
  const knee = exercise?.criteria.kneeAngleMax;
  const angle = exercise?.recommendedCameraAngle;
  const steps = [
    { title: '인정 기준', body: knee != null
      ? `무릎 각도 ${knee}° 이하까지 내려갔다 올라와야 1회로 셉니다.`
      : '엉덩이가 무릎 높이까지 내려갔다 올라와야 1회로 셉니다.' },
    { title: '폰 놓는 법', body: `전신이 화면에 다 들어오게 세워 두십시오.${angle ? ` 권장 각도: ${angle}` : ''}` },
    { title: '영상은 저장하지 않습니다', body: '폰 안에서만 세고, 얼굴을 뺀 관절 정보만 보냅니다.' },
  ];

  return <Page>
    <Header />
    <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 16, gap: 18 }}>
      <Text accessibilityRole="header" style={[T.display, { fontSize: 24, lineHeight: 32 }]}>{exerciseName(code)}는 이렇게 셉니다</Text>
      <View style={{ height: 220, borderRadius: 16, backgroundColor: DS.bg2, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 28 }}>
        <Svg width={70} height={140} viewBox="0 0 120 240" accessibilityLabel="선 자세">
          <Circle cx={60} cy={22} r={16} fill={DS.label2} />
          <Rect x={40} y={42} width={40} height={98} rx={14} fill={DS.label2} />
          <Rect x={42} y={142} width={16} height={86} rx={8} fill={DS.label2} />
          <Rect x={62} y={142} width={16} height={86} rx={8} fill={DS.label2} />
        </Svg>
        <Svg width={24} height={24} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no">
          <Path fill={DS.label2} fillRule="evenodd" d="m14.707 5.636 5.657 5.657a1 1 0 0 1 0 1.414l-5.657 5.657a1 1 0 0 1-1.414-1.414l3.95-3.95H4a1 1 0 1 1 0-2h13.243l-3.95-3.95a1 1 0 1 1 1.414-1.414Z" />
        </Svg>
        <Svg width={90} height={140} viewBox="0 0 150 240" accessibilityLabel="앉은 자세: 인정 기준까지 내려감">
          <Circle cx={70} cy={70} r={16} fill={DS.label2} />
          <Rect x={50} y={90} width={40} height={70} rx={14} fill={DS.label2} />
          <Rect x={60} y={160} width={70} height={18} rx={9} fill={DS.accent} />
          <Rect x={112} y={160} width={18} height={70} rx={9} fill={DS.accent} />
          <Line x1={20} y1={169} x2={146} y2={169} stroke={DS.accent} strokeWidth={2} strokeDasharray="6 6" />
        </Svg>
      </View>
      <View style={{ gap: 12 }}>
        {steps.map((st, i) => <View key={st.title} style={{ flexDirection: 'row', gap: 12, padding: 16, borderRadius: 14, backgroundColor: DS.bg2 }}>
          <Text style={{ fontSize: 18, fontWeight: '600', color: DS.accent }}>{i + 1}</Text>
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: DS.label }}>{st.title}</Text>
            <Text style={{ fontSize: 13, lineHeight: 20, color: DS.label2 }}>{st.body}</Text>
          </View>
        </View>)}
      </View>
    </ScrollView>
    <BottomBar>
      <Cta title="확인했습니다" height={56} disabled={!exercise}
        onPress={() => router.push({ pathname: '/workout/goal', params: { exerciseCode: code } })} />
    </BottomBar>
  </Page>;
}
