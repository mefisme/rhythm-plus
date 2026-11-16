"""Lossless DSP upload compression, derived from Circuit Remix dspz.py (MIT).

240-byte LZSS window also serves as the contiguous, word-aligned SPI chunk.
Unlike Remix, no automation ITCM or shared storage buffer is borrowed. All
scratch lies in a dedicated 288-byte SRAM slot; DMA completes before reuse.
Only mode-zero core0 changes; core1 and other modes retain native senders.
"""
import hashlib, json, struct, zlib
from pathlib import Path
from thumb import (Asm, add_sp_imm, str_sp, adds_imm8, adds_reg, b, b_cond, b_w, bl, cmp_imm, cmp_reg, ldr_imm, ldr_sp, ldrb_imm, ldrb_reg,
                   lsls_imm, lsrs_imm, mov_reg, movs_imm, movt, movw, orrs_reg, pop_list, push_list, str_imm, strb_imm, strb_reg,
                   subs_imm8, subs_reg, sub_sp_imm)
BASE, BLK0 = 0x08010000, 0x0801a838
WAIT, SELECT, SPI, END = 0x08046414, 0x08031048, 0x08046504, 0x0803107a
WIN, CHUNK, MAXL = 240, 80, 265
MAGIC = b'RZ1\0'
# Bound at generation time; actual firmware uses dedicated, fixed addresses.
RING = STAGE = S = None
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'buildtmp/dspzip-cache'

def is_packed(img):
    return bytes(img[BLK0-BASE:BLK0-BASE+4])==MAGIC

def raw_stream(img):
    off=BLK0-BASE
    assert is_packed(img)
    words,crc=struct.unpack_from('<II',img,off+4)
    raw=unpack_stream(img[off+12:],words*3)
    assert zlib.crc32(raw)==crc
    return raw

