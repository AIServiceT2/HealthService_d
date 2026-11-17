// MVP 화면 공통 요소. 값은 시안(frontend/design/screens-mvp-draft.html)과 가입 화면(src/onboarding/ui.tsx)에 맞춘다.
import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type ViewStyle } from 'react-native';
import { useRouter } from 'expo-router';
import { COLORS } from '../theme/tokens';
import { OB } from '../onboarding/ui';
import type { Tone } from './rules';

export const TONE_COLOR: Record<Tone, string> = {
  lime: COLORS.primary, warn: COLORS.warning, danger: COLORS.danger, muted: OB.muted,
};

export function Card({ children, style, tone }: { children: ReactNode; style?: ViewStyle; tone?: Tone }) {
  return <View style={[s.card, tone === 'lime' && { borderColor: COLORS.primary, borderWidth: 2 },
    tone && tone !== 'lime' && tone !== 'muted' && { borderColor: TONE_COLOR[tone] }, style]}>{children}</View>;
}

export function Chip({ label, tone = 'muted' }: { label: string; tone?: Tone }) {
  return <View style={[s.chip, { borderColor: TONE_COLOR[tone] }]}><Text style={[s.chipText, { color: TONE_COLOR[tone] }]}>{label}</Text></View>;
}

export function KV({ label, value, tone }: { label: string; value: ReactNode; tone?: Tone }) {
  return <View style={s.kv}><Text style={s.kvLabel}>{label}</Text>
    <Text style={[s.kvValue, tone && { color: TONE_COLOR[tone] }]}>{value}</Text></View>;
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return <Card style={s.stat}><Text style={s.cap}>{label}</Text><Text style={s.statNum}>{value}</Text></Card>;
}

export function AiBlock({ label, text, fallback }: { label: string; text: string; fallback?: boolean }) {
  return <Card style={{ gap: 6 }}>
    <View style={s.aiRow}><View style={s.aiBadge}><Text style={s.aiBadgeText}>AI</Text></View><Text style={s.cap}>{label}{fallback ? ' · 기본 문구' : ''}</Text></View>
    <Text style={s.body}>{text}</Text>
  </Card>;
}

export function Caption({ children, tone }: { children: ReactNode; tone?: Tone }) {
  return <Text style={[s.cap, tone && { color: TONE_COLOR[tone] }]}>{children}</Text>;
}

export function Note({ children }: { children: ReactNode }) {
  return <Text style={s.note}>{children}</Text>;
}

export function TopBar({ right, close = false, onBack }: { right?: ReactNode; close?: boolean; onBack?: () => void }) {
  const router = useRouter();
  const back = onBack ?? (() => (router.canGoBack() ? router.back() : router.replace('/home')));
  return <View style={s.top}>
    <Pressable accessibilityRole="button" accessibilityLabel={close ? '닫기' : '뒤로'} onPress={back} style={s.back} hitSlop={8}>
      <Text style={s.backText}>{close ? '✕' : '‹'}</Text>
    </Pressable>
    {right}
  </View>;
}

export function Loading({ label = '불러오는 중' }: { label?: string }) {
  return <View style={s.center}><ActivityIndicator color={COLORS.primary} /><Text style={s.cap}>{label}</Text></View>;
}

/** 실패한 조회를 빈 화면으로 보이지 않게, 오류와 다시 불러오기를 함께 보여 준다 (DESIGN.md 5절) */
export function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <View style={s.center}>
    <Text style={[s.body, { textAlign: 'center' }]}>{message}</Text>
    <Pressable accessibilityRole="button" onPress={onRetry} style={s.retry}><Text style={s.retryText}>다시 불러오기</Text></Pressable>
  </View>;
}

