# 기술 스택 결정 기록

> **저장 위치:** `docs/STACK.md`

> **결정은 팀이 합니다.** Claude는 후보 2안을 비교해 줄 뿐입니다. "AI가 추천해서"는 이유가 아닙니다. **우리 팀 경험·기간·핵심 기능**으로 씁니다.
> 확인하지 못한 버전이나 실행 명령은 추측하지 말고 `확인 필요`로 씁니다. `>`로 시작하는 안내 문장은 지워도 됩니다.

- 결정일: 2026-10-27
- 검토 상태: 앱 개발 방향은 유지. LLM 제공사·예산은 재확인 전이며, 아래 구현·검증 계획은 실행 결과가 아닌 계획이다.
- 근거: [stack-inputs.md](decisions/stack-inputs.md)(팀 경험·조건), [mvp-scope.md](decisions/mvp-scope.md), [backlog.md](requirements/backlog.md)(필수 스토리), [user-flows.md](requirements/user-flows.md), [client-meeting-1.md](interview/client-meeting-1.md), [draft.md](proposal/draft.md), [03-rules-states-llm.md](domain/03-rules-states-llm.md), [roles.md](team/roles.md), [working-agreement.md](team/working-agreement.md)

## 우리 팀 상황
> 지난 시간에 쓴 `docs/decisions/stack-inputs.md`에서 요약해 옮깁니다. 새로 쓰지 않습니다.

| 항목 | 내용 |
| --- | --- |
| 서비스 | 맨몸 운동을 꾸준히 하려는 10~20대가 카메라 자세 인식으로 AI 판정을 바로 받은 운동 기록을 캐릭터 성장과 전투 리플레이로 이어가는 서비스 ([draft.md](proposal/draft.md) Ⅳ-9). 고객 목표 규모: 3개월 500명, 길드 약 50개, 하루 제출 300건 ([client-meeting-1.md](interview/client-meeting-1.md) 질의응답 4·5) |
| 핵심 기능 (필수 스토리 기준) | ① 스쿼트 카메라 렙 인식·자동 제출(US-01) ② 보상 미리보기·AI 확신도 자동 승인·한 번만 지급(US-02~04) ③ 리플레이·결과 카드·교정 코멘트(US-05). 취소·확인 요청·반려(US-06~08)도 MVP 필수지만 첫 데모 이후. 첫 데모(3주차)는 스쿼트 30회 `SUBMITTED → PREPARED → APPROVED → REWARDED` → 리플레이, 중복 지급 요청·LLM 장애 확인 포함 ([mvp-scope.md](decisions/mvp-scope.md), [user-flows.md](requirements/user-flows.md)) |
| 팀이 **직접 써 본** 언어·도구 (이름만 들어 본 것은 제외) | **백엔드:** FastAPI 3명(강준석·성민규·김지은), Spring Boot 3명(강준석·성민규·이시은. 이시은은 Java가 어려웠다고 함)<br>**프론트:** React·TypeScript 3명(성민규·손범수·이시은), Vite·Tailwind(손범수), Next.js(이시은), Vue(성민규·이시은)<br>**모바일:** Kotlin(성민규). **React Native: 써 본 사람 없음**. 이시은의 "앱 화면"이 어떤 기술인지 `확인 필요`<br>**DB:** PostgreSQL 2명(강준석·성민규), MySQL 3명(강준석·성민규·이시은), SQLite·SQLAlchemy·Redis(김지은)<br>**기타:** pytest·Docker Compose·Gemini API(김지은), AWS(강준석·성민규), CI/CD(성민규), Figma(이시은)<br>**자세 인식 모델: 써 본 사람 없음**<br>괄호·`?`로 적힌 경험(김지은 React·TS, 손범수 Node.js·Express·Spring Boot)은 직접 써 봤는지 분명하지 않아 뺐음 (`확인 필요`) |
| 개발 기간 | 5명, 전체 8주, 주 2회 수업. 3주차 첫 데모, 8주 안에 MVP. 남은 수업일 수·회당 개발 가능 시간·수업 외 개인별 시간은 미정. 다음 팀 회의에서 `남은 수업일 × 회당 개발 시간 + 개인별 수업 외 시간`으로 산정하며, 미확인 시간을 가정해 총량을 계산하지 않음 |
| 화면 (웹 / 모바일, 반응형 여부) | **모바일 앱** (React Native + Expo). 첫 데모와 MVP는 Android 우선, iOS는 Mac·iPhone이 있으면 개발용으로만 설치. 웹은 만들지 않음 |
| 시연 방식 (로컬 / 외부 접속) | 팀원 Android 폰에 앱(APK)을 직접 설치하고, 앱은 Render에 올린 백엔드(HTTPS)에 접속. 배포가 막히면 개발자 PC 백엔드 + HTTPS 터널. 시연 폰 기종은 3주차 첫 데모 전 카메라 테스트에서 통과한 기기로 정함 |
| 제약 (비용, 설치 권한, 외부 서비스) | **무료 범위 우선 검토 (유료 사용 여부·예산 상한은 팀 확인 필요)** → 현재 시연안에서는 Apple Developer Program(연 $99)·Google Play 등록($25)은 하지 않음. 앱 빌드에는 Android Studio(Android SDK)가 필요하고, iOS 빌드는 Mac·Xcode가 필요함. 팀원별 OS·설치 권한은 뼈대 세우기 전에 각자 확인 (`확인 필요`). 카메라가 있는 폰과 전신 촬영 공간 필요. 영상은 기기 밖으로 보내지 않음(R11). LLM 제공사는 대상 연령·데이터 처리 조건을 확인한 뒤 확정. Gemini는 아래 연령 제한으로 도입 보류. 키 발급·학교 네트워크 접근도 확인 필요. 고객 요구: 자세 인식 모델 여러 개 비교·기록(피드백 15), 온디바이스 AI(피드백 16), 반복 요청 처리 설계(피드백 17), LLM 장애 시 대체 동작(피드백 14) |

### 팀원별 새로 배워야 할 것

| 이름 (S1 역할) | 어려웠던 것 (stack-inputs) | 이 프로젝트에서 새로 배워야 할 것 |
| --- | --- | --- |
| 강준석 (테스트 담당) | 로그인 인증, 테이블 관계 설계, FastAPI 비동기·요청 검증, 테스트 코드 | 상태 전이·중복 보상 방지 테스트, Jest로 렙 판정 로직 테스트 |
| 성민규 (테크 리드) | JWT, DB 관리 | React Native·Expo 빌드, 자세 인식 모델 (Kotlin 경험은 네이티브 모듈이 필요할 때 활용) |
| 김지은 (리더) | 로그인, 테이블 관계 설계 | 상태 전이 API·테스트, 온디바이스 자세 인식 비교, LLM 출력 규칙 검사 |
| 손범수 (개발자 2) | 전역 상태 관리, 로그인 토큰 저장·갱신, API 에러 처리 | React Native 화면, 카메라 운동 화면 |
| 이시은 (개발자 1) | Java | React Native 화면, 자세 인식 결과·리플레이·결과 카드 화면 |

- 다섯 명 모두 React Native는 처음입니다. React·TypeScript 경험(3명)은 그대로 쓰이지만, 화면 요소(`View`·`Text`), 스타일, 빌드·설치 방식은 새로 배워야 합니다.

## 후보 2안 비교

