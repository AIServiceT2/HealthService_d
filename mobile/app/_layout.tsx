import '../global.css';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { COLORS } from '../src/theme/tokens';
export default function Layout() {
  return <><StatusBar style="light" /><Stack screenOptions={{ headerStyle: { backgroundColor: COLORS.background }, headerTintColor: COLORS.text, contentStyle: { backgroundColor: COLORS.background } }}>
    <Stack.Screen name="index" options={{ title: '전운시' }} />
    <Stack.Screen name="workout/[id]" options={{ title: '보상 미리보기' }} />
  </Stack></>;
}
