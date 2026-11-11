// 생년월일 휠 한 칸 (시안 '생년월일': 가운데 줄이 크고 밝고, 위아래로 갈수록 작아짐).
// 스크린리더는 위·아래로 쓸어 값을 바꾼다 (adjustable).
import { useEffect, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, View, type NativeScrollEvent, type NativeSyntheticEvent, type ScrollViewInstance } from 'react-native';

export const ITEM_H = 40;
const VISIBLE = 5;

export function WheelColumn({ values, index, onChange, label, width }: {
  values: string[]; index: number; onChange: (index: number) => void; label: string; width: number;
}) {
  const ref = useRef<ScrollViewInstance>(null);
  const [offset, setOffset] = useState(index * ITEM_H);

  useEffect(() => {
    // 바깥에서 값이 바뀌면(예: 2월로 바꿔 31일이 30일로 줄어듦) 그 자리로 옮긴다
    if (Math.round(offset / ITEM_H) !== index) {
      ref.current?.scrollTo({ y: index * ITEM_H, animated: false });
      setOffset(index * ITEM_H);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, values.length]);

  const settle = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const next = Math.max(0, Math.min(values.length - 1, Math.round(e.nativeEvent.contentOffset.y / ITEM_H)));
    if (next !== index) onChange(next);
  };

  return <View style={{ width, height: ITEM_H * VISIBLE }}
    accessible accessibilityRole="adjustable" accessibilityLabel={label} accessibilityValue={{ text: values[index] }}
    accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}
    onAccessibilityAction={(e) => {
      const next = e.nativeEvent.actionName === 'increment' ? index + 1 : index - 1;
      if (next >= 0 && next < values.length) onChange(next);
    }}>
    <ScrollView ref={ref} showsVerticalScrollIndicator={false} snapToInterval={ITEM_H} decelerationRate="fast"
      contentOffset={{ x: 0, y: index * ITEM_H }}
      contentContainerStyle={{ paddingVertical: ITEM_H * Math.floor(VISIBLE / 2) }}
      onScroll={(e) => setOffset(e.nativeEvent.contentOffset.y)} scrollEventThrottle={16}
      onMomentumScrollEnd={settle} onScrollEndDrag={(e) => { if (!e.nativeEvent.velocity?.y) settle(e); }}>
      {values.map((value, i) => {
        const distance = Math.min(3, Math.abs(i - offset / ITEM_H));
        const size = 22 - distance * 3;
        return <View key={value} style={styles.item}>
          <Text style={{ fontSize: size, fontWeight: distance < 0.5 ? '600' : '400', color: distance < 0.5 ? '#FFFFFF' : distance < 1.5 ? '#98989F' : '#8E8E93' }}>{value}</Text>
        </View>;
      })}
    </ScrollView>
  </View>;
}

const styles = StyleSheet.create({ item: { height: ITEM_H, alignItems: 'center', justifyContent: 'center' } });
