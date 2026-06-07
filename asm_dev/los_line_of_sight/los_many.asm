; -----------------------------------------------------------------------------
; Function: los_many
; Purpose:  Batched non-supercover Bresenham LOS for simple_rl
; Target:   x86-64 Linux, SysV ABI, NASM
; Inputs:   rdi=starts_x, rsi=starts_y, rdx=ends_x, rcx=ends_y, r8=transparency,
;           r9d=height, [rbp+16]=width, [rbp+24]=out, [rbp+32]=n
; Outputs:  out[i] (memory array), 1 if line-of-sight clear, else 0
; Clobbers: rax, rcx, rdx, rsi, rdi, r8-r11, rflags
; Stack:    16-byte aligned, 88-byte frame, no red-zone usage
; Memory:   transparency row-major (y*width+x), arrays bound by n
; ISA:      Baseline x86-64
; -----------------------------------------------------------------------------
section .text
global los_many

los_many:
    push    rbp
    mov     rbp, rsp
    push    rbx
    push    r12
    push    r13
    push    r14
    push    r15
    sub     rsp, 88                     ; 16-byte aligned frame

    ; Spill outer state to free registers for the inner loop
    mov     [rsp+0],  rdi               ; starts_x
    mov     [rsp+8],  rsi               ; starts_y
    mov     [rsp+16], rdx               ; ends_x
    mov     [rsp+24], rcx               ; ends_y
    mov     [rsp+32], r8                ; transparency

    mov     rax, [rbp+32]
    mov     [rsp+40], rax               ; n

    mov     eax, [rbp+16]
    movsxd  rax, eax
    mov     [rsp+48], rax               ; width (64-bit)

    mov     rax, [rbp+24]
    mov     [rsp+56], rax               ; out

    mov     [rsp+72], r9d               ; height

    xor     rdi, rdi                    ; i = 0

.main_loop:
    cmp     rdi, [rsp+40]
    jge     .done

    ; Load query
    mov     rax, [rsp+0]
    mov     r8d, [rax + rdi*4]          ; x0
    mov     rax, [rsp+8]
    mov     r9d, [rax + rdi*4]          ; y0
    mov     rax, [rsp+16]
    mov     eax, [rax + rdi*4]          ; x1
    mov     rcx, [rsp+24]
    mov     ecx, [rcx + rdi*4]          ; y1

    ; Bounds checks
    test    r8d, r8d
    jl      .blocked
    test    r9d, r9d
    jl      .blocked
    test    eax, eax
    jl      .blocked
    test    ecx, ecx
    jl      .blocked

    cmp     r8d, dword [rsp+48]
    jge     .blocked
    cmp     r9d, dword [rsp+72]
    jge     .blocked
    cmp     eax, dword [rsp+48]
    jge     .blocked
    cmp     ecx, dword [rsp+72]
    jge     .blocked

    ; Terminal overlap check
    cmp     r8d, eax
    jne     .do_los
    cmp     r9d, ecx
    je      .clear

.do_los:
    mov     r14d, eax                   ; target x1
    mov     r15d, ecx                   ; target y1

    mov     eax, r8d                    ; current x
    mov     ecx, r9d                    ; current y

    ; dx = abs(x1 - x0)
    mov     r10d, r14d
    sub     r10d, eax
    mov     edx, r10d
    sar     edx, 31
    xor     r10d, edx
    sub     r10d, edx

    ; dy = -abs(y1 - y0)
    mov     r11d, r15d
    sub     r11d, ecx
    mov     edx, r11d
    sar     edx, 31
    xor     r11d, edx
    sub     r11d, edx
    neg     r11d

    ; sx as 64-bit value to avoid sign-extension in hot loop
    mov     r8, 1
    mov     rdx, -1
    cmp     eax, r14d
    cmovg   r8, rdx

    ; sy + precompute 64-bit sy_stride
    mov     r9d, 1
    mov     rdx, [rsp+48]
    cmp     ecx, r15d
    jle     .store_sy
    mov     r9d, -1
    neg     rdx
.store_sy:
    mov     [rsp+64], rdx               ; sy_stride

    lea     r12d, [r10 + r11]           ; err = dx + dy

    ; n_steps = max(dx, -dy)
    mov     edx, r11d
    neg     edx
    cmp     r10d, edx
    cmovg   edx, r10d
    mov     [rsp+76], edx               

    ; Initial 1D index
    movsxd  r13, ecx
    imul    r13, [rsp+48]
    movsxd  rdx, eax
    add     r13, rdx

    mov     rbx, [rsp+32]               ; transparency map pointer
    xor     esi, esi                    ; step counter = 0

.step_loop:
    cmp     esi, [rsp+76]
    jge     .clear

    lea     edx, [r12 + r12]            ; e2 = 2 * err

    ; X step
    cmp     edx, r11d
    jl      .check_y
    add     r12d, r11d
    add     eax, r8d
    add     r13, r8                     ; idx += sx

.check_y:
    ; Y step
    cmp     edx, r10d
    jg      .do_check
    add     r12d, r10d
    add     ecx, r9d
    add     r13, [rsp+64]               ; idx += sy_stride

.do_check:
    cmp     byte [rbx + r13], 0
    je      .blocked

    cmp     eax, r14d
    jne     .next_step
    cmp     ecx, r15d
    je      .clear

.next_step:
    inc     esi
    jmp     .step_loop

.blocked:
    mov     rax, [rsp+56]
    mov     byte [rax + rdi], 0
    jmp     .next_query

.clear:
    mov     rax, [rsp+56]
    mov     byte [rax + rdi], 1

.next_query:
    inc     rdi
    jmp     .main_loop

.done:
    add     rsp, 88
    pop     r15
    pop     r14
    pop     r13
    pop     r12
    pop     rbx
    pop     rbp
    ret
