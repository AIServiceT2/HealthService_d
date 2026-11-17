// 길드 가입 (시안 'GuildJoin'). 초대 코드(API-013) 또는 추천 길드([추가] API) 중 하나로 가입. 건너뛸 수 있다.
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import type { RecommendedGuild } from '../../src/api/account';
import { HttpError } from '../../src/api/http';
import { api } from '../../src/auth/session';
import { useDraft } from '../../src/onboarding/draft';
import { isInviteCode, normalizeInviteCode } from '../../src/onboarding/rules';
import { Cta, DS, Page } from '../../src/design/kit';
import { ErrorLine, InputField, QuietButton, StepHeading } from '../../src/onboarding/parts';

export default function Guild() {
  const router = useRouter();
  const { reset } = useDraft();
  const [code, setCode] = useState('');
  const [guilds, setGuilds] = useState<RecommendedGuild[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null); setGuilds(null);
    try { setGuilds(await api.recommendedGuilds()); } catch (e) { setLoadError(e instanceof Error ? e.message : '추천 길드를 불러오지 못했어요.'); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const finish = () => { reset(); router.dismissAll(); router.replace('/home'); };
  const usingCode = code.trim().length > 0;
  const codeError = usingCode && !isInviteCode(code) ? '초대 코드는 영문·숫자 6자예요.' : null;

  const join = async () => {
    if (busy || (usingCode ? codeError : !selected)) return;
    setBusy(true); setError(null);
    try {
      if (usingCode) await api.joinGuildByCode(normalizeInviteCode(code));
      else await api.joinGuild(selected!);
      finish();
    } catch (e) {
      if (e instanceof HttpError && e.status === 404) setError(usingCode ? '초대 코드를 찾을 수 없어요. 길드장에게 다시 확인해 주세요.' : '길드를 찾을 수 없어요. 목록을 새로 불러와 주세요.');
      else setError(e instanceof Error ? e.message : '길드에 가입하지 못했어요.');
      setBusy(false);
    }
  };

  return <Page>
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <StepHeading title="함께할 길드를 골라요" sub="애매한 기록은 길드장에게 확인을 요청할 수 있습니다." />
        <InputField variant="box" label="초대 코드" value={code} onChangeText={(v) => { setCode(v); if (v) setSelected(null); }}
          placeholder="길드장에게 받은 코드" autoCapitalize="characters" autoCorrect={false} maxLength={8} error={codeError} />
        <Text style={styles.section}>추천 길드</Text>
        <View style={{ gap: 10 }}>
          {guilds === null && !loadError && <ActivityIndicator color={DS.accent} accessibilityLabel="추천 길드 불러오는 중" />}
          {loadError && <View style={{ gap: 4 }}><ErrorLine>{loadError}</ErrorLine><QuietButton title="다시 불러오기" onPress={load} /></View>}
          {guilds?.length === 0 && <Text style={styles.empty}>아직 추천할 길드가 없어요. 초대 코드로 가입하거나 나중에 할 수 있어요.</Text>}
          {guilds?.map((g) => {
            const on = selected === g.guildId;
            return <Pressable key={g.guildId} accessibilityRole="radio" accessibilityState={{ checked: on }}
              accessibilityLabel={`${g.name}, 길드원 ${g.memberCount}명`}
              onPress={() => { setSelected(on ? null : g.guildId); setCode(''); }}
              style={[styles.card, on && styles.cardOn]}>
              <View style={styles.emblem} />
              <View style={{ gap: 4, flex: 1 }}>
                <Text style={styles.cardName}>{g.name}</Text>
                <Text style={styles.cardSub}>길드원 {g.memberCount}명</Text>
              </View>
            </Pressable>;
          })}
        </View>
        <ErrorLine>{error}</ErrorLine>
      </ScrollView>
      <View style={styles.bottom}>
        <Cta title="가입하고 시작" onPress={join} loading={busy} disabled={usingCode ? !!codeError : !selected} />
        <QuietButton title="나중에 하겠습니다" onPress={finish} disabled={busy} />
      </View>
    </KeyboardAvoidingView>
  </Page>;
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, paddingHorizontal: 20, paddingTop: 16, paddingBottom: 16, gap: 24 },
  section: { fontSize: 13, color: DS.label2, marginBottom: -14 },
  empty: { color: DS.label2, fontSize: 14, lineHeight: 21 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, borderRadius: 14, borderWidth: 1, borderColor: DS.bg3, backgroundColor: DS.bg2 },
  cardOn: { borderWidth: 2, borderColor: DS.accent, padding: 15 },
  emblem: { width: 44, height: 44, borderRadius: 12, backgroundColor: DS.bg3 },
  cardName: { fontSize: 16, fontWeight: '600', color: DS.label },
  cardSub: { fontSize: 13, color: DS.label2 },
  bottom: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 4 },
});
