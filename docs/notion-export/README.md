# 노션 명세 내보내기 (JSON)

노션 `전운시` 페이지의 명세 3개를 JSON으로 내보낸 파일이다. 내보낸 시각은 각 파일의 `exported_at`(2026-11-10T05:12:16Z)이고, 원본 주소는 `source`에 있다.

| 파일 | 노션 원본 | 내용 |
| --- | --- | --- |
| `jeonunsi_api_spec.json` | 전운시 API 명세서 (DB) | 공통 규칙(인증·시간·목록·에러 본문·If-Match) + API 70개(요청·응답·Error Code) |
| `jeonunsi_db.json` | DB (ERD) | 테이블 15개·관계 18개, `DATA-MODEL.md`에서 바꾼 곳, 아직 정하지 못한 것, Mermaid ERD |
| `jeonunsi_feature_spec.json` | 전운시 기능명세서 | 기능 38개(범위·사용자·스토리·상태 전이·LLM) |

- 노션 내용은 **참고 자료**다. 저장소 문서(`backlog.md`·`API.md`·`DATA-MODEL.md` 등)와 다르면 한쪽에 맞추지 않고 알린다 (CLAUDE.md 팀 규칙).
- 노션이 바뀌어도 이 파일은 자동으로 바뀌지 않는다. 다시 내보내면 파일을 통째로 바꾸고 `exported_at`을 확인한다.
- 파일 안의 이메일·비밀번호·토큰 값은 명세 예시(`user@example.com`, `example-password`, `eyJ...`)이며 실제 값이 아니다.
