// 캐릭터 정보 (시안 'F-01 캐릭터 성장 조회'). API-005·007·044
// 경험치는 확정(confirmed)과 24시간 확정 대기(pending)를 나눠 보여 주고, 확정 대기를 확정에 더해 표시하지 않는다 (DESIGN.md 4절, backlog US-04).
// 시안의 능력치 4칸(상체·하체·코어·지구력)은 서버 능력치 축이 미정(stats 빈 배열)이라 만들지 않는다.
import { Image, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { api, game } from '../src/auth/session';
import { DS, ErrorState, Header, Icon, Loading, Page, T } from '../src/design/kit';
import { skillName } from '../src/game/rules';
import { useLoad } from '../src/game/useLoad';
import { home, type InventoryItem } from '../src/home/api';
import { avatarImage, HIcon, kstShort } from '../src/home/parts';

export default function Character() {
  const { data, error, loading, reload } = useLoad(async () => {
    const [me, character, items] = await Promise.all([
      api.me(), game.myCharacter(), home.inventory().catch(() => null as InventoryItem[] | null),
    ]);
    return { me, character, items };
  }, []);

  if (!data && loading) return <Page><Header title="캐릭터 정보" /><Loading /></Page>;
  if (!data) return <Page><Header title="캐릭터 정보" /><ErrorState message={error ?? '캐릭터 정보를 불러오지 못했어요'} onRetry={reload} /></Page>;

  const { me, character, items } = data;
  const { confirmed, pending } = character.exp;
  const total = confirmed + pending;
  const locked = items?.filter((i) => i.status === 'LOCKED') ?? [];
  const nextUnlock = locked.map((i) => i.unlockAt).sort()[0];

  return <Page>
    <Header title="캐릭터 정보" />
    <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 40, gap: 28 }}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={reload} tintColor={DS.accent} />}>
      <View style={st.card}>
        <Image source={avatarImage(character.avatarId)} accessibilityLabel="내 캐릭터" resizeMode="contain" style={st.avatar} />
        <View style={st.info}>
          <Text numberOfLines={1} style={[T.display, { fontSize: 20 }]}>{me.nickname}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Text style={{ color: DS.label, fontSize: 13, fontWeight: '800' }}>LV.{character.level}</Text>
            {/* 막대 전체 = 확정 + 확정 대기. 레벨업 기준 경험치는 서버에 없어 비율로만 그린다 */}
            <View accessibilityLabel={`경험치 확정 ${confirmed}, 확정 대기 ${pending}`} style={st.bar}>
              {total > 0 && <View style={[st.fill, { width: '100%', backgroundColor: '#E5E5EA' }]} />}
              {total > 0 && <View style={[st.fill, { width: `${(confirmed / total) * 100}%`, backgroundColor: '#34C759' }]} />}
              <View style={st.shine} />
            </View>
          </View>
          <Text style={T.foot}>경험치 {confirmed.toLocaleString()} 확정</Text>
          {pending > 0 && <Text style={T.foot}>+{pending.toLocaleString()} 경험치는 24시간 뒤 확정</Text>}
          <View style={{ marginTop: 6, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <View style={st.skillIcon}><HIcon name="shorts" size={18} color={DS.accent} /></View>
            <View><Text style={T.foot}>스킬</Text><Text style={{ color: DS.label, fontSize: 14, fontWeight: '700' }}>{skillName('SQUAT')}</Text></View>
          </View>
        </View>
      </View>

      <View style={{ gap: 12 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <Text accessibilityRole="header" style={{ color: DS.label, fontSize: 14, fontWeight: '700' }}>최근 얻은 아이템</Text>
          <Text style={T.foot}>24시간 뒤 사용 가능</Text>
        </View>
        {items === null
          ? <Text style={[T.foot, { color: DS.danger }]}>아이템을 불러오지 못했어요. 아래로 당겨 다시 불러오세요.</Text>
          : items.length === 0
            ? <Text style={T.foot}>아직 얻은 아이템이 없어요. 운동 보상이 지급되면 여기에 보여요.</Text>
            : <>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12 }}>
                {items.map((it) => {
                  const isLocked = it.status === 'LOCKED';
                  return <View key={it.itemId} accessible
                    accessibilityLabel={isLocked ? `잠긴 아이템, ${kstShort(it.unlockAt)}부터 사용 가능` : '사용 가능한 아이템'}
                    style={[st.item, { borderColor: isLocked ? DS.accent700 : DS.separator }]}>
                    <HIcon name="box" size={22} color={isLocked ? DS.accent : DS.label} />
                    {isLocked && <View style={st.lock}><Icon name="lock" size={11} color={DS.label} /></View>}
                  </View>;
                })}
              </View>
              {locked.length > 0 && nextUnlock && <Text style={T.foot}>
                잠긴 아이템 {locked.length}개 · {kstShort(nextUnlock)}부터 차례로 풀려요
              </Text>}
            </>}
      </View>
    </ScrollView>
  </Page>;
}

const st = StyleSheet.create({
  card: { minHeight: 188, borderRadius: 20, backgroundColor: DS.bg2, overflow: 'hidden', flexDirection: 'row' },
  avatar: { width: 120, height: 176, marginLeft: 8, alignSelf: 'flex-end' },
  info: { flex: 1, paddingTop: 22, paddingBottom: 16, paddingLeft: 12, paddingRight: 16, gap: 6 },
  bar: { flex: 1, height: 16, borderRadius: 4, borderWidth: 1.5, borderColor: DS.bg, backgroundColor: DS.dot, overflow: 'hidden' },
  fill: { position: 'absolute', left: 0, top: 0, bottom: 0 },
  shine: { position: 'absolute', left: 0, right: 0, top: 0, height: '40%', backgroundColor: 'rgba(255,255,255,0.22)' },
  skillIcon: { width: 36, height: 36, borderRadius: 999, borderWidth: 1.5, borderColor: DS.accent, alignItems: 'center', justifyContent: 'center' },
  item: { width: 64, height: 64, borderRadius: 14, borderWidth: 1.5, backgroundColor: DS.bg2, alignItems: 'center', justifyContent: 'center' },
  lock: { position: 'absolute', right: -4, top: -4, width: 20, height: 20, borderRadius: 999, backgroundColor: DS.bg3, alignItems: 'center', justifyContent: 'center' },
});
