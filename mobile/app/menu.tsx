// 홈 사이드 메뉴 (시안 'HomeMenu'). _layout.tsx에서 transparentModal로 연다.
// 시안의 출석 체크·설정은 MVP 밖이라 뺐고, 받은 확인 요청(US-07·08)을 넣었다.
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, type Href } from 'expo-router';
import { api, logout } from '../src/auth/session';
import { DS, Icon } from '../src/design/kit';
import { useLoad } from '../src/game/useLoad';

export default function Menu() {
  const router = useRouter();
  const { data: me } = useLoad(() => api.me(), []);
  const [leaving, setLeaving] = useState(false);

  const close = () => (router.canGoBack() ? router.back() : router.replace('/home'));
  // 메뉴(모달)를 목적지 화면으로 바꾼다. 뒤로 가면 홈으로 돌아간다
  const go = (href: Href) => router.replace(href);

  const items: { label: string; onPress: () => void }[] = [
    { label: '내 캐릭터', onPress: () => go('/character') },
  ];
  if (me?.guildId) items.push({ label: '내 길드', onPress: () => go({ pathname: '/guild/[id]', params: { id: me.guildId! } }) });
  else if (me) items.push({ label: '길드 만들기', onPress: () => go('/guild/create') });
  items.push(
    { label: '운동 기록', onPress: () => go('/records') },
    { label: '받은 확인 요청', onPress: () => go('/reviews') },
    {
      label: '로그아웃', onPress: async () => {
        if (leaving) return;
        setLeaving(true);
        await logout();
        router.dismissAll();
        router.replace('/');
      },
    },
  );

  return <View style={st.root}>
    {/* 시안: 오른쪽으로 밀린 홈 화면 카드 (장식) */}
    <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={StyleSheet.absoluteFill} pointerEvents="none">
      <View style={[st.ghost, { left: '66%', top: 100, bottom: 100, backgroundColor: DS.bg3 }]} />
      <View style={[st.ghost, { left: '68%', top: 88, bottom: 88, backgroundColor: DS.dot }]} />
      <View style={[st.ghost, { left: '70%', top: 77, bottom: 77, backgroundColor: DS.bg, overflow: 'hidden' }]}>
        <View style={{ position: 'absolute', left: 36, top: 148, width: 200, height: 284, borderRadius: 16, backgroundColor: DS.accent }} />
        <View style={{ position: 'absolute', left: 20, top: 530, width: 180, height: 8, borderRadius: 999, backgroundColor: DS.bg3 }} />
        <View style={{ position: 'absolute', left: 40, top: 548, width: 140, height: 8, borderRadius: 999, backgroundColor: DS.bg3 }} />
      </View>
    </View>

    <SafeAreaView edges={['top', 'bottom']} style={{ flex: 1 }}>
      <Pressable accessibilityRole="button" accessibilityLabel="메뉴 닫기" onPress={close} style={st.close}>
        <Icon name="close" size={18} color={DS.bg2} />
      </Pressable>
      <View accessibilityRole="menu" accessibilityLabel="메뉴" style={st.nav}>
        {items.map((it) => <Pressable key={it.label} accessibilityRole="menuitem" onPress={it.onPress}
          disabled={leaving} style={st.item}>
          <Text style={st.itemText}>{it.label}</Text>
        </Pressable>)}
      </View>
    </SafeAreaView>
  </View>;
}

const st = StyleSheet.create({
  root: { flex: 1, backgroundColor: DS.bg2 },
  ghost: { position: 'absolute', width: 220, borderRadius: 32 },
  close: { marginLeft: 14, marginTop: 10, width: 44, height: 44, borderRadius: 999, backgroundColor: '#E5E5EA', alignItems: 'center', justifyContent: 'center' },
  nav: { marginLeft: 22, marginTop: 35, width: 230, gap: 22 },
  item: { minHeight: 48, justifyContent: 'center' },
  itemText: { color: DS.label, fontSize: 20, fontWeight: '600' },
});
