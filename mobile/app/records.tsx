// 운동 기록 (시안 'WorkoutRecord'). API-005·029 (from·to KST 기간 조회)
// MVP 운동은 스쿼트 하나라 분야 탭(하체·상체·코어)은 만들지 않고, 기간은 '주'만 둔다 (일·월·년 집계 API 없음).
// 막대: 확정 = 지급 완료(REWARDED), 확정 대기 = 승인·지급 전 처리 중(SUBMITTED·PREPARED·PENDING_REVIEW·APPROVED) [제안]
// 취소·반려·종료 건은 막대와 평균에서 뺀다.
import { useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import type { Submission } from '../src/api/game';
import { api } from '../src/auth/session';
import { DS, ErrorState, Header, Icon, IconButton, Loading, Page, T, Tag } from '../src/design/kit';
import { exerciseName, skillName, statusCopy } from '../src/game/rules';
import { useLoad } from '../src/game/useLoad';
import { home } from '../src/home/api';
import { HIcon, kstDateKey, kstTime, kstWeek, weekLabel } from '../src/home/parts';

const DAYS = ['월', '화', '수', '목', '금', '토', '일'];
const DAY_NAMES = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일'];
const PENDING = ['SUBMITTED', 'PREPARED', 'PENDING_REVIEW', 'APPROVED'];
const TONE_OF = { lime: 'accent', warn: 'warn', danger: 'danger', muted: 'muted' } as const;
const CHART_H = 150;

export default function Records() {
  const router = useRouter();
  const [offset, setOffset] = useState(0);
  const week = useMemo(() => kstWeek(offset), [offset]);
  const today = kstDateKey(new Date());

  const { data, error, loading, reload } = useLoad(async () => {
    const [me, list] = await Promise.all([api.me(), home.submissionsBetween(week[0], week[6])]);
    return { me, ...list, week };
  }, [week]);
  const [picked, setPicked] = useState<number | null>(null);

  const header = <Header title="운동 기록" />;

  if (!data && loading) return <Page>{header}<Loading /></Page>;
  if (!data) return <Page>{header}<ErrorState message={error ?? '운동 기록을 불러오지 못했어요'} onRetry={reload} /></Page>;

  const squats = data.items.filter((x) => x.exerciseCode === 'SQUAT');
  const byDay = data.week.map((day) => {
    const ofDay = squats.filter((x) => kstDateKey(new Date(x.startedAt)) === day);
    const sum = (list: Submission[]) => list.reduce((n, x) => n + x.countedReps, 0);
    return {
      day,
      confirmed: sum(ofDay.filter((x) => x.status === 'REWARDED')),
      pending: sum(ofDay.filter((x) => PENDING.includes(x.status))),
    };
  });
  const totals = byDay.map((d) => d.confirmed + d.pending);
  const activeDays = totals.filter((n) => n > 0).length;
  const average = activeDays > 0 ? Math.round(totals.reduce((a, b) => a + b, 0) / activeDays) : 0;
  const max = Math.max(...totals, 0);
  const scale = max > 0 ? Math.ceil(max / 3 / 5) * 5 * 3 : 0; // 눈금 3칸이 5의 배수가 되게
  const todayIndex = data.week.indexOf(today);
  const sel = picked ?? (todayIndex >= 0 ? todayIndex : null);
  const todays = squats.filter((x) => kstDateKey(new Date(x.startedAt)) === today);

  return <Page>
    {header}
    <View style={{ height: 1, backgroundColor: DS.bg2 }} />
    <ScrollView contentContainerStyle={{ paddingBottom: 40 }}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={reload} tintColor={DS.accent} />}>
      <View style={st.weekRow}>
        <View style={{ flex: 1, gap: 6 }}>
          <Text numberOfLines={1} style={[T.display, { fontSize: 20, color: DS.accent }]}>{data.me.nickname}</Text>
          <Text style={T.foot}>{offset === 0 ? '이번 주 · ' : ''}{weekLabel(data.week[0])}</Text>
        </View>
        <IconButton name="back" label="이전 주" onPress={() => { setPicked(null); setOffset((o) => o - 1); }} />
        <Pressable accessibilityRole="button" accessibilityLabel="다음 주" accessibilityState={{ disabled: offset >= 0 }}
          disabled={offset >= 0} onPress={() => { setPicked(null); setOffset((o) => o + 1); }} style={[st.iconBtn, offset >= 0 && { opacity: 0.3 }]}>
          <Icon name="chevron" />
        </Pressable>
      </View>

      <View style={st.band} />
      <View style={st.section}>
        <Text style={T.headline}>스쿼트 평균</Text>
        <View style={{ flexDirection: 'row' }}>
          <View style={{ flex: 1, gap: 4 }}><Text style={T.foot}>하루 평균</Text><Text style={[T.display, { fontSize: 20 }]}>{average}회</Text></View>
          <View style={{ flex: 1, gap: 4 }}><Text style={T.foot}>운동한 날</Text><Text style={[T.display, { fontSize: 20 }]}>{activeDays}일</Text></View>
        </View>
        {!data.complete && <Text style={[T.cap, { color: DS.warn }]}>기록이 많아 이번 주 일부만 집계했어요.</Text>}
        {error && <Text style={[T.cap, { color: DS.danger }]}>최신 기록을 불러오지 못했어요. 아래로 당겨 다시 불러오세요.</Text>}

        {/* 요일별 막대 */}
        <View accessibilityLabel={`요일별 스쿼트 횟수. ${byDay.map((d, i) => `${DAY_NAMES[i]} ${totals[i]}회`).join(', ')}`}
          style={{ height: CHART_H + 32, marginTop: 8 }}>
          <View style={[st.grid, { height: CHART_H }]}>
            {[0, 1, 2, 3].map((i) => <View key={i} style={{ height: 1, backgroundColor: i === 3 ? DS.bg3 : DS.bg2 }} />)}
          </View>
          <View style={[st.axis, { height: CHART_H + 14 }]}>
            {[scale, (scale * 2) / 3, scale / 3, 0].map((v, i) => <Text key={i} style={st.axisText}>{Math.round(v)}</Text>)}
          </View>
          <View style={st.bars}>
            {byDay.map((d, i) => {
              const h = (n: number) => (scale > 0 ? (n / scale) * CHART_H : 0);
              const on = sel === i;
              return <Pressable key={d.day} accessibilityRole="button" accessibilityState={{ selected: on }}
                accessibilityLabel={`${DAY_NAMES[i]} 스쿼트 ${totals[i]}회${d.pending > 0 ? `, 그중 확정 대기 ${d.pending}회` : ''}`}
                onPress={() => setPicked(i)} style={st.barCol}>
                {on && totals[i] > 0 && <View style={[st.bubble, { bottom: h(totals[i]) + 32 }]}>
                  <Text style={{ color: DS.onAccent, fontSize: 13, fontWeight: '700' }}>{totals[i]}회</Text>
                </View>}
                <View style={{ width: 16, height: CHART_H, justifyContent: 'flex-end' }}>
                  {totals[i] === 0
                    ? <View style={{ height: 4, borderRadius: 8, backgroundColor: DS.dot }} />
                    : <>
                      {d.pending > 0 && <View style={{ height: h(d.pending), backgroundColor: DS.accent300, borderTopLeftRadius: 8, borderTopRightRadius: 8, borderBottomLeftRadius: d.confirmed > 0 ? 0 : 8, borderBottomRightRadius: d.confirmed > 0 ? 0 : 8 }} />}
                      {d.confirmed > 0 && <View style={{ height: h(d.confirmed), backgroundColor: DS.accent, borderBottomLeftRadius: 8, borderBottomRightRadius: 8, borderTopLeftRadius: d.pending > 0 ? 0 : 8, borderTopRightRadius: d.pending > 0 ? 0 : 8 }} />}
                    </>}
                </View>
                <Text style={{ color: on ? DS.label : DS.gray, fontSize: 13, fontWeight: on ? '700' : '500' }}>{DAYS[i]}</Text>
              </Pressable>;
            })}
          </View>
        </View>
        <View style={{ flexDirection: 'row', gap: 16 }}>
          <View style={st.legend}><View style={[st.swatch, { backgroundColor: DS.accent }]} /><Text style={T.foot}>확정</Text></View>
          <View style={st.legend}><View style={[st.swatch, { backgroundColor: DS.accent300 }]} /><Text style={T.foot}>확정 대기</Text></View>
        </View>
      </View>

      <View style={st.band} />
      <View style={st.section}>
        <Text accessibilityRole="header" style={T.headline}>오늘 기록</Text>
        {todays.length === 0
          ? <Text style={T.foot}>오늘은 아직 스쿼트 기록이 없어요.</Text>
          : todays.map((x) => {
            const copy = x.status === 'REWARDED' && x.approvalPath === 'AI_AUTO' ? { chip: '자동 승인', tone: 'lime' as const } : statusCopy(x.status);
            const skill = x.reservedReps > 0 ? ` · ${skillName(x.exerciseCode)} ×${x.reservedReps}` : '';
            return <Pressable key={x.id} accessibilityRole="button" accessibilityLabel={`${exerciseName(x.exerciseCode)} ${x.countedReps}회, ${copy.chip}`}
              onPress={() => router.push({ pathname: '/submission/[id]', params: { id: x.id } })} style={st.record}>
              <View style={st.recordIcon}><HIcon name="shorts" size={20} color={DS.accent} /></View>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={{ color: DS.label, fontSize: 14, fontWeight: '700' }}>{exerciseName(x.exerciseCode)} {x.countedReps}회</Text>
                <Text style={T.foot}>{kstTime(x.startedAt)}{skill}</Text>
              </View>
              <Tag label={copy.chip} tone={copy.chip === '자동 승인' ? 'solid' : TONE_OF[copy.tone]} />
            </Pressable>;
          })}
      </View>
    </ScrollView>
  </Page>;
}

