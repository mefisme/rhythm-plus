"""Offline adapter: stock-resolved region and Q15 pitch increment into grains.

Single engine, emulator-only control mailbox. Not a firmware allocation or bridge.
Per-grain binding keeps old regions with old grains; native ratio is used without
rounding to semitones. A tighter copy bound supports stock pitch extremes in the existing256-word scratch.
Native reverse is mapped through the region; sub8-sample regions remain rejected.
"""
import granular0 as G
import granular_source_binding as binding

CONTROL=0x1fc0
REVERSE=CONTROL+12
GRAIN_RATIO=binding.META+binding.WORDS
# floor(32*q)+3 must fit the existing scratch buffer in either direction.
SAFE_RATIO=((G.LB_N-2)<<14)-1
# Free words in the voice state: live grains this block, smoothed output gain.
V_LIVE,V_SMOOTH=29,30
# Voice word 31: bit 0 Bounce direction, bits 1..6 the last Timing sync seen.
V_MOTION=31
# Lock: its own random state, the next of 16 grain steps, 16 seeds of 12 bits (two a word, even step high).
LOCK_RNG,LOCK_STEP,LOCK_SEEDS=G.GB+0x11,G.GB+0x12,G.GB+0x13
# Field 1 (replaces Gate): samples between grains (0 = Density), sync count << 18.
# Field 8 (replaces Fine): Size Scatter, Jitter << 8, step chance << 16.
TIMING,SCATTER=G.P_GATE,G.P_FINE
PITCH_SETS=((0,),(0,7),(0,3,7),(0,4,7))


def sound(result,tab_at):
    live,smooth=f'x:(r7+${V_LIVE:x})',f'x:(r7+${V_SMOOTH:x})'
    # Overlap in 1/16 grains: 2 + Density^2 x 254 / 10000, Density 0..100.
    at=result.index(f'move x:(r6+${G.P_DENS:x}),x0',result.index(('label','g_von')))
    end=result.index(f'move x0,x:(r7+${G.V_GAIN:x})',at)+1
    result[at:end]=[f'move x:(r6+${G.P_DENS:x}),x0','mpy x0,x0,a','asr a','move a0,x1','move #>$1a01,y0',
                    'mpy x1,y0,a','asr a','asr #18,a,a','move a0,a','add #>$2,a',
                    'move #>$10,x0','move x0,b','asl #4,b,b','cmp b,a','tgt b,a','move a1,x0','clr a',
                    f'move x:(r7+${G.V_LGB:x}),a0','asl #4,a,a',('jsr','g_udiv'),f'move a0,x:(r7+${G.V_I:x})']
    # Grains peak at full scale; the block gain below sets the level.
    at=result.index(f'move x:(r7+${G.V_GAIN:x}),a0')
    result[at]='move #>$7fffff,a0'
    # Edge 0 gives one-sample fades.
    at=result.index('add #>$5,a',result.index(('label','g_w0')))
    result[at:at+1]=['tst a',('jcc','eq','stock_edge_hard'),'add #>$5,a',('label','stock_edge_hard')]
    # Square the fade so it leaves zero with zero slope. 16 grains cannot clip after >> 4.
    start=result.index('do x1,${g_e:x}')
    at=result.index('move b1,y1',start)
    result[at:at+1]=['move b1,y0','mpy y0,y0,b','move b1,y1']
    at=result.index('mpy x0,y1,b',start)+1
    result[at:at]=['asr #4,b,b']
    # Clean: FIR over the copied source before a pitch rise of x1.5 or more.
    at=result.index(('jsr','g_pcopy'),result.index(('label','g_grain')))+1
    result[at:at]=['move x:(r6+$d),x1','btst #$2,x1',('jcc','cs','stock_clean_done'),
                   f'move x:(r2+${G.G_IH:x}),b',f'move x:(r2+${G.G_IL:x}),b0','abs b','asl b',
                   'cmp #>$3,b',('jcc','lt','stock_clean_done'),
                   'move r5,a',f'sub #>${G.LB:x},a','sub #>$1,a','tst a',('jcc','le','stock_clean_done'),
                   'move a1,x1',('jsr','stock_fir'),'cmp #>$6,b',('jcc','ge','stock_clean_done'),
                   ('jsr','stock_fir'),('label','stock_clean_done')]
    at=result.index('rts',result.index(('label','g_pcx')))+1
    result[at:at]=[('label','stock_fir'),f'move #>${G.LB:x},r4',f'move #>${G.LB+1:x},r5','nop','move x:(r4),a',
                   'do x1,${stock_fir_end:x}','move x:(r5)+,x0','add x0,a','asr a','move a,x:(r4)+','move x0,a',
                   ('label','stock_fir_end'),'rts']
    at=result.index(('label','g_grain'))+1
    result[at:at]=[f'move {live},a','add #>$1,a',f'move a1,{live}']
    at=result.index('do #$10,${g_gl:x}')
    result[at:at]=['clr a',f'move a,{live}']
    # Field 14: Q23 output gain / 8; 0 is the reference. Gain follows the live
    # grain count, reaching the new value over about 4 blocks.
    at=result.index(('label','g_out'))+1
    result[at:at]=[f'move {live},a','tst a',('jcc','gt','stock_gain_live'),'move #>$1,a',('label','stock_gain_live'),
                   'sub #>$1,a',f'add #>${tab_at["GAIN_T"]:x},a','move a1,r0','nop','move p:(r0),y0',
                   'move x:(r6+$e),a','tst a',('jcc','ne','stock_gain_level'),'move #>$100000,a',('label','stock_gain_level'),
                   'move a1,x0','mpy y0,x0,a',f'move {smooth},b','tst b',('jcc','ne','stock_gain_ramp'),'move a1,b',
                   ('label','stock_gain_ramp'),'sub b,a','asr #7,a,a','move a,x1',
                   f'move x:(r7+${G.V_BUF:x}),r0','nop','do #$20,${stock_gain_end:x}',
                   'add x1,b','move b,y0','move y:(r0),x0','mpy y0,x0,a','asl #7,a,a','move a,y:(r0)+',
                   ('label','stock_gain_end'),f'move b1,{smooth}']


