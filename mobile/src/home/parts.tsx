// 홈·길드·캐릭터 화면 전용 부품. 공통 부품은 src/design/kit.tsx를 쓰고, 여기에는 이 영역에서만 쓰는 것만 둔다.
import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View, type ImageSourcePropType, type ViewStyle } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { DS } from '../design/kit';

// 시안에서 옮긴 아이콘 (kit에 없는 것)
const PATHS = {
  plus: 'M11 20a1 1 0 1 0 2 0v-7h7a1 1 0 1 0 0-2h-7V4a1 1 0 1 0-2 0v7H4a1 1 0 1 0 0 2h7z',
  arrowUpRight: 'M18 5a1 1 0 0 1 1 1v8a1 1 0 1 1-2 0V8.414l-9.95 9.95a1 1 0 0 1-1.414-1.414L15.586 7H10a1 1 0 1 1 0-2h8Z',
  addUser: 'M16 14a5 5 0 0 1 5 5v2a1 1 0 1 1-2 0v-2a3 3 0 0 0-3-3H8a3 3 0 0 0-3 3v2a1 1 0 1 1-2 0v-2a5 5 0 0 1 5-5zm4-6a1 1 0 0 1 1 1v1h1a1 1 0 1 1 0 2h-1v1a1 1 0 1 1-2 0v-1h-1a1 1 0 1 1 0-2h1V9a1 1 0 0 1 1-1m-8-6a5 5 0 1 1 0 10 5 5 0 0 1 0-10m0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6',
  box: 'M20 3a2 2 0 0 1 1.995 1.85L22 5v4h-1v10a2 2 0 0 1-1.85 1.995L19 21H5a2 2 0 0 1-1.995-1.85L3 19V9H2V5a2 2 0 0 1 1.85-1.995L4 3zm-1 6H5v10h14zm-5 4a1 1 0 1 1 0 2h-4a1 1 0 1 1 0-2zm6-8H4v2h16z',
  shorts: 'M16.105 2a2 2 0 0 1 1.964 1.621l.024.158 1.777 16a2 2 0 0 1-1.84 2.216l-.147.005h-3.08a2 2 0 0 1-1.911-1.407l-.042-.16L12 16.61l-.85 3.824a2 2 0 0 1-1.788 1.56L9.198 22h-3.08a2 2 0 0 1-2-2.074l.011-.147 1.778-16a2 2 0 0 1 1.828-1.773L7.895 2zm.333 5H7.562L6.117 20h3.08l1.827-8.217a1 1 0 0 1 1.952 0L14.802 20h3.08L16.439 7Zm-.333-3h-8.21l-.111 1h8.432z',
  share: 'M9 2a2 2 0 0 0-2 2v2h2V4h11v11h-2v2h2a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zM4 7a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2zm0 2h11v11H4z',
  link: 'M10.232 10.231a5 5 0 0 1 6.89-.172l.181.172 2.828 2.829a5 5 0 0 1-6.89 7.243l-.18-.172-2.122-2.122a1 1 0 0 1 1.32-1.497l.094.083 2.122 2.122a3 3 0 0 0 4.377-4.1l-.135-.143-2.828-2.828a3 3 0 0 0-4.243 0 1 1 0 0 1-1.414-1.415M3.868 3.867a5 5 0 0 1 6.89-.172l.181.172L13.06 5.99a1 1 0 0 1-1.32 1.497l-.094-.083-2.121-2.121A3 3 0 0 0 5.147 9.38l.135.144 2.829 2.829a3 3 0 0 0 4.242 0 1 1 0 1 1 1.415 1.414 5 5 0 0 1-6.89.172l-.182-.172-2.828-2.829a5 5 0 0 1 0-7.07Z',
} as const;
export type HIconName = keyof typeof PATHS;

export function HIcon({ name, size = 22, color = DS.label }: { name: HIconName; size?: number; color?: string }) {
  return <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" accessibilityElementsHidden importantForAccessibility="no">
    <Path fill={color} fillRule="evenodd" d={PATHS[name]} />
  </Svg>;
}

