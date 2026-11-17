// 회원가입 (시안 'Login' = 회원가입 화면). 이메일·비밀번호만 모으고, 실제 가입(API-001)은 닉네임을 받는 이름 단계에서 한다.
// 시안의 Apple·Google·카카오 가입은 API가 없어 넣지 않았고, 그래서 안내 문구의 '다른 계정으로 가입' 부분도 뺐다.
// 시안의 다음 화면(온보딩 질문)은 MVP 밖이라 바로 캐릭터 선택으로 간다.
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Cta, DS, Icon, Page } from '../../src/design/kit';
import { useDraft } from '../../src/onboarding/draft';
import { isEmail, isPassword } from '../../src/onboarding/rules';
import { FooterLink, InputField, StepHeading } from '../../src/onboarding/parts';

export default function Signup() {
  const router = useRouter();
  const { draft, update } = useDraft();
  const [email, setEmail] = useState(draft.email);
  const [password, setPassword] = useState(draft.password);
  const [confirm, setConfirm] = useState(draft.password);
  const [agreed, setAgreed] = useState(!!draft.password); // 이미 이 단계를 지났으면 동의한 것
  const [touched, setTouched] = useState(false);
  const emailError = touched && !isEmail(email) ? '이메일 형식을 확인해 주세요.' : null;
  const passwordError = touched && !isPassword(password) ? '비밀번호는 8~64자로 입력해 주세요.' : null;
  const confirmError = touched && isPassword(password) && confirm !== password ? '비밀번호가 서로 달라요.' : null;
  const agreeError = touched && !agreed ? '약관에 동의해야 가입할 수 있어요.' : null;

  const next = () => {
    setTouched(true);
    if (!isEmail(email) || !isPassword(password) || confirm !== password || !agreed) return;
    // 이메일이 바뀌면 새로 가입해야 하므로 '가입됨' 표시를 지운다
    update({ email: email.trim(), password, signedUp: draft.signedUp && draft.email === email.trim() });
    router.push('/onboarding/avatar');
  };

  return <Page>
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <StepHeading center title="회원가입" sub="아래 정보를 입력해 주십시오" />
        <View style={styles.form}>
          <InputField label="이메일" value={email} onChangeText={setEmail} placeholder="example@email.com" error={emailError}
            keyboardType="email-address" autoCapitalize="none" autoCorrect={false} autoComplete="email" textContentType="emailAddress" />
          <InputField label="비밀번호" password value={password} onChangeText={setPassword} placeholder="8자 이상" error={passwordError}
            autoCapitalize="none" autoComplete="new-password" textContentType="newPassword" />
          <InputField label="비밀번호 확인" password value={confirm} onChangeText={setConfirm} placeholder="한 번 더 입력" error={confirmError}
            autoCapitalize="none" autoComplete="new-password" textContentType="newPassword" onSubmitEditing={next} />
          <View style={{ gap: 6 }}>
            <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: agreed }}
              accessibilityLabel="이용약관 및 개인정보 처리방침에 동의합니다" onPress={() => setAgreed((v) => !v)} style={styles.agree}>
              <View style={[styles.box, agreed && styles.boxOn]}>{agreed && <Icon name="check" size={12} color={DS.onAccent} />}</View>
              <Text style={styles.agreeText}><Text style={styles.agreeStrong}>이용약관 및 개인정보 처리방침</Text>에 동의합니다</Text>
            </Pressable>
            {agreeError ? <Text accessibilityLiveRegion="polite" style={styles.error}>{agreeError}</Text> : null}
          </View>
          <Cta title="회원가입" onPress={next} style={{ marginTop: 8 }} />
        </View>
      </ScrollView>
      <View style={styles.bottom}>
        <FooterLink text="이미 계정이 있습니까?" link="로그인" onPress={() => router.push('/login')} />
      </View>
    </KeyboardAvoidingView>
  </Page>;
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, paddingHorizontal: 20, paddingTop: 90 },
  form: { marginTop: 40, gap: 16 },
  agree: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 44 },
  box: { width: 20, height: 20, borderRadius: 6, borderWidth: 1.5, borderColor: DS.gray2, alignItems: 'center', justifyContent: 'center' },
  boxOn: { backgroundColor: DS.accent, borderColor: DS.accent },
  agreeText: { flex: 1, color: DS.label, fontSize: 13 },
  agreeStrong: { color: DS.accent, fontWeight: '700' },
  error: { color: DS.danger, fontSize: 13, lineHeight: 18 },
  bottom: { paddingHorizontal: 20, paddingBottom: 16 },
});
