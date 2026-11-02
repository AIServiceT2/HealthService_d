export { COLORS } from './palette';
// DESIGN.md 2절 간격·글자·형태 [제안·팀 확인 필요]
export const SPACE = { small: 8, medium: 16, large: 24, section: 32 } as const;
export const FONT = {
  caption: { fontSize: 14, lineHeight: 20 },
  body: { fontSize: 16, lineHeight: 24 },
  title: { fontSize: 24, lineHeight: 32, fontWeight: '700' },
  counter: { fontSize: 48, lineHeight: 56, fontWeight: '700' },
} as const;
export const RADIUS = { pill: 999, control: 8, card: 12 } as const;
export const TOUCH_MIN = 48;
