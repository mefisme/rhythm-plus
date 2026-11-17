"""Core 0 idle counter for load measurement: Y:$1400 + 1 on each main-loop pass that finds no block to make.

Stock P:$1F5 returns at P:$201 while the output ring has no room for a block. P:$1FF `jge $202` becomes
`jlt IDLE` and P:$201 a nop, so the block path is unchanged. The counter is 24 bits and wraps.
Host read: core 0, address Y_IDLE | 0x8000.
"""
import core0

AT = 0x2090
Y_IDLE = 0x1400
STOCK = {0x1FF: [0x0AF0A1, 0x000202], 0x201: [0x00000C]}


def segments(native):
    for address, words in STOCK.items():
        assert native[address:address + len(words)] == words, hex(address)
    idle, _ = core0.asm_at([f"move y:>${Y_IDLE:x},a1", "add #>1,a", f"move a1,y:>${Y_IDLE:x}", "rts"], AT)
    branch, _ = core0.asm_at([("jcc", "lt", AT)], 0x1FF)
    return [(AT, idle), (0x1FF, branch), (0x201, [0])], dict(at=hex(AT), words=len(idle), y_idle=hex(Y_IDLE), host=hex(Y_IDLE | 0x8000))
