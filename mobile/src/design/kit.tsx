// 시안 '전운시 화면 시안'(Claude Design 캔버스) 공통 부품. 값은 시안 '디자인 시스템' 보드에서 옮겼다.
// 시안 글꼴(G마켓 산스·Pretendard)은 woff 파일이라 앱에서 쓸 수 없어 시스템 글꼴 굵기로 대신한다 [팀 확인 필요].
import type { ReactNode } from 'react';
import { ActivityIndicator, Modal, Pressable, StyleSheet, Text, View, type TextStyle, type ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import { useRouter } from 'expo-router';

export const DS = {
  accent: '#B9FD50', accent300: '#D6FF94', accent700: '#7FAF2E', onAccent: '#000000',
  bg: '#000000', bg2: '#1C1C1E', bg3: '#2C2C2E', band: '#0E0E0F',
  label: '#FFFFFF', label2: '#98989F', gray: '#8E8E93', gray2: '#636366', separator: '#38383A', dot: '#3A3A3C',
  warn: '#FF9F43', danger: '#FF8080', dim: 'rgba(0,0,0,0.7)',
} as const;

// 시안 글자 단계 (Large Title 34 … Caption 2 11). display = 시안의 G마켓 산스 자리.
export const T = StyleSheet.create({
  display: { color: DS.label, fontWeight: '800', letterSpacing: -0.3 },
  title1: { color: DS.label, fontSize: 28, lineHeight: 36, fontWeight: '800' },
  title2: { color: DS.label, fontSize: 24, lineHeight: 32, fontWeight: '800' },
  title3: { color: DS.label, fontSize: 20, lineHeight: 26, fontWeight: '700' },
  headline: { color: DS.label, fontSize: 17, lineHeight: 22, fontWeight: '700' },
  body: { color: DS.label, fontSize: 16, lineHeight: 24 },
  sub: { color: DS.label2, fontSize: 14, lineHeight: 21 },
  foot: { color: DS.label2, fontSize: 13, lineHeight: 18 },
  cap: { color: DS.label2, fontSize: 12, lineHeight: 16 },
});

const ICONS = {
  back: 'M8.293 12.707a1 1 0 0 1 0-1.414l5.657-5.657a1 1 0 1 1 1.414 1.414L10.414 12l4.95 4.95a1 1 0 0 1-1.414 1.414l-5.657-5.657Z',
  close: 'm12 13.414 5.657 5.657a1 1 0 0 0 1.414-1.414L13.414 12l5.657-5.657a1 1 0 0 0-1.414-1.414L12 10.586 6.343 4.929A1 1 0 0 0 4.93 6.343L10.586 12l-5.657 5.657a1 1 0 1 0 1.414 1.414z',
  check: 'M21.192 5.465a1 1 0 0 1 0 1.414L9.95 18.122a1.1 1.1 0 0 1-1.556 0l-5.586-5.586a1 1 0 1 1 1.415-1.415l4.95 4.95L19.777 5.465a1 1 0 0 1 1.414 0Z',
  lock: 'M12 2a6 6 0 0 1 5.996 5.775L18 8h1a2 2 0 0 1 1.995 1.85L21 10v10a2 2 0 0 1-1.85 1.995L19 22H5a2 2 0 0 1-1.995-1.85L3 20V10a2 2 0 0 1 1.85-1.995L5 8h1a6 6 0 0 1 6-6m7 8H5v10h14zm-7 2a2 2 0 0 1 1.134 3.647l-.134.085V17a1 1 0 0 1-1.993.117L11 17v-1.268A2 2 0 0 1 12 12m0-8a4 4 0 0 0-4 4h8a4 4 0 0 0-4-4',
  chevron: 'M15.707 11.293a1 1 0 0 1 0 1.414l-5.657 5.657a1 1 0 1 1-1.414-1.414L13.586 12l-4.95-4.95a1 1 0 0 1 1.414-1.414l5.657 5.657Z',
  menu: 'M3 6a1 1 0 0 1 1-1h16a1 1 0 1 1 0 2H4a1 1 0 0 1-1-1m0 6a1 1 0 0 1 1-1h16a1 1 0 1 1 0 2H4a1 1 0 0 1-1-1m1 5a1 1 0 1 0 0 2h16a1 1 0 1 0 0-2z',
  search: 'M10 3a7 7 0 0 1 5.6 11.2l4.1 4.1a1 1 0 0 1-1.4 1.4l-4.1-4.1A7 7 0 1 1 10 3m0 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10',
  rotate: 'M2 12.08c-.006-.862.91-1.356 1.618-.975l.095.058 2.678 1.804c.972.655.377 2.143-.734 2.007l-.117-.02-1.063-.234a8.002 8.002 0 0 0 14.804.605 1 1 0 0 1 1.82.828c-1.987 4.37-6.896 6.793-11.687 5.509A10.003 10.003 0 0 1 2 12.08m.903-4.228C4.89 3.482 9.799 1.06 14.59 2.343a10.002 10.002 0 0 1 7.414 9.581c.007.863-.91 1.358-1.617.976l-.096-.058-2.678-1.804c-.972-.655-.377-2.143.734-2.007l.117.02 1.063.234A8.002 8.002 0 0 0 4.723 8.68a1 1 0 1 1-1.82-.828',
} as const;
export type IconName = keyof typeof ICONS;

export function Icon({ name, size = 22, color = DS.label }: { name: IconName; size?: number; color?: string }) {
  return <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" accessibilityElementsHidden importantForAccessibility="no">
    <Path fill={color} fillRule="evenodd" d={ICONS[name]} />
  </Svg>;
}

export function IconButton({ name, label, onPress, color, style }: { name: IconName; label: string; onPress: () => void; color?: string; style?: ViewStyle }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} hitSlop={6} style={[s.iconBtn, style]}>
    <Icon name={name} color={color} />
  </Pressable>;
}

