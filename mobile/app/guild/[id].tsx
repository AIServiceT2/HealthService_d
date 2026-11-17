// 길드 상세 (시안 'GuildDetail'). API-005·010·011·046
// 길드 사진·소개·분야는 서버에 없어 빼고, 사진 자리에는 이번 주 보스를 그린다. '길드 저장'은 API가 없어 만들지 않는다.
// 길드 정보는 소속원만 볼 수 있어(API-010 GUILD_MEMBER) 시안의 '길드 가입하기' 대신 길드장에게는 친구 초대, 길드원에게는 운동 시작을 둔다.
import { Image, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { HttpError } from '../../src/api/http';
import { api, game } from '../../src/auth/session';
import { BottomBar, Cta, DS, ErrorState, Icon, Loading, Page, T, Tag } from '../../src/design/kit';
import { useLoad } from '../../src/game/useLoad';
import { home } from '../../src/home/api';
import { Faces, HIcon, RoundButton } from '../../src/home/parts';

export default function GuildDetail() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const { data, error, loading, reload } = useLoad(async () => {
    const [me, guild, members, boss] = await Promise.all([
      api.me(), home.guild(id).catch((e: unknown) => {
        // 소속원이 아니면 403 (API-010)
        if (e instanceof HttpError && e.status === 403) throw new Error('이 길드의 소속원만 볼 수 있어요');
        throw e;
      }), home.members(id).catch(() => null), game.guildBoss(id).catch(() => null),
    ]);
    return { me, guild, members: members?.items ?? null, boss };
  }, [id]);

  const back = () => (router.canGoBack() ? router.back() : router.replace('/home'));
  const topBack = <View style={st.topBar}><RoundButton label="뒤로" onPress={back} style={{ backgroundColor: 'transparent' }}><Icon name="back" /></RoundButton></View>;

  if (!data && loading) return <Page>{topBack}<Loading /></Page>;
  if (!data) return <Page>{topBack}<ErrorState message={error ?? '길드 정보를 불러오지 못했어요'} onRetry={reload} /></Page>;

  const { me, guild, members, boss } = data;
  const isLeader = me.id === guild.leader.userId;
  const invite = () => router.push({ pathname: '/guild/invite', params: { id: guild.id, name: guild.name } });

  return <Page edges={['bottom']}>
    <ScrollView contentContainerStyle={{ paddingBottom: 24 }}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={reload} tintColor={DS.accent} />}>
      {/* 사진 자리: 이번 주 보스 + 시안의 라임 낙서 (장식) */}
      <View style={st.hero}>
        <Image source={require('../../assets/design/boss.png')} accessibilityLabel="이번 주 보스" resizeMode="contain" style={st.boss} />
        <Svg width="100%" height={470} viewBox="0 0 390 470" preserveAspectRatio="xMidYMid slice" style={StyleSheet.absoluteFill}
          accessibilityElementsHidden importantForAccessibility="no">
          <Path d="M-10 300 C 40 270, 70 240, 95 210 C 115 186, 70 200, 60 235 C 50 270, 110 300, 150 285 C 175 276, 190 300, 230 296" fill="none" stroke={DS.accent} strokeWidth={16} strokeLinecap="round" strokeLinejoin="round" />
          <Path d="M240 320 C 290 300, 340 290, 400 270" fill="none" stroke={DS.accent} strokeWidth={10} strokeLinecap="round" opacity={0.85} />
          <Path d="M118 112 l18 -16 M112 132 l26 -4" fill="none" stroke={DS.accent} strokeWidth={6} strokeLinecap="round" />
          <Path d="M258 220 C 290 214, 320 214, 350 210" fill="none" stroke={DS.accent} strokeWidth={5} strokeLinecap="round" />
        </Svg>
        <Text accessibilityElementsHidden importantForAccessibility="no" style={st.hand}>오늘도{'\n'}같이{'\n'}한 세트!</Text>
        <View style={st.fade} pointerEvents="none" />
        <View style={[st.topBar, st.heroBar, { top: insets.top + 4 }]}>
          <RoundButton label="뒤로" onPress={back} style={{ backgroundColor: 'transparent' }}><Icon name="back" /></RoundButton>
          {isLeader && <RoundButton label="친구 초대" onPress={invite}><HIcon name="addUser" size={20} /></RoundButton>}
        </View>
      </View>

      <View style={st.titleRow}>
        <View style={{ flex: 1, gap: 8 }}>
          <Text accessibilityRole="header" style={[T.display, { fontSize: 24, lineHeight: 28 }]}>{guild.name}</Text>
          <Text style={T.sub}>길드장 {guild.leader.nickname}</Text>
          <View style={{ marginTop: 6, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            {members && <Faces names={members.map((m) => m.nickname)} size={28} />}
            <Text style={T.foot}>{guild.memberCount}명 참여 중</Text>
          </View>
        </View>
        {boss && <View style={st.badge} accessible accessibilityLabel={`이번 주 보스, ${boss.status === 'DEFEATED' ? '처치 완료' : `남은 체력 ${boss.hp}`}`}>
          <Svg width={140} height={96} viewBox="0 0 140 96" style={StyleSheet.absoluteFill}>
            <Path d="M14 22 C 34 2, 104 0, 126 18 C 146 36, 138 78, 108 88 C 76 98, 26 94, 10 72 C -4 52, 0 34, 14 22 Z" fill={DS.accent} />
          </Svg>
          <Text style={{ color: DS.onAccent, fontSize: 13, fontWeight: '600' }}>이번 주 보스</Text>
          <Text style={[T.display, { color: DS.onAccent, fontSize: 18 }]}>{boss.status === 'DEFEATED' ? '처치 완료' : `HP ${boss.hp.toLocaleString()}`}</Text>
        </View>}
      </View>

      <View style={st.stats}>
        <Stat value={`${guild.memberCount}명`} label="길드원" />
        <Stat value="스쿼트" label="운동" divider />
        <Stat value={boss ? boss.guildTotalDamage.toLocaleString() : '-'} label="이번 주 피해" />
      </View>

      <View style={{ paddingHorizontal: 20, paddingTop: 24, gap: 4 }}>
        <Text accessibilityRole="header" style={T.headline}>길드원</Text>
        {members === null
          ? <Text style={[T.foot, { color: DS.danger }]}>길드원 목록을 불러오지 못했어요. 아래로 당겨 다시 불러오세요.</Text>
          : members.map((m) => <View key={m.userId} style={st.member}>
            <Faces names={[m.nickname]} size={36} />
            <Text style={[T.body, { flex: 1 }]} numberOfLines={1}>{m.nickname}{m.userId === me.id ? ' (나)' : ''}</Text>
            {m.role === 'LEADER' && <Tag label="길드장" tone="accent" />}
          </View>)}
      </View>
    </ScrollView>
    <BottomBar>
      {isLeader
        ? <Cta title="친구 초대하기" onPress={invite} />
        : <Cta title="운동 시작" onPress={() => router.push('/workout/setup')} />}
    </BottomBar>
  </Page>;
}

function Stat({ value, label, divider }: { value: string; label: string; divider?: boolean }) {
  return <View style={[st.stat, divider && { borderLeftWidth: 1, borderRightWidth: 1, borderColor: DS.separator }]}>
    <Text numberOfLines={1} style={[T.display, { fontSize: 18 }]}>{value}</Text>
    <Text style={T.foot}>{label}</Text>
  </View>;
}

const st = StyleSheet.create({
  topBar: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 20, paddingTop: 8 },
  hero: { height: 470, backgroundColor: DS.dot, overflow: 'hidden' },
  heroBar: { position: 'absolute', left: 0, right: 0, justifyContent: 'space-between' },
  boss: { position: 'absolute', left: '15%', right: '15%', top: 90, bottom: 40, width: undefined, height: undefined },
  hand: { position: 'absolute', right: 70, top: 108, color: DS.accent, fontSize: 20, lineHeight: 20, fontStyle: 'italic', fontWeight: '700', textAlign: 'center', transform: [{ rotate: '-7deg' }] },
  fade: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 140, backgroundColor: 'rgba(0,0,0,0.55)' },
  titleRow: { flexDirection: 'row', alignItems: 'flex-start', paddingHorizontal: 20, marginTop: 18, gap: 12 },
  badge: { width: 140, height: 96, alignItems: 'center', justifyContent: 'center' },
  stats: { marginHorizontal: 20, marginTop: 24, height: 74, borderRadius: 18, backgroundColor: DS.bg2, flexDirection: 'row', alignItems: 'center' },
  stat: { flex: 1, alignItems: 'center', gap: 4, paddingHorizontal: 4 },
  member: { minHeight: 56, flexDirection: 'row', alignItems: 'center', gap: 12 },
});
