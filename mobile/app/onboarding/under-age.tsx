// 만 14세 미만 (시안 '만 14세 미만 (개인정보 보호)'). 서버에 아무것도 보내지 않는다.
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import Svg, { Path, Rect } from 'react-native-svg';
import { OB, PillButton, Screen, Sub, Title } from '../../src/onboarding/ui';

const Check = () => <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke={OB.accent} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" style={{ marginTop: 1 }}>
  <Path d="M5 12.5l4 4 10-10" />
</Svg>;

export default function UnderAge() {
  const router = useRouter();
  return <Screen>
    <Pressable accessibilityRole="button" accessibilityLabel="뒤로" onPress={() => router.back()} style={styles.back}>
      <Svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"><Path d="M15 18l-6-6 6-6" /></Svg>
    </Pressable>
    <View style={styles.body}>
      <View style={styles.badge}>
        <Svg width={51} height={51} viewBox="0 0 24 24" fill="none" stroke={OB.accent} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <Path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" /><Rect x={9} y={11} width={6} height={5} rx={1} /><Path d="M10 11V9.5a2 2 0 0 1 4 0V11" />
        </Svg>
      </View>
      <View style={{ gap: 10 }}>
        <Title>만 14세 미만은{'\n'}지금 가입할 수 없습니다</Title>
        <Sub>개인정보 보호법에 따라 만 14세 미만의 개인정보를 받으려면 부모님 등 법정대리인의 동의가 필요합니다.</Sub>
      </View>
      <View style={styles.card}>
        <View style={styles.row}><Check /><Text style={styles.rowText}>입력한 생년월일은 저장하지 않았습니다</Text></View>
        <View style={styles.row}><Check /><Text style={styles.rowText}>만 14세가 되면 다시 가입할 수 있습니다</Text></View>
      </View>
    </View>
    <View style={styles.bottom}>
      <PillButton title="생년월일 다시 입력" onPress={() => router.back()} />
      <PillButton title="처음으로" variant="secondary" onPress={() => router.dismissTo('/')} />
    </View>
  </Screen>;
}

const styles = StyleSheet.create({
  back: { marginLeft: 16, marginTop: 4, width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  body: { flex: 1, paddingHorizontal: 24, paddingTop: 28, gap: 20 },
  badge: { width: 72, height: 72, borderRadius: 999, backgroundColor: OB.surfaceRaised, alignItems: 'center', justifyContent: 'center' },
  card: { padding: 18, borderRadius: 16, backgroundColor: OB.surfaceRaised, gap: 12 },
  row: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  rowText: { flex: 1, color: '#FFFFFF', fontSize: 15, lineHeight: 22 },
  bottom: { paddingHorizontal: 24, paddingBottom: 24, gap: 10 },
});
