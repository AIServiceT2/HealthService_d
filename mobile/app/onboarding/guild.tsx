// 길드 가입 (시안 'F-01 길드 가입'). 초대 코드(API-013) 또는 추천 길드([추가] API) 중 하나로 가입. 건너뛸 수 있다.
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import type { RecommendedGuild } from '../../src/api/account';
import { HttpError } from '../../src/api/http';
import { api } from '../../src/auth/session';
import { useDraft } from '../../src/onboarding/draft';
import { isInviteCode, normalizeInviteCode } from '../../src/onboarding/rules';
import { ErrorText, Field, OB, PillButton, Screen, Sub, Title } from '../../src/onboarding/ui';

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

  return <Screen>
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={{ gap: 8 }}>
          <Title>함께할 길드를 골라요</Title>
          <Sub>애매한 기록은 길드장에게 확인을 요청할 수 있습니다.</Sub>
        </View>
        <Field variant="box" label="초대 코드" value={code} onChangeText={(v) => { setCode(v); if (v) setSelected(null); }}
          placeholder="길드장에게 받은 코드" autoCapitalize="characters" autoCorrect={false} maxLength={8} error={codeError} />
        <Text style={styles.section}>추천 길드</Text>
        <View style={{ gap: 10 }}>
          {guilds === null && !loadError && <ActivityIndicator color={OB.accent} accessibilityLabel="추천 길드 불러오는 중" />}
          {loadError && <View style={{ gap: 4 }}><ErrorText>{loadError}</ErrorText><PillButton variant="text" title="다시 불러오기" onPress={load} /></View>}
          {guilds?.length === 0 && <Sub>아직 추천할 길드가 없어요. 초대 코드로 가입하거나 나중에 할 수 있어요.</Sub>}
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
        <ErrorText>{error}</ErrorText>
      </ScrollView>
      <View style={styles.bottom}>
        <PillButton title="가입하고 시작" onPress={join} loading={busy} disabled={usingCode ? !!codeError : !selected} />
        <PillButton title="나중에 하겠습니다" variant="text" onPress={finish} disabled={busy} />
      </View>
    </KeyboardAvoidingView>
  </Screen>;
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, paddingHorizontal: 24, paddingTop: 16, gap: 24 },
  section: { fontSize: 13, color: OB.muted, marginBottom: -14 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, borderRadius: 14, borderWidth: 1, borderColor: OB.surfaceRaised, backgroundColor: OB.surface },
  cardOn: { borderWidth: 2, borderColor: OB.accent, padding: 15 },
  emblem: { width: 44, height: 44, borderRadius: 12, backgroundColor: OB.surfaceRaised },
  cardName: { fontSize: 16, fontWeight: '600', color: '#FFFFFF' },
  cardSub: { fontSize: 13, color: OB.muted },
  bottom: { paddingHorizontal: 24, paddingBottom: 8 },
});
