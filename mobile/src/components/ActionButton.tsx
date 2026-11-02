import { Pressable, StyleSheet, Text } from 'react-native';
import { COLORS } from '../theme/tokens';

export function ActionButton({ title, onPress, disabled = false, secondary = false }: {
  title: string; onPress: () => void; disabled?: boolean; secondary?: boolean;
}) {
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled}
    onPress={onPress} style={({ pressed }) => [styles.button, secondary && styles.secondary, (disabled || pressed) && { opacity: 0.6 }]}>
    <Text className="font-bold" style={[styles.label, secondary && { color: COLORS.text }]}>{title}</Text>
  </Pressable>;
}
const styles = StyleSheet.create({
  button: { backgroundColor: COLORS.primary, borderRadius: 999, minHeight: 52, padding: 16, alignItems: 'center', justifyContent: 'center' },
  secondary: { backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border },
  label: { color: COLORS.background, fontSize: 16, fontWeight: '700' },
});