def motion(result):
    timing,mix,flags,word=f'x:(r6+${TIMING:x})',f'x:(r6+${SCATTER:x})','x:(r6+$d)',f'x:(r7+${V_MOTION:x})'
    interval,countdown=f'x:(r7+${G.V_I:x})',f'x:(r7+${G.V_CD:x})'
    at=result.index(f'move x:(r6+${G.P_GATE:x}),a')
    end=result.index(('label','g_gd'),at)
    assert result[at+1:at+3]==['tst a',('jcc','ne','g_fol')]
    result[at:end]=[f'move #>${G.ONE:x},x0',f'move x0,x:(r7+${G.V_GLV:x})']
    at=result.index(f'move x:(r6+${G.P_FINE:x}),x0')
    assert result[at+1]=='add x0,a'
    del result[at:at+2]
    # A sync pulls the next grain to the grid, unless one has just played.
    at=result.index(f'move a0,{interval}')+1
    result[at:at]=[f'move {timing},a','and #>$3ffff,a',('jcc','eq','stock_timing_off'),f'move a1,{interval}',
                   f'move {timing},a','asr #18,a,a','and #>$3f,a','move a1,x1',f'move {word},b','asr b','and #>$3f,b',
                   'cmp x1,b',('jcc','eq','stock_timing_off'),
                   'asl a',f'move {word},b','and #>$1,b','move b1,x0','or x0,a',f'move a1,{word}',
                   f'move {countdown},a','tst a',('jcc','eq','stock_timing_off'),
                   f'move {interval},x0','move x0,b','asr b','cmp b,a',('jcc','gt','stock_timing_recent'),
                   'move #>$1,a',('jmp','stock_timing_set'),('label','stock_timing_recent'),'move x0,a',
                   ('label','stock_timing_set'),f'move a1,{countdown}',('label','stock_timing_off')]
    # Bounce: the playhead reverses at each end of the zone.
    at=result.index(f'move x:(r7+${G.V_PL:x}),b0',result.index('asl #18,a,a'))+1
    result[at:at]=[f'move {flags},x1','btst #$4,x1',('jcc','cc','stock_scan_wrap'),
                   f'move {word},x1','btst #$0,x1',('jcc','cc','stock_bounce_up'),'neg a',('label','stock_bounce_up'),
                   'add a,b',f'move x:(r7+${G.V_Z:x}),x0','tst b',('jcc','lt','stock_bounce_low'),
                   'cmp x0,b',('jcc','lt','g_w2'),'neg b','add x0,b','add x0,b',('jmp','stock_bounce_flip'),
                   ('label','stock_bounce_low'),'neg b',('label','stock_bounce_flip'),
                   f'move {word},a','move #>$1,x1','eor x1,a',f'move a1,{word}',
                   'tst b',('jcc','lt','stock_bounce_clear'),'cmp x0,b',('jcc','lt','g_w2'),
                   ('label','stock_bounce_clear'),'clr b',('jmp','g_w2'),('label','stock_scan_wrap')]
    # Timing steps play by chance, except the first grain of a voice (countdown -32).
    at=result.index(('jsr','g_spawn'))
    result[at:at]=['move #>$ffffe0,x0','cmp x0,a',('jcc','eq','stock_step_play'),
                   f'move {timing},a','and #>$3ffff,a',('jcc','eq','stock_step_play'),
                   ('jsr','g_rnd'),'clr a','move x0,a1','lsr #17,a','move a1,x1',
                   f'move {mix},a','asr #16,a,a','and #>$ff,a','move a1,a','cmp x1,a',('jcc','le','stock_step_skip'),
                   ('label','stock_step_play')]
    at=result.index(('jsr','g_spawn'),at)+1
    result[at:at]=[('label','stock_step_skip')]
    # Jitter moves the next grain by up to one interval either way.
    at=result.index(f'move {interval},x0',at)
    assert result[at+1]=='add x0,a'
    result[at:at+2]=[f'move {mix},a','asr #8,a,a','and #>$7f,a',('jcc','eq','stock_jitter_off'),
                     ('jsr','g_rnd'),f'move {mix},a','asr #8,a,a','and #>$7f,a','asl #16,a,a','move a1,y0','mpy y0,x0,a',
                     'move a1,y0',f'move {interval},x0','mpy y0,x0,a',f'move {interval},x0','add x0,a',('jmp','stock_jitter_add'),
                     ('label','stock_jitter_off'),f'move {interval},a',('label','stock_jitter_add'),
                     'move a1,x0',f'move {countdown},a','add x0,a']
    # Size Scatter shortens each grain by a random part of its length, to 32 samples at least.
    length=f'x:(r7+${G.V_LGG:x})'
    at=result.index(f'move x0,{length}',result.index(('label','g_spawn')))+1
    result[at:at]=[f'move {mix},a','and #>$7f,a',('jcc','eq','stock_scatter_off'),
                   ('jsr','g_rnd'),'move x0,a','abs a','move a1,x0',f'move {mix},a','and #>$7f,a','asl #16,a,a','move a1,y0',
                   'mpy y0,x0,a','move a1,y0',f'move {length},x0','mpy y0,x0,a','move x0,b','sub a,b',
                   'move #>$20,x0','cmp x0,b','tlt x0,b',f'move b1,{length}',('label','stock_scatter_off')]
    # Pitch Set snaps the scatter (b1, 1/64 semitone, within one octave) to chord tones.
    at=result.index('move #>$300,x0',result.index(('label','g_spawn')))+2
    assert result[at-1]=='mpy x1,x0,b'
    result[at:at]=[f'move {flags},a','asr #5,a,a','and #>$7,a',('jcc','eq','stock_set_off'),'sub #>$1,a',
                   'move a1,x0','move #>$19,x1','mpy x1,x0,a','asr a','move a0,x0','move b1,b','add #>$20,b','asr #6,b,b',
                   'add #>$c,b','add x0,b','add #>${stock_pitch_sets:x},b','move b1,r0','nop','move p:(r0),b','asl #6,b,b',
                   ('label','stock_set_off')]
    result += [('label','stock_pitch_sets'),('words',pitch_sets())]