> 두 안 모두 React Native(TypeScript) 앱이고 백엔드·DB는 같습니다. 차이는 앱을 만드는 방식(Expo 사용 여부)과 자세 인식 모델을 연결하는 방식입니다.

| 비교 항목 | A안 (선택) | B안 |
| --- | --- | --- |
| 프론트엔드 | React Native + Expo 개발 빌드 (TypeScript), Android 우선 | React Native CLI (Expo 없이, TypeScript), Android 우선 |
| 백엔드 | FastAPI + SQLAlchemy (Python) | 같음 |
| DB | PostgreSQL | 같음 |
| UI 도구 | NativeWind (React Native용 Tailwind) | 같음 (또는 기본 `StyleSheet`) |
| 새로 배워야 할 것 | React Native, Expo 개발 빌드, VisionCamera 프레임 처리, fast-tflite로 TFLite 자세 모델 실행(입력 크기 맞추기·출력 해석) | React Native, Android 네이티브 프로젝트 직접 관리(Gradle 등), Kotlin으로 MediaPipe 네이티브 모듈 작성 |
| 화면·서버 연결에서 어려울 곳 | 관절 좌표(얼굴 제외)·렙 타임스탬프 전송 형식, 로그인 토큰 저장·갱신, 앱은 HTTP 주소를 기본으로 막아서 개발 중 PC 서버 접속 설정 필요 | 같음 + 네이티브 모듈과 JS 사이 데이터 전달 |
| 테스트·실행 재현 | pytest + Docker Compose(PostgreSQL), Jest + React Native Testing Library. 로컬 빌드 담당 PC에 Android Studio 설치 필요. 다른 팀원은 공유 APK로 검증 가능. 실행 명령 `확인 필요` | 같음. 네이티브 설정을 팀원마다 맞춰야 해서 재현이 더 어려움. 실행 명령 `확인 필요` |
| 비용·무료 한도 (확인한 것 / 확인 필요) | 확인한 것: 로컬 빌드 무료, EAS Build Free(Android 15회·iOS 15회, 낮은 우선순위), Android APK 직접 설치 무료, iOS 무료 계정은 7일마다 다시 설치. Render Free·Neon Free·Gemini 무료 등급. 확인 필요: EAS 15회가 매달 초기화되는지, Gemini 무료 호출 한도 숫자 | 로컬 빌드 무료(EAS 없음). 나머지는 같음 |

