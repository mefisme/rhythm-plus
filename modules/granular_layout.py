"""Explicit candidate allocation for the in-place engine, checked against A0122.

The shared tail follows stock's last known control fields (37310); Remix's
envexp formerly used 37400. We exclude that feature, rather than sharing its
storage. This is a static integration candidate, not a hardware canary result.
The context manager relocates generators only; it never writes a device.
"""
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    core: int
    space: str
    start: int
    words: int
    owner: str

    @property
    def end(self):return self.start+self.words


REGIONS=(
    Region(-1,'shared',0x37400,32,'granular route controls'),
    Region(-1,'shared',0x37420,64,'granular native snapshots'),
    Region(1,'y',0x1f80,7,'granular snapshot saves'),
    Region(1,'y',0x1f90,8,'granular accepted-note serials'),
    Region(1,'y',0x1f98,2,'granular note scratch'),
    Region(1,'y',0x1f9a,1,'granular Flow scratch'),
    Region(0,'x',0x1400,256,'granular working controls and voice'),
    Region(0,'x',0x1500,256,'granular sample copy'),
    Region(0,'y',0x1410,32,'granular sum'),
    # Register saves 1440..1457 are already owned by c0fx: sequential use only.
    Region(0,'y',0x1f80,48,'granular bound grain sources'),
    Region(0,'y',0x1fb0,16,'granular per-grain pitch ratios'),
    Region(0,'y',0x1fc0,13,'granular latched controls and lifetime'),
    Region(0,'x',0x2400,2048,'granular persistent track contexts'),
    Region(0,'y',0x2800,640,'granular persistent grain metadata'),
    Region(0,'y',0x2b00,226,'granular narrow host mailbox'),
    Region(0,'y',0x1f40,24,'granular pool outer register saves'),
    Region(0,'y',0x1fd0,5,'granular pool scheduling scratch'),
    Region(0,'y',0x1fd8,2,'granular first-pass flag and r0 save'),
)


def validate(report):
    import dspmap
    if any(name in report for name in ('envexp','granchain','autoprot','autobank')) or ('granular' in report and report['granular'].get('integration_version')!=1):
        raise ValueError('incompatible legacy engine or diagnostic allocation')
    old=dspmap.regions({key:value for key,value in report.items() if key!='granular'})
    for i,region in enumerate(REGIONS):
        if region.space=='shared':
            assert 0x37330<=region.start<region.end<=0x38000
        else:
            assert 0<=region.start<region.end<=dspmap.SIZE[region.core,region.space]
            for other in old:
                if (region.core,region.space)==(other.core,other.space):
                    assert not(region.start<other.end and other.start<region.end),(region,other)
        for other in REGIONS[:i]:
            if (region.core,region.space)==(other.core,other.space):
                assert not(region.start<other.end and other.start<region.end),(region,other)
    assert report['c0fx']['mix'] is False
    return REGIONS


@contextmanager
def allocated():
    import granular_route_candidate as R
    import granular_snapshot_candidate as S
    import granular_note_candidate as N
    import granular_inplace_candidate as I
    import granular_flow_candidate as F
    changes=((R,'CONTROL',0x37400),(I,'CONTROL',0x37400),(S,'CONTROL',0x37400),
             (S,'SNAPSHOT',0x37420),(I,'SNAPSHOT',0x37420),
             (S,'SAVE',0x1f80),(N,'SERIAL',0x1f90),(S,'SERIAL',0x1f90),
             (N,'TEMP',0x1f98),(F,'SAVE',0x1f9a))
    old=[getattr(module,name) for module,name,value in changes]
    try:
        for module,name,value in changes:setattr(module,name,value)
        yield
    finally:
        for (module,name,value),previous in zip(changes,old):setattr(module,name,previous)
