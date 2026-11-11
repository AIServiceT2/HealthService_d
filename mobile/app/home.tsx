import { useState } from 'react';
import { useRouter } from 'expo-router';
import { ScrollView, Text, TextInput, StyleSheet } from 'react-native';
import { ActionButton } from '../src/components/ActionButton';
import { COLORS, FONT, RADIUS, SPACE, TOUCH_MIN } from '../src/theme/tokens';
import { IS_MOCK_MODE, isSubmissionId } from '../src/api/submissions';
import { logout } from '../src/auth/session';
export default function Home() {
  const [id, setId] = useState(''); const router = useRouter();
  const valid = isSubmissionId(id.trim());
  const open = () => router.push({ pathname: '/workout/[id]', params: { id: id.trim() } });
  return <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
    <Text style={styles.eyebrow}>운동이 전투가 되는 순간</Text>
    <Text style={styles.title}>오늘의 운동,{'\n'}얼마나 강해졌을까?</Text>
    <Text style={styles.body}>운동 기록의 인정 횟수와 계산된 타격 수를 확인하세요.</Text>
    <Text style={styles.label}>제출건 ID</Text>
    <TextInput accessibilityLabel="제출건 ID" value={id} onChangeText={setId} autoCapitalize="none" autoCorrect={false}
      placeholder="시드로 생성한 제출건 UUID" placeholderTextColor={COLORS.textMuted} style={styles.input}
      onSubmitEditing={() => valid && open()} />
    {id.length === 0 && <Text style={styles.hint}>제출건 ID를 입력하면 버튼을 누를 수 있어요.</Text>}
    {id.length > 0 && !valid && <Text style={styles.error}>UUID 형식의 제출건 ID를 입력해 주세요.</Text>}
    <ActionButton title="보상 미리보기" disabled={!valid} onPress={open} />
    <ActionButton title="로그아웃" secondary onPress={async () => { await logout(); router.replace('/'); }} />
    <Text style={styles.note}>첫 기능 시연 · US-02{'\n'}{IS_MOCK_MODE ? '목데이터 모드입니다. UUID로 예시 기록을 조회하며 서버에는 저장되지 않아요.' : '서버 시드로 만든 기록을 조회합니다. 아직 전투 결과가 지급된 상태는 아닙니다.'}</Text>
  </ScrollView>;
}
const styles = StyleSheet.create({
  page: { padding: SPACE.medium, gap: SPACE.medium, paddingBottom: SPACE.section },
  eyebrow: { ...FONT.caption, color: COLORS.primary, marginTop: SPACE.large },
  title: { ...FONT.title, color: COLORS.text },
  body: { ...FONT.body, color: COLORS.textMuted, marginBottom: SPACE.large },
  label: { ...FONT.body, color: COLORS.text },
  input: { ...FONT.body, color: COLORS.text, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border, borderRadius: RADIUS.control, minHeight: TOUCH_MIN, paddingHorizontal: SPACE.medium },
  hint: { ...FONT.caption, color: COLORS.textMuted },
  error: { ...FONT.caption, color: COLORS.danger },
  note: { ...FONT.caption, color: COLORS.textMuted, marginTop: SPACE.large },
});