/** 검정 바탕 화면. edges 기본 위·아래 안전 영역 */
export function Page({ children, style, edges = ['top', 'bottom'], bg = DS.bg }: { children: ReactNode; style?: ViewStyle; edges?: ('top' | 'bottom')[]; bg?: string }) {
  return <SafeAreaView edges={edges} style={[{ flex: 1, backgroundColor: bg }, style]}>{children}</SafeAreaView>;
}

/** 시안 상단 바: 왼쪽 뒤로(또는 닫기), 가운데 제목, 오른쪽 자리 */
export function Header({ title, close, onBack, right }: { title?: string; close?: boolean; onBack?: () => void; right?: ReactNode }) {
  const router = useRouter();
  const back = onBack ?? (() => (router.canGoBack() ? router.back() : router.replace('/home')));
  return <View style={s.header}>
    <IconButton name={close ? 'close' : 'back'} label={close ? '닫기' : '뒤로'} onPress={back} />
    {title ? <Text accessibilityRole="header" numberOfLines={1} style={s.headerTitle}>{title}</Text> : null}
    <View style={s.headerRight}>{right}</View>
  </View>;
}

type CtaVariant = 'primary' | 'secondary' | 'outline' | 'text';
/** 시안 알약 버튼 (높이 52). 라임 버튼 위 글자는 검정 */
export function Cta({ title, onPress, variant = 'primary', disabled, loading, style, height = 52 }: {
  title: string; onPress: () => void; variant?: CtaVariant; disabled?: boolean; loading?: boolean; style?: ViewStyle; height?: number;
}) {
  const off = !!disabled || !!loading;
  const box: ViewStyle[] = [s.cta, { height }];
  const label: TextStyle[] = [s.ctaText];
  if (variant === 'primary') { box.push({ backgroundColor: off ? DS.bg3 : DS.accent }); label.push({ color: off ? DS.gray2 : DS.onAccent }); }
  if (variant === 'secondary') { box.push({ backgroundColor: DS.bg3 }); label.push({ color: DS.label }); }
  if (variant === 'outline') { box.push({ borderWidth: 1, borderColor: DS.gray2 }); label.push({ color: DS.label }); }
  if (variant === 'text') { label.push({ color: DS.label2, fontWeight: '600', fontSize: 15 }); }
  if (off && variant !== 'primary') box.push({ opacity: 0.5 });
  if (style) box.push(style);
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled: off, busy: !!loading }} disabled={off} onPress={onPress} style={box}>
    {loading ? <ActivityIndicator color={variant === 'primary' ? DS.onAccent : DS.label} /> : <Text style={label}>{title}</Text>}
  </Pressable>;
}

/** 화면 아래 고정 버튼 자리 (시안: 좌우 20, 아래 48 → 안전 영역 위 16) */
export function BottomBar({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[s.bottom, style]}>{children}</View>;
}

/** 시안 아래 시트 (반투명 검정 위 #1C1C1E, 위 모서리 28) */
export function Sheet({ visible, onClose, children, label }: { visible: boolean; onClose: () => void; children: ReactNode; label: string }) {
  return <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose} statusBarTranslucent>
    <Pressable accessibilityLabel="닫기" style={s.scrim} onPress={onClose} />
    <SafeAreaView edges={['bottom']} accessibilityViewIsModal accessibilityLabel={label} style={s.sheet}>
      <IconButton name="close" label="닫기" color={DS.label2} onPress={onClose} style={{ position: 'absolute', right: 12, top: 12 }} />
      {children}
    </SafeAreaView>
  </Modal>;
}

