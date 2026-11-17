// 사람 확인(F-04) 화면 공통 부품. 시안 ReviewRequest·ReviewerView·RejectReason 보드에서 옮겼다.
// 공통 kit(src/design/kit.tsx)에 없는 것만 여기에 둔다.
import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type ViewStyle } from 'react-native';
import { useRouter } from 'expo-router';
import Svg, { Circle, G, Line } from 'react-native-svg';
import { DS, IconButton, T } from '../design/kit';

// 시안 AI 블록의 '이상한 점' 글자색 (디자인 시스템 보드에 없는 값)
export const ANOMALY_TEXT = '#FFB877';

/** 시안 상단: 왼쪽 뒤로 + 왼쪽 정렬 큰 제목 (24, G마켓 산스 자리) */
export function TitleBar({ title, onBack }: { title?: string; onBack?: () => void }) {
  const router = useRouter();
  const back = onBack ?? (() => (router.canGoBack() ? router.back() : router.replace('/home')));
  return <View style={st.titleBar}>
    <IconButton name="back" label="뒤로" onPress={back} />
    {title ? <Text accessibilityRole="header" numberOfLines={1} style={[T.display, { fontSize: 24, lineHeight: 32, flex: 1 }]}>{title}</Text> : null}
  </View>;
}

/** 시안 관절선 그림 (얼굴 없음). 실제 기록 좌표가 아니라 정해 둔 예시 모양이다 */
export function JointFigure({ width, height, dots, label }: { width: number; height: number; dots?: boolean; label: string }) {
  return <View accessible accessibilityRole="image" accessibilityLabel={label} style={{ width, height }}>
  <Svg width={width} height={height} viewBox="0 0 170 220">
    <G stroke={DS.accent} strokeWidth={dots ? 4 : 5} strokeLinecap="round" fill="none">
      <Line x1={70} y1={40} x2={80} y2={110} /><Line x1={72} y1={55} x2={120} y2={75} />
      <Line x1={80} y1={110} x2={130} y2={120} /><Line x1={130} y1={120} x2={125} y2={200} />
    </G>
    {dots && <G fill={DS.label}>
      <Circle cx={72} cy={55} r={5} /><Circle cx={120} cy={75} r={5} /><Circle cx={80} cy={110} r={5} />
      <Circle cx={130} cy={120} r={5} /><Circle cx={125} cy={200} r={5} />
    </G>}
  </Svg>
  </View>;
}

/** 회색 알약 정보 (시안: 스쿼트 · N회) */
export function InfoPill({ label }: { label: string }) {
  return <View style={st.infoPill}><Text style={{ color: DS.label, fontSize: 13 }}>{label}</Text></View>;
}

/** 시안 카드 (#1C1C1E, 모서리 16) */
export function Panel({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[st.panel, style]}>{children}</View>;
}

/** 하나만 고르는 줄 (확인자 선택·반려 사유). 고르면 테두리 2px 강조색 */
export function ChoiceRow({ selected, onPress, label, hint, color = DS.accent, leading, disabled }: {
  selected: boolean; onPress: () => void; label: string; hint?: string; color?: string; leading?: ReactNode; disabled?: boolean;
}) {
  return <Pressable accessibilityRole="radio" accessibilityState={{ checked: selected, selected, disabled: !!disabled }}
    accessibilityLabel={hint ? `${label}, ${hint}` : label} disabled={disabled} onPress={onPress}
    style={[st.choice, selected ? { borderWidth: 2, borderColor: color, paddingHorizontal: 15, paddingVertical: 13 } : null, disabled && { opacity: 0.5 }]}>
    {leading}
    <View style={{ flex: 1, gap: 2 }}>
      <Text style={{ color: DS.label, fontSize: 14, fontWeight: '600' }}>{label}</Text>
      {hint ? <Text style={{ color: DS.label2, fontSize: 13 }}>{hint}</Text> : null}
    </View>
  </Pressable>;
}

/** 라디오 동그라미 (시안 반려 사유 input radio 자리) */
export function RadioDot({ on, color }: { on: boolean; color: string }) {
  return <View style={[st.radio, { borderColor: on ? color : DS.gray2 }]}>{on && <View style={[st.radioIn, { backgroundColor: color }]} />}</View>;
}

/** 주황 버튼 (시안 반려: 테두리형 / 반려하기: 채움형) */
export function WarnButton({ title, onPress, filled, disabled, loading, style }: {
  title: string; onPress: () => void; filled?: boolean; disabled?: boolean; loading?: boolean; style?: ViewStyle;
}) {
  const off = !!disabled || !!loading;
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled: off, busy: !!loading }} disabled={off} onPress={onPress}
    style={[st.warnBtn, filled ? { backgroundColor: DS.warn } : { borderWidth: 1, borderColor: DS.warn }, off && { opacity: 0.5 }, style]}>
    {loading ? <ActivityIndicator color={filled ? DS.onAccent : DS.warn} />
      : <Text style={{ fontSize: 17, fontWeight: '700', color: filled ? DS.onAccent : DS.warn }}>{title}</Text>}
  </Pressable>;
}

/** 아래 안내·오류 한 줄 */
export function Notice({ children, tone }: { children: ReactNode; tone?: 'warn' | 'danger' }) {
  return <Text accessibilityLiveRegion={tone ? 'polite' : undefined}
    style={{ fontSize: 13, lineHeight: 19, color: tone === 'danger' ? DS.danger : tone === 'warn' ? DS.warn : DS.label2 }}>{children}</Text>;
}

const st = StyleSheet.create({
  titleBar: { flexDirection: 'row', alignItems: 'center', gap: 8, marginLeft: -12, minHeight: 44 },
  infoPill: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, backgroundColor: DS.bg3 },
  panel: { padding: 16, borderRadius: 16, backgroundColor: DS.bg2 },
  choice: { minHeight: 56, flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 14, borderRadius: 14, borderWidth: 1, borderColor: DS.bg3, backgroundColor: DS.bg2 },
  radio: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  radioIn: { width: 10, height: 10, borderRadius: 5 },
  warnBtn: { height: 56, borderRadius: 999, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 24 },
});
