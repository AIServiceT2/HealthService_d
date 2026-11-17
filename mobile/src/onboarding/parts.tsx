// 01 시작 영역 공통 부품 (시안 'Start'·'SignIn'·'AgeStep'·'Login'·'NameStep'·'GuildJoin' 등에서 옮김).
// 공용 부품은 src/design/kit.tsx, 몸 실루엣 등은 ./ui.tsx 를 쓴다.
import { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View, type TextInputProps } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { DS, T } from '../design/kit';

/** 시안 제목 (G마켓 산스 24 → 시스템 글꼴 800) + 설명 14 */
export function StepHeading({ title, sub, center = false }: { title: ReactNode; sub?: ReactNode; center?: boolean }) {
  return <View style={[{ gap: 8 }, center && { alignItems: 'center' }]}>
    <Text accessibilityRole="header" style={[s.title, center && { textAlign: 'center' }]}>{title}</Text>
    {sub ? <Text style={[s.sub, center && { textAlign: 'center', fontSize: 13 }]}>{sub}</Text> : null}
  </View>;
}

export const Lime = ({ children }: { children: ReactNode }) => <Text style={{ color: DS.accent }}>{children}</Text>;

/** 가입 단계 점 (활성 18×3 라임, 나머지 3×3 흰 점) */
export function StepDots({ count, active }: { count: number; active: number }) {
  return <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={s.dots}>
    {Array.from({ length: count }, (_, i) => <View key={i} style={i === active ? s.dotOn : s.dotOff} />)}
  </View>;
}

const EYE_OFF = 'M3.05 9.31a1 1 0 1 1 1.914-.577c2.086 6.986 11.982 6.987 14.07.004a1 1 0 1 1 1.918.57 9.509 9.509 0 0 1-1.813 3.417L20.414 14A1 1 0 0 1 19 15.414l-1.311-1.311a9.116 9.116 0 0 1-2.32 1.269l.357 1.335a1 1 0 1 1-1.931.518l-.364-1.357c-.947.14-1.915.14-2.862 0l-.364 1.357a1 1 0 1 1-1.931-.518l.357-1.335a9.118 9.118 0 0 1-2.32-1.27l-1.31 1.312A1 1 0 0 1 3.585 14l1.275-1.275c-.784-.936-1.41-2.074-1.812-3.414Z';
const EYE_ON = 'M12 5c-5 0-8.5 4.5-9.5 7 1 2.5 4.5 7 9.5 7s8.5-4.5 9.5-7c-1-2.5-4.5-7-9.5-7m0 2c3.6 0 6.3 3 7.4 5-1.1 2-3.8 5-7.4 5s-6.3-3-7.4-5C5.7 10 8.4 7 12 7m0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6';

/**
 * 시안 입력칸 두 가지.
 * fill: 로그인·회원가입 (높이 44, #1C1C1E, 테두리 없음, 라벨 13 굵게 흰색). password면 '비밀번호 보기' 버튼.
 * box: 이름·초대 코드 (높이 46, #2C2C2E, 테두리 #38383A, 라벨 13 회색).
 */
export function InputField({ label, error, variant = 'fill', password = false, ...input }: TextInputProps & {
  label: string; error?: string | null; variant?: 'fill' | 'box'; password?: boolean;
}) {
  const [shown, setShown] = useState(false);
  return <View style={{ gap: 8 }}>
    <Text style={variant === 'fill' ? s.labelFill : s.labelBox}>{label}</Text>
    <View>
      <TextInput accessibilityLabel={label} placeholderTextColor={DS.gray2} secureTextEntry={password && !shown} {...input}
        style={[variant === 'fill' ? s.inputFill : s.inputBox, password && { paddingRight: 48 }, error ? { borderWidth: 1, borderColor: DS.danger } : null]} />
      {password && <Pressable accessibilityRole="button" accessibilityLabel={shown ? '비밀번호 숨기기' : '비밀번호 보기'}
        onPress={() => setShown((v) => !v)} style={s.eye}>
        <Svg width={20} height={20} viewBox="0 0 24 24" fill="none"><Path fill={DS.gray} fillRule="evenodd" d={shown ? EYE_ON : EYE_OFF} /></Svg>
      </Pressable>}
    </View>
    {error ? <Text accessibilityLiveRegion="polite" style={s.error}>{error}</Text> : null}
  </View>;
}

