// 가입 화면 공통 요소. 값은 시안(frontend/design/screens-draft.html, Figma '전운시 표백제' Section 2)에서 옮겼다.
import type { ReactNode } from 'react';
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, TextInput, View, type TextInputProps, type ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Circle, Defs, G, Line, LinearGradient, Rect, Stop } from 'react-native-svg';
import { COLORS } from '../theme/tokens';

// 시안에만 있는 회색 단계 [제안·팀 확인 필요: DESIGN.md 2절 토큰에 없음]
export const OB = {
  accent: COLORS.primary,
  muted: '#98989F',
  mutedStrong: '#CCCCCC',
  surface: '#1C1C1E',
  surfaceRaised: '#2C2C2E',
  line: '#38383A',
  dim: '#636366',
  dot: '#3A3A3C',
} as const;

export function Screen({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <SafeAreaView style={[styles.screen, style]} edges={['top', 'bottom']}>{children}</SafeAreaView>;
}

export function Title({ children, size = 30, center = false }: { children: ReactNode; size?: number; center?: boolean }) {
  return <Text accessibilityRole="header" style={[styles.title, { fontSize: size, lineHeight: Math.round(size * 1.35) }, center && { textAlign: 'center' }]}>{children}</Text>;
}

export function Sub({ children, center = false }: { children: ReactNode; center?: boolean }) {
  return <Text style={[styles.sub, center && { textAlign: 'center' }]}>{children}</Text>;
}

export const Accent = ({ children }: { children: ReactNode }) => <Text style={{ color: OB.accent }}>{children}</Text>;

export function PillButton({ title, onPress, disabled, loading, variant = 'primary', arrow = false }: {
  title: string; onPress: () => void; disabled?: boolean; loading?: boolean; variant?: 'primary' | 'secondary' | 'text'; arrow?: boolean;
}) {
  const off = disabled || loading;
  // NativeWind가 Pressable의 style 함수 결과를 적용하지 않아(시뮬레이터에서 배경이 사라짐) 고정 배열로 넘긴다
  const style = [
    variant === 'primary' && styles.primary,
    variant === 'secondary' && styles.secondary,
    variant === 'text' && styles.textButton,
    arrow && styles.arrowPad,
    variant === 'primary' && off && styles.primaryOff,
  ].filter(Boolean) as ViewStyle[];
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled: !!off, busy: !!loading }} disabled={off} onPress={onPress}
    style={style} android_ripple={{ color: '#00000022', borderless: false }}>
    {loading ? <ActivityIndicator color={variant === 'primary' ? '#000' : COLORS.text} /> : <>
      <Text style={[styles.buttonLabel, variant !== 'primary' && { color: variant === 'text' ? OB.muted : COLORS.text, fontWeight: variant === 'text' ? '400' : '600', fontSize: variant === 'text' ? 15 : 17 }, variant === 'primary' && off && { color: OB.dim }]}>{title}</Text>
      {arrow && <View style={styles.arrow}><Text style={styles.arrowText}>→</Text></View>}
    </>}
  </Pressable>;
}

export function ProgressDots({ count, active }: { count: number; active: number }) {
  return <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={styles.dots}>
    {Array.from({ length: count }, (_, i) => <View key={i} style={i === active ? styles.dotOn : styles.dotOff} />)}
  </View>;
}

export function ErrorText({ children }: { children?: string | null }) {
  if (!children) return null;
  return <Text accessibilityLiveRegion="polite" style={styles.error}>{children}</Text>;
}

export function Field({ label, error, variant = 'round', ...input }: TextInputProps & { label: string; error?: string | null; variant?: 'round' | 'box' }) {
  return <View style={{ gap: 6 }}>
    <Text style={[styles.label, variant === 'box' && { color: OB.muted }]}>{label}</Text>
    <TextInput accessibilityLabel={label} placeholderTextColor={OB.dim} {...input}
      style={[variant === 'round' ? styles.inputRound : styles.inputBox, error ? { borderColor: COLORS.danger } : null]} />
    <ErrorText>{error}</ErrorText>
  </View>;
}

// 관절 좌표 (시안 viewBox 30 110 540 865). 얼굴 점은 없다 (얼굴은 인식하지 않음, R11)
const JOINTS: [number, number][] = [[300, 262], [215, 295], [385, 295], [150, 420], [450, 420], [85, 560], [515, 560], [255, 525], [345, 525], [240, 730], [360, 730]];
const FEET: [number, number][] = [[238, 915], [362, 915]];
const BONES: [number, number][] = [[0, 1], [0, 2], [1, 3], [3, 5], [2, 4], [4, 6], [1, 7], [2, 8], [7, 8], [7, 9], [8, 10]];

