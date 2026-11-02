import { useState } from 'react';
import { useRouter } from 'expo-router';
import { ScrollView, Text, TextInput, StyleSheet } from 'react-native';
import { ActionButton } from '../src/components/ActionButton';
import { COLORS, SPACE } from '../src/theme/tokens';
import { isSubmissionId } from '../src/api/submissions';
export default function Home() {
  const [id, setId] = useState(''); const router = useRouter();
  const valid = isSubmissionId(id.trim());
  return <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
    <Text style={styles.eyebrow}>운동이 전투가 되는 순간</Text>
    <Text style={styles.title}>오늘의 운동,\n얼마나 강해졌을까?</Text>
    <Text style={styles.body}>운동 기록의 인정 횟수와 계산된 타격 수를 확인하세요.</Text>
    <Text style={styles.label}>제출건 ID</Text>
    <TextInput accessibilityLabel="제출건 ID" value={id} onChangeText={setId} autoCapitalize="none" autoCorrect={false}
      placeholder="시드로 생성한 제출건 UUID" placeholderTextColor={COLORS.muted} style={styles.input}
      onSubmitEditing={() => valid && router.push({ pathname: '/workout/[id]', params: { id: id.trim() } })} />
    {id.length > 0 && !valid && <Text style={styles.error}>UUID 형식의 제출건 ID를 입력해 주세요.</Text>}
    <ActionButton title="보상 미리보기" disabled={!valid} onPress={() => router.push({ pathname: '/workout/[id]', params: { id: id.trim() } })} />
    <Text style={styles.note}>첫 기능 시연 · US-02{ '\n' }서버 시드로 만든 기록을 조회합니다. 아직 전투 결과가 지급된 상태는 아닙니다.</Text>
  </ScrollView>;
}
const styles = StyleSheet.create({
  page: { padding: SPACE.large, gap: SPACE.medium, paddingBottom: 48 },
  eyebrow: { color: COLORS.primary, fontSize: 14, marginTop: 24 },
  title: { color: COLORS.text, fontSize: 32, lineHeight: 44, fontWeight: '800' },
  body: { color: COLORS.muted, fontSize: 16, lineHeight: 25, marginBottom: 24 },
  label: { color: COLORS.text, fontSize: 16 },
  input: { color: COLORS.text, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border, borderRadius: 12, padding: 16, fontSize: 16 },
  error: { color: COLORS.danger }, note: { color: COLORS.muted, fontSize: 14, lineHeight: 22, marginTop: 24 },
});