export function ErrorLine({ children }: { children?: string | null }) {
  if (!children) return null;
  return <Text accessibilityLiveRegion="polite" style={s.error}>{children}</Text>;
}

/** 시안 아래쪽 안내 줄: "계정이 없으십니까? 회원가입" */
export function FooterLink({ text, link, onPress, disabled }: { text: string; link: string; onPress: () => void; disabled?: boolean }) {
  return <View style={s.footer}>
    <Text style={s.footerText}>{text} </Text>
    <Pressable accessibilityRole="link" accessibilityLabel={link} onPress={onPress} disabled={disabled} hitSlop={8} style={s.footerBtn}>
      <Text style={s.footerLink}>{link}</Text>
    </Pressable>
  </View>;
}

/** 버튼 아래 회색 글자 버튼 (높이 44, 14) */
export function QuietButton({ title, onPress, disabled }: { title: string; onPress: () => void; disabled?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={onPress} style={s.quiet}>
    <Text style={[s.quietText, disabled && { opacity: 0.5 }]}>{title}</Text>
  </Pressable>;
}

/** 캐릭터 선택 위 진행 원 (r 32, 굵기 5, 가운데 사람 모양) */
export function CharacterRing({ ratio, label }: { ratio: number; label: string }) {
  const c = 2 * Math.PI * 32;
  return <Svg width={72} height={72} viewBox="0 0 72 72" accessibilityRole="image" accessibilityLabel={label}>
    <Circle cx={36} cy={36} r={32} fill="none" stroke={DS.bg3} strokeWidth={5} />
    <Circle cx={36} cy={36} r={32} fill="none" stroke={DS.accent} strokeWidth={5} strokeLinecap="round"
      strokeDasharray={`${c * ratio} ${c}`} transform="rotate(-90 36 36)" />
    <Circle cx={36} cy={30} r={9} fill={DS.dot} />
    <Path d="M20 52c3-8 9-12 16-12s13 4 16 12" fill={DS.dot} />
  </Svg>;
}

const s = StyleSheet.create({
  title: { ...T.display, fontSize: 24, lineHeight: 32 },
  sub: { color: DS.label2, fontSize: 14, lineHeight: 21 },
  dots: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  dotOn: { width: 18, height: 3, borderRadius: 999, backgroundColor: DS.accent },
  dotOff: { width: 3, height: 3, borderRadius: 999, backgroundColor: DS.label },
  labelFill: { color: DS.label, fontSize: 13, fontWeight: '700' },
  labelBox: { color: DS.label2, fontSize: 13 },
  inputFill: { height: 44, paddingHorizontal: 16, borderRadius: 10, backgroundColor: DS.bg2, color: DS.label, fontSize: 14 },
  inputBox: { height: 46, paddingHorizontal: 16, borderRadius: 10, borderWidth: 1, borderColor: DS.separator, backgroundColor: DS.bg3, color: DS.label, fontSize: 16 },
  eye: { position: 'absolute', right: 4, top: 0, width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  error: { color: DS.danger, fontSize: 13, lineHeight: 18 },
  footer: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', minHeight: 44 },
  footerText: { color: DS.label2, fontSize: 13 },
  footerBtn: { minHeight: 44, justifyContent: 'center' },
  footerLink: { color: DS.accent, fontSize: 13, fontWeight: '700' },
  quiet: { height: 44, alignItems: 'center', justifyContent: 'center' },
  quietText: { color: DS.label2, fontSize: 14 },
});
