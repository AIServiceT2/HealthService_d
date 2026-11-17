// 반려 사유 입력 (시안 RejectReason). F-04 / US-08
// 사유 코드 1개와 설명이 둘 다 있어야 반려를 보낸다 (backlog US-08 (실패·거절)). 보내기는 부모가 한다(API-039).
import { useEffect, useState } from 'react';
import { BackHandler, ScrollView, Text, TextInput, View } from 'react-native';
import type { RejectReason } from '../api/game';
import { BottomBar, DS } from '../design/kit';
import { ChoiceRow, Notice, RadioDot, TitleBar, WarnButton } from './ui';

export function RejectForm({ reasons, busy, error, onBack, onSubmit }: {
  reasons: RejectReason[]; busy: boolean; error: string | null;
  onBack: () => void; onSubmit: (reasonCode: string, reasonText: string) => void;
}) {
  const [reasonCode, setReasonCode] = useState<string | null>(null);
  const [reasonText, setReasonText] = useState('');
  const [tried, setTried] = useState(false);

  // Android 뒤로 버튼은 확인 화면으로 돌아간다
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => { onBack(); return true; });
    return () => sub.remove();
  }, [onBack]);

  const missingText = reasonText.trim().length === 0;
  const submit = () => {
    setTried(true);
    if (!reasonCode || missingText) return;
    onSubmit(reasonCode, reasonText.trim());
  };

  return <>
    <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 8, paddingBottom: 24, gap: 18 }} keyboardShouldPersistTaps="handled">
      <TitleBar title="반려 사유" onBack={onBack} />
      <Text style={{ color: DS.label2, fontSize: 14, lineHeight: 21 }}>사유와 설명이 있어야 반려할 수 있습니다. 반려된 기록은 보상을 받지 않습니다.</Text>

      <View style={{ gap: 10 }}>
        <Text nativeID="reason-legend" style={{ color: DS.label, fontSize: 14, fontWeight: '600' }}>사유 (1개)</Text>
        <View accessibilityRole="radiogroup" accessibilityLabelledBy="reason-legend" style={{ gap: 10 }}>
          {reasons.map((r) => <ChoiceRow key={r.code} label={r.label} selected={reasonCode === r.code} color={DS.warn} disabled={busy}
            onPress={() => setReasonCode(r.code)} leading={<RadioDot on={reasonCode === r.code} color={DS.warn} />} />)}
        </View>
        {tried && !reasonCode && <Notice tone="danger">사유를 골라야 반려할 수 있어요</Notice>}
      </View>

      <View style={{ gap: 8 }}>
        <Text nativeID="reason-desc" style={{ color: DS.label, fontSize: 14, fontWeight: '600' }}>설명 (필수)</Text>
        <TextInput accessibilityLabel="설명 (필수)" accessibilityLabelledBy="reason-desc" value={reasonText} onChangeText={setReasonText}
          editable={!busy} multiline maxLength={500} placeholder="무엇이 이상했는지 적어 주십시오" placeholderTextColor={DS.gray}
          style={{ height: 120, borderRadius: 16, borderWidth: 1, borderColor: tried && missingText ? DS.danger : DS.separator, backgroundColor: DS.bg3, color: DS.label, fontSize: 14, paddingHorizontal: 16, paddingVertical: 14, textAlignVertical: 'top' }} />
        {tried && missingText && <Notice tone="danger">설명을 입력해야 반려할 수 있어요</Notice>}
      </View>
      {error && <Notice tone="danger">{error}</Notice>}
    </ScrollView>
    <BottomBar>
      <WarnButton title="반려하기" filled loading={busy} onPress={submit} />
    </BottomBar>
  </>;
}
