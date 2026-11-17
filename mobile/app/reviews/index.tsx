// 받은 확인 요청 목록 (전용 시안 없음 → kit·확인자 화면 시안에 맞춤). F-04 / US-07
// API-036. 나에게 온 요청만 보인다.
import { useCallback } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { game } from '../../src/auth/session';
import { Cta, DS, EmptyState, ErrorState, Icon, Loading, Page, Tag } from '../../src/design/kit';
import { Notice, TitleBar } from '../../src/review/ui';
import { exerciseName, shortTime } from '../../src/game/rules';
import { useLoad } from '../../src/game/useLoad';

export default function ReceivedReviews() {
  const router = useRouter();
  const { data, error, loading, reload } = useLoad(async () => (await game.receivedReviews(50)).items, []);
  useFocusEffect(useCallback(() => { void reload(); }, [reload]));

  if (!data && loading) return <Page><Loading /></Page>;
  if (!data) return <Page>
    <View style={{ paddingHorizontal: 20 }}><TitleBar title="받은 확인 요청" /></View>
    <ErrorState message={error ?? '요청을 불러오지 못했어요'} onRetry={reload} />
  </Page>;

  return <Page>
    <ScrollView contentContainerStyle={{ flexGrow: 1, paddingHorizontal: 20, paddingTop: 8, paddingBottom: 24, gap: 12 }}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={reload} tintColor={DS.accent} />}>
      <TitleBar title="받은 확인 요청" />
      {error && <Notice tone="danger">최신 목록을 불러오지 못했어요. 아래로 당겨 다시 불러오세요.</Notice>}
      {data.length === 0
        ? <EmptyState message="받은 확인 요청이 없어요"
          action={<Cta title="홈으로" variant="outline" onPress={() => router.replace('/home')} style={{ paddingHorizontal: 28 }} />} />
        : data.map((r) => {
          const title = `${r.requester.nickname} · ${exerciseName(r.exerciseCode)} ${r.countedReps}회`;
          const when = shortTime(r.requestedAt);
          return <Pressable key={r.submissionId} accessibilityRole="button" accessibilityLabel={`${title}, ${when} 요청, 확인 대기`}
            onPress={() => router.push({ pathname: '/reviews/[id]', params: { id: r.submissionId } })}
            style={({ pressed }) => [{ minHeight: 72, flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16, borderRadius: 16, backgroundColor: DS.bg2 }, pressed && { opacity: 0.7 }]}>
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={{ color: DS.label, fontSize: 15, fontWeight: '600' }}>{title}</Text>
              {when ? <Text style={{ color: DS.label2, fontSize: 13 }}>{when} 요청</Text> : null}
            </View>
            <Tag label="확인 대기" tone="warn" />
            <Icon name="chevron" color={DS.label2} size={18} />
          </Pressable>;
        })}
    </ScrollView>
  </Page>;
}
