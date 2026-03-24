# AIVideoStudio (AVS) — 개발 로드맵 & TODO
# 업데이트: 2026-03-24 (v0.5.20)

## ═══════════════════════════════════════
## Phase 0: 기반 인프라 ✅ 완료
## ═══════════════════════════════════════

### 0-1. 환경 & 프로젝트 세팅
- [x] Python 3.12 + uv 설치 및 검증
- [x] pyproject.toml 작성 및 모든 의존성 설치 확인
- [x] FFmpeg 8.1 설치 및 PATH 등록
- [x] GPU 가속 확인 — NVIDIA RTX 4070, Driver 595.79, CUDA 13.2, NVENC OK
- [x] Git 리포지토리 초기화 + .gitignore
- [x] GitHub Public: https://github.com/hoonoh57/aivideostudio
- [ ] pre-commit 설정

## ═══════════════════════════════════════
## Phase 1: 코어 엔진 ✅ 완료
## ═══════════════════════════════════════

- [x] Config / 유틸리티 (config_manager.py, constants.py)
- [x] .avs 프로젝트 포맷 (JSON 기반 저장/로드)
- [x] 기본 타임라인 데이터 모델 (Track, Clip, Gap)
- [x] 키프레임 엔진 스켈레톤
- [x] Undo / Redo (QUndoStack)
- [x] 재생 엔진 (playback_engine.py)
- [x] 기본 FFmpeg 엔진

## ═══════════════════════════════════════
## Phase 2: GUI 프레임워크 ✅ 완료
## ═══════════════════════════════════════

- [x] 메인 윈도우 레이아웃 (main_window.py)
- [x] 타임라인 UI (timeline_panel.py, TimelineCanvas)
- [x] 프리뷰 패널 (preview_panel.py)
- [x] 자막 시스템 (subtitle_panel.py, subtitle_engine.py)
- [x] Export 패널 기본 기능

## ═══════════════════════════════════════
## Phase 3: Export 시스템 ✅ v0.5.17 완료
## ═══════════════════════════════════════

- [x] In/Out Zone Bar (24px, I/O 키, 드래그 핸들)
- [x] 멀티트랙 비디오 병합 (모든 활성 비디오 트랙 순차 export)
- [x] Styled ASS 자막 생성 (프리뷰 스타일 → ASS 변환)
- [x] ASS/SRT 이중 자막 번인 지원
- [x] NVENC 자동 감지 + CPU fallback
- [x] 세그먼트 검증 (zero-duration 스킵, 실패 시 continue)
- [x] 동적 자막 폰트 크기 (해상도 기반)
- [x] concat.txt 경로 수정, _make_black CPU 전용
- [x] GPU 드라이버 업데이트 (566.36 → 595.79)

## ═══════════════════════════════════════
## Phase 3.5: PIP & 자막 스타일 관리 ✅ v0.5.20 완료
## ═══════════════════════════════════════

### PIP (Picture-in-Picture)
- [x] PIP 로직을 트랙 번호 기반 → clip_data["pip"] 속성 기반으로 재설계
- [x] playback_engine.py: get_pip_video_layers() clip_data["pip"] 기반 수집
- [x] playback_engine.py: query() 내 PIP 클립 base video 제외 (elif 분기)
- [x] export_panel.py: PIP overlay FFmpeg 합성 (위치/크기/불투명도)
- [x] timeline_panel.py: 어떤 트랙이든 PIP 설정 가능 (우클릭 메뉴)
- [x] Export 최종 파일 PIP 오버레이 정상 출력 확인

### 자막 Export 효과
- [x] Export ASS에 typewriter(__TYPEWRITER__) → \k 태그 변환
- [x] 프리뷰와 동일한 타이핑 효과가 Export 결과물에도 적용

### 자막 스타일 관리
- [x] "Save as Default" — 현재 스타일을 default_subtitle_style.json에 저장
- [x] "Reset ALL to Default" — 모든 자막 클립 기본값 초기화 (확인 대화상자)
- [x] Lock(🔒) 체크박스 — 잠금 클립은 Reset ALL에서 보호
- [x] 잠금 상태 타임라인 표식 (클립 우상단 🔒 아이콘)
- [x] style_locked 프로젝트 저장/복원 (직렬화 포함)
- [x] 신규 자막 클립 생성 시 저장된 기본값 자동 적용
- [x] 불필요한 버튼 제거 (Reset to Default, Apply Style to All, 🎨 뱃지)

### 프로젝트 저장 개선
- [x] subtitle_style 직렬화 (_serialize_project)
- [x] pip 설정 직렬화
- [x] style_locked 직렬화
- [x] 프로젝트 열기 시 모든 속성 복원

## ═══════════════════════════════════════
## Phase 4: 현재 알려진 이슈
## ═══════════════════════════════════════

### 버그/경고
- [ ] Zone Bar 타임라인에 표시되지 않음 (paintEvent 조사 필요)
- [ ] mpv "No video or audio streams" / mp3 파싱 에러 (콘솔 로그)
- [ ] Qt "QWidgetWindow must be a top level window" 경고 반복
- [ ] 자막 기본 위치가 화면 중앙 (하단 정렬 \an2 기본값 필요)
- [ ] 프리뷰 패널 PIP 오버레이 미구현 (Export만 동작)

### 코드 품질
- [ ] QFont setPointSize 경고 제거 (preview_panel.py, subtitle_panel.py)
- [ ] 진단 스크립트 추가 정리 (tools/ 이동 완료 후 검증)
- [ ] pre-commit 설정

## ═══════════════════════════════════════
## Phase 5: 다음 개발 단계 (우선순위순)
## ═══════════════════════════════════════

### 즉시 (1-2h)
- [ ] 자막 기본 정렬 \an2 (하단 중앙) 수정
- [ ] Zone Bar 표시 문제 진단 및 수정
- [ ] 프리뷰 PIP 오버레이 (Method A: 2nd mpv instance)

### 단기 (3-5h 각)
- [ ] 기본 오디오 편집 (클립 게인, 페이드 인/아웃, 파형 표시)
- [ ] 클립 복사/붙여넣기 + 다중 선택 (Ctrl+C/V, Shift/Ctrl 클릭)
- [ ] 이펙트 & 트랜지션 기초 (crossfade, fade-to-black, FFmpeg xfade)

### 중기
- [ ] 프록시 / 렌더 엔진
- [ ] 트랙 높이 컨트롤
- [ ] 오디오 파형 오버레이
- [ ] 이펙트 브라우저
- [ ] 자동 저장

### 장기 (AI 기능)
- [ ] 배경 제거
- [ ] 업스케일링
- [ ] 장면 감지
- [ ] 객체 추적
- [ ] 색보정 도구
- [ ] 모션 그래픽

### 배포
- [ ] PyInstaller 빌드
- [ ] FFmpeg 번들링
- [ ] 인스톨러
- [ ] 문서화

## ═══════════════════════════════════════
## 버전 히스토리
## ═══════════════════════════════════════

| 버전   | 커밋     | 주요 변경                                              |
|--------|----------|-------------------------------------------------------|
| v0.5.17| -        | Export 시스템 완성, Zone Bar, NVENC, 자막 번인          |
| v0.5.18| da07c6d  | PIP clip-attribute 기반, typewriter export, 프로젝트 저장 |
| v0.5.19| 5a32ade  | 자막 스타일 관리 (Save Default, Reset ALL, Lock)       |
| v0.5.20| -        | style_locked 직렬화/복원, 잠금 상태 영속화              |
