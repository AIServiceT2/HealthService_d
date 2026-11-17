// 친구 초대 (시안 'GuildInvite'). API-012 초대 코드 발급 (길드장만), React Native Share로 보낸다.
// 시안의 초대 링크·친구 목록 선택은 링크·친구 목록 API가 없어 만들지 않는다 (API-017 지인 목록은 빈 라우터).
import { Pressable, Share, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { HttpError } from '../../src/api/http';
import { Cta, DS, Icon, Loading, Page, T } from '../../src/design/kit';
import { useLoad } from '../../src/game/useLoad';
import { home } from '../../src/home/api';
import { HIcon, kstShort } from '../../src/home/parts';

export default function GuildInvite() {
  const router = useRouter();
  const { id, name } = useLocalSearchParams<{ id: string; name?: string }>();
  // 화면을 열 때 한 번 발급한다 (코드마다 만료 시각이 있음)
  const { data, error, loading, reload } = useLoad(async () => {
    try {
      return await home.invite(id);
    } catch (e) {
      if (e instanceof HttpError && e.status === 403) throw new Error('길드장만 초대 코드를 만들 수 있어요.');
      throw e;
    }
  }, [id]);

  const close = () => (router.canGoBack() ? router.back() : router.replace({ pathname: '/guild/[id]', params: { id } }));
  const share = async () => {
    if (!data) return;
    const guildName = name ? `'${name}' 길드` : '우리 길드';
    await Share.share({ message: `전운시 ${guildName}에서 같이 주간 보스를 공략해요! 초대 코드: ${data.inviteCode}` }).catch(() => undefined);
  };

  return <Page bg={DS.bg}>
    <Pressable accessibilityLabel="닫기" onPress={close} style={StyleSheet.absoluteFill} />
    <View accessibilityViewIsModal accessibilityLabel="친구 초대" style={st.dialog}>
      <View style={st.badge} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <HIcon name="link" size={28} color={DS.accent} />
      </View>
      <Pressable accessibilityRole="button" accessibilityLabel="닫기" onPress={close} style={st.close}>
        <Icon name="close" size={16} />
      </Pressable>

      <View style={{ alignItems: 'center', gap: 8 }}>
        <Text accessibilityRole="header" style={[T.title2, { fontWeight: '700' }]}>친구 초대</Text>
        <Text style={[T.sub, { textAlign: 'center' }]}>
          {name ? <Text style={{ color: DS.accent }}>{name}</Text> : '우리'} 길드에서 함께{'\n'}주간 보스를 공략할 친구를 초대합니다
        </Text>
      </View>

      {loading && !data
        ? <View style={{ height: 120 }}><Loading label="초대 코드 만드는 중" /></View>
        : !data
          ? <View style={{ marginTop: 20, gap: 12 }}>
            <Text style={[T.body, { textAlign: 'center' }]}>{error ?? '초대 코드를 만들지 못했어요.'}</Text>
            <Cta title="다시 시도" variant="outline" onPress={reload} />
          </View>
          : <>
            <View style={st.codeBox}>
              <Text accessibilityLabel={`초대 코드 ${data.inviteCode.split('').join(' ')}`} style={st.code}>{data.inviteCode}</Text>
              <Pressable accessibilityRole="button" accessibilityLabel="초대 코드 공유" onPress={share} style={st.copy}>
                <HIcon name="share" size={20} />
              </Pressable>
            </View>
            <Text style={[T.foot, { marginTop: 8 }]}>{kstShort(data.expiresAt)}까지 쓸 수 있어요</Text>
            <Cta title="초대 보내기" onPress={share} height={56} style={{ marginTop: 22 }} />
          </>}
    </View>
  </Page>;
}

const st = StyleSheet.create({
  dialog: { position: 'absolute', left: 16, right: 16, bottom: 24, paddingTop: 48, paddingHorizontal: 20, paddingBottom: 24, borderRadius: 32, backgroundColor: DS.bg2 },
  badge: { position: 'absolute', alignSelf: 'center', top: -36, width: 72, height: 72, borderRadius: 999, backgroundColor: DS.bg3, borderWidth: 4, borderColor: DS.bg2, alignItems: 'center', justifyContent: 'center' },
  close: { position: 'absolute', right: 14, top: 14, width: 44, height: 44, borderRadius: 999, borderWidth: 1.5, borderColor: '#48484A', alignItems: 'center', justifyContent: 'center' },
  codeBox: { marginTop: 20, height: 56, paddingLeft: 16, paddingRight: 6, borderRadius: 14, backgroundColor: DS.bg3, flexDirection: 'row', alignItems: 'center', gap: 8 },
  code: { flex: 1, color: DS.label, fontSize: 20, fontWeight: '800', letterSpacing: 4 },
  copy: { width: 44, height: 44, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
});