def lock(result):
    # Field 13 bits 8..14 Lock, 0 off. Each grain step reseeds the grain random
    # numbers from its seed; a seed changes with chance (127 - Lock) / 128.
    countdown=f'x:(r7+${G.V_CD:x})'
    at=result.index('move #>$ffffe0,x0',result.index(('label','g_sp')))
    result[at:at]=['move x:(r6+$d),a','asr #8,a,a','and #>$7f,a',('jcc','eq','stock_lock_off'),'move a1,y1',
        f'move x:>${LOCK_RNG:x},x0',f'move x0,x:>${G.RNG:x}',('jsr','g_rnd'),f'move x0,x:>${LOCK_RNG:x}',
        f'move x:>${LOCK_STEP:x},a','move a1,x1','add #>$1,a','and #>$f,a',f'move a1,x:>${LOCK_STEP:x}',
        'move x1,a','asr a',f'add #>${LOCK_SEEDS:x},a','move a1,r0','nop','move x:(r0),b',
        'btst #$0,x1',('jcc','cs','stock_lock_low'),'move b1,a','asr #12,a,a',('jmp','stock_lock_half'),
        ('label','stock_lock_low'),'move b1,a',('label','stock_lock_half'),'and #>$fff,a','move a1,y0',
        ('jcc','eq','stock_lock_new'),
        'move #>$7f,a','sub y1,a','move a1,y1','clr a','move x0,a1','and #>$7f,a','cmp y1,a',('jcc','ge','stock_lock_keep'),
        ('label','stock_lock_new'),'move x0,a','asr #11,a,a','and #>$fff,a','or #>$1,a','move a1,y0',
        'btst #$0,x1',('jcc','cs','stock_lock_put_low'),
        'move b1,a','and #>$fff,a','move a1,x0','move y0,a','asl #12,a,a','or x0,a',('jmp','stock_lock_put'),
        ('label','stock_lock_put_low'),'move b1,a','and #>$fff000,a','move y0,x0','or x0,a',
        ('label','stock_lock_put'),'move a1,x:(r0)',
        ('label','stock_lock_keep'),'move y0,a','asl #12,a,a','or #>$5a5,a',f'move a1,x:>${G.RNG:x}',
        ('label','stock_lock_off'),f'move {countdown},a']
    # A new voice starts its Lock steps from the first.
    at=result.index(f'move a,x:(r7+${G.V_CD:x})',result.index(('label','g_voice')))+1
    result[at:at]=[f'move a,x:>${LOCK_STEP:x}']


