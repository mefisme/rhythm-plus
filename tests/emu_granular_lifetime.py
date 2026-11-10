"""Native reader position and release remain authoritative for Triggered grains."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from granular_lifetime_reference import run,R


def main():
    for length,start in ((1024,0),(2048,0),(2048,4096),(4096,1000)):
        native=run(sample_length=length,sample_start=start)
        routed=run(candidate=True,sample_length=length,sample_start=start)
        assert routed['trace']==native['trace']
        assert 0<sum(bool(row[0]) for row in routed['trace'])<160
    print('PASS One Shot grains end with the sample for every sample length and offset')
    for release in (None,20):
        native=run(loop=True,release_at=release)
        routed=run(candidate=True,loop=True,release_at=release)
        assert routed['trace']==native['trace']
        active=sum(bool(row[0]) for row in routed['trace'])
        assert active==160 if release is None else 20<=active<160
    gated=run(candidate=True,engine_mode=R.TEXTURE,sample_length=1024,release_at=40)
    assert 40<=sum(bool(row[0]) for row in gated['trace'])<160
    print('PASS Gated and Looped grains outlast a short sample and end at the note-off')
    texture=run(candidate=True,engine_mode=R.TEXTURE)
    assert all(row[0] for row in texture['trace'])
    assert len(set(row[2] for row in texture['trace']))==1
    print('PASS Texture audio continues past native reader end without advancing reader position')
    print('LIMIT: Texture activation/normal-note-off policy and transitions still need explicit owner; timing and physical memory remain unproved')
    print('ALL PASS')


if __name__=='__main__':main()
