"""Compact absolute control flow for candidate code inside DSP1's4K program space.

Uses the stock instruction forms: JMP Cxxx, JSR Dxxx, Jcc E<cc>xxx.
No submodule changes; data instructions and DO labels use the existing assembler.
"""
import core0
from rhdsppatch import CC


def assemble(items,address):
    prepared=[];fixups=[]
    for item in items:
        if isinstance(item,tuple) and item[0] in ('jmp','jsr','jcc'):
            name=f'_gshort_{len(fixups)}'
            if item[0]=='jcc':opcode,target=0x0e0000|(CC[item[1]]<<12),item[2]
            else:opcode,target=(0x0c0000 if item[0]=='jmp' else 0x0d0000),item[1]
            prepared += [('label',name),('words',[0])];fixups.append((name,opcode,target))
        else:prepared.append(item)
    words,labels=core0.asm_at(prepared,address)
    assert 0<=address<address+len(words)<=0x1000
    for name,opcode,target in fixups:
        target=labels[target] if isinstance(target,str) else target
        assert 0<=target<0x1000
        words[labels[name]-address]=opcode|target
    return words,{name:value for name,value in labels.items() if not name.startswith('_gshort_')}
