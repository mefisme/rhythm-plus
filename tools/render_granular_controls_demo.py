"""Synthetic-source comparison of the offline stock-controlled grain reference."""
from pathlib import Path
import json
from granular_voice_reference import controls
from render_granular_reference import fixture,render,wav,RATE
from granular_stock_reference import process


def main():
    destination=Path(__file__).resolve().parents[1]/'buildtmp/granular-controls'
    destination.mkdir(parents=True,exist_ok=True)
    source=fixture();settings=dict(size=90,dens=55,pos=42,scan=12,spr=24,pspr=0,win=50)
    cases=[('full-region',{},{}),('cropped-region',dict(start=32,length=48),{}),
           ('cropped-octave',dict(start=32,length=48,note=72),{}),
           ('stock-shaping',dict(start=32,length=48,note=72),dict(lp=60,resonance=70,distortion=30))]
    report=dict(scope='Offline actual DSP grain renderer and stock processing; synthetic source; not firmware',
                order=[case[0] for case in cases],sample_rate=RATE,gap_seconds=.12,settings=settings,clips={})
    comparison=[]
    for name,knobs,shaping in cases:
        snapshot=controls(**knobs)
        grains,render_info=render(source,.75,settings,stock_snapshot=snapshot)
        audio,process_info=process(grains,**shaping)
        metrics=wav(destination/(name+'.wav'),audio)
        report['clips'][name]=dict(knobs=knobs,stock_snapshot=snapshot,shaping=shaping,
                                  renderer_words=render_info['renderer_words'],**metrics)
        comparison+=audio+[0]*round(.12*RATE)
    report['comparison']=wav(destination/'comparison.wav',comparison)
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
