// 시안 '06 상태 화면' 공통 틀: 가운데 그림 · 제목 · 설명 · 작은 알약 · 주 버튼 · 글자 버튼.
// 그림은 시안 SVG를 그대로 옮겼다 (카메라 권한·중단·재시도·중복·일일 상한).
import type { ReactNode } from 'react';
import { Text, View } from 'react-native';
import Svg, { Circle, Ellipse, Path, Rect } from 'react-native-svg';
import { Cta, DS, Page, T } from '../design/kit';

export type StateArt = 'cameraDenied' | 'interrupted' | 'retry' | 'duplicate' | 'dailyCap';

export function StateIllustration({ art }: { art: StateArt }) {
  return <Svg width={120} height={120} viewBox="0 0 120 120" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
    {art === 'cameraDenied' && <>
      <Ellipse cx={60} cy={106} rx={40} ry={6} fill="#1C1C1E" />
      <Rect x={18} y={38} width={84} height={58} rx={14} fill="#8E8E93" />
      <Rect x={18} y={38} width={84} height={16} rx={8} fill="#AEAEB2" />
      <Rect x={42} y={26} width={36} height={18} rx={6} fill="#AEAEB2" />
      <Circle cx={60} cy={68} r={19} fill="#636366" />
      <Circle cx={60} cy={68} r={11} fill="#C7C7CC" />
      <Path d="M24 26 L98 104" stroke="#000000" strokeWidth={12} strokeLinecap="round" />
      <Path d="M24 26 L98 104" stroke="#D1D1D6" strokeWidth={6} strokeLinecap="round" />
    </>}
    {art === 'interrupted' && <>
      <Ellipse cx={60} cy={108} rx={38} ry={6} fill="#1C1C1E" />
      <Circle cx={60} cy={58} r={44} fill="#8E8E93" />
      <Path d="M16 58a44 44 0 0 1 88 0" fill="#AEAEB2" />
      <Rect x={44} y={38} width={11} height={40} rx={5} fill="#E5E5EA" />
      <Rect x={65} y={38} width={11} height={40} rx={5} fill="#E5E5EA" />
    </>}
    {art === 'retry' && <>
      <Ellipse cx={60} cy={106} rx={40} ry={6} fill="#1C1C1E" />
      <Path d="M34 88h54a20 20 0 0 0 2-40 28 28 0 0 0-54-6 22 22 0 0 0-2 46z" fill="#8E8E93" />
      <Path d="M36 52a28 28 0 0 1 54-4 18 18 0 0 1 12 8H30a22 22 0 0 1 6-4z" fill="#AEAEB2" />
      <Rect x={55} y={54} width={10} height={20} rx={5} fill="#E5E5EA" />
      <Circle cx={60} cy={81} r={5} fill="#E5E5EA" />
    </>}
    {art === 'duplicate' && <>
      <Ellipse cx={60} cy={108} rx={38} ry={6} fill="#1C1C1E" />
      <Rect x={38} y={14} width={56} height={70} rx={10} fill="#636366" />
      <Rect x={24} y={28} width={56} height={74} rx={10} fill="#AEAEB2" />
      <Rect x={24} y={28} width={56} height={16} rx={8} fill="#C7C7CC" />
      <Rect x={34} y={54} width={36} height={6} rx={3} fill="#E5E5EA" />
      <Rect x={34} y={66} width={28} height={6} rx={3} fill="#E5E5EA" />
      <Rect x={34} y={78} width={32} height={6} rx={3} fill="#E5E5EA" />
    </>}
    {art === 'dailyCap' && <>
      <Ellipse cx={60} cy={104} rx={42} ry={6} fill="#1C1C1E" />
      <Rect x={12} y={36} width={88} height={54} rx={12} fill="#8E8E93" />
      <Rect x={12} y={36} width={88} height={14} rx={7} fill="#AEAEB2" />
      <Rect x={100} y={52} width={10} height={22} rx={4} fill="#8E8E93" />
      {[22, 38, 54, 70].map((x) => <Rect key={x} x={x} y={48} width={12} height={32} rx={3} fill="#E5E5EA" />)}
      <Rect x={86} y={48} width={6} height={32} rx={3} fill="#E5E5EA" />
    </>}
  </Svg>;
}

type Action = { title: string; onPress: () => void; loading?: boolean; disabled?: boolean };

/** 상태 화면 본문 (Page 안에 넣어 쓴다) */
export function StateBody({ art, title, body, tag, primary, secondary, extra }: {
  art: StateArt; title: string; body: string; tag?: string | null; primary?: Action; secondary?: Action; extra?: ReactNode;
}) {
  return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8, paddingHorizontal: 20, paddingBottom: 40 }}>
    <View style={{ marginBottom: 20 }}><StateIllustration art={art} /></View>
    <Text accessibilityRole="header" style={[T.title3, { textAlign: 'center' }]}>{title}</Text>
    <Text style={{ fontSize: 14, lineHeight: 22, color: DS.gray, textAlign: 'center' }}>{body}</Text>
    {tag ? <View style={{ marginTop: 4, height: 30, paddingHorizontal: 14, borderRadius: 999, backgroundColor: DS.bg2, justifyContent: 'center' }}>
      <Text style={{ fontSize: 13, fontWeight: '600', color: DS.label }}>{tag}</Text>
    </View> : null}
    {primary ? <Cta title={primary.title} onPress={primary.onPress} loading={primary.loading} disabled={primary.disabled} height={48} style={{ marginTop: 16 }} /> : null}
    {extra}
    {secondary ? <Cta title={secondary.title} variant="text" onPress={secondary.onPress} loading={secondary.loading} disabled={secondary.disabled} height={44} /> : null}
  </View>;
}

/** 화면 전체를 차지하는 상태 화면 */
export function StateScreen(props: Parameters<typeof StateBody>[0]) {
  return <Page><StateBody {...props} /></Page>;
}