def slice_start(result):
    # Field 13 bits 15..18 slices - 1, 0 off: a grain starts at the start of its slice,
    # moved on by the step in bits 19..22 and kept inside the region.
    at=result.index(f'move b1,x:(r7+${G.V_SPR:x})',result.index(('label','g_sc1')))
    result[at:at]=['move x:(r6+$d),a','asr #15,a,a','and #>$f,a',('jcc','eq','stock_slice_off'),'add #>$1,a',
        'move a1,y1','move b1,y0',f'move x:(r7+${G.V_L:x}),a','sub #>$4,a','move a1,x1',
        'clr a','move x1,a0','move y1,x0',('jsr','g_udiv'),'clr b','move a0,b1','tst b',('jcc','eq','stock_slice_whole'),
        'move b1,x1','clr a','move y0,a0','move x1,x0',('jsr','g_udiv'),
        'move a0,b','move y1,a','sub #>$1,a','move a1,x0','cmp x0,b','tgt x0,b',
        'move x:(r6+$d),a','asr #19,a,a','and #>$f,a','move a1,x0','add x0,b',
        'move y1,x0','cmp x0,b',('jcc','lt','stock_slice_in'),'sub x0,b',('label','stock_slice_in'),
        'move b1,x0','mpy x0,x1,a','asr a','move a0,b',
        f'move x:(r7+${G.V_L:x}),a','sub #>$4,a',f'move x:(r7+${G.V_SPAN:x}),x0','sub x0,a','move a1,x0','cmp x0,b','tgt x0,b',
        ('jmp','stock_slice_off'),
        ('label','stock_slice_whole'),'move y0,b',('label','stock_slice_off')]


