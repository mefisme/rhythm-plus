"""Host-only copy-on-write proof; not a DSP driver or a changed firmware format.

Candidate safety policy:224 physical payload blocks,208 charged data blocks,
16 staging blocks sufficient for a complete384-event pattern. No extra ARM copy.
Readers access only the published view; one serialized worker owns all mutations.
"""
from copy import deepcopy
from automation_model import Bank,Event,pack_block


class TransactionBank:
    def __init__(self):
        self.view=(Bank(payload_blocks=208),tuple(() for _ in range(64)))
        self.words=[0]*(224*32)

    def events(self,index):
        bank,chains=self.view
        from automation_model import unpack_block
        result=[]
        for block in chains[index]:
            result.extend(unpack_block(self.words[block*32:block*32+32]))
        return result[:len(bank.patterns[index].events)]

    def edit(self,index,operation,fail_after=None):
        """Failure after N successful word writes never publishes the candidate.

        An interrupted staging write may leave garbage in free blocks; no live
        chain points to it. No persistent metadata is assumed across reboot.
        """
        if not 0<=index<64 or fail_after is not None and fail_after<0:
            raise ValueError('invalid transaction')
        bank,chains=self.view;candidate=deepcopy(bank)
        operation(candidate)
        if any(candidate.patterns[i]!=bank.patterns[i] for i in range(64) if i!=index):
            raise ValueError('one-pattern transaction required')
        if candidate.patterns[index]==bank.patterns[index]:return True
        source=sorted(candidate.patterns[index].events.values())
        need=(len(source)+23)//24
        owned={block for chain in chains for block in chain}
        free=[block for block in range(224) if block not in owned]
        assert len(owned)<=208 and len(free)>=16 and need<=16
        target=tuple(free[:need]);written=0
        for number,block in enumerate(target):
            chunk=source[number*24:(number+1)*24]
            chunk+= [Event(0,0,0)]*(24-len(chunk))
            for offset,word in enumerate(pack_block(chunk)):
                if written==fail_after:return False
                assert block not in owned
                self.words[block*32+offset]=word;written+=1
        if written==fail_after:return False
        published=list(chains);published[index]=target
        # One reference publication models serialized metadata ownership only.
        self.view=(candidate,tuple(published))
        return True
