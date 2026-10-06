# Fig. 1 measurement firmware (hwchar_tbl.c), ChipWhisperer-Nano (STM32F030)
#
# Build: copy this folder into the ChipWhisperer firmware tree under chipwhisperer/firmware/mcu/
# (for example mcu/simpleserial-hwchar-tbl/) and run
#   make PLATFORM=CWNANO CRYPTO_TARGET=NONE
# which produces simpleserial-hwchar-tbl-CWNANO.hex.  The image used for the measurement was
# built by arm-none-eabi-gcc 14.2.1 and is not included; listings/hwchar_tbl_O0_*.lss is the
# disassembly of a rebuild with 15.2.1, whose event functions have the same instruction stream
# (see listings/README.md).

TARGET = simpleserial-hwchar-tbl
SRC += hwchar_tbl.c
EXTRAINCDIRS += .
OPT = 0
ifeq ($(CRYPTO_TARGET),)
  CRYPTO_TARGET = NONE
endif
include ../simpleserial/Makefile.simpleserial
FIRMWAREPATH = ../.
include $(FIRMWAREPATH)/Makefile.inc