export function ProgressBar({ ratio, color = DS.accent, track = DS.dot, height = 8 }: { ratio: number; color?: string; track?: string; height?: number }) {
  const r = Math.max(0, Math.min(1, ratio));
  return <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ height, borderRadius: 999, backgroundColor: track, overflow: 'hidden' }}>
    <View style={{ width: `${r * 100}%`, height: '100%', borderRadius: 999, backgroundColor: color }} />
  </View>;
}

/** 작은 알약 표시 (상태·태그) */
export function Tag({ label, tone = 'muted', style }: { label: string; tone?: 'accent' | 'muted' | 'warn' | 'danger' | 'solid'; style?: ViewStyle }) {
  const map = {
    accent: { bg: 'transparent', bd: DS.accent, fg: DS.accent }, muted: { bg: DS.bg3, bd: DS.bg3, fg: DS.label2 },
    warn: { bg: 'transparent', bd: DS.warn, fg: DS.warn }, danger: { bg: 'transparent', bd: DS.danger, fg: DS.danger },
    solid: { bg: DS.accent, bd: DS.accent, fg: DS.onAccent },
  }[tone];
  return <View style={[s.tag, { backgroundColor: map.bg, borderColor: map.bd }, style]}><Text style={[s.tagText, { color: map.fg }]}>{label}</Text></View>;
}

/** 선택 알약 (분류 탭 등). 선택되면 라임 배경·검정 글자 */
export function Chip({ label, on, onPress, disabled }: { label: string; on?: boolean; onPress?: () => void; disabled?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ selected: !!on, disabled: !!disabled }} disabled={disabled} onPress={onPress}
    style={[s.chip, on ? { backgroundColor: DS.accent } : { backgroundColor: DS.bg2 }, disabled && { opacity: 0.45 }]}>
    <Text style={[s.chipText, { color: on ? DS.onAccent : DS.label }]}>{label}</Text>
  </Pressable>;
}

/** 목록 한 줄 (왼쪽 글, 오른쪽 › ) */
export function Row({ title, sub, onPress, right }: { title: string; sub?: string; onPress?: () => void; right?: ReactNode }) {
  return <Pressable accessibilityRole={onPress ? 'button' : undefined} disabled={!onPress} onPress={onPress} style={s.row}>
    <View style={{ flex: 1, gap: 2 }}><Text style={T.headline}>{title}</Text>{sub ? <Text style={T.foot}>{sub}</Text> : null}</View>
    {right ?? (onPress ? <Icon name="chevron" color={DS.label2} size={18} /> : null)}
  </Pressable>;
}

export function Divider({ band }: { band?: boolean }) {
  return band ? <View style={{ height: 8, backgroundColor: DS.band, marginHorizontal: -20 }} /> : <View style={{ height: StyleSheet.hairlineWidth, backgroundColor: DS.separator }} />;
}

/** 조회 상태 공통 (DESIGN.md 5절: 로딩·오류·빈 화면 구분) */
export function Loading({ label = '불러오는 중' }: { label?: string }) {
  return <View style={s.center}><ActivityIndicator color={DS.accent} /><Text style={T.foot}>{label}</Text></View>;
}
export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <View style={s.center}><Text style={[T.body, { textAlign: 'center' }]}>{message}</Text><Cta title="다시 불러오기" variant="outline" onPress={onRetry} style={{ paddingHorizontal: 28 }} /></View>;
}
export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return <View style={s.center}><Text style={[T.sub, { textAlign: 'center' }]}>{message}</Text>{action}</View>;
}

const s = StyleSheet.create({
  iconBtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  header: { height: 56, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8 },
  headerTitle: { position: 'absolute', left: 64, right: 64, textAlign: 'center', color: DS.label, fontSize: 17, fontWeight: '700' },
  headerRight: { marginLeft: 'auto', flexDirection: 'row', alignItems: 'center' },
  cta: { borderRadius: 999, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 24, flexDirection: 'row' },
  ctaText: { fontSize: 17, fontWeight: '700' },
  bottom: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 16, gap: 8 },
  scrim: { ...StyleSheet.absoluteFill, backgroundColor: DS.dim },
  sheet: { position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: DS.bg2, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingTop: 28, paddingHorizontal: 20, paddingBottom: 16 },
  tag: { alignSelf: 'flex-start', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, borderWidth: 1 },
  tagText: { fontSize: 13, fontWeight: '600' },
  chip: { minHeight: 36, paddingHorizontal: 16, borderRadius: 999, justifyContent: 'center' },
  chipText: { fontSize: 14, fontWeight: '600' },
  row: { minHeight: 56, flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14, padding: 24 },
});
