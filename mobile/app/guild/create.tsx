// 길드 만들기 1/3·2/3·3/3 (시안 'GuildCreate', 'GuildCreate2', 'GuildCreate3'). API-009·010·046
// API-009는 이름만 받는다. 시안의 함께할 친구·분야·공개 설정·길드 소개는 받을 곳이 없어 만들지 않고,
// 길드 활동 목록·평균 스쿼트도 조회 API가 없어 뺐다. 친구는 만든 뒤 초대 코드(API-012)로 부른다.
import { useState } from 'react';
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';
import { HttpError } from '../../src/api/http';
import type { GuildBoss } from '../../src/api/game';
import { game } from '../../src/auth/session';
import { BottomBar, Cta, DS, Header, IconButton, Page, T } from '../../src/design/kit';
import { errorMessage, useLoad } from '../../src/game/useLoad';
import { home, type Guild } from '../../src/home/api';
import { avatarImage, HIcon, kstDateKey, Pill, StepCount } from '../../src/home/parts';

const NAME_MIN = 2;
const NAME_MAX = 20; // API-009: 앞뒤 공백을 뺀 2~20자

export default function GuildCreate() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ guild: Guild | null; guildId: string; boss: GuildBoss | null } | null>(null);
  const { data: character } = useLoad(() => game.myCharacter(), []);

  const trimmed = name.trim();
  const nameOk = trimmed.length >= NAME_MIN && trimmed.length <= NAME_MAX;

  const create = async () => {
    if (busy || !nameOk) return;
    setBusy(true); setError(null);
    try {
      const res = await home.createGuild(trimmed);
      const [guild, boss] = await Promise.all([home.guild(res.guildId).catch(() => null), game.guildBoss(res.guildId).catch(() => null)]);
      setCreated({ guild, guildId: res.guildId, boss });
      setStep(3);
    } catch (e) {
      if (e instanceof HttpError && e.status === 409) setError('이미 길드에 소속돼 있어요. 길드는 하나만 가입할 수 있어요.');
      else setError(errorMessage(e, '길드를 만들지 못했어요.'));
    } finally {
      setBusy(false);
    }
  };

  if (step === 3 && created) return <Created name={created.guild?.name ?? trimmed} {...created} />;

  const back = step === 2 ? () => { setError(null); setStep(1); } : undefined;

  return <Page>
    <Header title="길드 만들기" onBack={back} right={<View style={{ paddingRight: 12 }}><StepCount step={step} total={3} /></View>} />
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      {step === 1
        ? <ScrollView contentContainerStyle={{ padding: 20, gap: 10 }} keyboardShouldPersistTaps="handled">
          <Text nativeID="guildNameLabel" style={st.label}>길드 이름</Text>
          <TextInput value={name} onChangeText={setName} maxLength={NAME_MAX + 4} autoFocus
            accessibilityLabel="길드 이름" accessibilityLabelledBy="guildNameLabel"
            placeholder="2~20자" placeholderTextColor={DS.gray2} returnKeyType="next"
            onSubmitEditing={() => nameOk && setStep(2)} style={st.input} />
          <Text style={[T.foot, trimmed.length > NAME_MAX && { color: DS.danger }]}>
            {trimmed.length > NAME_MAX ? `길드 이름은 ${NAME_MAX}자까지예요.` : `${trimmed.length}/${NAME_MAX}자`}
          </Text>
        </ScrollView>
        : <View style={{ flex: 1 }}>
          <View style={st.preview}>
            <Pill filled style={{ alignSelf: 'center' }}>{trimmed}</Pill>
            <View style={st.circle}>
              <Image source={avatarImage(character?.avatarId)} accessibilityLabel="길드장이 될 내 캐릭터" resizeMode="contain" style={{ width: 120, height: 150 }} />
            </View>
          </View>
          <View style={st.panel}>
            <Text style={T.headline}>길드장이 됩니다</Text>
            <Text style={T.sub}>만든 뒤 초대 코드로 친구를 부를 수 있어요. 애매한 기록은 길드원이 길드장에게 확인을 요청해요.</Text>
            {error && <Text style={[T.foot, { color: DS.danger }]}>{error}</Text>}
          </View>
        </View>}
      <BottomBar style={step === 2 ? { backgroundColor: DS.bg2 } : undefined}>
        {step === 1
          ? <Cta title="다음" onPress={() => setStep(2)} disabled={!nameOk} />
          : <Cta title="길드 만들기" onPress={create} loading={busy} />}
      </BottomBar>
    </KeyboardAvoidingView>
  </Page>;
}

