import { Pressable, StyleSheet, Text } from 'react-native';
import { COLORS, FONT, RADIUS, SPACE, TOUCH_MIN } from '../theme/tokens';

// 비활성은 투명도 대신 색으로 구분한다 (DESIGN.md 2절). 비활성 이유는 버튼 옆 문구로 표시한다.
export function ActionButton({ title, onPress, disabled = false, secondary = false }: {
  title: string; onPress: () => void; disabled?: boolean; secondary?: boolean;
}) {
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled}
    onPress={onPress} style={({ pressed }) => [styles.button, secondary && styles.secondary, disabled && styles.disabled, pressed && styles.pressed]}>
    <Text style={[styles.label, secondary && { color: COLORS.text }, disabled && { color: COLORS.textMuted }]}>{title}</Text>
  </Pressable>;
}
const styles = StyleSheet.create({
  button: { backgroundColor: COLORS.primary, borderRadius: RADIUS.pill, minHeight: TOUCH_MIN, paddingHorizontal: SPACE.large, paddingVertical: SPACE.small, alignItems: 'center', justifyContent: 'center' },
  secondary: { backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border },
  disabled: { backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border, borderStyle: 'dashed' },
  pressed: { transform: [{ scale: 0.98 }], opacity: 0.85 },
  label: { ...FONT.body, color: COLORS.onPrimary, fontWeight: '700', textAlign: 'center' },
});
