// 캐릭터 이름 (시안 'F-01 캐릭터 이름'). 이 이름이 닉네임. '다음'에서 가입·로그인·캐릭터 생성을 한다.
import { useState } from 'react';
import { Image, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { api } from '../../src/auth/session';
import { completeSignup } from '../../src/onboarding/complete';
import { avatarOf, useDraft } from '../../src/onboarding/draft';
import { NAME_MAX, NAME_MIN, isName } from '../../src/onboarding/rules';
import { ErrorText, Field, OB, PillButton, Screen, Sub, Title } from '../../src/onboarding/ui';

export default function Name() {
  const router = useRouter();
  const { draft, update } = useDraft();
  const [name, setName] = useState(draft.nickname);
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; backTo?: 'signup' | 'birth' } | null>(null);
  const avatar = avatarOf(draft.avatarId);

  const next = async () => {
    setTouched(true);
    if (!isName(name) || busy) return;
    setBusy(true); setError(null);
    const result = await completeSignup(api, { ...draft, nickname: name }, () => update({ signedUp: true }));
    setBusy(false);
    if (result.ok) {
      update({ nickname: name.trim(), password: '' }); // 비밀번호는 더 들고 있지 않는다
      router.replace('/onboarding/guild');
    } else {
      update({ nickname: name.trim() });
      setError(result);
    }
  };

  return <Screen>
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={{ gap: 8 }}>
          <Title>캐릭터 이름을 지어 주십시오</Title>
          <Sub>이 이름이 닉네임으로도 쓰입니다.</Sub>
        </View>
        <View style={styles.preview}>
          <Image source={avatar.image} accessibilityLabel="고른 캐릭터 미리보기" resizeMode="contain" style={{ height: 176, width: 113 }} />
        </View>
        <Field variant="box" label="이름" value={name} onChangeText={setName} placeholder={`${NAME_MIN}~${NAME_MAX}자`} maxLength={NAME_MAX + 4}
          error={touched && !isName(name) ? `이름은 ${NAME_MIN}~${NAME_MAX}자로 지어 주세요.` : null} onSubmitEditing={next} returnKeyType="done" />
        {error && <View style={{ gap: 8 }}>
          <ErrorText>{error.message}</ErrorText>
          {error.backTo === 'signup' && <PillButton variant="text" title="이메일 다시 입력" onPress={() => router.dismissTo('/onboarding/signup')} />}
          {error.backTo === 'birth' && <PillButton variant="text" title="생년월일 다시 입력" onPress={() => router.dismissTo('/onboarding/birth')} />}
        </View>}
      </ScrollView>
      <View style={styles.bottom}>
        <PillButton title="다음" onPress={next} loading={busy} />
        <PillButton title="아바타 다시 고르기" variant="text" onPress={() => router.back()} disabled={busy} />
      </View>
    </KeyboardAvoidingView>
  </Screen>;
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, paddingHorizontal: 24, paddingTop: 16, gap: 28 },
  preview: { height: 200, borderRadius: 16, backgroundColor: OB.surface, alignItems: 'center', justifyContent: 'center' },
  bottom: { paddingHorizontal: 24, paddingBottom: 8 },
});
