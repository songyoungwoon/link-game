# Stone Sanctum · The Sunlit Archive

Stone Sanctum은 LINK의 사실적인 재질·환경광·그림자를 확인하기 위한 작은 석조 성소입니다. 원본으로 만든 아케이드, 조각 기둥, 두꺼운 벽, 겹쳐진 문틀, 부서진 천장, 제단과 잔해에 **실제 표면에서 제작된 Poly Haven PBR 재질**을 입혔습니다. 모델·색 텍스처·노멀·표면 거칠기·AO·HDR 환경광을 함께 다루는 기준 공간입니다.

## 원본 제작물과 외부 재질

기둥·아치·벽돌·조각·바닥·잔해·배경 암석 메시와 세계 배치는 `tools/generate_stone_sanctum.py`에서 독자적으로 생성합니다. 기존 게임의 맵이나 캐릭터 모델은 사용하지 않습니다. 생성기는 같은 폴더의 기존 원본 메시 도구 `generate_moon_garden.py`를 불러오며, Python 표준 라이브러리만 필요합니다.

| 파일 / 소재 | 제작자 | 라이선스와 공식 출처 |
| --- | --- | --- |
| 건축물·지면·잔해 메시, 생성기, LINK 문서 | Song Youngwoon / LINK 프로젝트 | [Apache-2.0](../LICENSE) |
| Sandstone Blocks 04 | Rob Tuytel | [Poly Haven 자산](https://polyhaven.com/a/sandstone_blocks_04), CC0-1.0 |
| Sandstone Cracks | Rob Tuytel | [Poly Haven 자산](https://polyhaven.com/a/sandstone_cracks), CC0-1.0 |
| Stone Floor | Dimitrios Savva | [Poly Haven 자산](https://polyhaven.com/a/stone_floor), CC0-1.0 |
| Quarry 01 HDRI | Sergej Majboroda | [Poly Haven 자산](https://polyhaven.com/a/quarry_01), CC0-1.0 |

외부 파일의 작성자·공식 다운로드 URL·크기·MD5·SHA-256은 `worlds/stone-sanctum/sources/polyhaven-materials.json`과 `lighting/SOURCE.json`에 기록했습니다. 재질 원본은 `sources/`에, HDR 원본은 `lighting/`에 포함되어 clone 후 네트워크 다운로드 없이 재생성할 수 있습니다. 생성된 GLB에 포함된 재질도 해당 원본의 CC0 조건을 따릅니다. 원본 건축물 메시와 생성기는 프로젝트의 Apache-2.0 조건을 따릅니다.

Poly Haven은 재질과 HDR 자산을 [CC0](https://polyhaven.com/license)로 제공합니다. 홈페이지의 로고·자산 예시 렌더·웹페이지 본문을 이 세계에 복제하지 않았습니다. 실제 자산 파일만 공식 API에서 받았으며, 파일을 이 저장소에 포함할 수 있는 조건을 확인했습니다.

## 자산 구조와 재생성

```text
worlds/stone-sanctum/
  world.link
  scene.element
  appearance.style
  asset-report.json
  models/
    sanctuary.glb
    paving.glb
    rubble.glb
  lighting/
    quarry_01_1k.hdr
    SOURCE.json
  sources/
    polyhaven-materials.json
    CC0-NOTICE.txt
    ... 원본 PBR 재질 맵 9개
```

`link-game` 디렉터리에서 실행합니다.

```powershell
python tools/generate_stone_sanctum.py
```

생성기는 내려받기·패키지 설치 없이 원본 파일의 SHA-256을 먼저 확인합니다. 고정된 난수 시드로 3개 GLB와 세계 문서, 자산 보고서를 생성합니다. `sources/`와 `lighting/`의 원본 파일을 덮어쓰거나 기존 RPG의 세계·저장 데이터를 사용하지 않습니다. 세계 배치나 재질을 지속적으로 바꾸려면 생성기 소스를 수정하세요. 직접 편집한 산출물은 다음 생성 때 교체됩니다.

| 모델 | 정점 | 삼각형 | 재질 배치 | 내장 이미지 | 파일 크기 |
| --- | ---: | ---: | ---: | ---: | ---: |
| sanctuary.glb | 65,217 | 46,252 | 5 | 6 | 8,988,128B |
| paving.glb | 11,136 | 5,104 | 1 | 3 | 7,775,728B |
| rubble.glb | 10,614 | 13,616 | 2 | 6 | 6,168,072B |
| 합계 | 86,967 | 64,972 | 8 | 15 | 22,931,928B |

모델은 각각 별도의 자체 포함 GLB이며 외부 URI를 참조하지 않습니다. 각 파일은 65,536 정점·삼각형, 16 MiB 파일, 8개 내장 이미지, 8 MiB 압축 이미지 예산 안에 있습니다. 같은 재질이 건축물과 잔해 파일에 들어가는 경우 모델별로 포함되므로 GPU 메모리 예산은 독립적으로 계산됩니다. `lighting-v1`의 PC 모델 예산을 사용합니다.

### 재질 데이터

- Base color: 1,024픽셀 JPEG, sRGB.
- Normal: 1,024픽셀 PNG, OpenGL 방향의 tangent-space normal.
- ARM: JPEG의 R 채널은 AO, G는 roughness, B는 metalness입니다. 하나의 이미지가 `occlusionTexture`와 `metallicRoughnessTexture`에 함께 연결됩니다. 석재의 metallicFactor는 0입니다.
- 재질 맵은 모두 UV0을 사용하고 반복하며, 내장 이미지가 GLB bufferView에 들어갑니다.
- Style은 흰색을 곱하고 roughness·metalness를 덮어쓰지 않아 원본 재질 값을 유지합니다.
- 조각은 실제 메시 요철·실루엣이며 노멀 맵의 미세한 표면 요철과 함께 표현됩니다.
- 건축물은 대부분 개별 모서리를 깎은 돌로 생성하며, 바닥과 암석의 삼각형 방향·유한한 정점·단위 법선을 검증했습니다.

## 열어 보기

`models-v1`과 `lighting-v1`을 지원하는 최신 LINK Browser가 필요합니다. 기존 LINK TCP 서버가 실행 중이면 새 자산 형식 지원을 포함한 서버로 재시작합니다.

```powershell
# link-game 디렉터리의 PowerShell에서 로컬 실행
& ..\link\build\native\Release\LINK.exe --worlds "$PWD\worlds" --open link://local/stone-sanctum

# 서버에서 접속할 때
# LINK 주소창: link://127.0.0.1:8002/stone-sanctum
```

다른 PC에서는 `127.0.0.1`을 서버 컴퓨터의 실제 주소로 바꿉니다. Quest Link PC VR에서는 접속 후 F8로 VR에 진입합니다. 이 문서의 화면 품질과 모델 구조 검증이 실제 헤드셋 성능·편안함을 보장하지는 않습니다.

월드의 `views`에는 진입 장면, 기둥·조각 세부, 측면 복도, 제단 네 구도를 제공합니다. 카메라 시작 위치는 `[2.15,1.68,3.2]`, 바라보는 지점은 `[-.45,2.15,-7.8]`입니다. 주 동선은 가운데 통로로 제한되어 있고 기존 LINK의 평면 걷기를 사용합니다. 옆 복도·제단·벽·돌에 대한 물리 충돌 시스템은 포함하지 않습니다.

## 조명

채석장 HDR 환경광으로 간접광과 반사의 기준을 제공합니다. 따뜻한 방향광은 위쪽과 입구 쪽에서 들어오며 열린 천장·부서진 벽·아치·기둥이 실제 그림자를 만듭니다. 제단 양옆 화로는 작은 따뜻한 점광원과 일치하도록 배치했습니다. 뒤쪽 문 안에는 바닥·양쪽 벽·천장·뒷벽·낮은 단차를 실제 두께로 만들고 세 번째 따뜻한 점광원으로 내부 깊이를 보여줍니다. 그림자는 이 공간을 포함하는 고정 범위의 맵을 사용합니다.

현재 공간은 정적인 작은 유적입니다. 전체 게임 규모의 자원 스트리밍, 자동 LOD, 지형 충돌, 파괴 시뮬레이션, 전역 조명의 실시간 다중 반사, Quest 단독 APK는 이 자산 패키지의 범위 밖입니다. 이 공간은 그 기능을 완성했다고 주장하는 결과가 아니라 실제 PBR 재질·조명·그림자 조합을 평가할 수 있는 기준 장면입니다.
