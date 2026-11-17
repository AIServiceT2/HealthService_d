import '../global.css';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { DraftProvider } from '../src/onboarding/draft';
import { COLORS } from '../src/theme/tokens';
// 시안(전운시 화면 시안)은 모든 화면이 자기 상단 바를 그리므로 기본 헤더를 끈다.
export default function Layout() {
  return <DraftProvider><StatusBar style="light" /><Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: COLORS.background } }}>
    <Stack.Screen name="workout/camera" options={{ gestureEnabled: false }} />
    <Stack.Screen name="submission/[id]/replay" options={{ animation: 'fade' }} />
    <Stack.Screen name="menu" options={{ presentation: 'transparentModal', animation: 'fade' }} />
  </Stack></DraftProvider>;
}