/** 3/3 만들어진 뒤 */
function Created({ name, guild, guildId, boss }: { name: string; guild: Guild | null; guildId: string; boss: GuildBoss | null }) {
  const router = useRouter();
  const memberCount = guild?.memberCount;
  const today = kstDateKey(new Date());
  // 보스 마감까지 남은 날 (오늘 포함, KST)
  const daysLeft = boss ? Math.max(0, Math.round((Date.parse(boss.weekEnd) - Date.parse(today)) / 86400000) + 1) : null;

  return <Page>
    <View style={st.createdTop}>
      <IconButton name="menu" label="메뉴 열기" onPress={() => router.push('/menu')} />
      <View style={{ flex: 1, alignItems: 'center' }}>
        <View accessibilityRole="alert" style={st.toast}>
          <Text style={{ color: DS.label, fontSize: 13 }}>길드가 만들어졌습니다{memberCount !== undefined ? ` · 길드원 ${memberCount}명` : ''}</Text>
        </View>
      </View>
      <View style={{ width: 44 }} />
    </View>
    <ScrollView contentContainerStyle={{ paddingBottom: 24 }}>
      <View style={st.bubbles}>
        {boss && <View style={[st.bubble, { width: 160, height: 160, left: '50%', top: 8, backgroundColor: DS.accent }]}>
          <Text style={st.bubbleCap}>이번 주 피해</Text><Text style={[st.bubbleVal, { fontSize: 20 }]}>{boss.guildTotalDamage.toLocaleString()}</Text>
        </View>}
        {memberCount !== undefined && <View style={[st.bubble, { width: 104, height: 104, left: 52, top: 28, backgroundColor: DS.accent300 }]}>
          <Text style={st.bubbleCap}>길드원</Text><Text style={st.bubbleVal}>{memberCount}명</Text>
        </View>}
        {daysLeft !== null && <View style={[st.bubble, { width: 96, height: 96, left: 178, top: 186, backgroundColor: DS.accent700 }]}>
          <Text style={st.bubbleCap}>보스 마감</Text><Text style={st.bubbleVal}>{daysLeft}일</Text>
        </View>}
      </View>
      <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 20, flexWrap: 'wrap' }}>
        <Pill>{name}</Pill>
      </View>
      <View style={st.activity}>
        <Text accessibilityRole="header" style={T.headline}>다음 할 일</Text>
        <Text style={T.sub}>친구를 초대해 이번 주 보스를 함께 공략해 보세요. 스쿼트 기록이 보상으로 지급되면 보스 피해에 더해져요.</Text>
        <Cta title="길드 보기" variant="outline" onPress={() => router.replace({ pathname: '/guild/[id]', params: { id: guildId } })} />
      </View>
    </ScrollView>
    <Pressable accessibilityRole="button" accessibilityLabel="친구 초대" onPress={() => router.push({ pathname: '/guild/invite', params: { id: guildId, name } })} style={st.fab}>
      <HIcon name="addUser" size={24} color={DS.onAccent} />
    </Pressable>
  </Page>;
}

const st = StyleSheet.create({
  label: { color: DS.label, fontSize: 14, fontWeight: '700' },
  input: { height: 48, paddingHorizontal: 20, borderRadius: 999, borderWidth: 1.5, borderColor: '#48484A', color: DS.label, fontSize: 15 },
  preview: { height: 260, alignItems: 'center', gap: 16, paddingTop: 8 },
  circle: { width: 200, height: 200, borderRadius: 999, borderWidth: 1.5, borderStyle: 'dashed', borderColor: '#48484A', alignItems: 'center', justifyContent: 'flex-end', overflow: 'hidden' },
  panel: { flex: 1, borderTopLeftRadius: 28, borderTopRightRadius: 28, backgroundColor: DS.bg2, padding: 20, paddingTop: 28, gap: 10 },
  createdTop: { height: 56, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8 },
  toast: { height: 30, paddingHorizontal: 14, borderRadius: 999, backgroundColor: DS.bg2, justifyContent: 'center' },
  bubbles: { height: 300, marginTop: 8 },
  bubble: { position: 'absolute', borderRadius: 999, alignItems: 'center', justifyContent: 'center', gap: 2 },
  bubbleCap: { color: DS.onAccent, fontSize: 13, fontWeight: '600' },
  bubbleVal: { color: DS.onAccent, fontSize: 14, fontWeight: '700' },
  activity: { marginTop: 24, marginHorizontal: 0, borderTopLeftRadius: 28, borderTopRightRadius: 28, backgroundColor: DS.band, padding: 20, gap: 12, minHeight: 260 },
  fab: { position: 'absolute', right: 20, bottom: 48, width: 60, height: 52, borderRadius: 999, backgroundColor: DS.accent, alignItems: 'center', justifyContent: 'center', elevation: 6, shadowColor: '#000', shadowOpacity: 0.5, shadowRadius: 10, shadowOffset: { width: 0, height: 8 } },
});
