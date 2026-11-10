"""AD001: opt-in ITCM canary and bounded lossless ARM decoder proof (MIT).

Only four new diagnostic commands (32..35); no sequencer/knob/SD/DSP hooks.
Commands 33..35 require KEY. ITCM is never enabled by this module. The lowest
256 bytes and any active low vector table are protected. No arbitrary execution
or host-supplied memory addresses/data. Decoder inputs are ROM fixtures only.
"""
import math
import random
import struct

from thumb import (Asm, add_sp_imm, adds_imm8, adds_reg, ands_reg, b, b_cond, b_w,
                   bl, bx_lr, cmp_imm, cmp_reg, eors_reg, h, ldr_imm, ldr_sp,
                   ldrb_imm, lsls_imm, lsls_reg, lsrs_imm, lsrs_reg, mov_reg,
                   movs_imm, movt, movw, orrs_reg, pop_list, push_list, raw,
                   str_imm, str_sp, strh_imm, sub_sp_imm, subs_imm8, subs_reg)

KEY = 0x41434431  # "ACD1", explicit test authorization, not a security credential
START, END, OUTPUT, OUTPUT_END = 0x100, 0x4000, 0x2000, 0x2180
PATTERN = 0xA17C0121
ITCMCR, VTOR, MPUCTRL = 0xE000EF90, 0xE000ED08, 0xE000ED94
DEMCR, DWTCTRL, CYCCNT, LAR, LSR = 0xE000EDFC, 0xE0001000, 0xE0001004, 0xE0001FB0, 0xE0001FB4
FORMAT = 0xAD000001


def pack(values, bits):
    acc = count = 0
    out = bytearray()
    for v in values:
        acc |= v << count
        count += bits
        while count >= 8:
            out.append(acc & 255); acc >>= 8; count -= 8
    if count:
        out.append(acc & 255)
    return bytes(out)


