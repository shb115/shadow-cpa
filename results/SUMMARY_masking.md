# Shadow32 마스킹 부채널 분석 — masking_ISW vs masking_ISWLUT

- **대상**: ChipWhisperer-Nano (STM32F030F4, Cortex-M0), Shadow32 1라운드
- **측정**: 각 버전 **고정 4096 + 랜덤 4096 = 8192 트레이스**, `samples=10000`, `clkout=adc_freq=7.5MHz`, `clk_src=int`, **-O0**
- **평문**: `pt[0:4]` (고정군만 고정), 마스크/난수 `pt[4:20]`은 양군 모두 랜덤

## 두 버전

| 구현 | AND 구현 | 대책 |
|---|---|---|
| `masking_ISW` | **산술 ISW** AND | 없음 (refresh만) |
| `masking_ISWLUT` | **ISW LUT** AND (마스킹 테이블 룩업) | **레지스터/버스 세척** |

## 결과 요약 (4096/셋)

| 지표 | masking_ISW (산술) | masking_ISWLUT (LUT+세척) |
|---|---|---|
| **TVLA** max\|t\| | **13.46** | **3.61** |
| **TVLA** \|t\|>4.5 초과 | **18** (누설) | **0** (통과) |
| **CPA HW** 정답키 랭크 | 133 / 256 (미복구) | 170 / 256 (미복구) |
| **CPA HD** 정답키 랭크 | 208 / 256 (미복구) | 112 / 256 (미복구) |
| 상태 l0 상관 | 0.187 | 0.056 (잡음) |
| 상태 r0 상관 | 0.210 (누설) | 0.044 (잡음) |
| 키 s0 상관 | 0.062 (잡음) | 0.054 (잡음) |

## 해석

1. **CPA는 두 버전 모두 키 복구 실패** (HW·HD 모두). 마스킹(2-공유 + 키 마스킹)이 키를 지킵니다.
2. **TVLA는 masking_ISW만 초과(누설)**, masking_ISWLUT는 통과.
   - masking_ISW의 TVLA 누설은 **평문 상태(l0/r0)** 가 두 공유의 재결합(해밍거리·천이)으로 1차 누설되는 것 — 키가 아니라 평문입니다. 그래서 TVLA는 뜨지만 CPA(키)는 실패합니다.
   - masking_ISWLUT는 (a) 산술 AND 대신 **테이블 룩업**으로 게이트에서 두 공유가 안 만나게 하고, (b) **세척**으로 레지스터/버스 재결합 천이를 끊어 상태 누설을 제거 → TVLA 0 초과.
3. **핵심 결론**: 마스킹(ISW)만으로는 CPA엔 안전하나 **평문 상태의 TVLA 누설**이 남고, 이를 없애려면 **테이블화 + 레지스터/버스 세척**이 필요합니다. (마스킹 알고리즘은 순수 C 가능, 세척은 asm 필요.)

## 파일 구성

```
data/masked/masking_ISW_traces.npz          산술 ISW, 8192 x 10000 (65 MB)
data/masked/masking_ISWLUT_traces.npz       ISW LUT + 세척, 8192 x 10000 (64 MB)
firmware/masking_ISW.c                      소스 (산술 ISW)
firmware/masking_ISWLUT.c                   소스 (ISW LUT + 레지스터/버스 세척)
analysis/analyze_wide.py                    TVLA 분석 코드 (Welch t + HW모델 상관)
analysis/cpa_offline.py                     CPA 공격 코드 (HW/HD 모델)
results/SUMMARY_masking.md                  이 파일
results/masking_ISW_result.txt              수치 요약
results/masking_ISW_tvla.png                TVLA t-통계 + HW모델 상관
results/masking_ISW_cpa.png                 CPA (HW 모델)
results/masking_ISW_cpaHD.png               CPA (HD 모델)
results/masking_ISWLUT_result.txt
results/masking_ISWLUT_tvla.png
results/masking_ISWLUT_cpa.png
results/masking_ISWLUT_cpaHD.png
```

**`.npz` 내용** (numpy `np.load`): `traces` (8192 × 10000, float16) — 파형,
`pt` (8192 × 20, uint8) — 평문+난수, `group` (8192, uint8) — 0=고정/1=랜덤,
`key` (4, uint8) — 라운드키, 그리고 `clkout`/`adc_freq`/`samples`/`version` 메타.
불러오기 예: `d = np.load('masking_ISW_traces.npz'); tr = d['traces']; g = d['group']`

## 분석 재현 (`analysis/` 폴더에서 실행)

원본 파형이 함께 있으므로 아래 코드로 표의 TVLA·CPA 결과를 그대로 재현할 수 있습니다.
(numpy, matplotlib 필요. 인자를 생략하면 `masking_ISW` 쪽이 기본값이다.)

```
# TVLA (Welch t) — 인자: 데이터셋 경로, 샘플수
python analyze_wide.py ../data/masked/masking_ISW_traces.npz 10000
python analyze_wide.py ../data/masked/masking_ISWLUT_traces.npz 10000

# CPA — 기본 HW 모델
python cpa_offline.py ../data/masked/masking_ISW_traces.npz
python cpa_offline.py ../data/masked/masking_ISWLUT_traces.npz

# CPA — HD(레지스터 천이) 모델은 환경변수 CPA_MODEL 로 선택
#   POSIX 셸  : CPA_MODEL=HD python cpa_offline.py <데이터셋>
#   PowerShell: $env:CPA_MODEL="HD"; python cpa_offline.py <데이터셋>
#   cmd       : set CPA_MODEL=HD && python cpa_offline.py <데이터셋>
CPA_MODEL=HD python cpa_offline.py ../data/masked/masking_ISW_traces.npz
CPA_MODEL=HD python cpa_offline.py ../data/masked/masking_ISWLUT_traces.npz
```

각 실행은 `results/` 에 `<데이터셋>_tvla.png` / `_cpa.png` / `_cpaHD.png` 를 만들고,
TVLA 최대 |t|·초과 샘플수, CPA 정답키(0x0D) 랭크를 출력합니다.

> 주: 두 버전 모두 키 관련 상관이 위 표의 0.04~0.06 수준, 즉 상태 누설(0.19~0.21)보다
> 훨씬 낮아 랭크가 잡음으로 정해진다. 따라서 랭크의 구체적 값(133/170/208/112)은
> 두 구현을 비교하는 지표가 아니며, "정답키가 최상위 추측에 오르지 못함 = 미복구"가 핵심이다.