def pitch_sets():
    # Semitones -12..12 snapped to the nearest tone of each set, in all octaves.
    words=[]
    for chord in PITCH_SETS:
        tones=[octave*12+tone for octave in range(-2,3) for tone in chord]
        words += [min(tones,key=lambda t:(abs(t-s),abs(t)))&0xffffff for s in range(-12,13)]
    return words


def items(source,latched_source=False,raw_output=None,grain_cap=None,tab_at=None):
    result=binding.items(source)
    sound(result,tab_at)
    # Field 13 bit 3: no new grains, so the ones playing finish with their own fades.
    at=result.index(('jsr','g_spawn'))
    result[at:at+1]=['move x:(r6+$d),x1','btst #$3,x1',('jcc','cs','stock_spawn_held'),('jsr','g_spawn'),('label','stock_spawn_held')]
    motion(result)
    lock(result)
    slice_start(result)
    # Convert the 12-word grain offset to a slot index. The rounded-up Q23
    # reciprocal gives the exact quotient for all 16 valid offsets.
    ratio_address=['move r2,x0',f'move #>${G.GR0:x},a','neg a','add x0,a',
                   'move a1,x0','move #>$aaaab,x1','mpy x0,x1,a',
                   f'add #>${GRAIN_RATIO:x},a','move a1,r4']
    combine=G.note_q()
    at=result.index(combine[0],result.index(('label','g_sok')))
    result[at:at]=ratio_address+[f'move x:(r7+${G.V_Q:x}),x0','move x0,y:(r4)']
    at=result.index(('label','g_grain'))+1
    result[at:at]=[f'move #>${G.LB:x},r5','clr a','do #$100,${stock_copy_clear:x}',
                   'move a,x:(r5)+',('label','stock_copy_clear')]
    at=result.index(('label','g_smp'))+1
    result[at:at]=[f'move y:>${CONTROL:x},x0',f'move x0,x:(r7+${G.V_S:x})',
                   f'move y:>${CONTROL+1:x},x0',f'move x0,x:(r7+${G.V_L:x})']
    # Position is a position within the native region, not the old offset of a
    # smaller Zone. With Zone=127 that old control otherwise did nothing.
    at=result.index(f'move x:(r6+${G.P_POS:x}),a')
    assert result[at-2]=='sub b,a'
    result[at-2]='sub #>$4,a'
    # Combine scan phase and position circularly before the grain-span clamp.
    at=result.index(('label','g_sc1'))-3
    assert result[at]=='tst b'
    result[at:at]=[f'move x:(r7+${G.V_L:x}),a','sub #>$4,a','move a1,x0',
                   'cmp x0,b',('jcc','lt','stock_pos_negative'),'sub x0,b','cmp x0,b',
                   ('jcc','lt','stock_pos_negative'),'sub x0,b',('label','stock_pos_negative'),
                   'tst b',('jcc','ge','stock_pos_wrapped'),'add x0,b',('label','stock_pos_wrapped')]
    if raw_output is not None:
        at=result.index(f'move a1,x:(r7+${G.V_BUF:x})')
        result[at:at+1]=[f'move #>${raw_output:x},a',f'move a1,x:(r7+${G.V_BUF:x})']
    if latched_source:
        at=result.index(f'add #>${G.PAR0:x},a')
        at=result.index('move y:(r0),a',at)
        result[at]=f'move y:>${CONTROL+3:x},a'
    # Replace conservative integer-only copy sizing. Fractional sizing supports
    # the stock ~7.9x maximum without writing258 words into a256-word buffer.
    at=result.index(f'move x:(r2+${G.G_PH:x}),a',result.index(('label','g_grain')))
    end=result.index(('label','g_gcp'),at)
    result[at:end]=[
        *ratio_address,'move y:(r4),x0',f'move y:>${CONTROL+2:x},x1',*combine[2:-1],
        'move b1,a','asr #19,a,a',f'move x:(r2+${G.G_IH:x}),b','tst b',
        ('jcc','ge','stock_rate_forward'),'neg a',('label','stock_rate_forward'),
        f'move a1,x:(r2+${G.G_IH:x})',f'move a0,x:(r2+${G.G_IL:x})',
        f'move x:(r2+${G.G_PH:x}),a',f'move x:(r2+${G.G_IH:x}),b',
        'tst b',('jcc','lt','g_gneg'),'move a1,y1','asl #5,b,b',
        f'move x:(r2+${G.G_IL:x}),a','lsr #19,a','move a1,x0',
        'add x0,b','add #>$3,b','move y1,a',('jmp','g_gcp'),
        ('label','g_gneg'),'move a1,y1','asl #5,b,b',
        f'move x:(r2+${G.G_IL:x}),a','lsr #19,a','move a1,x0',
        'add x0,b','move y1,a','add b,a','neg b','add #>$4,b',
        'move #>$100,x0','cmp x0,b','tgt x0,b']
    # Native reverse maps the grain's position through the region as well as
    # reversing its direction. Grain-level reverse chance remains independent.
    at=result.index(f'move b1,x:(r7+${G.V_SPR:x})',result.index(('label','g_sc1')))+1
    result[at:at]=[f'move y:>${REVERSE:x},a','tst a',('jcc','eq','stock_direction'),
                   f'move x:(r7+${G.V_L:x}),a','sub #>$4,a',f'move x:(r7+${G.V_SPAN:x}),x0',
                   'sub x0,a','sub b,a',f'move a1,x:(r7+${G.V_SPR:x})',('label','stock_direction')]
    at=result.index(f'move b1,x:(r7+${G.V_REV:x})')
    result[at:at]=[f'move y:>${REVERSE:x},x0','eor x0,b']
    if grain_cap is not None:
        # Limit density compensation, available spawn slots and the render loop
        # together. The pool wrapper retires slots above a reduced cap first.
        at=result.index('move #>$10,x0',result.index(('label','g_von')))
        result[at]=f'move y:>${grain_cap:x},x0'
        at=result.index('move #>$10,b',result.index(('label','g_spawn')))
        result[at]=f'move y:>${grain_cap:x},b'
        at=result.index('do #$10,${g_gl:x}')
        result[at:at+1]=[f'move y:>${grain_cap:x},b','do b,${g_gl:x}']
    return result