// 근육 실루엣 + 관절선 + 아래쪽 검정 그라데이션 (시작·생년월일·성별·가입·로그인 화면)
export function BodyHero({ width, height, feet = false, label }: { width: number; height: number; feet?: boolean; label?: string }) {
  const joints = feet ? [...JOINTS, ...FEET] : JOINTS;
  const bones = feet ? [...BONES, [9, 11], [10, 12]] as [number, number][] : BONES;
  return <View style={{ width, height }} accessible={!!label} accessibilityLabel={label} accessibilityRole={label ? 'image' : undefined}
    importantForAccessibility={label ? 'yes' : 'no-hide-descendants'}>
    <Image source={require('../../assets/onboarding/body.png')} style={{ position: 'absolute', left: 0, top: 0, width, height }} resizeMode="contain" />
    <Svg width={width} height={height} viewBox="30 110 540 865" style={{ position: 'absolute', left: 0, top: 0 }}>
      <G stroke={OB.accent} strokeWidth={4} strokeLinecap="round">
        {bones.map(([a, b]) => <Line key={`${a}-${b}`} x1={joints[a][0]} y1={joints[a][1]} x2={joints[b][0]} y2={joints[b][1]} />)}
      </G>
      {joints.map(([x, y]) => <Circle key={`h${x}-${y}`} cx={x} cy={y} r={16} fill={OB.accent} opacity={0.25} />)}
      {joints.map(([x, y]) => <Circle key={`p${x}-${y}`} cx={x} cy={y} r={7} fill={OB.accent} />)}
    </Svg>
  </View>;
}

export function FadeToBlack({ top, height }: { top: number; height: number }) {
  return <Svg pointerEvents="none" width="100%" height={height} style={{ position: 'absolute', left: 0, right: 0, top }}>
    <Defs><LinearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
      <Stop offset="0" stopColor="#000" stopOpacity={0} /><Stop offset="0.7" stopColor="#000" stopOpacity={1} />
    </LinearGradient></Defs>
    <Rect x="0" y="0" width="100%" height="100%" fill="url(#fade)" />
  </Svg>;
}

// 캐릭터 선택 화면 위의 진행 원 (시안 '가입 진행 1/3단계')
export function StepRing({ step, total }: { step: number; total: number }) {
  const r = 30; const c = 2 * Math.PI * r;
  return <Svg width={72} height={72} viewBox="0 0 72 72" accessibilityLabel={`가입 진행 ${step}/${total}단계`}>
    <Circle cx={36} cy={36} r={r} stroke={OB.surfaceRaised} strokeWidth={4} fill="none" />
    <Circle cx={36} cy={36} r={r} stroke={OB.accent} strokeWidth={4} fill="none" strokeLinecap="round"
      strokeDasharray={`${(c * step) / total} ${c}`} transform="rotate(-90 36 36)" />
  </Svg>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: COLORS.background },
  title: { color: COLORS.text, fontWeight: '700' },
  sub: { color: OB.muted, fontSize: 15, lineHeight: 22 },
  primary: { height: 60, borderRadius: 999, backgroundColor: OB.accent, alignItems: 'center', justifyContent: 'center', flexDirection: 'row' },
  primaryOff: { backgroundColor: OB.surfaceRaised },
  secondary: { height: 56, borderRadius: 999, backgroundColor: OB.surfaceRaised, alignItems: 'center', justifyContent: 'center' },
  textButton: { minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  arrowPad: { justifyContent: 'space-between', paddingLeft: 28, paddingRight: 10 },
  buttonLabel: { color: '#000', fontSize: 17, fontWeight: '600' },
  arrow: { width: 40, height: 40, borderRadius: 999, backgroundColor: '#000', alignItems: 'center', justifyContent: 'center' },
  arrowText: { color: OB.accent, fontSize: 18, fontWeight: '700' },
  dots: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  dotOn: { width: 18, height: 3, borderRadius: 999, backgroundColor: OB.accent },
  dotOff: { width: 3, height: 3, borderRadius: 999, backgroundColor: COLORS.text },
  label: { fontSize: 13, color: OB.mutedStrong },
  inputRound: { height: 48, paddingHorizontal: 16, borderRadius: 14, borderWidth: 1, borderColor: '#808080', backgroundColor: '#1B1B1B', color: '#F7F7F7', fontSize: 16 },
  inputBox: { height: 52, paddingHorizontal: 16, borderRadius: 10, borderWidth: 1, borderColor: OB.line, backgroundColor: OB.surfaceRaised, color: COLORS.text, fontSize: 16 },
  error: { color: COLORS.danger, fontSize: 14, lineHeight: 20 },
});
