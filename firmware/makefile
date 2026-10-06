# ------------------------------------------------------------------
# Build file of the Shadow-32 / Shadow-64 capture firmwares (ChipWhisperer-Nano)
#
# This makefile works inside the ChipWhisperer firmware tree. To build an image:
#   1) copy the .c file to build and this makefile into a new folder under
#      <chipwhisperer>/firmware/mcu/
#   2) set TARGET and SRC below to that file (each source is a single self-contained file):
#        Shadow-32 : TARGET = shadow32_nop        SRC += shadow32_nop.c
#                    (capture_lab.py looks for the image of the same source built as
#                     TARGET = shadow32_nop_O0)
#        Shadow-64 : TARGET = shadow64_newkey     SRC += shadow64_nop_newkey.c
#        masked    : TARGET = masking_ISW_v2      SRC += masking_ISW.c      (trace acquisition, one round)
#                    TARGET = masking_ISW_v2_KAT  + EXTRA_OPTS = SHADOW32_KAT  (known-answer test: returns the state after the round)
#                    TARGET = masking_ISW_v2_FULL + EXTRA_OPTS = SHADOW32_FULL (full 16-round encryption)
#                    (the same three targets for masking_ISWLUT; capture_lab.py looks for the
#                     images of these names. The source of masking_ISWLUT.c is revision v3 of the
#                     file; the target and trace-file names keep masking_ISWLUT_v2.)
#   3) build:
#        make PLATFORM=CWNANO CRYPTO_TARGET=TINYAES128C
#      -> <TARGET>-CWNANO.hex (for example shadow32_nop-CWNANO.hex) together with the
#         disassembly listing <TARGET>-CWNANO.lss (listings/ in the repository); the default
#         target of the ChipWhisperer makefile does a full clean and rebuild each time and
#         writes the .lss as part of it, so no separate `make lss` step is needed (that
#         target would clean and rebuild again and leave no .hex behind).
#
# OPT = 0 (-O0) must be kept. At -O0 every intermediate value is written to stack memory on
# each operation, which gives the strong Hamming-weight leakage the attack targets and a
# correct-key correlation of about 0.9 on the deposited traces. An optimized build (-O2 or
# -Os) keeps intermediate values in registers and is expected to leak less; the paper's
# figures are those of the -O0 build only.
#
# CRYPTO_TARGET=TINYAES128C is needed for KEY_LENGTH / DEFAULT_KEY of aes-independant.h and the
# empty aes_indep_enc_pre/posttrigger functions. The cipher itself never calls AES.
# ------------------------------------------------------------------

TARGET = shadow32_nop

# One self-contained source file (no extern / VPATH).
SRC += shadow32_nop.c
# To build another firmware, comment out the line above and use one of the following
# (and change TARGET accordingly):
# SRC += shadow64_nop_newkey.c
# SRC += masking_ISW.c
# SRC += masking_ISWLUT.c

OPT = 0
CFLAGS += -fomit-frame-pointer

# -----------------------------------------------------------------------------
# Variants of the masked firmwares: SHADOW32_KAT (returns the unmasked state after one round),
# SHADOW32_FULL (full 16-round encryption, 200-byte input). The acquisition image is NO_EXTRA_OPTS.
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