def packed(vals):
    """Benchmark codec 4, exact 14-bit samples plus presence map."""
    mask = bytearray(24)
    present = []
    for i, v in enumerate(vals):
        if v != 0xFFFF:
            mask[i // 8] |= 1 << (i % 8)
            present.append(v)
    if not present:
        return b""
    delta = [b-a for a, b in zip(present, present[1:])]
    zz = [2*d if d >= 0 else -2*d-1 for d in delta]
    width = max((v.bit_length() for v in zz), default=0)
    return b"\x04" + mask + bytes([width]) + struct.pack("<H", present[0]) + pack(zz, width)


def fixtures():
    rng = random.Random(121)
    sweep = [round((1 + math.sin(i * .075)) * 8191) for i in range(192)]
    sparse = [0xFFFF] * 192
    for i, v in ((0, 0), (5, 16383), (31, 8192), (96, 4), (191, 16382)):
        sparse[i] = v
    randoms = [rng.randrange(16384) for _ in range(192)]
    cutoff = [v * 128 for v in (90, 83, 74, 62, 54, 44, 34, 30, 21, 12, 6, 0)] + [0xFFFF] * 180
    entries = [("empty", [0xFFFF]*192, b""),
               ("constant", [8192]*192, packed([8192]*192)),
               ("sparse-boundaries", sparse, packed(sparse)),
               ("fine-sweep", sweep, packed(sweep)),
               ("dense-random-raw", randoms, b"\x00" + struct.pack("<192H", *randoms)),
               ("captured-cutoff-prefix-scaled", cutoff, packed(cutoff))]
    assert all(len(vals) == 192 and all(v == 0xFFFF or 0 <= v <= 16383 for v in vals) for _, vals, _ in entries)
    return entries


def decoder(base):
    """r0=src, r1=end, r2=384-byte dst; r0=0 OK / 1 malformed.

    Supports empty, raw halfwords (0), packed exact deltas (4). Reads bounded by
    end, writes at most 192 halfwords, preserves r4-r11 and SP. Partial output on
    malformed input is discarded by the caller. Max stack = 64 bytes.
    """
    a = Asm(base); E = a.emit
    inverse = dict(eq="ne", ne="eq", lo="hs", hs="lo", hi="ls", ls="hi")
    serial = [0]

    def far(label, cond):
        serial[0] += 1
        skip = f"d_skip{serial[0]}"
        E(b_cond, skip, inverse[cond]); E(b_w, label); a.label(skip)

    a.label("c_acdecode")
    E(push_list, [4, 5, 6, 7], lr=True); E(sub_sp_imm, 44)
    E(mov_reg, 4, 0); E(mov_reg, 7, 2); E(str_sp, 1, 0)
    E(cmp_reg, 0, 1); far("d_bad", "hi"); far("d_empty", "eq")
    E(ldrb_imm, 0, 4, 0); E(cmp_imm, 0, 0); far("d_raw", "eq")
    E(cmp_imm, 0, 4); far("d_bad", "ne")
    E(mov_reg, 0, 4); E(adds_imm8, 0, 28); E(cmp_reg, 0, 1); far("d_bad", "hi")
    E(ldrb_imm, 5, 4, 25); E(cmp_imm, 5, 15); far("d_bad", "hi"); E(str_sp, 5, 24)
    E(ldrb_imm, 0, 4, 26); E(ldrb_imm, 1, 4, 27); E(lsls_imm, 1, 1, 8); E(orrs_reg, 0, 1)
    E(lsrs_imm, 1, 0, 14); E(cmp_imm, 1, 0); far("d_bad", "ne"); E(str_sp, 0, 20)
    E(mov_reg, 0, 4); E(adds_imm8, 0, 1); E(str_sp, 0, 8)
    E(movs_imm, 0, 0)
    for off in (12, 16, 28, 32, 36): E(str_sp, 0, off)
    E(movs_imm, 0, 192); E(str_sp, 0, 40); E(adds_imm8, 4, 28)
    a.label("d_cell")
    E(ldr_sp, 0, 16); E(cmp_imm, 0, 0); E(b_cond, "d_mask", "ne")
    E(ldr_sp, 1, 8); E(ldrb_imm, 2, 1, 0); E(adds_imm8, 1, 1); E(str_sp, 1, 8); E(str_sp, 2, 12)
    E(movs_imm, 0, 8)
    a.label("d_mask")
    E(subs_imm8, 0, 1); E(str_sp, 0, 16)
    E(ldr_sp, 2, 12); E(lsrs_imm, 0, 2, 1); E(str_sp, 0, 12)
    E(lsls_imm, 2, 2, 31); E(b_cond, "d_present", "ne")
    E(movw, 2, 0xFFFF); E(b, "d_put")
    a.label("d_present")
    E(ldr_sp, 0, 36); E(cmp_imm, 0, 0); E(b_cond, "d_bits", "ne")
    E(movs_imm, 0, 1); E(str_sp, 0, 36); E(ldr_sp, 2, 20); E(b, "d_put")
    a.label("d_bits")
    E(ldr_sp, 0, 28); E(ldr_sp, 1, 32)
    a.label("d_more")
    E(cmp_reg, 1, 5); E(b_cond, "d_value", "hs")
    E(ldr_sp, 2, 0); E(cmp_reg, 4, 2); far("d_bad", "hs")
    E(ldrb_imm, 2, 4, 0); E(adds_imm8, 4, 1); E(lsls_reg, 2, 1); E(orrs_reg, 0, 2); E(adds_imm8, 1, 8)
    E(b, "d_more")
    a.label("d_value")
    E(movs_imm, 2, 1); E(lsls_reg, 2, 5); E(subs_imm8, 2, 1); E(ands_reg, 2, 0)
    E(lsrs_reg, 0, 5); E(str_sp, 0, 28); E(subs_reg, 1, 1, 5); E(str_sp, 1, 32)
    E(lsls_imm, 0, 2, 31); E(lsrs_imm, 2, 2, 1); E(cmp_imm, 0, 0); E(b_cond, "d_pos", "eq")
    E(movs_imm, 0, 0); E(subs_reg, 2, 0, 2); E(subs_imm8, 2, 1)
    a.label("d_pos")
    E(ldr_sp, 0, 20); E(adds_reg, 2, 2, 0); E(lsrs_imm, 0, 2, 14); E(cmp_imm, 0, 0); far("d_bad", "ne")
    E(str_sp, 2, 20)
    a.label("d_put")
    E(strh_imm, 2, 7, 0); E(adds_imm8, 7, 2)
    E(ldr_sp, 0, 40); E(subs_imm8, 0, 1); E(str_sp, 0, 40); far("d_cell", "ne")
    E(ldr_sp, 0, 36); E(cmp_imm, 0, 0); far("d_bad", "eq")
    E(ldr_sp, 0, 0); E(cmp_reg, 4, 0); far("d_bad", "ne"); E(b, "d_ok")
    a.label("d_raw")
    E(mov_reg, 0, 4); E(movw, 2, 385); E(adds_reg, 0, 0, 2); E(cmp_reg, 0, 1); far("d_bad", "ne")
    E(adds_imm8, 4, 1); E(movs_imm, 6, 192)
    a.label("d_rawloop")
    E(ldrb_imm, 0, 4, 0); E(ldrb_imm, 1, 4, 1); E(lsls_imm, 1, 1, 8); E(orrs_reg, 0, 1)
    E(movw, 1, 0xFFFF); E(cmp_reg, 0, 1); E(b_cond, "d_rawput", "eq")
    E(lsrs_imm, 1, 0, 14); E(cmp_imm, 1, 0); far("d_bad", "ne")
    a.label("d_rawput")
    E(strh_imm, 0, 7, 0); E(adds_imm8, 4, 2); E(adds_imm8, 7, 2); E(subs_imm8, 6, 1); E(b_cond, "d_rawloop", "ne")
    E(b, "d_ok")
    a.label("d_empty")
    E(movs_imm, 6, 192); E(movw, 0, 0xFFFF)
    a.label("d_emptyloop")
    E(strh_imm, 0, 7, 0); E(adds_imm8, 7, 2); E(subs_imm8, 6, 1); E(b_cond, "d_emptyloop", "ne")
    a.label("d_ok")
    E(movs_imm, 0, 0); E(b, "d_return")
    a.label("d_bad"); E(movs_imm, 0, 1)
    a.label("d_return"); E(add_sp_imm, 44); E(pop_list, [4, 5, 6, 7], pc=True)
    return a.assemble()


def commands(base, extern, table, count):
    a = Asm(base); E = a.emit
    serial = [0]
    inverse = dict(eq="ne", ne="eq", lo="hs", hs="lo", hi="ls", ls="hi")

    def imm(r, v): E(movw, r, v & 0xFFFF); E(movt, r, v >> 16)
    def far(label, cond):
        serial[0] += 1; skip = f"c_skip{serial[0]}"
        E(b_cond, skip, inverse[cond]); E(b_w, label); a.label(skip)
    def field_reg(r):
        E(mov_reg, 1, r); E(mov_reg, 0, 6); E(bl, extern['c_p32']); E(mov_reg, 6, 0)
    def field(v): imm(1, v); field_reg(1)
    def wordfield(address): imm(0, address); E(ldr_imm, 1, 0, 0); field_reg(1)
    def stackfield(off): E(ldr_sp, 1, off); field_reg(1)

    a.label('c_accommand')  # r0=cmd, r1=reply/request payload; outer r4/r7 preserved
    E(push_list, [4, 5, 6, 7], lr=True); E(sub_sp_imm, 76)
    E(mov_reg, 5, 0); E(mov_reg, 4, 1); E(mov_reg, 6, 1)
    E(movs_imm, 0, 0)
    for off in range(0, 76, 4): E(str_sp, 0, off)
    E(cmp_imm, 5, 32); far('c_status', 'eq')
    E(cmp_imm, 5, 33); far('c_unknown', 'lo')
    E(cmp_imm, 5, 35); far('c_unknown', 'hi')
    E(mov_reg, 0, 4); E(bl, extern['c_g32']); imm(1, KEY); E(cmp_reg, 0, 1); far('c_keybad', 'ne')
    E(bl, 'c_acusable'); E(cmp_imm, 0, 0); far('c_error', 'ne')
    E(cmp_imm, 5, 33); far('c_fill', 'eq')
    # fill is required before checking/benchmarking; two fixed header words
    for addr in (START, START + 4):
        imm(0, addr); E(ldr_imm, 0, 0, 0); imm(1, PATTERN ^ addr); E(cmp_reg, 0, 1); far('c_unarmed', 'ne')
    E(cmp_imm, 5, 34); far('c_check', 'eq')
    E(b_w, 'c_bench')

    a.label('c_status')
    field(0); field(FORMAT)
    for addr in (ITCMCR, VTOR, MPUCTRL, DWTCTRL, DEMCR): wordfield(addr)
    field(START); field(END); field(count)
    E(b_w, 'c_return')
    a.label('c_fill')
    imm(0, START); imm(1, END); imm(3, PATTERN)
    a.label('c_fillloop')
    E(mov_reg, 2, 0); E(eors_reg, 2, 3); E(str_imm, 2, 0, 0); E(adds_imm8, 0, 4); E(cmp_reg, 0, 1); E(b_cond, 'c_fillloop', 'lo')
    E(raw, h(0xF3BF)+h(0x8F4F))  # DSB SY, no instruction execution from ITCM
    field(0); field((END-START)//4); E(b_w, 'c_return')
    a.label('c_check')
    imm(0, START); imm(1, END); imm(3, PATTERN)
    a.label('c_checkloop')
    imm(2, OUTPUT); E(cmp_reg, 0, 2); E(b_cond, 'c_checkread', 'ne')
    imm(0, OUTPUT_END)
    a.label('c_checkread')
    E(ldr_sp, 2, 4); E(adds_imm8, 2, 1); E(str_sp, 2, 4)
    E(ldr_imm, 2, 0, 0); E(eors_reg, 2, 3); E(cmp_reg, 2, 0); E(b_cond, 'c_checknext', 'eq')
    E(ldr_sp, 2, 0); E(adds_imm8, 2, 1); E(str_sp, 2, 0); E(cmp_imm, 2, 1); E(b_cond, 'c_checknext', 'ne')
    E(str_sp, 0, 8); E(ldr_imm, 2, 0, 0); E(str_sp, 2, 12)
    a.label('c_checknext')
    E(adds_imm8, 0, 4); E(cmp_reg, 0, 1); E(b_cond, 'c_checkloop', 'lo')
    field(0)
    for off in (0, 4, 8, 12): stackfield(off)
    E(b_w, 'c_return')

    a.label('c_bench')
    E(mov_reg, 0, 4); E(adds_imm8, 0, 8); E(bl, extern['c_g32']); E(cmp_imm, 0, count); far('c_argbad', 'hs')
    E(str_sp, 0, 16)
    E(movs_imm, 1, 12); E(raw, h(0x4348))  # muls r0,r1
    imm(1, table); E(adds_reg, 0, 0, 1)
    for off, dest in ((0, 20), (4, 24), (8, 28)):
        E(ldr_imm, 1, 0, off); E(str_sp, 1, dest)
    E(mov_reg, 0, 4); E(adds_imm8, 0, 16); E(bl, extern['c_g32'])
    E(cmp_imm, 0, 1); E(b_cond, 'c_repsok', 'eq'); E(cmp_imm, 0, 8); far('c_argbad', 'ne')
    a.label('c_repsok'); E(str_sp, 0, 32); E(str_sp, 0, 36)
    # Preserve trace control; enable CYCCNT for this benchmark only, never zero it.
    for addr, off in ((DEMCR, 40), (DWTCTRL, 44), (LSR, 48)):
        imm(0, addr); E(ldr_imm, 1, 0, 0); E(str_sp, 1, off)
    imm(0, DEMCR); E(ldr_imm, 1, 0, 0); imm(2, 1 << 24); E(orrs_reg, 1, 2); E(str_imm, 1, 0, 0)
    imm(0, LAR); imm(1, 0xC5ACCE55); E(str_imm, 1, 0, 0)
    imm(0, DWTCTRL); E(ldr_imm, 1, 0, 0); E(movs_imm, 2, 1); E(orrs_reg, 1, 2); E(str_imm, 1, 0, 0)
    E(raw, h(0xF3BF)+h(0x8F4F))
    a.label('c_benchloop')
    imm(0, CYCCNT); E(ldr_imm, 7, 0, 0)
    E(ldr_sp, 0, 20); E(ldr_sp, 1, 24); imm(2, OUTPUT); E(bl, extern['c_acdecode'])
    E(str_sp, 0, 52)
    imm(0, CYCCNT); E(ldr_imm, 0, 0, 0); E(subs_reg, 0, 0, 7)
    E(ldr_sp, 1, 56); E(adds_reg, 1, 1, 0); E(str_sp, 1, 56)
    E(ldr_sp, 1, 60); E(cmp_reg, 0, 1); E(b_cond, 'c_maxok', 'ls'); E(str_sp, 0, 60)
    a.label('c_maxok')
    E(ldr_sp, 0, 52); E(cmp_imm, 0, 0); E(b_cond, 'c_restore', 'ne')
    E(ldr_sp, 0, 36); E(subs_imm8, 0, 1); E(str_sp, 0, 36); E(b_cond, 'c_benchloop', 'ne')
    a.label('c_restore')
    imm(0, DWTCTRL); E(ldr_sp, 1, 44); E(str_imm, 1, 0, 0)
    E(ldr_sp, 1, 48); E(lsls_imm, 1, 1, 30); E(b_cond, 'c_notlocked', 'pl')
    imm(0, LAR); E(movs_imm, 1, 0); E(str_imm, 1, 0, 0)
    a.label('c_notlocked')
    imm(0, DEMCR); E(ldr_sp, 1, 40); E(str_imm, 1, 0, 0)
    # Compare every decoded word, outside the timed region.
    imm(0, OUTPUT); E(ldr_sp, 1, 28); E(movs_imm, 7, 192)
    a.label('c_compare')
    E(ldr_imm, 2, 0, 0); E(ldr_imm, 3, 1, 0); E(cmp_reg, 2, 3); E(b_cond, 'c_compareok', 'eq')
    E(ldr_sp, 2, 64); E(adds_imm8, 2, 1); E(str_sp, 2, 64)
    a.label('c_compareok')
    E(adds_imm8, 0, 4); E(adds_imm8, 1, 4); E(subs_imm8, 7, 2); E(b_cond, 'c_compare', 'ne')
    field(0)
    for off in (16, 32, 52, 56, 60, 64): stackfield(off)
    E(ldr_sp, 1, 24); E(ldr_sp, 2, 20); E(subs_reg, 1, 1, 2); field_reg(1)
    E(b_w, 'c_return')

    for label, code in (('c_keybad', 1), ('c_unarmed', 4), ('c_argbad', 5)):
        a.label(label); E(movs_imm, 0, code); E(b, 'c_error')
    a.label('c_unknown'); imm(0, 0xFFFFFFFF)
    a.label('c_error'); field_reg(0)
    a.label('c_return')
    E(mov_reg, 0, 6); E(add_sp_imm, 76); E(pop_list, [4, 5, 6, 7], pc=True)

    a.label('c_acusable')
    imm(0, ITCMCR); E(ldr_imm, 0, 0, 0); E(lsls_imm, 1, 0, 31); E(b_cond, 'c_itoff', 'eq')
    E(lsls_imm, 1, 0, 25); E(lsrs_imm, 1, 1, 28); E(cmp_imm, 1, 5); E(b_cond, 'c_itoff', 'lo')
    imm(0, VTOR); E(ldr_imm, 0, 0, 0); imm(1, END); E(cmp_reg, 0, 1); E(b_cond, 'c_vector', 'lo')
    E(movs_imm, 0, 0); E(bx_lr)
    a.label('c_itoff'); E(movs_imm, 0, 2); E(bx_lr)
    a.label('c_vector'); E(movs_imm, 0, 3); E(bx_lr)
    return a.assemble()


def install(img, report, base_addr):
    import rhbuild
    import rh_fw
    rd = {k: int(v, 16) for k, v in report['rdiag']['labels'].items()}
    # Match the exact unknown-command response; existing commands are unmodified.
    found = []
    for at in range(rd['c_rdcmd'], rd['c_rdcmd'] + 0x180, 2):
        ins = list(rhbuild.MD.disasm(bytes(img[at-rh_fw.APP_BASE:at-rh_fw.APP_BASE+16]), at))
        if len(ins) == 5 and [(i.mnemonic, i.op_str) for i in ins[:3]] == [
                ('mov', 'r0, r1'), ('movw', 'r1, #0xffff'), ('movt', 'r1, #0xffff')] and ins[3].mnemonic == 'bl' and ins[4].mnemonic == 'b':
            found.append((at, int(ins[4].op_str.removeprefix('#'), 16)))
    assert len(found) == 1, found
    unknown, send = found[0]
    entries = fixtures()
    blob = bytearray(12*len(entries))
    reports = []
    for index, (name, vals, payload) in enumerate(entries):
        while len(blob) % 4: blob.append(0xFF)
        src = base_addr + len(blob); blob.extend(payload); end = base_addr + len(blob)
        while len(blob) % 4: blob.append(0xFF)
        expect = base_addr + len(blob); blob.extend(struct.pack('<192H', *vals))
        struct.pack_into('<III', blob, index*12, src, end, expect)
        reports.append(dict(index=index, name=name, source=hex(src), end=hex(end), expected=hex(expect), compressed_bytes=len(payload)))
    while len(blob) % 4: blob.append(0xFF)
    dec, dl = decoder(base_addr + len(blob)); blob.extend(dec)
    while len(blob) % 4: blob.append(0xFF)
    code, labels = commands(base_addr + len(blob), {**rd, **dl}, base_addr, len(entries)); blob.extend(code)
    img += bytes([0xFF])*(base_addr-rh_fw.APP_BASE-len(img)) + blob
    while len(img) % 4: img.append(0xFF)
    old = '|'.join(rhbuild.disasm(bytes(img[unknown-rh_fw.APP_BASE:unknown-rh_fw.APP_BASE+16]), unknown))
    rhbuild.patch(img, unknown, old, bl(unknown, labels['c_accommand']) + b_w(unknown+4, send) + h(0xBF00)*4)
    report['acdiag'] = dict(commands=dict(status=32, fill=33, check=34, bench=35), key=hex(KEY),
                            itcm=[hex(START), hex(END)], output=[hex(OUTPUT), hex(OUTPUT_END)],
                            canary_words=(END-START-(OUTPUT_END-OUTPUT))//4, decoder_stack=64,
                            decoder_bytes=len(dec), proof_only=True, live_automation=False,
                            stock_recording_unchanged=True, sd_writes=False, dsp_writes=False,
                            unknown_site=hex(unknown), fixtures=reports,
                            labels={k: hex(v) for k, v in {**dl, **labels}.items() if k.startswith('c_')})
