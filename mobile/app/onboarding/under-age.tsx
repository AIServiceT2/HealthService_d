// 만 14세 미만 (시안 'UnderAge'). 서버에 아무것도 보내지 않는다.
import { StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import Svg, { Path } from 'react-native-svg';
import { Cta, DS, Icon, IconButton, Page } from '../../src/design/kit';
import { StepHeading } from '../../src/onboarding/parts';

const SHIELD = 'M11.298 2.195a2 2 0 0 1 1.232-.055l.172.055 7 2.625a2 2 0 0 1 1.291 1.708l.007.165v5.363a9 9 0 0 1-4.709 7.911l-.266.139-3.354 1.677a1.5 1.5 0 0 1-1.198.062l-.144-.062-3.354-1.677a9 9 0 0 1-4.970-7.750l-.005-.3V6.693a2 2 0 0 1 1.145-1.808l.153-.065zM12 4.068 5 6.693v5.363a7 7 0 0 0 3.635 6.138l.235.123L12 19.882l3.13-1.565a7 7 0 0 0 3.865-5.997l.005-.264V6.693zm-.492 3.448a1.4 1.4 0 0 1 .846-.043l.138.043 2.8 1.05a1.4 1.4 0 0 1 .902 1.178l.006.133v2.145a4.2 4.2 0 0 1-2.131 3.655l-.19.102-1.342.67a1.2 1.2 0 0 1-.944.056l-.13-.055-1.341-.671a4.2 4.2 0 0 1-2.316-3.54l-.006-.217V9.877a1.4 1.4 0 0 1 .786-1.258l.122-.053zM12 9.468l-2.2.825v1.73a2.2 2.2 0 0 0 1.07 1.887l.146.08.984.492.984-.492a2.2 2.2 0 0 0 1.21-1.802l.006-.166v-1.729z';

const Line = ({ children }: { children: string }) => <View style={styles.row}>
  <View style={{ marginTop: 1 }}><Icon name="check" size={20} color={DS.accent} /></View>
  <Text style={styles.rowText}>{children}</Text>
</View>;

export default function UnderAge() {
  const router = useRouter();
  return <Page>
    <IconButton name="back" label="뒤로" onPress={() => router.back()} style={styles.back} />
    <View style={styles.body}>
      <View style={styles.badge}>
        <Svg width={51} height={51} viewBox="0 0 24 24" fill="none"><Path fill={DS.accent} fillRule="evenodd" d={SHIELD} /></Svg>
      </View>
      <StepHeading title={'만 14세 미만은\n지금 가입할 수 없습니다'}
        sub="개인정보 보호법에 따라 만 14세 미만의 개인정보를 받으려면 부모님 등 법정대리인의 동의가 필요합니다." />
      <View style={styles.card}>
        <Line>입력한 생년월일은 저장하지 않았습니다</Line>
        <Line>만 14세가 되면 다시 가입할 수 있습니다</Line>
      </View>
    </View>
    <View style={styles.bottom}>
      <Cta title="생년월일 다시 입력" onPress={() => router.back()} />
      <Cta title="처음으로" variant="secondary" height={56} onPress={() => router.dismissTo('/')} />
    </View>
  </Page>;
}

const styles = StyleSheet.create({
  back: { marginLeft: 16, marginTop: 4 },
  body: { flex: 1, paddingHorizontal: 20, paddingTop: 24, gap: 20 },
  badge: { width: 72, height: 72, borderRadius: 999, backgroundColor: DS.bg3, alignItems: 'center', justifyContent: 'center' },
  card: { marginTop: 12, padding: 18, borderRadius: 16, backgroundColor: DS.bg3, gap: 12 },
  row: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  rowText: { flex: 1, color: DS.label, fontSize: 14, lineHeight: 21 },
  bottom: { paddingHorizontal: 20, paddingBottom: 16, gap: 10 },
});