def gain_table():
    # 1/sqrt(live grains); 0.8 restores the RMS that the squared fade removes.
    return [round(.8/d**.5*(1<<23)) for d in range(1,17)]


def note_lgb(tab_at,V=G.X):
    return [f'move y:>${CONTROL+2:x},x0',f'move x0,{V("r7",G.V_R)}',
            f'move {V("r7",G.V_LGB)},a','asr #5,a,a',('jsr','g_udiv'),
            f'move a0,{V("r7",G.V_LGB)}']


def words(snapshot,source_length):
    begin,end,increment=(snapshot[k] for k in ('start','end','increment'))
    begin,end=min(begin,end),max(begin,end)
    if not 0<=begin<end<=source_length or end-begin<8:
        raise ValueError('offline adapter requires a region of at least8 samples')
    ratio=increment<<4  # Stock Q15 -> renderer Q19, exactly.
    if not 0<ratio<=SAFE_RATIO:
        raise ValueError('ratio exceeds the bounded renderer range; do not silently clamp')
    return [begin,end-begin,ratio]


def code(*,latched_source=False,raw_output=None,code_at=None,grain_cap=None):
    original_items,original_note,original_max,original_code,original_tables=G.items,G.note_lgb,G.Q_MAX,G.CODE,G.tables
    try:
        G.items=lambda *a,**k:items(original_items(*a,**k),latched_source,raw_output,grain_cap,a[0] if a else k['tab_at'])
        G.note_lgb=note_lgb
        G.Q_MAX=SAFE_RATIO
        G.tables=lambda:{**original_tables(),'GAIN_T':gain_table()}
        if code_at is not None:G.CODE=code_at
        return G.code(note=True)
    finally:G.items,G.note_lgb,G.Q_MAX,G.CODE,G.tables=original_items,original_note,original_max,original_code,original_tables
