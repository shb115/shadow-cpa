# ------------------------------------------------------------------
# Shadow-32 / Shadow-64 캡처 펌웨어 빌드 (ChipWhisperer-Nano)
#
# 이 makefile 은 ChipWhisperer 펌웨어 트리 안에서 동작한다. 빌드 방법:
#   1) 빌드할 .c 파일과 이 makefile 을 ChipWhisperer 펌웨어 트리의
#      <chipwhisperer>/firmware/mcu/ 아래 새 폴더에 복사
#   2) 아래 TARGET 과 SRC 를 그 파일에 맞게 지정 (단일 자립 파일이라 하나면 됨)
#        Shadow-32 : TARGET = shadow32_nop       SRC += shadow32_nop.c
#        Shadow-64 : TARGET = shadow64_newkey    SRC += shadow64_nop_newkey.c
#        마스킹     : TARGET = masking_ISW       SRC += masking_ISW.c
#                     (masking_ISWLUT 도 같은 방식)
#   3) 빌드:
#        make PLATFORM=CWNANO CRYPTO_TARGET=TINYAES128C
#      -> <TARGET>-CWNANO.hex 생성 (예: shadow32_nop-CWNANO.hex)
#
# ★ OPT = 0 (=-O0) 을 반드시 유지할 것.
#   -O0 는 중간값을 매 연산마다 스택 메모리에 저장 -> 강한 Hamming-weight 누설
#   -> CPA-HW 피크 ~0.89. -O2/-Os 로 바꾸면 중간값이 레지스터에 남아 누설이
#   약해지고 피크가 0.60 으로 떨어진다 (파형은 더 깔끔해 보이지만 공격이 약해짐).
#
# CRYPTO_TARGET=TINYAES128C 는 aes-independant.h 의 KEY_LENGTH/DEFAULT_KEY 와
# 빈 함수 aes_indep_enc_pre/posttrigger 때문에 필요하다. 사이퍼 자체는 AES 를
# 전혀 호출하지 않는다.
# ------------------------------------------------------------------

TARGET = shadow32_nop

# 빌드할 단일 파일 하나만 지정 (extern/VPATH 없이 자립).
SRC += shadow32_nop.c
# 다른 펌웨어를 빌드할 땐 위 줄을 주석 처리하고 아래 중 하나를 사용
# (TARGET 도 함께 바꿀 것):
# SRC += shadow64_nop_newkey.c
# SRC += masking_ISW.c
# SRC += masking_ISWLUT.c

OPT = 0
CFLAGS += -fomit-frame-pointer

# -----------------------------------------------------------------------------
EXTRA_OPTS = NO_EXTRA_OPTS
CFLAGS += -D$(EXTRA_OPTS)

ifeq ($(CRYPTO_TARGET),)
  ${info No CRYPTO_TARGET passed - defaulting to TINYAES128C}
  CRYPTO_TARGET = TINYAES128C
endif

${info Building for platform ${PLATFORM} with CRYPTO_TARGET=$(CRYPTO_TARGET)}

# Add simpleserial project to build
include ../simpleserial/Makefile.simpleserial

FIRMWAREPATH = ../.
include $(FIRMWAREPATH)/Makefile.inc
