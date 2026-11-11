// 로그인 (시안 '로그인'). API-002 → API-005로 캐릭터 유무를 보고 홈 또는 캐릭터 만들기로 보낸다.
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { HttpError } from '../src/api/http';
import { api } from '../src/auth/session';
import { isEmail } from '../src/onboarding/rules';
import { Accent, BodyHero, ErrorText, FadeToBlack, Field, PillButton, Screen, Sub, Title } from '../src/onboarding/ui';

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ready = isEmail(email) && password.length > 0;

  const login = async () => {
    if (!ready || busy) return;
    setBusy(true); setError(null);
    try {
      await api.login(email.trim(), password);
      const me = await api.me();
      router.dismissAll();
      router.replace(me.hasCharacter ? '/home' : { pathname: '/onboarding/avatar', params: { existing: '1' } });
    } catch (e) {
      setError(e instanceof HttpError && e.status === 401 ? '이메일 또는 비밀번호가 맞지 않아요.' : e instanceof Error ? e.message : '로그인하지 못했어요.');
      setBusy(false);
    }
  };

  return <Screen>
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={styles.hero} pointerEvents="none"><BodyHero width={330} height={529} /></View>
      <FadeToBlack top={250} height={300} />
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={{ gap: 8 }}>
          <Title>로그인</Title>
          <Sub>다시 오신 것을 <Accent>환영합니다</Accent>.</Sub>
        </View>
        <View style={{ gap: 12 }}>
          <Field label="이메일" value={email} onChangeText={setEmail} placeholder="you@example.com"
            keyboardType="email-address" autoCapitalize="none" autoCorrect={false} autoComplete="email" textContentType="emailAddress" />
          <Field label="비밀번호" value={password} onChangeText={setPassword} placeholder="비밀번호"
            secureTextEntry autoCapitalize="none" autoComplete="current-password" textContentType="password" onSubmitEditing={login} />
          <ErrorText>{error}</ErrorText>
        </View>
      </ScrollView>
      <View style={styles.bottom}>
        <PillButton title="로그인" onPress={login} loading={busy} disabled={!ready} />
        <PillButton title="처음이십니까? 회원가입" variant="text" onPress={() => router.push('/onboarding/birth')} disabled={busy} />
      </View>
    </KeyboardAvoidingView>
  </Screen>;
}

const styles = StyleSheet.create({
  hero: { position: 'absolute', left: 150, top: 24 },
  scroll: { flexGrow: 1, justifyContent: 'flex-end', paddingHorizontal: 24, paddingTop: 260, gap: 24, paddingBottom: 16 },
  bottom: { paddingHorizontal: 24, paddingBottom: 8 },
});
