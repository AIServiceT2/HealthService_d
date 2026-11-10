// 회원가입 (시안 'F-01 로그인·가입'). 이메일·비밀번호만 모으고, 실제 가입(API-001)은 닉네임을 받는 이름 단계에서 한다.
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useDraft } from '../../src/onboarding/draft';
import { isEmail, isPassword } from '../../src/onboarding/rules';
import { Accent, BodyHero, FadeToBlack, Field, PillButton, ProgressDots, Screen, Sub, Title } from '../../src/onboarding/ui';

export default function Signup() {
  const router = useRouter();
  const { draft, update } = useDraft();
  const [email, setEmail] = useState(draft.email);
  const [password, setPassword] = useState(draft.password);
  const [touched, setTouched] = useState(false);
  const emailError = touched && !isEmail(email) ? '이메일 형식을 확인해 주세요.' : null;
  const passwordError = touched && !isPassword(password) ? '비밀번호는 8~64자로 입력해 주세요.' : null;

  const next = () => {
    setTouched(true);
    if (!isEmail(email) || !isPassword(password)) return;
    // 이메일이 바뀌면 새로 가입해야 하므로 '가입됨' 표시를 지운다
    update({ email: email.trim(), password, signedUp: draft.signedUp && draft.email === email.trim() });
    router.push('/onboarding/avatar');
  };

  return <Screen>
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={styles.hero} pointerEvents="none"><BodyHero width={330} height={529} /></View>
      <FadeToBlack top={250} height={300} />
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <ProgressDots count={4} active={3} />
        <View style={styles.body}>
          <View style={{ gap: 8, maxWidth: 300 }}>
            <Title>회원가입</Title>
            <Sub>두 가지만 알려 주면 <Accent>바로</Accent> 운동을 시작할 수 있습니다.</Sub>
          </View>
          <View style={{ gap: 12 }}>
            <Field label="이메일" value={email} onChangeText={setEmail} placeholder="you@example.com" error={emailError}
              keyboardType="email-address" autoCapitalize="none" autoCorrect={false} autoComplete="email" textContentType="emailAddress" />
            <Field label="비밀번호" value={password} onChangeText={setPassword} placeholder="8자 이상" error={passwordError}
              secureTextEntry autoCapitalize="none" autoComplete="new-password" textContentType="newPassword" onSubmitEditing={next} />
          </View>
        </View>
      </ScrollView>
      <View style={styles.bottom}>
        <PillButton title="계속하기" onPress={next} />
        <PillButton title="이미 계정이 있습니다" variant="text" onPress={() => router.push('/login')} />
      </View>
    </KeyboardAvoidingView>
  </Screen>;
}

const styles = StyleSheet.create({
  hero: { position: 'absolute', left: 150, top: 24 },
  scroll: { flexGrow: 1, paddingHorizontal: 24, paddingTop: 12 },
  body: { flex: 1, justifyContent: 'flex-end', gap: 24, paddingTop: 240, paddingBottom: 16 },
  bottom: { paddingHorizontal: 24, paddingBottom: 8 },
});
