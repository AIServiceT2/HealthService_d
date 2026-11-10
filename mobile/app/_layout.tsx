import '../global.css';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { DraftProvider } from '../src/onboarding/draft';
import { COLORS } from '../src/theme/tokens';
export default function Layout() {
  return <DraftProvider><StatusBar style="light" /><Stack screenOptions={{ headerStyle: { backgroundColor: COLORS.background }, headerTintColor: COLORS.text, contentStyle: { backgroundColor: COLORS.background } }}>
    {/* 가입·로그인 화면은 시안대로 상단 바 없이 */}
    <Stack.Screen name="index" options={{ headerShown: false }} />
    <Stack.Screen name="login" options={{ headerShown: false }} />
    <Stack.Screen name="onboarding" options={{ headerShown: false }} />
    <Stack.Screen name="home" options={{ title: '전운시' }} />
    <Stack.Screen name="workout/[id]" options={{ title: '보상 미리보기' }} />
  </Stack></DraftProvider>;
}