const st = StyleSheet.create({
  weekRow: { flexDirection: 'row', alignItems: 'center', paddingLeft: 20, paddingRight: 8, paddingVertical: 20 },
  iconBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  band: { height: 8, backgroundColor: DS.bg2 },
  section: { paddingHorizontal: 20, paddingVertical: 24, gap: 14 },
  grid: { position: 'absolute', left: 0, right: 40, top: 0, justifyContent: 'space-between' },
  axis: { position: 'absolute', right: 0, top: -7, justifyContent: 'space-between' },
  axisText: { color: DS.gray, fontSize: 13, textAlign: 'right' },
  bars: { position: 'absolute', left: 0, right: 40, top: 0, flexDirection: 'row' },
  barCol: { flex: 1, alignItems: 'center', gap: 8, minHeight: 44 },
  bubble: { position: 'absolute', zIndex: 2, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10, backgroundColor: DS.label },
  legend: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  swatch: { width: 10, height: 10, borderRadius: 3 },
  record: { minHeight: 64, borderRadius: 16, backgroundColor: DS.bg2, paddingHorizontal: 16, paddingVertical: 14, flexDirection: 'row', alignItems: 'center', gap: 12 },
  recordIcon: { width: 40, height: 40, borderRadius: 999, backgroundColor: DS.bg3, alignItems: 'center', justifyContent: 'center' },
});
