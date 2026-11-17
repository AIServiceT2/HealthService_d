// 홈 (시안 'F-05·F-06 홈'). F-01·F-02·F-06 / US-01·05
// 캐릭터 요약(API-005·007), 내 길드(API-010·046) 또는 추천 길드([추가] API), 전투 결과 도착 카드, 내 운동 기록(API-029)
// 시안의 운동 검색·분야 탭은 MVP 밖이라 만들지 않는다. 받은 확인 요청·로그아웃은 메뉴(app/menu.tsx)로 옮겼다.
import { useCallback, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import type { RecommendedGuild } from '../src/api/account';
import type { GuildBoss } from '../src/api/game';
import { api, game } from '../src/auth/session';
import { BottomBar, Cta, DS, ErrorState, Icon, IconButton, Loading, Page, Sheet, T, Tag } from '../src/design/kit';
import { capExceeded, exerciseName, skillName, statusCopy } from '../src/game/rules';
import { errorMessage, useLoad } from '../src/game/useLoad';
import { home, type Guild } from '../src/home/api';
import { HIcon, kstShort } from '../src/home/parts';

const CARD_TONES = [
  { bg: DS.accent, fg: DS.onAccent }, { bg: DS.accent300, fg: DS.onAccent },
  { bg: DS.bg2, fg: DS.label }, { bg: DS.accent300, fg: DS.onAccent },
];
const TONE_OF = { lime: 'accent', warn: 'warn', danger: 'danger', muted: 'muted' } as const;

export default function Home() {
  const router = useRouter();
  const { data, error, loading, reload } = useLoad(async () => {
    const [me, character, list] = await Promise.all([api.me(), game.myCharacter(), game.mySubmissions(10)]);
    // 길드 정보·추천 길드는 실패해도 홈 전체를 막지 않는다
    let guild: Guild | null = null;
    let boss: GuildBoss | null = null;
    let recommended: RecommendedGuild[] | null = null;
    if (me.guildId) {
      [guild, boss] = await Promise.all([home.guild(me.guildId).catch(() => null), game.guildBoss(me.guildId).catch(() => null)]);
    } else {
      recommended = await api.recommendedGuilds().catch(() => null);
    }
    return { me, character, submissions: list.items, guild, boss, recommended };
  }, []);

  // 다른 화면에서 돌아오면 최신 상태로 (제출·취소·지급 결과 반영)
  useFocusEffect(useCallback(() => { void reload(); }, [reload]));

  const [picked, setPicked] = useState<RecommendedGuild | null>(null);
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  if (!data && loading) return <Page><Loading /></Page>;
  if (!data) return <Page><ErrorState message={error ?? '기록을 불러오지 못했어요'} onRetry={reload} /></Page>;

  const { me, character, submissions, guild, boss, recommended } = data;
  // 아직 결과를 열어 보지 않았는지는 서버에 없어서, 가장 최근 지급 완료 건을 보여 준다 [제안]
  const latestRewarded = submissions.find((x) => x.status === 'REWARDED');
  const recent = submissions.slice(0, 5);

  const join = async () => {
    if (!picked || joining) return;
    setJoining(true); setJoinError(null);
    try {
      const res = await api.joinGuild(picked.guildId);
      setPicked(null);
      await reload();
      router.push({ pathname: '/guild/[id]', params: { id: res.guildId } });
    } catch (e) {
      setJoinError(errorMessage(e, '길드에 가입하지 못했어요.'));
    } finally {
      setJoining(false);
    }
  };

  return <Page edges={['top']}>
    <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 120, gap: 20 }}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={reload} tintColor={DS.accent} />}>
      {/* 상단: 메뉴 + 내 캐릭터 요약 (시안의 검색 자리) */}
      <View style={st.top}>
        <IconButton name="menu" label="메뉴 열기" onPress={() => router.push('/menu')} style={{ marginLeft: -12 }} />
        <Pressable accessibilityRole="button" accessibilityLabel={`내 캐릭터, ${me.nickname}, 레벨 ${character.level}`}
          onPress={() => router.push('/character')} style={st.profile}>
          <Text numberOfLines={1} style={[T.headline, { flexShrink: 1, fontSize: 15 }]}>{me.nickname}</Text>
          <Text style={{ color: DS.accent, fontSize: 13, fontWeight: '800' }}>LV.{character.level}</Text>
          {character.exp.pending > 0 && <Text style={T.cap}>+{character.exp.pending} 확정 대기</Text>}
          <View style={{ marginLeft: 'auto' }}><Icon name="chevron" size={18} color={DS.label2} /></View>
        </Pressable>
      </View>

      {me.guildId
        ? <MyGuild guildId={me.guildId} guild={guild} boss={boss} onOpen={() => router.push({ pathname: '/guild/[id]', params: { id: me.guildId! } })} />
        : <View style={{ gap: 16 }}>
          <View style={{ flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
            <Text accessibilityRole="header" style={[T.display, { fontSize: 24, lineHeight: 28 }]}>
              함께할 길드를{'\n'}<Text style={{ color: DS.accent }}>찾아보십시오</Text>
            </Text>
            <Pressable accessibilityRole="button" onPress={() => router.push('/guild/create')} style={st.createBtn}>
              <HIcon name="plus" size={16} color={DS.accent} />
              <Text style={{ color: DS.label, fontSize: 14, fontWeight: '700' }}>길드 만들기</Text>
            </Pressable>
          </View>
          {recommended === null
            ? <Text style={T.foot}>추천 길드를 불러오지 못했어요. 아래로 당겨 다시 불러오세요.</Text>
            : recommended.length === 0
              ? <Text style={T.foot}>아직 추천할 길드가 없어요. 길드를 만들거나 초대 코드로 가입할 수 있어요.</Text>
              : <View style={{ flexDirection: 'row', gap: 10 }}>
                {[0, 1].map((col) => <View key={col} style={{ flex: 1, gap: 10 }}>
                  {recommended.filter((_, i) => i % 2 === col).map((g, j) => {
                    const i = j * 2 + col;
                    const tone = CARD_TONES[i % CARD_TONES.length];
                    return <Pressable key={g.guildId} accessibilityRole="button" accessibilityLabel={`${g.name} 길드 보기, 길드원 ${g.memberCount}명`}
                      onPress={() => { setJoinError(null); setPicked(g); }}
                      style={[st.guildCard, { backgroundColor: tone.bg, minHeight: [168, 152, 176, 184][i % 4] }]}>
                      <Text numberOfLines={2} style={{ color: tone.fg, fontSize: 17, fontWeight: '700' }}>{g.name}</Text>
                      <View style={st.guildCardFoot}>
                        <Text style={{ color: tone.fg, fontSize: 13, fontWeight: '600' }}>길드원 {g.memberCount}명</Text>
                        <View style={st.arrow}><HIcon name="arrowUpRight" size={18} color={DS.accent} /></View>
                      </View>
                    </Pressable>;
                  })}
                </View>)}
              </View>}
          <Pressable accessibilityRole="button" onPress={() => router.push('/onboarding/guild')} style={st.textLink}>
            <Text style={{ color: DS.label2, fontSize: 14, fontWeight: '600' }}>초대 코드로 가입하기</Text>
          </Pressable>
        </View>}

      {latestRewarded && <View style={st.result}>
        <Tag label="전투 결과 도착" tone="solid" style={{ backgroundColor: DS.onAccent, borderColor: DS.onAccent }} />
        <Text style={[T.display, { color: DS.onAccent, fontSize: 22 }]}>
          {capExceeded(latestRewarded) ? '일일 상한 초과' : `${skillName(latestRewarded.exerciseCode)} ×${latestRewarded.reservedReps}`}
        </Text>
        <Text style={{ color: '#3F5A12', fontSize: 14 }}>{exerciseName(latestRewarded.exerciseCode)} {latestRewarded.countedReps}회가 전투가 됐어요.</Text>
        <Pressable accessibilityRole="button"
          onPress={() => router.push({ pathname: capExceeded(latestRewarded) ? '/submission/[id]/result' : '/submission/[id]/replay', params: { id: latestRewarded.id } })}
          style={st.resultBtn}>
          <Text style={{ color: DS.accent, fontSize: 15, fontWeight: '700' }}>{capExceeded(latestRewarded) ? '결과 보기' : '리플레이 보기'}</Text>
        </Pressable>
      </View>}

      <View style={{ gap: 12 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
          <Text accessibilityRole="header" style={T.headline}>내 운동 기록</Text>
          <Pressable accessibilityRole="button" accessibilityLabel="운동 기록 전체 보기" onPress={() => router.push('/records')} style={st.more}>
            <Text style={{ color: DS.label2, fontSize: 13, fontWeight: '600' }}>전체 보기</Text>
          </Pressable>
        </View>
        {error && <Text style={[T.foot, { color: DS.danger }]}>최신 기록을 불러오지 못했어요. 아래로 당겨 다시 불러오세요.</Text>}
        {recent.length === 0
          ? <View style={st.empty}><Text style={T.body}>아직 운동 기록이 없어요</Text><Text style={T.foot}>아래 '운동 시작'으로 첫 기록을 남겨 보세요.</Text></View>
          : recent.map((x) => {
            const copy = statusCopy(x.status);
            return <Pressable key={x.id} accessibilityRole="button" accessibilityLabel={`${exerciseName(x.exerciseCode)} ${x.countedReps}회, ${copy.chip}`}
              onPress={() => router.push({ pathname: '/submission/[id]', params: { id: x.id } })} style={st.record}>
              <View style={st.recordIcon}><HIcon name="shorts" size={20} color={DS.accent} /></View>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={{ color: DS.label, fontSize: 14, fontWeight: '700' }}>{exerciseName(x.exerciseCode)} {x.countedReps}회</Text>
                <Text style={T.foot}>{kstShort(x.startedAt)}</Text>
              </View>
              <Tag label={copy.chip} tone={TONE_OF[copy.tone]} />
            </Pressable>;
          })}
      </View>
    </ScrollView>

    <BottomBar style={st.bottom}>
      <Cta title="운동 시작" onPress={() => router.push('/workout/setup')} />
    </BottomBar>

    <Sheet visible={!!picked} onClose={() => setPicked(null)} label="길드 가입">
      {picked && <View style={{ gap: 14 }}>
        <Text style={[T.display, { fontSize: 24 }]}>{picked.name}</Text>
        <Text style={T.sub}>길드원 {picked.memberCount}명 · 애매한 기록은 길드장에게 확인을 요청할 수 있습니다.</Text>
        {joinError && <Text style={[T.foot, { color: DS.danger }]}>{joinError}</Text>}
        <Cta title="길드 가입하기" onPress={join} loading={joining} />
      </View>}
    </Sheet>
  </Page>;
}

/** 내 길드 카드 (시안 길드 카드의 라임 큰 카드 모양) */
function MyGuild({ guildId, guild, boss, onOpen }: { guildId: string; guild: Guild | null; boss: GuildBoss | null; onOpen: () => void }) {
  return <View style={{ gap: 14 }}>
    <Text accessibilityRole="header" style={[T.display, { fontSize: 24, lineHeight: 28 }]}>
      오늘도 같이{'\n'}<Text style={{ color: DS.accent }}>한 세트!</Text>
    </Text>
    <Pressable key={guildId} accessibilityRole="button" accessibilityLabel={`내 길드${guild ? `, ${guild.name}` : ''} 보기`} onPress={onOpen}
      style={[st.guildCard, { backgroundColor: DS.accent, minHeight: 150 }]}>
      <Text style={{ color: '#3F5A12', fontSize: 13, fontWeight: '600' }}>내 길드</Text>
      <Text numberOfLines={2} style={[T.display, { color: DS.onAccent, fontSize: 22 }]}>{guild?.name ?? '길드 정보를 불러오지 못했어요'}</Text>
      <View style={st.guildCardFoot}>
        <View style={{ gap: 2 }}>
          {guild && <Text style={{ color: DS.onAccent, fontSize: 13, fontWeight: '600' }}>길드원 {guild.memberCount}명</Text>}
          {boss && <Text style={{ color: '#3F5A12', fontSize: 13 }}>이번 주 보스 피해 {boss.guildTotalDamage.toLocaleString()}</Text>}
        </View>
        <View style={st.arrow}><HIcon name="arrowUpRight" size={18} color={DS.accent} /></View>
      </View>
    </Pressable>
  </View>;
}

const st = StyleSheet.create({
  top: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingTop: 6 },
  profile: { flex: 1, minHeight: 44, borderRadius: 999, borderWidth: 1.5, borderColor: DS.separator, paddingLeft: 16, paddingRight: 10, flexDirection: 'row', alignItems: 'center', gap: 8 },
  createBtn: { height: 44, paddingLeft: 10, paddingRight: 14, borderRadius: 999, borderWidth: 1.5, borderColor: '#48484A', flexDirection: 'row', alignItems: 'center', gap: 6 },
  guildCard: { borderRadius: 22, padding: 14, gap: 2 },
  guildCardFoot: { marginTop: 'auto', paddingTop: 12, flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: 8 },
  arrow: { width: 44, height: 44, borderRadius: 999, backgroundColor: DS.bg, alignItems: 'center', justifyContent: 'center' },
  textLink: { alignSelf: 'center', minHeight: 44, justifyContent: 'center', paddingHorizontal: 12 },
  result: { borderRadius: 22, backgroundColor: DS.accent, padding: 18, gap: 8 },
  resultBtn: { marginTop: 6, height: 48, borderRadius: 999, backgroundColor: DS.bg, alignItems: 'center', justifyContent: 'center' },
  more: { minHeight: 44, justifyContent: 'center', paddingLeft: 12 },
  empty: { borderRadius: 16, backgroundColor: DS.bg2, padding: 20, alignItems: 'center', gap: 4 },
  record: { minHeight: 64, borderRadius: 16, backgroundColor: DS.bg2, paddingHorizontal: 16, paddingVertical: 12, flexDirection: 'row', alignItems: 'center', gap: 12 },
  recordIcon: { width: 40, height: 40, borderRadius: 999, backgroundColor: DS.bg3, alignItems: 'center', justifyContent: 'center' },
  bottom: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingBottom: 32 },
});