export function Stepper({ label, value, unit, onChange, min = 1, max = 99 }: {
  label: string; value: number; unit: string; onChange: (v: number) => void; min?: number; max?: number;
}) {
  return <View style={s.stepper} accessibilityLabel={`${label} ${value}${unit}`}>
    <Pressable accessibilityRole="button" accessibilityLabel={`${label} 줄이기`} disabled={value <= min} onPress={() => onChange(Math.max(min, value - 1))} style={s.sb}><Text style={s.sbText}>−</Text></Pressable>
    <Text style={s.stepValue}>{value}<Text style={s.cap}> {unit}</Text></Text>
    <Pressable accessibilityRole="button" accessibilityLabel={`${label} 늘리기`} disabled={value >= max} onPress={() => onChange(Math.min(max, value + 1))} style={s.sb}><Text style={s.sbText}>+</Text></Pressable>
  </View>;
}

export function Pill({ label, on, disabled, onPress }: { label: string; on?: boolean; disabled?: boolean; onPress?: () => void }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ selected: !!on, disabled: !!disabled }} disabled={disabled} onPress={onPress}
    style={[s.pill, on && s.pillOn, disabled && { opacity: 0.45 }]}>
    <Text style={[s.pillText, on && { color: COLORS.onPrimary, fontWeight: '600' }]}>{label}</Text>
  </Pressable>;
}

export function Bar({ ratio, color = COLORS.primary, height = 6 }: { ratio: number; color?: string; height?: number }) {
  return <View style={[s.bar, { height }]}><View style={{ width: `${Math.max(0, Math.min(1, ratio)) * 100}%`, height: '100%', backgroundColor: color }} /></View>;
}

export const s = StyleSheet.create({
  card: { backgroundColor: OB.surface, borderWidth: 1, borderColor: OB.surfaceRaised, borderRadius: 14, padding: 16, gap: 10 },
  chip: { alignSelf: 'flex-start', height: 26, paddingHorizontal: 10, borderRadius: 999, borderWidth: 1, justifyContent: 'center' },
  chipText: { fontSize: 12, fontWeight: '600' },
  kv: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 },
  kvLabel: { fontSize: 15, color: OB.muted },
  kvValue: { fontSize: 17, fontWeight: '600', color: COLORS.text, flexShrink: 1, textAlign: 'right' },
  stat: { flex: 1, gap: 4 },
  statNum: { fontSize: 24, fontWeight: '600', color: COLORS.text },
  cap: { fontSize: 13, lineHeight: 18, color: OB.muted },
  body: { fontSize: 15, lineHeight: 23, color: COLORS.text },
  note: { fontSize: 12, lineHeight: 18, color: OB.muted },
  aiRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  aiBadge: { borderWidth: 1, borderColor: OB.muted, borderRadius: 999, paddingHorizontal: 6 },
  aiBadgeText: { fontSize: 10, fontWeight: '600', color: OB.muted },
  top: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 48 },
  back: { width: 44, height: 44, borderRadius: 999, backgroundColor: OB.surface, alignItems: 'center', justifyContent: 'center' },
  backText: { color: COLORS.text, fontSize: 22, lineHeight: 24 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24 },
  retry: { minHeight: 48, paddingHorizontal: 24, borderRadius: 999, borderWidth: 1, borderColor: COLORS.border, justifyContent: 'center' },
  retryText: { color: COLORS.text, fontSize: 15, fontWeight: '600' },
  stepper: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: OB.surface, borderRadius: 14, padding: 10 },
  sb: { width: 44, height: 44, borderRadius: 999, backgroundColor: OB.surfaceRaised, alignItems: 'center', justifyContent: 'center' },
  sbText: { color: COLORS.text, fontSize: 20 },
  stepValue: { color: COLORS.text, fontSize: 20, fontWeight: '600' },
  pill: { minHeight: 44, paddingHorizontal: 18, borderRadius: 999, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.surface, justifyContent: 'center' },
  pillOn: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  pillText: { color: COLORS.text, fontSize: 15 },
  bar: { borderRadius: 999, backgroundColor: '#222', overflow: 'hidden' },
  h1: { fontSize: 26, lineHeight: 34, fontWeight: '600', color: COLORS.text },
  page: { paddingHorizontal: 24, paddingTop: 8, paddingBottom: 32, gap: 18 },
  row: { flexDirection: 'row', gap: 10 },
});