def install(img, report, base_addr, counter=True, loader=True, segs=None):
    import core0, rhbuild, rhstate
    global RING,STAGE,S
    assert loader and not counter and segs is not None
    assert rhbuild.bl_target(img,core0.UPLOAD_BL0)==core0.SEND
    n,at,words=core0.block_words(img)
    assert (n,at)==(core0.N0,0)
    packwords=lambda ws:b''.join(w.to_bytes(3,'big') for w in ws)
    raw=packwords([n,at]+words)+b''.join(packwords([len(ws),a]+list(ws)) for a,ws in segs)+bytes(6)
    key=hashlib.sha256(raw+bytes([WIN])).hexdigest()
    cache=CACHE/(key+'.rz')
    if cache.exists():blob=cache.read_bytes()
    else:
        blob=MAGIC+struct.pack('<II',len(raw)//3,zlib.crc32(raw))+_pack(raw)
        CACHE.mkdir(parents=True,exist_ok=True);cache.write_bytes(blob)
    assert unpack_stream(blob[12:],len(raw))==raw
    assert len(blob)<(n+2)*3, 'packed stream must fit original native block'
    slot=rhstate.ST+rhstate.OFF['dspzip'][0]
    size=rhstate.OFF['dspzip'][1]
    RING=STAGE=(slot+31)&~31;S=RING+WIN
    assert RING%32==0 and S+20<=slot+size
    assert rhstate.ST>=0x2004ea98, 'never overlap stock allocations'
    a=Asm(base_addr);E=a.emit
    def imm32(rd,v):
        E(movw,rd,v&65535);E(movt,rd,v>>16)
    a.label('c_d0up')
    E(push_list,[4,5,6],lr=True)
    E(mov_reg,4,0);E(mov_reg,5,1)
    imm32(2,BLK0);E(cmp_reg,0,2);E(b_cond,'other','ne')
    # Reserve/initialize our complete SRAM block before first decoder use.
    E(bl,int(report['rhstate']['labels']['c_rst'],16))
    E(cmp_imm,0,0);E(b_cond,'unavailable','eq')
    # Address is resolved in a second assembly pass after the decoder size.
    imm32(0,0);a.label('loader_address_end')
    E(movs_imm,1,0);E(bl,core0.SEND)
    imm32(0,BLK0);E(movs_imm,1,0);E(bl,'c_dz')
    E(pop_list,[4,5,6],pc=True)
    a.label('other');E(mov_reg,0,4);E(mov_reg,1,5);E(bl,core0.SEND)
    E(pop_list,[4,5,6],pc=True)
    # Allocation failure cannot interpret packed bytes as native instructions.
    a.label('unavailable');E(b,'unavailable')
    emit_one(a,E,imm32);emit_fill(a,E,imm32)
    code,labels=a.assemble()
    la=(base_addr+len(code)+3)&~3
    pos=labels['loader_address_end']-base_addr-8
    code=bytearray(code)
    code[pos:pos+8]=movw(0,la&65535)+movt(0,la>>16)
    lw,_=core0.asm_at(core0.loader_items(),core0.LD)
    lb=packwords([len(lw),core0.LD]+lw)
    original=bytes(img[BLK0-BASE:BLK0-BASE+(n+2)*3])
    img[BLK0-BASE:BLK0-BASE+(n+2)*3]=blob+b'\xff'*((n+2)*3-len(blob))
    img+=b'\xff'*(base_addr-BASE-len(img))+code
    img+=b'\xff'*(la-BASE-len(img))+lb
    while len(img)%4:img.append(255)
    rhbuild.patch(img,core0.UPLOAD_BL0,f'bl #{core0.SEND:#x}',bl(core0.UPLOAD_BL0,labels['c_d0up']))
    rep=dict(format='RZ1',raw_bytes=len(raw),packed_bytes=len(blob),window=WIN,
             chunk_bytes=3*CHUNK,scratch=hex(slot),scratch_bytes=size,ring=hex(RING),state=hex(S),
             loader=hex(la),decoder_bytes=len(code),raw_sha256=hashlib.sha256(raw).hexdigest(),
             native_sha256=hashlib.sha256(original).hexdigest(),itcm_bytes=0)
    report['dspzip']=rep
    report['core0']=dict(labels={k:hex(v) for k,v in labels.items() if k.startswith('c_') or k=='dz_fill'},
        blocks=[hex(la)],ld=hex(core0.LD),ld_words=len(lw),segs=[(hex(a),len(ws)) for a,ws in segs])
    assert raw_stream(img)==raw
    return labels

def _pack(raw: bytes) -> bytes:
    n = len(raw)
    best = [(0, 0)] * n
    heads: dict = {}
    for i in range(n):
        bl_, bo = 0, 0
        chain = heads.get(raw[i:i + 3])
        if chain and i + 3 <= n:
            for k in range(len(chain) - 1, max(-1, len(chain) - 1 - 2048), -1):
                j = chain[k]
                if i - j > WIN:
                    break
                ln = 0
                while ln < MAXL and i + ln < n and raw[j + ln] == raw[i + ln]:
                    ln += 1
                if ln > bl_:
                    bl_, bo = ln, i - j
                if ln == MAXL:
                    break
        best[i] = (bl_, bo)
        heads.setdefault(raw[i:i + 3], []).append(i)
    INF = 1 << 60
    cost = [INF] * (n + 1)
    cost[n] = 0
    pick = [0] * n                                   # 0 = literal, else the match length
    for i in range(n - 1, -1, -1):
        c, p = 9 + cost[i + 1], 0
        ln = best[i][0]
        for m in range(3, ln + 1):
            mc = (25 if m >= 10 else 17) + cost[i + m]
            if mc < c:
                c, p = mc, m
        cost[i], pick[i] = c, p
    out, flags, items, i, nf = bytearray(), 0, bytearray(), 0, 0
    while i < n:
        ln = pick[i]
        if ln == 0:
            flags |= 1 << nf
            items.append(raw[i])
            i += 1
        else:
            o = best[i][1] - 1
            code = 7 if ln >= 10 else ln - 3
            items += bytes([o & 0xFF, (o >> 8) | code << 5])
            if code == 7:
                items.append(ln - 10)
            i += ln
        nf += 1
        if nf == 8:
            out.append(flags)
            out += items
            flags, items, nf = 0, bytearray(), 0
    if nf:
        out.append(flags)
        out += items
    return bytes(out)


def unpack_stream(stream: bytes, size: int) -> bytes:
    out, i, flags = bytearray(), 0, 1
    while len(out) < size:
        if flags == 1:
            flags = stream[i] | 0x100
            i += 1
        lit = flags & 1
        flags >>= 1
        if lit:
            out.append(stream[i])
            i += 1
        else:
            t = stream[i] | stream[i + 1] << 8
            i += 2
            o, c = (t & 0x1FFF) + 1, t >> 13
            if c == 7:
                ln = 10 + stream[i]
                i += 1
            else:
                ln = c + 3
            for _ in range(ln):
                out.append(out[-o])
    assert len(out) == size
    return bytes(out)


def emit_one(a, E, imm32):
    a.label("c_dz")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(sub_sp_imm, 4)                                                    # AAPCS alignment at native calls
    E(mov_reg, 4, 1)                                                    # r4 = core
    imm32(3, S)
    E(adds_imm8, 0, 12)
    E(str_imm, 0, 3, 0)                                                 # src
    E(movs_imm, 2, 1)
    E(str_imm, 2, 3, 4)                                                 # flags: empty
    E(movs_imm, 2, 0)
    E(str_imm, 2, 3, 8)
    E(str_imm, 2, 3, 16)                                                # no match, write index 0
    E(subs_imm8, 0, 12)
    E(ldr_imm, 6, 0, 4)                                                 # r6 = the stream's words
    E(movs_imm, 5, 0)                                                   # r5 = words sent
    E(bl, WAIT)
    E(mov_reg, 0, 4)
    E(bl, SELECT)
    a.label("dz_lp")
    E(subs_reg, 7, 6, 5)
    E(cmp_imm, 7, CHUNK)
    E(b_cond, "dz_k", "le")
    E(movs_imm, 7, CHUNK)
    a.label("dz_k")
    E(adds_reg, 5, 5, 7)
    E(adds_reg, 1, 7, 7)
    E(adds_reg, 7, 1, 7)                                                # r7 = bytes of this chunk
    imm32(0, STAGE)
    E(mov_reg, 1, 7)
    E(bl, "dz_fill")
    imm32(0, STAGE)
    E(mov_reg, 1, 7)
    E(bl, SPI)
    E(bl, WAIT)
    E(cmp_reg, 5, 6)
    E(b_cond, "dz_lp", "lt")
    E(bl, WAIT)
    E(mov_reg, 0, 4)
    E(add_sp_imm, 4)
    E(pop_list, [4, 5, 6, 7])
    E(pop_list, [3])                                                    # lr back through r3
    E(mov_reg, 14, 3)
    E(b_w, END)


def emit_fill(a, E, imm32):
    # ---- dz_fill(dst, bytes): r0 dst, [sp] end, r1 the ring, r2 src, r3 flags, r4 match left, r5 match index, r6 write index, r7 byte
    a.label("dz_fill")
    E(push_list, [4, 5, 6, 7], lr=True)
    E(adds_reg, 1, 0, 1)
    E(push_list, [1])                                                   # [sp] = end
    imm32(7, S)
    E(ldr_imm, 2, 7, 0)
    E(ldr_imm, 3, 7, 4)
    E(ldr_imm, 4, 7, 8)
    E(ldr_imm, 5, 7, 12)
    E(ldr_imm, 6, 7, 16)
    imm32(1, RING)
    a.label("df_lp")
    E(ldr_sp, 7, 0)
    E(cmp_reg, 0, 7)
    E(b_cond, "df_x", "hs")
    E(cmp_imm, 4, 0)
    E(b_cond, "df_cp", "ne")
    E(cmp_imm, 3, 1)
    E(b_cond, "df_fl", "ne")
    E(ldrb_imm, 3, 2, 0)
    E(adds_imm8, 2, 1)
    E(movs_imm, 7, 1)
    E(lsls_imm, 7, 7, 8)
    E(orrs_reg, 3, 7)
    a.label("df_fl")
    E(lsrs_imm, 3, 3, 1)
    E(b_cond, "df_m", "cc")
    E(ldrb_imm, 7, 2, 0)
    E(adds_imm8, 2, 1)
    E(b, "df_put")
    a.label("df_m")
    E(ldrb_imm, 7, 2, 0)
    E(ldrb_imm, 5, 2, 1)
    E(adds_imm8, 2, 2)
    E(lsrs_imm, 4, 5, 5)
    E(lsls_imm, 5, 5, 27)
    E(lsrs_imm, 5, 5, 19)
    E(orrs_reg, 5, 7)                                                   # r4 = length code, r5 = offset - 1
    E(cmp_imm, 4, 7)
    E(b_cond, "df_s", "ne")
    E(ldrb_imm, 7, 2, 0)
    E(adds_imm8, 2, 1)
    E(adds_reg, 4, 4, 7)                                                # 7 + extra (+ 3 below = 10 + extra)
    a.label("df_s")
    E(adds_imm8, 4, 3)
    E(subs_reg, 5, 6, 5)
    E(subs_imm8, 5, 1)
    E(cmp_imm, 5, 0)
    E(b_cond, "df_nonnegative", "ge")
    E(adds_imm8, 5, WIN)
    a.label("df_nonnegative")
    a.label("df_cp")
    E(ldrb_reg, 7, 1, 5)
    E(adds_imm8, 5, 1)
    E(cmp_imm, 5, WIN)
    E(b_cond, "df_read_wrapped", "lo")
    E(subs_imm8, 5, WIN)
    a.label("df_read_wrapped")
    E(subs_imm8, 4, 1)
    a.label("df_put")
    E(strb_reg, 7, 1, 6)
    E(adds_imm8, 6, 1)
    E(cmp_imm, 6, WIN)
    E(b_cond, "df_write_wrapped", "lo")
    E(subs_imm8, 6, WIN)
    a.label("df_write_wrapped")
    E(strb_imm, 7, 0, 0)
    E(adds_imm8, 0, 1)
    E(b, "df_lp")
    a.label("df_x")
    imm32(7, S)
    E(str_imm, 2, 7, 0)
    E(str_imm, 3, 7, 4)
    E(str_imm, 4, 7, 8)
    E(str_imm, 5, 7, 12)
    E(str_imm, 6, 7, 16)
    E(add_sp_imm, 4)
    E(pop_list, [4, 5, 6, 7], pc=True)


