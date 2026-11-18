# 서버 사이를 여행하는 NPC

Liora가 `traveler-a`에서 포탈까지 걸어가 `traveler-b`로 이동하고 다시 돌아오는 시연입니다. 두 서버는 서로 다른 TCP 주소와 SQLite 데이터베이스를 사용합니다. 브라우저가 모두 닫혀 있어도 서버가 이동을 계속 계산합니다. 현재 행동은 정해진 경로를 따르는 방식이며, 자율 AI·길 찾기·일반 충돌 시스템은 이번 범위에 포함하지 않습니다.

## 같은 PC에서 시작

Python 3.10 이상과 `npc-travel-v1`을 지원하도록 새로 빌드한 형제 폴더 `../link`의 LINK Browser가 필요합니다. 별도 Python 패키지는 없습니다.

1. `LINK_GAME_NPC_START.cmd`를 실행합니다. 두 서버가 시작되며 이 창을 유지합니다.
2. `LINK_GAME_NPC_PLAY.cmd`를 실행합니다. A 정원이 열립니다.
3. Liora가 걷다가 포탈 안으로 들어가면 A에서 사라집니다. 직접 포탈을 지나 B 정원에 가면 같은 ID의 Liora를 만날 수 있습니다.
4. NPC가 다른 곳에 있으면 잠시 기다리거나 반대편 공간으로 이동하세요. 명패의 `Journeys`와 `Epoch`가 이동할 때마다 올라갑니다.
5. PC VR은 `LINK_GAME_NPC_PLAY.cmd --vr`로 실행합니다. 서버 동작과 NPC 표현은 동일한 규격을 사용합니다.
6. 서버 창에서 `Ctrl+C`로 종료합니다. 다시 실행하면 저장된 위치와 인계 상태에서 이어집니다.

| 공간 | 접속 주소 | 저장 파일 |
| --- | --- | --- |
| A: Dawn Court | `link://127.0.0.1:8010/traveler-a` | `data/npc-a.sqlite3` |
| B: Azure Court | `link://127.0.0.1:8011/traveler-b` | `data/npc-b.sqlite3` |

전용 실행기는 `data/npc-peer.key`가 없을 때 무작위 공유 키를 한 번 만듭니다. `data/`는 Git과 공개 월드 디렉터리에서 제외됩니다. 기존 RPG의 `characters.sqlite3`와 플레이어 토큰은 사용하지 않습니다. 8010·8011 포트가 사용 중이면 기존 프로그램을 종료하지 않고 오류를 표시합니다. 기본 시연은 loopback으로만 수신하므로 같은 PC에서 접속합니다.

A·B 창을 동시에 두 개 열면 서로 다른 세계에서 같은 여행을 관찰할 수도 있습니다. NPC 이동 때문에 사용자의 카메라나 머리 방향이 바뀌지 않습니다. 시연 월드는 한 개의 `liora` 표현 슬롯을 제공하고, 통신 규격은 최대 16개 NPC를 받을 수 있습니다.

## 서로 다른 PC에서 실행

서버를 실행할 두 PC의 실제 IPv4 주소를 정합니다. `127.0.0.1`은 각 PC 자신만 가리키므로 다른 컴퓨터에서 사용할 주소로 바꿔야 합니다. 아래 예시 주소는 실제 환경에 맞게 교체하세요.

```powershell
# link-game 폴더. 생성기는 두 월드의 포탈 주소와 두 서버 설정을 함께 갱신합니다.
python .\tools\generate_npc_journey.py --host-a 192.168.0.10 --port-a 8010 --host-b 192.168.0.11 --port-b 8011
```

갱신된 월드와 `configs/npc-traveler-a.json`, `configs/npc-traveler-b.json`을 각 서버에 배치합니다. 두 서버에 동일한 64자리 hex 공유 키를 별도 파일로 준비하고 안전하게 전달하세요. 키를 월드나 Git에 넣지 않습니다. 키가 바뀌면 두 서버 모두 같은 키로 재시작해야 합니다.

```powershell
# 최초 한 번 키 생성. 다른 서버에도 같은 파일을 별도 전달합니다.
python -c "from pathlib import Path; import secrets; p=Path('data'); p.mkdir(exist_ok=True); f=p/'npc-peer.key'; f.open('x',encoding='ascii').write(secrets.token_hex(32)+'\n')"

# PC A
python .\server\npc_server.py --config .\configs\npc-traveler-a.json --database .\data\npc-a.sqlite3 --peer-key-file .\data\npc-peer.key --host 0.0.0.0

# PC B
python .\server\npc_server.py --config .\configs\npc-traveler-b.json --database .\data\npc-b.sqlite3 --peer-key-file .\data\npc-peer.key --host 0.0.0.0
```

두 서버 사이의 해당 TCP 포트가 양방향으로 도달 가능해야 하며, 브라우저도 각 주소에 접속할 수 있어야 합니다. 주소를 바꾼 경우 기존 NPC DB는 원래 authority에 묶여 있으므로 다른 DB 경로를 지정하여 별도 시연을 시작합니다. 기존 DB를 삭제하거나 수정해 강제로 바꾸지 마세요. 기본 `LINK_GAME_NPC_START.cmd`는 loopback 설정 전용이며 원격 설정에서는 위 명령을 각 PC에서 실행합니다. 원격 브라우저는 실제 주소를 주소창에 입력합니다.

