"""Track + stays open through actual stock page button, including length/duplicate actions."""
from pathlib import Path
import struct
import sys
import emu_tmenu as E


def main():
    stock, fw, ram = (Path(p).read_bytes() for p in sys.argv[1:4])
    uc, ref = E.setup(fw, ram), E.setup(stock, ram, False)
    t = E.sel(uc)
    so = E.u32(uc, E.T.CONT + E.T.STEPOBJ + 4*t)
    rso = E.u32(ref, E.T.CONT + E.T.STEPOBJ + 4*t)
    head = E.rhbuild.bl_target(bytearray(fw), E.C.LED_CALLS[0])
    refhead = E.rhbuild.bl_target(bytearray(stock), E.C.LED_CALLS[0])
    rec = E.u32(uc, E.T.AUTO + E.T.AUTO_RECS + 4*t)
    pats = E.u32(uc, rec+4)
    def frame(): return E.led(uc, head)
    def viewpage(u, obj): return u.mem_read(E.ptr(u, E.u32(u, obj+0x60), 0), 1)[0]
    def position(u, obj): return u.mem_read(E.ptr(u, E.u32(u, obj+0x18), 1), 1)[0]
    E.tap(uc, t); frame()
    E.tap(ref, t); E.led(ref, refhead)
    # Keep stock play stopped and seed the same first-page selection in both.
    for u, obj in ((uc, so), (ref, rso)):
        u.mem_write(E.ptr(u, E.C.TRANSPORT, 0), b'\0')
        u.mem_write(E.ptr(u, E.u32(u, obj+0x60), 0), b'\0')
    for i in range(4):
        E.press(uc, 21); E.release(uc, 21)
        E.press(ref, 21); E.release(ref, 21)
        f = frame(); E.led(ref, refhead)
        E.check(f'page press {i+1}: Track + remains open', E.b8(uc, E.T.O_OPEN) == 1)
        E.check(f'page press {i+1}: page and selection match stock', (viewpage(uc,so), position(uc,so)) == (viewpage(ref,rso), position(ref,rso)), (viewpage(uc,so), viewpage(ref,rso)))
        E.check(f'page press {i+1}: pattern bytes match stock page/length operation', bytes(uc.mem_read(pats,8*E.T.PAT_SIZE)) == bytes(ref.mem_read(pats,8*E.T.PAT_SIZE)))
        selected = position(uc,so)
        if selected >> 4 == viewpage(uc,so):
            E.check(f'page press {i+1}: selected white marker on shown page', f[selected & 15] in (0x1A,0x1B))
    # Existing Clear and Duplicate page gestures must still reach the stock.
    for name, bit in (('Duplicate',24),('Clear',23)):
        for u in (uc,ref):
            u.mem_write(E.C.CTRL+0xA0,struct.pack('<I',E.u32(u,E.C.CTRL+0xA0)|(1<<bit)))
            # The stock page controller also reads its modifier store; use the real button.
            E.press(u,bit)
            E.press(u,21); E.release(u,21)
            E.release(u,bit)
            u.mem_write(E.C.CTRL+0xA0,struct.pack('<I',E.u32(u,E.C.CTRL+0xA0)&~(1<<bit)))
        frame(); E.led(ref,refhead)
        E.check(f'{name} + page: Track + stays open',E.b8(uc,E.T.O_OPEN)==1)
        E.check(f'{name} + page: page and full pattern data match stock',viewpage(uc,so)==viewpage(ref,rso) and bytes(uc.mem_read(pats,8*E.T.PAT_SIZE))==bytes(ref.mem_read(pats,8*E.T.PAT_SIZE)))
    # Every knob page must keep its identity when the step page changes.
    for page in [i for i in E.PADMAP if i is not None]:
        E.pad(uc,E.pp(page));E.unpad(uc,E.pp(page));frame()
        E.press(uc,21);E.release(uc,21);frame()
        E.check(f'knob page {page+1}: step paging preserves menu and knob page',E.b8(uc,E.T.O_OPEN)==1 and E.b8(uc,E.T.O_PAGE)==page)
    # Hold the same physical pad on each step page: show that page's automation.
    E.pad(uc,E.T.PAD_PAGE0);E.unpad(uc,E.T.PAD_PAGE0);frame()
    uc.mem_write(E.SLOT+E.T.O_KNOB,b'\x03')
    for wanted_page, step, value in ((0,4,33),(1,20,100)):
        if viewpage(uc,so)!=wanted_page:
            E.press(uc,21);E.release(uc,21);frame()
        lane=E.lane_addr(uc,t,2,step)
        uc.mem_write(lane,bytes([value])+b'\xff'*5)
        before=bytes(uc.mem_read(pats,8*E.T.PAT_SIZE))
        E.pad(uc,4);frame()
        E.check(f'page {wanted_page+1}: pad 5 shows step {step+1} automation',E.b8(uc,E.T.O_AV)==value,(E.b8(uc,E.T.O_AV),value))
        E.check(f'page {wanted_page+1}: selecting automation does not add a note',bytes(uc.mem_read(pats,8*E.T.PAT_SIZE))==before)
        E.unpad(uc,4);f=frame()
        E.check(f'page {wanted_page+1}: released selection marker stays on pad 5',f[4] in (0x1A,0x1B),hex(f[4]))
    print('ALL PASS'  if not E.FAILS else f'{len(E.FAILS)} FAILED')
    if E.FAILS: raise SystemExit(1)


if __name__=='__main__':main()
