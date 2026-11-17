// 로그인 (시안 'SignIn'). API-002 → API-005로 캐릭터 유무를 보고 홈 또는 캐릭터 만들기로 보낸다.
// 시안의 '비밀번호를 잊으셨습니까?'(비밀번호 재설정)와 Apple·Google·카카오 로그인은 API가 없어 넣지 않았다.
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { HttpError } from '../src/api/http';
import { api } from '../src/auth/session';
import { Cta, Page } from '../src/design/kit';
import { isEmail } from '../src/onboarding/rules';
import { ErrorLine, FooterLink, InputField, StepHeading } from '../src/onboarding/parts';

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

  return <Page>
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <StepHeading center title="로그인" sub="다시 오신 것을 환영합니다" />
        <View style={styles.form}>
          <InputField label="이메일" value={email} onChangeText={setEmail} placeholder="example@email.com"
            keyboardType="email-address" autoCapitalize="none" autoCorrect={false} autoComplete="email" textContentType="emailAddress" />
          <InputField label="비밀번호" password value={password} onChangeText={setPassword} placeholder="비밀번호 입력"
            autoCapitalize="none" autoComplete="current-password" textContentType="password" onSubmitEditing={login} />
          <ErrorLine>{error}</ErrorLine>
          <Cta title="로그인" onPress={login} loading={busy} disabled={!ready} style={{ marginTop: 12 }} />
        </View>
      </ScrollView>
      <View style={styles.bottom}>
        <FooterLink text="계정이 없으십니까?" link="회원가입" onPress={() => router.push('/onboarding/birth')} disabled={busy} />
      </View>
    </KeyboardAvoidingView>
  </Page>;
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, paddingHorizontal: 20, paddingTop: 150 },
  form: { marginTop: 48, gap: 16 },
  bottom: { paddingHorizontal: 20, paddingBottom: 16 },
});