> 출처와 확인 날짜는 아래 [외부 사실 확인 기록](#외부-사실-확인-기록)에 있습니다.

### 영역별 세부 비교

> 기준: 팀 숙련도 / 구현 난이도 / 운영 부담 / 비용 / MVP 적합성. 영역마다 현실적인 후보 2~3개만 비교합니다.

**앱 만드는 방식**

| 기준 | Expo 개발 빌드 | React Native CLI (Expo 없이) |
| --- | --- | --- |
| 팀 숙련도 | React Native 경험 없음. React·TS 3명 | 같음. Android 네이티브 설정은 Kotlin 경험자 1명(성민규) |
| 구현 난이도 | 네이티브 설정을 Expo가 대부분 만들어 줌(prebuild). 추가 네이티브 라이브러리(VisionCamera·fast-tflite)도 개발 빌드로 사용 | Android·iOS 네이티브 프로젝트를 직접 관리해야 함 |
| 운영 부담 | 로컬 빌드 또는 EAS Build Free | 로컬 빌드만 |
| 비용 | 무료 | 무료 |
| MVP 적합성 | React Native 공식 문서가 새 앱에 Expo 같은 프레임워크를 권장. 8주·경험 없음에 맞음 | 네이티브 설정에 시간이 들어 첫 데모까지 부담 |

- Expo Go(설치만 하면 바로 실행되는 앱)로는 카메라 프레임 처리·자세 인식 같은 추가 네이티브 라이브러리를 쓸 수 없습니다. **개발 빌드**(우리 앱 전용 개발용 앱)를 만들어 설치해야 합니다.
- 플랫폼은 Android를 우선합니다. Android는 앱 파일(APK)을 무료로 직접 설치할 수 있고, iOS는 무료 계정이면 7일마다 다시 설치해야 하며 빌드에 Mac이 필요합니다.

**백엔드**

| 기준 | FastAPI 단독 | Spring Boot 단독 | Spring Boot + FastAPI 함께 |
| --- | --- | --- | --- |
| 팀 숙련도 | 3명. pytest 경험 1명 | 3명 (1명은 Java가 어려웠음) | 두 기술을 모두 다뤄야 해서 담당이 나뉨 |
| 구현 난이도 | 관절 통계·LLM 호출·출력 검사를 Python 하나에서 처리. 잠금·트랜잭션은 SQLAlchemy로 직접 작성 | `@Transactional`·JPA 잠금이 익숙함. 관절 통계·LLM 출력 검사는 Java로 작성 | 서버 사이 호출·인증·에러 전달을 따로 만들어야 함 |
| 운영 부담 | 서버 1개 | 서버 1개 | 서버 2개, 배포·CI·로그 두 벌 |
| MVP 적합성 | 적합 | 적합 | 지금은 필요 없음 |

- **함께 쓸 필요가 있는가:** 자세 인식은 폰 안에서 하므로 서버에서 모델을 돌리지 않습니다(R11, 피드백 16). 서버가 Python으로 할 일은 관절 통계와 LLM 호출뿐이고 하루 300건 규모라 백엔드 하나로 충분합니다.

**데이터베이스**

| 기준 | PostgreSQL | MySQL |
| --- | --- | --- |
| 팀 숙련도 | 2명 | 3명 |
| 구현 난이도 | 트랜잭션·행 잠금·유니크 제약·조건부 갱신 지원. `jsonb`로 관절 좌표·스냅샷 저장이 편함 | 트랜잭션·행 잠금·유니크 제약·JSON 컬럼 지원 |
| 운영 부담·비용 | 무료 관리형 서비스(Neon·Supabase) 확인함 | 무료 관리형 서비스 `확인 필요` |

- 테스트를 SQLite로 대신하면 잠금·동시성 동작이 달라 US-04·US-06 테스트가 실제와 어긋날 수 있습니다. 테스트에서도 같은 DB(Docker)를 씁니다.

**앱 안 자세 인식** (3주차 첫 데모 전 비교 테스트로 확인. 피드백 15)

| 기준 | VisionCamera + react-native-fast-tflite + TFLite 자세 모델 (MoveNet 등) | MediaPipe Pose Landmarker (Android·iOS 공식 SDK) | ML Kit Pose Detection |
| --- | --- | --- | --- |
| 하는 일 | 카메라 프레임마다 TFLite 모델을 돌려 관절 좌표 출력 | 프레임마다 관절 좌표 33개 | 프레임마다 관절 좌표 33개 |
| React Native 연결 | fast-tflite 예제가 VisionCamera v5와 함께 쓰는 방법을 보여 줌. TypeScript에서 대부분 처리 | 공식 RN 패키지 없음. 커뮤니티 Expo 모듈을 쓰거나 Kotlin/Swift로 네이티브 모듈을 직접 만들어야 함 | 공식 RN 패키지 없음. 커뮤니티 플러그인은 옛 VisionCamera(v2~v3) 기준이라 v5 호환 `확인 필요` |
| 상태 | 라이브러리 유지 중 (npm 3.0.1) | 공식 지원 | **베타** (변경될 수 있고 SLA 없음) |
| 데이터 전송 | 라이브러리의 데이터 전송 조건 `확인 필요` | 입력 처리는 기기 안. 성능·사용 지표는 Google로 전송 | 입력 처리는 기기 안. 성능·사용 지표는 Google로 전송하고, **앱 사용자에게 알려야 함** |
| 얼굴 정보 | MoveNet은 17개 중 0~4번(코·눈·귀)을 전송 전 제거. 모델 교체 시 해당 모델의 얼굴 인덱스를 별도로 정의 | 0~10번(코·눈·귀·입) 제거 | 귀·눈·입·코 지점 제거 |
| 팀 숙련도 | 없음 | 없음 (Kotlin 1명) | 없음 (Kotlin 1명) |

- 렙 판정 로직(관절 각도 → 인정·미인정)은 모델과 별개로 우리가 TypeScript로 작성합니다. 모델 출력은 관절 번호·좌표계·신뢰도 의미가 서로 다릅니다. 모델별 어댑터에서 공통 관절 이름, 정규화 좌표, 타임스탬프, 유효성 표시로 변환한 뒤 판정 로직에 넘깁니다. 카메라 회전·좌우 반전·크롭을 보정하고 필요한 관절이 없으면 판정을 보류합니다. 모델 교체 때 같은 기준 데이터로 다시 검증하며, 원시 신뢰도 점수를 그대로 자동 승인 확률로 사용하지 않습니다.
- 위 세 방법 모두 Expo Go가 아니라 개발 빌드가 필요합니다.

**LLM 연동**

| 기준 | Google Gemini API | 유료 LLM API (Claude API, OpenAI API 등) |
| --- | --- | --- |
| 팀 숙련도 | 김지은이 FastAPI에서 연결해 봄 | 없음 |
| 비용 | 무료 등급 있음. 무료 호출 한도 숫자는 AI Studio에서만 보임(`확인 필요`) | Claude API는 공식 문서에 무료 등급 없음. OpenAI "Free" 등급이 실제 무료인지 `확인 필요` |
| 개인정보 | **무료 등급에 보낸 내용은 Google 제품 개선에 쓰임**(유료 등급은 쓰지 않음) | 제공사별 정책 `확인 필요` |

- **Gemini 후보 보류 근거:** [공식 추가 약관](https://ai.google.dev/gemini-api/terms)의 Age Requirements는 18세 미만을 대상으로 하거나 이들이 접근할 가능성이 있는 앱에서 사용을 제한한다(2026-10-27 확인). 현재 10~20대 대상과 충돌하므로 무료·유료 등급 변경이나 식별 정보 제거만으로 해결된다고 보지 않는다. 대상 연령을 임의로 바꾸지 않고 리더가 고객·팀과 제공사 조건을 확인한다.
- 제공사 확정 전 모의 응답과 기본 문구로 실패 경로를 개발한다. 실제 LLM 사용이라는 과제 조건은 적합한 제공사·모델의 실제 호출 검증 후 충족한 것으로 기록한다.

**테스트·빌드·배포·CI**

| 영역 | 후보 | 비교 |
| --- | --- | --- |
| 백엔드 테스트 | pytest / JUnit | 백엔드 선택을 따라감 |
| 앱 테스트 | Jest + React Native Testing Library / E2E 도구 | React Native 기본 템플릿에 Jest가 들어 있고 공식 문서가 권장. 렙 판정 로직은 Jest 단위 테스트로 충분. E2E는 첫 데모 뒤 |
| CI | GitHub Actions | 이미 GitHub 사용, 공개 저장소라 표준 러너 무료 |
| 앱 빌드 | 로컬 빌드(`npx expo run:android`) / EAS Build Free | 로컬 빌드는 횟수 제한 없음, Android Studio 필요. EAS Free는 Android·iOS 각 15회, 대기 우선순위 낮음 |
| 앱 설치 | Android APK 직접 설치 / iOS 무료 계정 설치 / 스토어 등록 | Android는 USB 디버깅으로 무료 설치. iOS 무료 계정은 7일마다 다시 설치하고 Mac·Xcode 필요. 스토어 등록은 유료(Google $25, Apple 연 $99) |
| 백엔드 배포 | Render Free | 15분 미사용 시 잠듦 → 시연 전에 깨워야 함. 주소가 HTTPS라 앱에서 그대로 접속 가능 |
| DB 배포 | Neon Free / Supabase Free | **Render 무료 Postgres는 만든 지 30일 뒤 만료되어 8주 프로젝트에 맞지 않음** |
| 시연 대안 | 개발자 PC + HTTPS 터널(cloudflared·ngrok 등) | 앱은 HTTP 주소를 기본으로 막으므로(Android 9 이상, iOS ATS) PC 서버도 HTTPS 터널로 연결. 무료 조건 `확인 필요` |

### 개발 빌드와 시연 APK

- 개발 빌드는 Metro에서 JS를 받아 수정·디버깅하는 용도다. `npx expo run:android` 실행만으로 독립 시연용 APK 검증이 끝난 것으로 보지 않는다.
- 시연 APK는 JS 번들·모델 파일을 포함하고 Android 기기에 설치 가능한 서명을 갖춰야 한다. 빌드 명령, 환경 변수, API 주소, 모델 버전, 서명키 관리 담당을 기록한다. 키·비밀번호는 저장소에 넣지 않는다.
- 원격 백엔드 시연은 Metro와 개발자 PC를 끄고 앱 재실행 → 카메라 → 제출 → 결과까지 확인한다. PC 백엔드 대안에서는 백엔드·터널 PC만 켜 두되 Metro는 필요 없어야 한다.
- APK 설치·카메라 권한 거절·앱 중단·네트워크 재연결은 실제 Android 기기에서 검증한다. 화면 크기 변경과 시스템 글자 크기에 따른 버튼·결과 카드 잘림도 확인한다.
- 근거: [Expo 개발 빌드](https://docs.expo.dev/develop/development-builds/introduction/), [내부 배포](https://docs.expo.dev/build/internal-distribution/). 명령과 패키지 호환성은 아직 실행 검증 전이다.

### 외부 사실 확인 기록

> 확인 날짜는 모두 **2026-10-27**입니다. 패키지 버전은 npm·PyPI 공식 레지스트리, 나머지는 공식 문서·요금 페이지에서 확인했습니다. 실제로 쓸 버전은 뼈대를 세울 때 Expo SDK에 맞는 버전과 별도 네이티브 라이브러리의 호환성을 함께 검증해 고정합니다. 기존 버전·요금 수치는 이번 보완에서 전부 재검증하지 않았으며, 설치·과금 판단 전 공식 출처를 다시 확인합니다.

| 항목 | 확인한 내용 | 출처 |
| --- | --- | --- |
| React Native | 0.88.0. 공식 문서가 새 앱은 Expo 같은 프레임워크 사용을 권장 | https://registry.npmjs.org/react-native/latest , https://reactnative.dev/docs/environment-setup |
| Expo | `expo` 58.0.19 (SDK 58) | https://registry.npmjs.org/expo/latest |
| Expo Go / 개발 빌드 | Expo Go는 Expo SDK에 포함된 네이티브 라이브러리만 사용 가능. 추가 네이티브 모듈은 개발 빌드(`expo-dev-client`) 필요. 로컬·EAS 둘 다 빌드 가능 | https://docs.expo.dev/workflow/customizing/ , https://docs.expo.dev/develop/development-builds/introduction/ |
| EAS Build Free | Android 15회·iOS 15회, 낮은 우선순위, 빌드 45분 제한. 매달 초기화되는지 `확인 필요` | https://expo.dev/pricing |
| 로컬 빌드 | `npx expo run:android`로 로컬 Android SDK에서 빌드. release 빌드는 서명되지 않아 스토어 제출 불가 | https://docs.expo.dev/guides/local-app-development/ |
| iOS 무료 설치 | 무료 Apple 계정(Personal Team): 기기 3대, 기기당 앱 3개, 7일 뒤 만료 | https://developer.apple.com/support/compare-memberships/ |
| Apple Developer Program | 연 $99 | https://developer.apple.com/programs/ |
| Android 직접 설치 | 개발자 옵션 → USB 디버깅, `adb install`. Android 11 이상은 무선 디버깅 가능 | https://developer.android.com/studio/run/device |
| Google Play 등록 | 1회 $25 | https://support.google.com/googleplay/android-developer/answer/6112435 |
| react-native-vision-camera | 5.2.3. v5는 프레임 처리를 "Frame Output"(`useFrameOutput`)으로 함, `react-native-worklets` 등 필요 | https://registry.npmjs.org/react-native-vision-camera/latest , https://visioncamera.margelo.com/docs/guides/frame-processors |
| react-native-fast-tflite | 3.0.1. VisionCamera v5 `useFrameOutput` 예제 있음. Expo는 prebuild(개발 빌드) 필요 | https://github.com/mrousavy/react-native-fast-tflite |
| MediaPipe Pose Landmarker | Android·iOS·Web·Python 공식 지원, 랜드마크 33개(0~10번 얼굴 부위). React Native 공식 패키지 없음. 입력 처리는 기기 안, 성능·사용 지표는 Google로 전송 | https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker , https://github.com/google-ai-edge/mediapipe |
| ML Kit Pose Detection | 랜드마크 33개, Android·iOS, **베타**. 입력 처리는 기기 안, 성능·사용 지표는 Google로 전송하며 사용자에게 알려야 함. React Native 공식 패키지 없음 | https://developers.google.com/ml-kit/vision/pose-detection , https://developers.google.com/ml-kit/terms |
| 커뮤니티 자세 인식 패키지 | `@gymbrosinc/react-native-mediapipe-pose` 1.0.8(Expo 모듈), `react-native-mediapipe` 0.6.0(옛 worklets 기준), `react-native-vision-camera-v3-pose-detection` 1.1.3(VisionCamera v3 기준). 모두 비공식, VisionCamera v5 호환 `확인 필요` | npm 레지스트리 |
| NativeWind | 4.2.7 (Tailwind CSS v3 기반), Expo 지원 | https://registry.npmjs.org/nativewind/latest , https://www.nativewind.dev/docs/getting-started/installation |
| react-native-reanimated | 4.7.1, Expo SDK 문서에 "Expo Go 포함"으로 표시 | https://registry.npmjs.org/react-native-reanimated/latest , https://docs.expo.dev/versions/latest/sdk/reanimated/ |
| 앱 테스트 | React Native 기본 템플릿에 Jest 포함·권장. `@testing-library/react-native` 14.1.0 | https://reactnative.dev/docs/testing-overview , https://registry.npmjs.org/@testing-library/react-native/latest |
| Android HTTP 차단 | Android 9(API 28)부터 HTTP(cleartext) 기본 차단, `network_security_config.xml`로 예외 | https://developer.android.com/privacy-and-security/security-config |
| iOS HTTPS 요구 | ATS가 HTTPS를 요구, 예외는 Info.plist `NSAppTransportSecurity` | https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity |
| FastAPI | 0.162.0, Python 3.10 이상 | https://pypi.org/pypi/fastapi/json |
| SQLAlchemy | 2.1.6, Python 3.11 이상 | https://pypi.org/pypi/sqlalchemy/json |
| PostgreSQL | 지원 중인 최신 메이저 18 (지원 범위 14~18) | https://www.postgresql.org/support/versioning/ |
| Gemini API | 무료 등급 있음, 무료 등급 내용은 제품 개선에 쓰임. 무료 한도 숫자 `확인 필요` | https://ai.google.dev/gemini-api/docs/pricing , https://ai.google.dev/gemini-api/docs/rate-limits |
| Claude API | 공식 요금·한도 문서에 무료 API 등급 없음 | https://claude.com/pricing , https://platform.claude.com/docs/en/api/rate-limits |
| Render Free | 웹 서비스 15분 미사용 시 잠듦. 무료 Postgres 30일 뒤 만료(14일 유예) | https://render.com/docs/free |
| Supabase Free | 프로젝트당 500MB, 1주 미사용 시 일시 중지 | https://supabase.com/pricing |
| Neon Free | 프로젝트당 1GB, 5분 미사용 시 잠듦 | https://neon.com/pricing |
| GitHub Actions | 공개 저장소 표준 러너 무료 (우리 저장소는 공개, 2026-10-27 확인) | https://docs.github.com/en/billing/concepts/product-billing/github-actions |
| MoveNet 모델 파일·라이선스, Expo SDK 58의 Node 최소 버전, HTTPS 터널 무료 조건 | 공식 문서로 확인하지 않음 → `확인 필요` | — |

- 추가 확인(2026-10-27): [MoveNet 공식 예제](https://www.tensorflow.org/hub/tutorials/movenet)는 17개 키포인트와 얼굴 인덱스 0~4를 명시한다. 모델 파일의 라이선스는 다운로드할 배포본 기준으로 별도 확인한다.
- 추가 확인(2026-10-27): [Gemini 추가 약관](https://ai.google.dev/gemini-api/terms)의 연령 조건을 확인했으며, 제공사 결정 보류 사유로 반영했다.

## 최종 선택

- 선택한 안: A안 (React Native + Expo 개발 빌드 앱 + FastAPI)
- 프론트엔드: React Native + Expo (TypeScript), 개발 빌드 사용, Android 우선
- 백엔드: FastAPI + SQLAlchemy (Python)
- DB: PostgreSQL
- UI 도구: NativeWind (React Native용 Tailwind)
- 테스트 방식: 백엔드 pytest + 실제 PostgreSQL(Docker Compose), 앱 Jest + React Native Testing Library(화면), Jest(렙 판정 로직), CI는 GitHub Actions로 PR마다 실행
- 시연·배포 환경: 개발은 Expo 개발 빌드, 시연은 JS 번들과 모델 파일이 포함된 서명된 Android APK를 직접 설치. 정확한 시연 빌드 명령·서명 설정은 실제 빌드 후 기록(EAS 내부 배포는 예비). 백엔드 Render Free, DB Neon Free. 막히면 개발자 PC 백엔드 + HTTPS 터널. 스토어 등록은 하지 않음
- 카메라·자세 인식: react-native-vision-camera + react-native-fast-tflite(TFLite 자세 모델)로 시작. 3주차 첫 데모 전에 MediaPipe(커뮤니티 Expo 모듈 또는 Kotlin 네이티브 모듈)와 비교
- LLM: 제공사·모델 미정(기존 Gemini 안은 연령 조건 검토로 보류). 백엔드에서만 호출하며 구현 중에는 모의 응답으로 연결을 검증

### 영역별 결정

> 2026-10-27 작성본 기준. LLM·예산은 검토 보류이며, 새 검증 계획의 담당 배정은 팀 확인이 필요하다. 영역마다 고른 기술과 이유, 뺀 대안, 앞으로 검증할 것을 정리합니다.

| 영역 | 결정 | 선택 이유 | 포기한 대안과 이유 | 검증할 사항 |
| --- | --- | --- | --- | --- |
| 플랫폼 | Android 우선 (iOS는 개발 확인용) | 운동 중 카메라·화면을 앱으로 다룸. Android는 무료로 직접 설치 가능 | iOS 정식 배포: 연 $99, 무료 계정은 7일마다 재설치·Mac 필요 | 팀원 중 Android 폰이 있는지 |
| 앱 프레임워크 | React Native + Expo 개발 빌드 (TypeScript) | React·TS 경험 3명을 그대로 씀. React Native 공식 문서가 새 앱에 Expo를 권장 | React Native CLI: 네이티브 프로젝트를 직접 관리해야 함. Expo Go: 추가 네이티브 라이브러리를 못 씀 | 개발 빌드가 팀원 PC마다 만들어지는지 |
| UI 도구 | NativeWind | 손범수의 Tailwind 경험을 앱에서 그대로 씀, Expo 지원 | React Native 기본 `StyleSheet`: 설정은 없지만 Tailwind 경험을 못 씀. 설정이 막히면 이것으로 바꿈 | Expo SDK 58과 함께 설정되는지 |
| 카메라 | react-native-vision-camera (v5) | 프레임마다 자세 인식 모델에 넘길 수 있음 | Expo 기본 카메라: 프레임 처리 기능이 없음 (`확인 필요`) | v5 Frame Output이 대상 폰에서 끊김 없이 도는지 |
| 자세 인식 | react-native-fast-tflite + TFLite 자세 모델로 시작, 3주차 첫 데모 전에 MediaPipe와 비교 | TypeScript 쪽에서 대부분 처리 가능하고 VisionCamera v5 예제가 있음. 고객 요청대로 두 모델을 같은 기준으로 비교(피드백 15) | ML Kit: 베타, RN 플러그인이 옛 버전 기준. Teachable Machine: 분류형이라 가동범위 판정에 추가 작업 | 렙 정확도, 폰 속도, 촬영 각도, 확신도 계산, 모델 라이선스·얼굴 키포인트 |
| 리플레이 애니메이션 | react-native-reanimated | Expo SDK에 포함, 타격 수만큼 반복·스킵 구현에 충분 | 기본 Animated API: 가능하지만 복잡한 연출에 불리 | 30 COMBO가 30초 안에 끝나는지 |
| 백엔드 | FastAPI + SQLAlchemy (백엔드는 하나만) | 경험자 3명. 관절 통계·LLM 호출·출력 검사를 Python 하나에서 처리 | Spring Boot 단독: LLM·통계 코드가 늘어남. 함께 쓰기: 서버 2개 부담 | SQLAlchemy로 잠금·멱등 지급 테스트 통과. Python 3.11 이상 |
| DB | PostgreSQL | 잠금·유니크 제약으로 US-04·US-06 처리, JSON 저장 편리, 무료 관리형 있음 | MySQL: 무료 호스팅 미확인 | Neon 한도·잠자기 |
| LLM | 제공사·모델 미정, Gemini 도입 보류 | 연결 경험만으로 확정하지 않고 서비스 대상 연령과 입력 데이터의 이용 조건을 먼저 검증 | 유료 API도 예산 미정이므로 배제 확정하지 않음 | 연령 조건, 입력 데이터 정책, 비용·한도, 키 발급, 네트워크 |
| 테스트 | pytest + 실제 PostgreSQL(Docker Compose), Jest + React Native Testing Library | 동시성·잠금 테스트에는 실제 DB 필요. Jest는 React Native 기본·공식 권장 | SQLite 대체: 잠금 동작이 다름. 앱 E2E: 첫 데모 뒤 | 팀원 PC Docker 설치 권한 |
| CI | GitHub Actions (PR마다 테스트) | 이미 GitHub 사용, 공개 저장소라 무료 | — | — |
| 앱 빌드·설치 | 로컬 빌드 APK를 Android 폰에 직접 설치, EAS Build Free는 예비 | 무료이고 횟수 제한 없음 | 스토어 등록: 유료. EAS만 쓰기: 무료 15회 제한·대기 | 팀원 PC에 Android Studio 설치 가능한지 |
| 백엔드·DB 배포 | Render Free + Neon Free. 막히면 PC + HTTPS 터널 | 무료, HTTPS 주소라 앱의 HTTP 차단 문제가 없음. Neon은 쓰지 않아도 프로젝트가 멈추지 않음 | Render 무료 Postgres: 30일 만료. Supabase: 1주 미사용 시 중지. AWS 직접 운영: 운영·비용 부담 | 잠자기 후 첫 응답 지연 |
| Redis·메시지 큐·마이크로서비스 | 넣지 않음 | 하루 300건 규모. LLM 결과 재사용은 DB 테이블, 비동기 생성은 DB에 작업 상태를 기록하고 재시도·재시작 복구를 검증한 뒤 사용 | — | LLM 지연이 화면을 막으면 다시 검토 |

## 선택 이유 (팀 경험·기간·핵심 기능으로)
1. **앱 React Native + Expo:** 서비스의 출발점이 "폰 카메라 앞에서 운동하면 기기가 렙을 센다"(US-01)이고, 고객도 자세 인식 모델을 가장 중요하게 봤다(피드백 15·16). 앱은 카메라 프레임을 기기 안에서 바로 처리할 수 있고, 모바일 자세 인식 SDK가 Android·iOS를 정식 지원한다. React Native는 팀의 React·TypeScript 경험(3명)을 그대로 쓸 수 있고, 공식 문서가 권장하는 Expo로 빌드·설정 부담을 줄인다. 유료 계정 없이 시연하기 위해 Android를 우선한다.
2. **백엔드 FastAPI + SQLAlchemy:** FastAPI를 직접 써 본 사람이 3명(강준석·성민규·김지은)이라 백엔드 작업을 나누기 쉽다. 관절 각도 통계(L4 입력), LLM 호출(L1~L4), 출력 규칙 검사(숫자·스킬명 거르기)를 Python 하나에서 처리할 수 있고, 김지은이 FastAPI에서 Gemini를 연결해 본 경험이 있다. 백엔드를 하나만 두어 8주·5명 일정에서 인증·배포·테스트를 한 벌로 유지한다.
3. **DB·UI·테스트·배포·자세 인식·LLM:** 무료 범위를 우선 검토하면서 중복 지급·동시 취소를 실제 DB로 검증하고 Tailwind·pytest 경험을 활용한다. LLM 제공사는 별도 확인 후 선택한다. 영역별 이유는 [영역별 결정](#영역별-결정) 표에 있다.

## 선택하지 않은 안과 이유
- **B안 React Native CLI (Expo 없이) + Kotlin MediaPipe 모듈:** 네이티브 프로젝트를 직접 관리하고 Kotlin 모듈을 처음부터 만들어야 해서, Kotlin 경험자 1명에게 일이 몰림. MediaPipe는 A안 안에서 3주차 첫 데모 전 비교 대상으로 남김
- **Expo Go만 쓰기:** 카메라 프레임 처리·자세 인식 라이브러리를 쓸 수 없음
- **Flutter·네이티브 앱(Kotlin/Swift):** Dart·Swift를 새로 배워야 하고, 두 플랫폼을 따로 만들어야 함(네이티브)
- **Spring Boot 단독:** 트랜잭션 처리는 익숙하지만, 관절 통계·LLM 호출·출력 검사를 Java로 새로 작성해야 하고 김지은·손범수는 Java 경험이 적음
- **Spring Boot + FastAPI 함께 쓰기:** 자세 인식은 폰 안에서 하므로 서버에서 Python 모델을 돌릴 일이 없고, 서버가 2개면 인증·배포·CI·테스트가 두 벌이 됨
- **MySQL:** 기능상 문제는 없지만 무료 관리형 호스팅을 확인하지 못했고, 관절 좌표·스냅샷 저장에 PostgreSQL `jsonb`가 편함
- **iOS 정식 배포·스토어 등록:** 유료(Apple 연 $99, Google $25)라 하지 않음

## LLM 연결
> 우리 서비스에서 LLM이 맡는 일(초안·요약·분류·설명)을 어느 스택에서 호출하는지, 상태를 바꾸는 최종 결정은 어디서 하는지 한 줄로 씁니다.
- LLM(L1 기록 요약, L2 이상치 설명, L3 전투 서사, L4 자세 교정 코멘트)은 **FastAPI 백엔드에서만** 호출하고(앱에 키를 넣지 않음), 상태 전이는 **백엔드 규칙과 사람(확인자)만** 결정한다. 출력은 `ai_summary`·`ai_flags`·`ai_story`·`ai_form_tip`에 저장만 하고, 실패하면 기본 문구로 진행한다. 닉네임·길드명, 메모 속 개인정보, 관절 좌표 원본, 얼굴 정보, 보상 수치는 보내지 않는다 ([03 3-4](domain/03-rules-states-llm.md), [backlog.md](requirements/backlog.md) US-02·05·07). 제공사·모델은 미정이며 Gemini 후보는 연령 조건 검토로 보류한다. L4에는 허용된 관절 각도 요약 통계와 판정 사유를 보낼 수 있다. 이는 보상 수치·원본 좌표를 보내지 않는다는 원칙과 구분한다.

### 입력 데이터 계약과 재시도 계획

- L1~L4별 허용 필드를 분리한다. L3에는 카탈로그 스킬명·운동 종류·적 이름·약점 여부, L4에는 판정 기준·관절 각도 요약 통계·미인정 사유만 담는다. L1·L2는 필요한 기록 요약 필드를 확정한 뒤 연결한다. 원본 좌표·얼굴·식별 정보·자유 메모·보상 수치는 외부 LLM에 보내지 않는다. 통계라도 입력의 이용 조건 검토를 생략하지 않는다.
- 제출 재시도에는 같은 세션 ID를 사용하고 사용자·세션에 대한 유니크 제약으로 중복 접수를 막는 안을 검증한다. 응답을 잃으면 기존 제출 상태를 조회한다. 지급 멱등성은 별도로 유지한다.
- 앱의 좌표 형식·판정 규칙·모델 버전을 함께 기록한다. Python과 TypeScript가 같은 기준 데이터에서 같은 인정량을 내는지 테스트한다. 서버 재계산은 앱의 횟수 변조를 검사하지만 조작된 좌표 자체의 진위를 보장하지 않으므로 기존 무작위 동작 확인·검토 흐름도 유지한다.
- 백그라운드 작업은 실행 전 DB에 대상 제출건·작업 종류·시도 횟수·처리 상태를 저장하는 안으로 구현한다. 재시작 시 미완료 작업을 다시 처리하고, 이미 완료된 결과는 중복 적용하지 않는다. 취소된 제출건은 늦게 도착한 작업 결과로 상태를 되돌리지 않는다.
- LLM 시간 초과 시 기본 문구로 진행한다. DB 트랜잭션을 잡은 채 외부 API 응답을 기다리지 않고 결과 반영 시 현재 상태를 다시 검사한다. 호출 시간 제한·재시도 간격은 검증 후 확정한다.

### 핵심 기능과 기술의 연결

> **자세 인식 모델 ≠ LLM.** 렙을 세고 확신도를 내는 것은 폰 안의 자세 인식 모델과 판정 규칙이고, LLM은 정해진 결과를 글로 설명만 합니다 ([03 3-4](domain/03-rules-states-llm.md) 공통 원칙).

| 구성 요소 | 맡는 일 | 맡지 않는 일 |
| --- | --- | --- |
| 자세 인식 모델 (폰 안) | 카메라 프레임 → 관절 좌표 | 렙 판정, 승인, 글 생성 |
| 앱 (React Native) | 카메라 열기(VisionCamera), 프레임마다 모델 실행, 관절 각도로 렙 인정·미인정 즉시 표시, 얼굴 키포인트를 뺀 좌표·렙 타임스탬프 전송, 미리보기·리플레이·결과 카드 표시 | 보상 계산, 상태 변경, LLM 호출 |
| 백엔드 (FastAPI) | 인증, 시간대 중복·일일 상한 검사, 렙 수 재계산, 상태 전이, 보상 계산·스냅샷, 확신도 기준 자동 승인, 한 번만 지급, LLM 호출·출력 검사 | 영상 받기 (받지 않음) |
| DB (PostgreSQL) | 제출건·상태·스냅샷·지급 내역·상한 예약 저장, 유니크 제약·잠금으로 중복 방지 | — |
| LLM API (제공사 미정) | L1~L4 글만 생성 | 렙 수, 승인, 보상, 상태 |

| 기능 | 흐름과 기술 | 관련 스토리 |
| --- | --- | --- |
| 카메라·자세 인식 | 앱 카메라 권한 → VisionCamera Frame Output → fast-tflite로 자세 모델 실행 → 관절 각도 계산(TypeScript) → 가동범위 기준으로 렙 인정·미인정 표시. 영상은 저장·전송하지 않음 | US-01, R11·R12 |
| 제출과 상태 전이 | 세션이 끝나면 얼굴을 뺀 좌표 + 렙 타임스탬프를 HTTPS로 전송 → 백엔드가 시간대 중복·일일 상한을 한 트랜잭션에서 검사하고 상한 예약 → `SUBMITTED`. 상태는 "현재 상태가 X일 때만 갱신"하는 조건부 UPDATE로만 바꿈 | US-01, US-03, US-06 |
| 렙 수 일관성 검사 | 앱이 보낸 렙 수를 그대로 믿지 않고, 백엔드가 받은 관절 좌표로 같은 판정 규칙을 다시 계산함. 백엔드 결과를 인정량으로 쓰고, 앱 값이 더 크면 요청을 거부함 | US-01 |
| 한 번만 지급 | 지급마다 멱등 키(예: 제출건 ID) + 지급 내역 유니크 제약 → 같은 요청이면 저장된 결과를 돌려줌. 보상 반영과 `APPROVED → REWARDED`를 한 트랜잭션으로, 실패하면 전부 롤백 | US-04, R7, 피드백 17 |
| 취소·승인 동시 요청 | 같은 행에 조건부 UPDATE 또는 행 잠금 → 먼저 성공한 하나만 반영 | US-06 |
| LLM 입력·출력 검증과 장애 | 입력은 L1~L4마다 허용 필드만 담는 함수로 만듦. L3 출력은 숫자·다른 스킬명·아이템명 검사, 2번 실패 시 기본 문구. 실패·시간 초과·한도 초과 시 기본 문구 저장, `PREPARED` 진행은 막지 않음. 같은 입력 결과는 DB에 저장해 재사용 | US-02, US-05, US-07, R5 |
| 리플레이·결과 화면 | 백엔드가 `REWARDED` 건의 스냅샷과 `ai_story`·`ai_form_tip`을 내려줌 → 앱이 타격 수만큼 공격 애니메이션(reanimated, 최대 30초, 스킵) + 결과 카드. 수치는 결과 카드에만 | US-05 |

## 예상 어려움과 대응
| 어려움 | 대응 |
| --- | --- |
| React Native를 써 본 사람이 없음 | 3주차 첫 데모 전에 테크 리드가 Expo 개발 빌드 뼈대를 먼저 만들어 전원이 자기 폰에 설치해 봄. 화면은 React 경험자 3명이 나눠 맡음 |
| 자세 인식 모델을 써 본 사람이 없고, React Native 공식 패키지가 없음 | 3주차 첫 데모 전에 fast-tflite 경로와 MediaPipe 경로를 비교. 모델별 어댑터로 좌표를 공통 형식에 맞추고, 모델 교체 시 판정 회귀 테스트를 다시 실행함. 커뮤니티 패키지가 맞지 않으면 성민규(Kotlin)가 Android 네이티브 모듈로 MediaPipe 연결 |
| Expo Go로는 실행이 안 됨 | 처음부터 개발 빌드로 시작. 빌드는 로컬, 막히면 EAS Build Free |
| 개발 중 앱이 PC 서버(HTTP)에 접속하지 못함 | Android 9 이상은 HTTP를 기본으로 막으므로 HTTPS 터널을 쓰거나, 개발 빌드에만 HTTP 예외 설정 |
| iOS 시연이 어려움 (유료 계정 없음, 7일 만료, Mac 필요) | 시연은 Android 폰으로 함. iOS는 Mac·iPhone이 있는 팀원이 개발 확인용으로만 설치 |
| 같은 지급 요청이 두 번 와도 한 번만 반영 (US-04) | 멱등 키 + 유니크 제약 + 한 트랜잭션. 중복 요청 테스트를 먼저 작성 |
| 취소와 승인이 동시에 옴 (US-06) | 조건부 UPDATE 또는 행 잠금. 동시 요청 테스트 |
| 로그인 토큰 처리 (여러 명이 어려웠다고 적음) | 방식을 하나로 정하고 경험자가 먼저 만든 뒤 공유. 앱에서는 토큰을 안전한 저장소에 보관 (저장 방식 `확인 필요`) |
| LLM 장애·한도 초과 | 기본 문구, 같은 입력 결과 재사용 |
| 무료 백엔드가 잠들어 시연 중 첫 응답이 늦음 | 시연 전에 미리 깨우기, 또는 PC + HTTPS 터널 |
| 서버에 얼굴·영상이 들어오면 안 됨 (R11) | 앱에서 얼굴 키포인트를 빼고, 백엔드에서도 형식 검사로 거부 |

### 확정 전 검증 계획

> 측정 전이라 성능 숫자(허용 오차·프레임 수)는 넣지 않았습니다. 모델 비교 시작 전에 테스트 담당이 정해 이 표에 적습니다.

| 검증 항목 | 통과 기준 | 실패 시 대안 |
| --- | --- | --- |
| 개발 빌드 설치 (팀원 PC에서 빌드, 팀원 Android 폰에 설치) | 전원이 자기 PC에서 빌드하고 폰에서 앱이 열림 | 빌드되는 PC 한 대에서 APK를 만들어 나눠 설치, 또는 EAS Build Free |
| 카메라 프레임 처리 (VisionCamera Frame Output) | 대상 폰에서 카메라 권한 요청이 뜨고 프레임이 끊김 없이 들어옴 | 해상도·프레임 수 낮추기 |
| 자세 인식 속도·정확도 (fast-tflite 모델과 MediaPipe를 같은 조건으로 비교, 결과를 `docs/decisions/`에 기록) | 렙 표시가 끊기지 않고 사람이 센 렙 수와 맞음 (허용 오차·프레임 수는 테스트 담당이 모델 비교 전에 정함) | 가벼운 모델로 바꾸기, 촬영 조건 좁히기, 다른 경로 |
| 확신도 계산 | 정상 스쿼트 대부분이 기준(90%, 미확정) 이상 | 기준값 조정은 고객·팀 결정 |
| 상태 전이 (pytest) | backlog 인수 조건의 전이 테스트 모두 통과 | — |
| 중복 보상 방지 (같은 지급 요청 순차·동시 2번) | 한 번만 늘고, 두 번째 응답이 첫 결과와 같음 | 잠금 방식 변경 (조건부 UPDATE ↔ `FOR UPDATE`) |
| 취소·승인 동시 요청 | 하나만 반영, 취소가 먼저면 지급 0건 | 위와 같음 |
| LLM 장애·한도 (실패·시간 초과·한도 초과로 바꿔 테스트) | `PREPARED`까지 가고 기본 문구 저장, 수치 변화 없음 | — |
| LLM 출력 검사 (숫자·다른 스킬명이 든 출력) | 저장하지 않고 다시 생성, 2번 실패 시 기본 문구 | 검사 규칙 보강 |
| 배포·비용 (Render·Neon에 빈 백엔드를 올리고 폰 앱에서 호출) | 앱에서 HTTPS로 응답을 받음, 비용 0원 | PC + HTTPS 터널로 시연 |

### 추가 검증 항목

| 검증 항목 | 통과 기준 | 실패 시 대응 |
| --- | --- | --- |
| 패키지 호환성 | Expo·RN·VisionCamera·fast-tflite·worklets·NativeWind를 함께 설치한 잠금 파일과 빌드 로그 기록, 실제 기기에서 카메라·모델 추론 성공 | 공식 호환 조합으로 조정, UI 설정이 막히면 StyleSheet 사용 |
| 단독 실행 APK | Metro 종료·앱 완전 종료 후 재실행해 원격 API로 핵심 흐름 완료 | 번들·모델 포함 여부, 서명, API 주소 수정 |
| 모델 어댑터·판정 일치 | 관절 이름·회전·반전·얼굴 제거 검증, 동일 기준 데이터의 앱/서버 판정 일치 | 변환·규칙 버전 수정 후 재검증 |
| 권한·앱 중단 | 카메라 권한 거절 시 안내, 백그라운드에서 촬영·추론 중단, 복귀 시 세션 상태 안내. 불완전 기록을 정상 완료로 자동 제출하지 않음 | 세션 재시작·종료 정책을 팀과 확정 |
| 제출 응답 유실 | 같은 세션을 재전송해도 제출건·상한 예약·지급이 중복 생성되지 않음 | 세션 식별자·유니크 제약·상태 조회 수정 |
| 서버 재시작 | LLM 처리 중 재시작해도 작업을 복구하거나 기본 문구로 완료하며, 중복 지급·취소 상태 복원 없음 | DB 작업 상태·복구 절차 보완 |
| 인증·키 관리 | 토큰 만료·로그아웃 처리 확인, 안전한 토큰 저장 방식 결정, APK·로그·저장소에 서버 비밀키 없음 | 저장 방식·환경 변수 분리 수정 |

## 확인할 것
| 확인할 내용 | 담당 | 언제 |
| --- | --- | --- |
| 괄호·`?`로 적힌 경험(김지은 React·TS, 손범수 Node.js·Express·Spring Boot)과 이시은의 "앱 화면" 기술이 무엇인지 | 각 본인 | 다음 팀 회의 |
| 팀원별 OS·사양, Android Studio·Docker·Python(3.11 이상)·Node 설치 권한 (Expo SDK 58의 Node 최소 버전 `확인 필요`) | 각 본인 | 뼈대 세우기 전 |
| 팀원별 Android 폰 보유 여부·기종, iPhone·Mac 보유 여부 | 각 본인 | 다음 팀 회의 |
| 수업 외 개인별 가능 시간 | 각 본인 | 다음 팀 회의 |
| Expo 개발 빌드 뼈대 만들기와 전원 설치 확인 | 성민규 (테크 리드) | 뼈대 세우기 |
| LLM 제공사·모델의 연령 조건·입력 정책 검토 후 키 발급, 학교 네트워크 접근과 호출 한도 확인 | 성민규 (테크 리드) | 뼈대 세우기 전 |
| Render·Neon에 빈 백엔드를 올려 폰 앱에서 HTTPS로 호출 | 성민규 (테크 리드) | 뼈대 세우기 전 |
| 시연 폰 카메라·프레임 처리 테스트, 촬영 공간 | 이시은 | 3주차 첫 데모 전 |
| 자세 인식 비교(fast-tflite 모델·MediaPipe) 기준과 통과 기준 숫자, 확신도 계산 방법, 모델 라이선스·얼굴 키포인트 | 강준석 (테스트 담당), 김지은 | 첫 데모 전 (모델 비교 전 기준 작성·비교 후 결과 기록) |
| 개인정보 처리방침에 자세 인식 라이브러리의 사용 지표 전송(MediaPipe·ML Kit를 쓰면), 선택한 LLM 제공사의 입력 데이터 이용 조건 반영 (고지만으로 부적합한 이용 조건이 해결되는 것은 아님) | 김지은 (리더) | 첫 데모 전 |

다음 담당·기한은 추가 검증을 위한 제안이며 다음 팀 회의에서 확정한다. 이전의 “1주차” 계획은 완료 근거가 없어 3주차 첫 데모 전 검증으로 정정했다.

| 확인할 내용 | 담당(제안) | 언제 |
| --- | --- | --- |
| 대상 연령과 LLM 제공사·모델 약관, 입력 데이터 정책 적합성 | 김지은·성민규 | 실제 API 연결 및 외부 사용자 시연 전 |
| 유료 사용 여부·월 예산, 남은 수업일·개인별 가능 시간 | 전원, 김지은 정리 | 다음 팀 회의 |
| Expo 및 네이티브 패키지 호환 버전·Android 최소 버전·Node/JDK/SDK 버전 고정 | 성민규 | 앱 뼈대 확정 전 |
| 모델 어댑터·얼굴 제거·앱/서버 판정 기준 데이터 | 강준석·김지은 | 모델 비교 시작 전 기준 작성, 첫 데모 전 검증 |
| 단독 실행 APK·서명키 관리·카메라 권한·앱 중단·토큰 저장 | 성민규·손범수·이시은 | 첫 데모 리허설 전 |
| 제출 재시도·백그라운드 작업 복구·취소 경합 테스트 | 강준석·백엔드 구현 담당 | 첫 데모 전 기본 경로, 취소 구현 PR에서 경합 검증 |

### 도입을 미룬 기술과 다시 검토할 조건
| 기술 | 미룬 이유 | 다시 검토할 조건 |
| --- | --- | --- |
| iOS 정식 배포·스토어 등록 | 유료 계정 필요 | 예산이 생기거나 고객이 스토어 배포를 요구할 때 |
| ML Kit Pose Detection | 베타, RN 플러그인이 옛 버전 기준 | fast-tflite·MediaPipe 경로가 모두 막힐 때 |
| 앱 E2E 테스트 | 첫 데모 전 시간 부족 | 첫 데모 뒤 회귀 테스트가 필요할 때 |
| Spring Boot + FastAPI 함께 쓰기 | 서버 2개 운영 부담 | 서버에서 Python 모델 추론이 꼭 필요해질 때 |
| Redis | 하루 300건 규모라 DB로 충분 | LLM 캐시·요청 제한을 DB로 감당할 수 없을 때 |
| 메시지 큐 | 우선 DB에 처리 상태를 기록하고 재시도·복구하는 구조로 검증 | 작업 유실 방지·처리량 요구를 이 구조로 만족하지 못할 때 |

### 문서 간 충돌과 이 문서의 판단

이번 보완은 STACK.md만 수정했다. 다른 문서의 LLM 제공사·수치 전송 범위·예산 관련 문구는 팀 결정 뒤 함께 정합성을 확인해야 한다.
| 충돌 | 내용 | 판단 |
| --- | --- | --- |
| stack-inputs ↔ 팀 결정 | [stack-inputs.md](decisions/stack-inputs.md)는 화면을 "모바일 우선 반응형 웹"으로 제안했음 | 2026-10-27 팀 결정(React Native 앱)을 따르고, stack-inputs의 화면 행에도 결정을 적음 |
| 03 3-2 ↔ user-flows·backlog | [03](domain/03-rules-states-llm.md) 3-2가 미팅 전 기준(타 길드 검토)이라 `PREPARED → APPROVED`가 없었음 | 2026-10-27 03 3-2·R4·3-3·3-4를 user-flows·backlog 기준으로 고침 (AI 자동 승인, 지인·길드장 확인, L4 추가) |
| 제안서 Ⅰ-3 ↔ mvp-scope | 제안서는 회수 경로를 MVP에 포함, mvp-scope는 제외 | 더 최신인 [mvp-scope.md](decisions/mvp-scope.md)를 따름. 스택 판단에는 영향 없음 |

## 의견이 갈렸다면
> 갈린 의견과, 어떤 정보가 부족했는지를 씁니다. 중요한 불확실성이 남았다면 **임시 선택과 확인 조건**을 남깁니다.
- **웹 → React Native 앱:** 처음 비교에서는 웹을 검토했으나, 팀이 React Native 앱으로 정함. 부족했던 정보는 React Native에서 앱 안 자세 인식을 연결하는 데 실제로 얼마나 걸리는지(공식 RN 패키지가 없음)
  - 임시 선택: Expo 개발 빌드 + VisionCamera + fast-tflite로 시작하고, Android 폰으로 시연한다
  - 확인 조건: 3주차 첫 데모 전에 대상 Android 폰에서 카메라 → 자세 모델 → 렙 표시가 돌아가는지 확인. 3주차 첫 데모 일정에 맞추지 못할 것 같으면 다음 팀 회의에서 범위(첫 데모 화면 수)나 방식을 다시 논의
- **백엔드·DB:** 기존 선택 유지. **LLM·예산:** 대상 연령과 약관, 비용 상한 확인 후 팀에서 확정. 그 전에는 모의 응답으로 개발하되 이를 실제 LLM 연동 완료로 기록하지 않음