## 무엇을 이동시키는가

전송되는 것은 `id`, `kind`, `name`, 위치·회전, 애니메이션 이름, 소유 세대 `epoch`, 이동 횟수 `journey`입니다. 목적지 서버는 자신의 진입 위치와 경로를 적용합니다. 각 공간의 Element·Script·Style은 `kind`에 맞는 로컬 GLB와 애니메이션으로 NPC를 표시합니다. 외부 Script나 파일 경로를 실행하지 않습니다.

현재 참조 서버는 `liora`, `Idle`·`Walk`, ID 최대 64자, 이름 최대 48 UTF-8 바이트를 지원하며 `journey = epoch - 1`을 사용합니다. 이는 브라우저 관찰 프로필보다 좁은 시연 서비스 정책입니다. NPC의 임의 메모리·소지품·대화 모델·추론 실행 상태를 이동시키는 범용 에이전트 포맷은 아직 아닙니다.

## 인계와 복구

출발 서버는 NPC를 `outgoing`으로 SQLite에 먼저 기록하여 이동을 멈춘 뒤 인계합니다. 목적지는 허용된 peer와 HMAC 서명·목적지·진입 위치·ID·세대를 검사하고 NPC와 중복 수신 영수증을 함께 저장한 뒤 ACK합니다. 출발 서버는 ACK를 받은 뒤 인계를 완료합니다.

ACK가 유실되어도 같은 transfer ID와 상태를 재전송하며 목적지에서 다시 생성하지 않습니다. NPC가 이미 왕복한 뒤 도착한 오래된 ACK는 새로운 NPC 상태를 지우지 않습니다. 응답이 없다는 이유로 출발 쪽에서 NPC를 다시 움직이지 않습니다. 따라서 단절 중에는 잠시 보이지 않거나 인계를 기다릴 수 있습니다. 모든 화면에서 동시에 사라지고 나타나는 원자적 화면 갱신을 보장하는 규격은 아닙니다.

초기 NPC는 A에서만 생성합니다. 같은 ID를 B에도 seed로 추가하거나 활성 DB를 다른 authority에 복제하여 동시에 실행하면 단일 소유 규칙을 지킬 수 없습니다. 각 authority에는 한 개의 운영 인스턴스와 고유 DB를 사용하세요.

두 서버와 키·설정·DB를 함께 보관합니다. **한쪽 DB만 되돌리거나 삭제하면** 반대편에 남은 소유 세대·영수증과 맞지 않아 인계가 거부될 수 있습니다. 초기화가 필요하면 두 서버를 중지하고 기존 파일을 보관한 뒤 양쪽 모두 새 DB 경로로 별도 시연을 시작하세요. 기존 DB 파일을 실행 중에 복사하기보다는 SQLite backup API 또는 정상 종료 후 복사합니다. 완료 영수증은 재시도 안전성을 위해 남습니다. 미해결 outbox는 최대 128개, 영수증은 최대 65,536개입니다. 영수증 상한 뒤에도 기존 동일 인계의 재시도에는 ACK하지만 새 인계는 거부합니다.

HMAC과 허용 peer 목록은 협력 서버 사이의 위조를 검사하는 장치입니다. 평문 LINK/TCP를 암호화하지 않으며 관찰 세션도 공개 인증 체계를 갖추지 않았습니다. 이번 버전은 신뢰할 수 있는 로컬/LAN 시연용입니다. 공개 인터넷 연합에는 TLS, 서버별 자격 증명과 폐기, 운영·복구 정책을 추가해야 합니다.

## 검증

`python -m unittest discover -s tests`로 기존 RPG와 신규 NPC 테스트를 함께 실행합니다. 테스트는 임시 DB를 사용합니다. 브라우저의 `link_npc_travel_transport`는 잘못된 메시지·목록·재생·취소와 읽기 전용 세션을 검사합니다.

두 서버가 실행 중일 때 실제 Browser 검사도 가능합니다.

```powershell
..\link\build\native\Release\LINK.exe --open link://127.0.0.1:8010/traveler-a --npc-smoke .\data\npc-smoke.json
```

이 검사는 NPC가 보이는 A → 사라진 A → 같은 ID가 도착한 B → 다시 돌아온 A를 순서대로 캡처하고, 소유 세대·이동 횟수 증가, 사용자 카메라 독립성, Home에서 자원 해제를 확인한 뒤 종료합니다. 신체 움직임·헤드셋 성능·멀미를 검증하는 실기기 시험과는 별도입니다.

기존 저장 파일 없이 전체 화면 검증을 재현하려면 아래 도구를 사용합니다. 임의 포트의 독립 서버 프로세스 두 개·임시 DB·임시 키·임시 프로필을 사용하고 종료 시 정리합니다. 보고서와 화면만 지정한 출력 폴더에 남깁니다.

```powershell
python .\tools\verify_npc_journey.py --probe ..\link\build\native\Release\link_npc_travel_probe.exe --output .\data\npc-qa
```