// 캐릭터 이미지 (가입 때 고른 avatarId: src/onboarding/draft.tsx AVATARS와 같은 값)
const AVATAR_IMAGES: Record<string, ImageSourcePropType> = {
  AVATAR_PANTS: require('../../assets/onboarding/avatar-pants.png'),
  AVATAR_SKIRT: require('../../assets/onboarding/avatar-skirt.png'),
};
export const avatarImage = (avatarId: string | null | undefined): ImageSourcePropType =>
  (avatarId && AVATAR_IMAGES[avatarId]) || AVATAR_IMAGES.AVATAR_PANTS;

// 시안의 겹친 동그라미 (사람 사진 자리). 실제 사진이 없어 닉네임 첫 글자를 넣는다. 장식이라 읽지 않음
const DOT_COLORS = [DS.gray2, DS.gray, DS.dot];
export function Faces({ names, size = 24, border = DS.bg, max = 3 }: { names: string[]; size?: number; border?: string; max?: number }) {
  if (names.length === 0) return null;
  return <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ flexDirection: 'row' }}>
    {names.slice(0, max).map((n, i) => <View key={`${n}-${i}`} style={{
      width: size, height: size, borderRadius: 999, borderWidth: 2, borderColor: border,
      backgroundColor: DOT_COLORS[i % DOT_COLORS.length], marginLeft: i === 0 ? 0 : -size / 3,
      alignItems: 'center', justifyContent: 'center',
    }}><Text style={{ color: DS.label, fontSize: size * 0.42, fontWeight: '700' }}>{n.slice(0, 1)}</Text></View>)}
  </View>;
}

/** 시안의 1/3 단계 표시 */
export function StepCount({ step, total }: { step: number; total: number }) {
  return <Text accessibilityLabel={`${total}단계 중 ${step}단계`} style={{ color: DS.label, fontSize: 17, fontWeight: '700' }}>
    {step}<Text style={{ color: DS.gray2 }}>/{total}</Text>
  </Text>;
}

/** 작은 알약 표시 (테두리만) */
export function Pill({ children, style, filled }: { children: ReactNode; style?: ViewStyle; filled?: boolean }) {
  return <View style={[st.pill, filled && { backgroundColor: DS.bg2, borderColor: DS.bg2 }, style]}><Text style={st.pillText}>{children}</Text></View>;
}

/** 둥근 검정 아이콘 버튼 (사진 위에 얹는 48 크기) */
export function RoundButton({ label, onPress, children, style }: { label: string; onPress: () => void; children: ReactNode; style?: ViewStyle }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} hitSlop={4} style={[st.round, style]}>{children}</Pressable>;
}

// KST 날짜 계산 (서버의 일일 상한·기간 조회가 KST 기준, API.md 공통 규칙)
const KST_MS = 9 * 60 * 60 * 1000;
export const kstDateKey = (d: Date) => new Date(d.getTime() + KST_MS).toISOString().slice(0, 10);
/** offset 0 = 이번 주. 월요일~일요일 KST 날짜 7개 */
export function kstWeek(offset: number, now = new Date()): string[] {
  const kst = new Date(now.getTime() + KST_MS);
  const dow = (kst.getUTCDay() + 6) % 7; // 월 0 … 일 6
  const monday = Date.UTC(kst.getUTCFullYear(), kst.getUTCMonth(), kst.getUTCDate() - dow + offset * 7);
  return Array.from({ length: 7 }, (_, i) => new Date(monday + i * 86400000).toISOString().slice(0, 10));
}
/** '11월 3주차' (그 주 월요일이 속한 달 기준) */
export function weekLabel(mondayKey: string) {
  const [, m, d] = mondayKey.split('-').map(Number);
  return `${m}월 ${Math.floor((d - 1) / 7) + 1}주차`;
}
export const kstTime = (iso: string) => {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '';
  const k = new Date(t + KST_MS);
  return `${String(k.getUTCHours()).padStart(2, '0')}:${String(k.getUTCMinutes()).padStart(2, '0')}`;
};
export const kstShort = (iso: string) => {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '';
  const k = new Date(t + KST_MS);
  return `${k.getUTCMonth() + 1}/${k.getUTCDate()} ${kstTime(iso)}`;
};

const st = StyleSheet.create({
  pill: { alignSelf: 'flex-start', height: 30, paddingHorizontal: 12, borderRadius: 999, borderWidth: 1, borderColor: DS.separator, justifyContent: 'center' },
  pillText: { color: DS.label, fontSize: 13 },
  round: { width: 48, height: 48, borderRadius: 999, backgroundColor: DS.bg, alignItems: 'center', justifyContent: 'center' },
});
