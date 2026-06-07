# Makefile for x86-64 SysV ABI LOS module

TARGET = liblos.so
SRC = los_many.asm
OBJ = los_many.o

ASM = nasm
ASMFLAGS = -f elf64
LD = ld
LDFLAGS = -shared -z noexecstack

all: $(TARGET)

$(TARGET): $(OBJ)
	$(LD) $(LDFLAGS) -o $@ $^

$(OBJ): $(SRC)
	$(ASM) $(ASMFLAGS) -o $@ $<

clean:
	rm -f $(OBJ) $(TARGET)

.PHONY: all clean
