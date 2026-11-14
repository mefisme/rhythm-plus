/* Offline Cortex-M7 owner candidate. No global state or firmware installation.
 * Caller must perform returned actions in order: invalidate/stop, then wait for
 * both DSP epoch acknowledgements before APPLY; APPLY precedes Texture START.
 */
#include <stdint.h>
#ifndef G_PAGE_PAD
#define G_PAGE_PAD 29
#endif
#ifndef G_EDITOR_SETTINGS
#define G_EDITOR_SETTINGS 0
#endif

enum { G_OFF=0,G_TRIGGERED=1,G_TEXTURE=2,G_QUIET=1,G_REPLACE=2,G_HELD=3,G_PASSHELD=5 };
enum { G_STOP=1,G_INVALIDATE=2,G_APPLY=4,G_START=8 };
typedef struct {
    uint32_t epoch,stop_note;
    uint8_t mode,wanted,phase,settings;
} GTrack;
typedef struct { GTrack track[8]; } GOwner;

uint32_t c_gr_owner_size(void) { return sizeof(GOwner); }
void c_gr_owner_init(GOwner *owner) {
    for(uint32_t t=0;t<8;t++) {
        owner->track[t]=(GTrack){.epoch=1};
    }
}
uint32_t c_gr_owner_request(GOwner *owner,uint32_t track,uint32_t mode,uint32_t serial) {
    if(track>=8 || mode>G_TEXTURE) return 0;
    GTrack *state=&owner->track[track];
    if(state->phase>=G_REPLACE) return 0;
    if(state->phase==G_QUIET) {
        state->wanted=(uint8_t)mode;
        // A start that never applied has no granular route to tear down.
        if(state->mode==G_OFF && mode==G_OFF) state->phase=0;
        return 0;
    }
    if(state->mode==mode) return 0;
    state->epoch=(state->epoch+1)&0xffffff;
    if(!state->epoch) state->epoch=1;
    state->stop_note=serial&0xffffff;
    state->wanted=(uint8_t)mode;
    state->phase=G_QUIET;
    return G_INVALIDATE|G_STOP;
}
uint32_t c_gr_owner_observe(GOwner *owner,uint32_t track,uint32_t consumer_epoch,
                          uint32_t producer_epoch,uint32_t active,uint32_t serial) {
    if(track>=8) return 0;
    GTrack *state=&owner->track[track];
    if((state->phase!=G_QUIET && state->phase!=G_REPLACE) || consumer_epoch!=state->epoch || producer_epoch!=state->epoch) return 0;
    /* A newer note serial does not prove our queued force stop was consumed:
     * that note may precede the stop. Block incoming starts during the barrier
     * and require actual idle, rather than applying over an old live voice.
     */
    (void)serial;
    if(active) return 0;
    state->mode=state->wanted;
    state->phase=state->phase==G_REPLACE?G_HELD:0;
    return G_APPLY|(state->mode==G_TEXTURE?G_START:0);
}
/* Reader returns one unshifted 24-bit word from shared DSP memory. The eventual
 * adapter supplies the stock locked accessor and startup/upload guards. Never
 * infer both-core completion from a native STATE tag alone. Re-read the header
 * so a publication/consumption during host reads cannot activate a torn mode.
 */
typedef uint32_t (*GRead)(uint32_t address);
uint32_t c_gr_owner_poll(GOwner *owner,uint32_t track,uint32_t base,GRead read) {
    if(track>=8 || (owner->track[track].phase!=G_QUIET && owner->track[track].phase!=G_REPLACE)) return 0;
    uint32_t frame=read(base+2),tag=read(base),epoch=read(base+1);
    if(tag!=0x674132 && tag!=0x674331 && tag!=0x674732) return 0;
    if(epoch!=owner->track[track].epoch) return 0;
    uint32_t serial=read(base+7);
    if(read(base+1)!=epoch || read(base)!=tag || read(base+2)!=frame) return 0;
    return c_gr_owner_observe(owner,track,epoch,epoch,tag!=0x674732,serial);
}
uint32_t c_gr_owner_forward(const GOwner *owner,uint32_t word,uint32_t value) {
    const GTrack *state=&owner->track[word&7];
    /* Native ARM already checks note identity and One Shot mode. Only suppress
       its ordinary release for a running Texture; force stop/panic always pass. */
    return !(state->mode==G_TEXTURE && !state->phase &&
             (word&0xf00000)==0x800000 && value==2);
}
/* Offline packet policy. The transport adapter must identify the native
 * pre-note choke by call site, never by value 3 alone. active is a coherent
 * acknowledged voice state; START bypasses Flow for the initial Texture note.
 * A0 is a candidate pitch-update command, not yet installed in the dispatcher.
 */
enum { G_PACKET_NORMAL=0,G_PACKET_PRECHOKE=1,G_PACKET_START=2,G_PACKET_SOURCECHOKE=3 };
uint32_t c_gr_owner_packet(const GOwner *owner,uint32_t *packet,
                           uint32_t context,uint32_t active) {
    uint32_t word=packet[0],value=packet[1];
    const GTrack *state=&owner->track[word&7];
    if(state->phase && state->phase!=G_PASSHELD &&
       ((word&0xf00000)==0x900000 || (word&0xf00000)==0xa00000)) return 0;
    if(state->mode!=G_TEXTURE || state->phase || context==G_PACKET_START) return 1;
    uint32_t command=word&0xf00000;
    if(command==0x800000 && value==2) return 0;
    if(!active || (state->settings&2)) return 1;
    if(command==0x800000 && value==3 &&
       (context==G_PACKET_PRECHOKE || context==G_PACKET_SOURCECHOKE)) return 0;
    if(command==0x900000) packet[0]=(word&~0xf00000u)|0xa00000;
    return 1;
}
/* Before project/pack/sample replacement, the caller invalidates each route
 * with these epochs and issues native force stops. Replacement may start only
 * after all eight idle acknowledgements. Notes stay blocked until completion;
 * unlike a normal mode change, a newer note cannot bypass this barrier.
 */
uint32_t c_gr_owner_quiesce(GOwner *owner) {
    for(uint32_t track=0;track<8;track++) {
        GTrack *state=&owner->track[track];
        state->epoch=(state->epoch+1)&0xffffff;
        if(!state->epoch) state->epoch=1;
        state->wanted=G_OFF;state->phase=G_REPLACE;
    }
    return 255;
}
uint32_t c_gr_owner_held(const GOwner *owner) {
    for(uint32_t track=0;track<8;track++) if(owner->track[track].phase!=G_HELD && owner->track[track].phase!=G_PASSHELD) return 0;
    return 1;
}
uint32_t c_gr_owner_resume(GOwner *owner) {
    if(!c_gr_owner_held(owner)) return 0;
    for(uint32_t track=0;track<8;track++) owner->track[track].phase=0;
    return 1;
}
uint32_t c_gr_owner_epoch(const GOwner *owner,uint32_t track) {
    return track<8?owner->track[track].epoch:0;
}
uint32_t c_gr_owner_mode(const GOwner *owner,uint32_t track) {
    return track<8?owner->track[track].mode:0;
}

/* Settings: bit0 sequencer source (else fixed), bit1 Texture envelope retrigger.
 * Kept separately from voice ownership: viewing another page cannot steal it.
 */
uint32_t c_gr_owner_flags(const GOwner *owner,uint32_t track) {
    return track<8?owner->track[track].settings:0;
}
uint32_t c_gr_owner_set_flags(GOwner *owner,uint32_t track,uint32_t flags) {
    if(track>=8 || flags>3) return 0;
    uint32_t changed=owner->track[track].settings!=flags;
    owner->track[track].settings=(uint8_t)flags;
    return changed;
}
/* Sequencer callback only. active is the frontend store's selected sample,
 * not DSP parameter 0 (which explicit Sample Flip changes). Preserve stock
 * resolution in Off mode and while changing mode. 255 means no source.
 */
uint32_t c_gr_owner_source(const GOwner *owner,uint32_t track,
                         uint32_t resolved,uint32_t active) {
    if(track>=8) return resolved;
    const GTrack *state=&owner->track[track];
    if(state->mode==G_OFF || state->phase || (state->settings&1)) return resolved;
    return active<128?active:255;
}

/* Candidate knob order: position, size, density, scan, position scatter,
 * pitch scatter, window, reverse chance. Stock Tune/Start/Length stay native.
 * Saved bytes are native seven-bit knob values, independent of DSP layout.
 */
typedef struct { uint8_t knob[8][8]; } GParameters;
void c_gr_params_init(GParameters *parameters) {
    static const uint8_t defaults[8]={0,64,51,72,0,0,64,0};
    for(uint32_t t=0;t<8;t++) for(uint32_t k=0;k<8;k++) parameters->knob[t][k]=defaults[k];
}
uint32_t c_gr_params_get(const GParameters *parameters,uint32_t track,uint32_t knob) {
    return track<8 && knob<8?parameters->knob[track][knob]:0;
}
uint32_t c_gr_params_put(GParameters *parameters,uint32_t track,uint32_t knob,uint32_t value) {
    if(track>=8 || knob>=8 || value>127) return 0;
    uint32_t changed=parameters->knob[track][knob]!=value;
    parameters->knob[track][knob]=(uint8_t)value;return changed;
}
uint32_t c_gr_params_word(const GParameters *parameters,uint32_t track,uint32_t knob) {
    if(track>=8 || knob>=8) return 0;
    uint32_t value=c_gr_params_get(parameters,track,knob);
    if(knob==3) return (value-64)&0xffffff;
    if(knob==2 || knob==6) return (value*100+63)/127;
    return value;
}
static uint32_t gr_crc(const uint8_t *bytes,uint32_t count) {
    uint32_t crc=~0u;
    for(uint32_t i=0;i<count;i++) {
        crc^=bytes[i];
        for(uint32_t bit=0;bit<8;bit++) crc=(crc>>1)^((0u-(crc&1))&0xedb88320u);
    }
    return ~crc;
}
static uint32_t gr_offset(uint32_t index) {
    if(index<32) return 296+index;
    if(index<48) return 404+index-32;
    if(index<58) return 520+index-48;
    return 860+index-58;
}
/* Eighty bytes in four explicitly unused tail fragments. Preserve the future
 * envelope/waveshape reservation, archived pages, scene data and stock ending.
 * V2 config: mode 0..1, retrigger 3, page 4, preferred mode 5, freeze 6.
 */
uint32_t c_gr_project_save(uint8_t *tail,const GParameters *parameters,const uint8_t *config) {
    uint8_t bytes[80];bytes[0]='G';bytes[1]='R';bytes[2]=2;bytes[3]=8;
    for(uint32_t t=0;t<8;t++) {
        if((config[t]&3)>G_TEXTURE) return 0;
        for(uint32_t k=0;k<8;k++) {
            uint32_t value=parameters->knob[t][k];if(value>127) return 0;
            bytes[4+t*8+k]=(uint8_t)value;
        }
        bytes[68+t]=config[t];
    }
    uint32_t crc=gr_crc(bytes,76);
    for(uint32_t i=0;i<4;i++) bytes[76+i]=(uint8_t)(crc>>(i*8));
    for(uint32_t i=0;i<80;i++) tail[gr_offset(i)]=bytes[i];
    return 1;
}
uint32_t c_gr_project_load(const uint8_t *tail,GParameters *parameters,uint8_t *config) {
    uint8_t bytes[80];
    for(uint32_t i=0;i<80;i++) bytes[i]=tail[gr_offset(i)];
    if(bytes[0]!='G' || bytes[1]!='R') return 0;
    if((bytes[2]!=1 && bytes[2]!=2) || bytes[3]!=8) return 2;
    uint32_t crc=0;
    for(uint32_t i=0;i<4;i++) crc|=(uint32_t)bytes[76+i]<<(i*8);
    if(gr_crc(bytes,76)!=crc) return 2;
    for(uint32_t t=0;t<8;t++) {
        if((bytes[2]==1 && bytes[68+t]>31) || (bytes[68+t]&3)>G_TEXTURE) return 2;
        for(uint32_t k=0;k<8;k++) if(bytes[4+t*8+k]>127) return 2;
    }
    for(uint32_t t=0;t<8;t++) {
        for(uint32_t k=0;k<8;k++) parameters->knob[t][k]=bytes[4+t*8+k];
        uint32_t old=bytes[68+t];
        config[t]=bytes[2]==1?((old&~4u)|((old&3)==G_TEXTURE?32:0)):old;
    }
    return 1;
}
enum { GR_LEVEL_OFFSET=420,G_LEVEL_DEFAULT=64 };
/* Sixteen bytes in the archived Filter block: 'GL', version, count, 8 levels, CRC32. */
uint32_t c_gr_levels_save(uint8_t *tail,const uint8_t *levels) {
    uint8_t bytes[16];bytes[0]='G';bytes[1]='L';bytes[2]=1;bytes[3]=8;
    for(uint32_t t=0;t<8;t++) { if(levels[t]>127) return 0;bytes[4+t]=levels[t]; }
    uint32_t crc=gr_crc(bytes,12);
    for(uint32_t i=0;i<4;i++) bytes[12+i]=(uint8_t)(crc>>(i*8));
    for(uint32_t i=0;i<16;i++) tail[GR_LEVEL_OFFSET+i]=bytes[i];
    return 1;
}
uint32_t c_gr_levels_load(const uint8_t *tail,uint8_t *levels) {
    const uint8_t *bytes=tail+GR_LEVEL_OFFSET;
    if(bytes[0]!='G' || bytes[1]!='L' || bytes[2]!=1 || bytes[3]!=8) return 0;
    uint32_t crc=0;
    for(uint32_t i=0;i<4;i++) crc|=(uint32_t)bytes[12+i]<<(i*8);
    if(gr_crc(bytes,12)!=crc) return 0;
    for(uint32_t t=0;t<8;t++) if(bytes[4+t]>127) return 0;
    for(uint32_t t=0;t<8;t++) levels[t]=bytes[4+t];
    return 1;
}
enum { GR_SHIFT_OFFSET=436,GR_SHIFT_BYTES=72,G_SHIFT_COUNT=7,G_SHIFT_TIMING=1,G_SHIFT_SLICE=3,G_SHIFT_LOCK=4,G_SHIFT_BURST=5,G_SHIFT_SPEED=6,G_TIMING_MIDDLE=64,G_BURST_FADE=16,G_BURST_PITCH=32 };
/* Shift knob k keeps its value in shift[k-1]. */
static uint32_t gr_shift_live(uint32_t knob) { return knob<=G_SHIFT_SPEED+1; }
/* Shift K3 Timing and K8 Burst Speed read from the middle. */
static uint32_t gr_shift_centred(uint32_t knob) { return knob==G_SHIFT_TIMING+1 || knob==G_SHIFT_SPEED+1; }
/* Slice and Burst: 0..7 off, then 2..16, eight values a step. */
static uint32_t gr_count(uint32_t value) { return value<8?0:2+(value-8)/8; }
/* After the Level record: 'GS', version, count, 7 Shift values and 1 setting per track, CRC32.
 * Setting: bit 0 Bounce, bits 1..3 Pitch Set 0..4, bit 4 Burst fade, bits 5..6 Burst pitch 0 off, 1 up, 2 down. */
static uint32_t gr_setting_ok(uint32_t setting) { return ((setting>>1)&7)<=4 && setting>>5<=2; }
uint32_t c_gr_shift_save(uint8_t *tail,const uint8_t *shift,const uint8_t *setting) {
    uint8_t bytes[GR_SHIFT_BYTES];bytes[0]='G';bytes[1]='S';bytes[2]=2;bytes[3]=8;
    for(uint32_t i=0;i<8*G_SHIFT_COUNT;i++) { if(shift[i]>127) return 0;bytes[4+i]=shift[i]; }
    for(uint32_t t=0;t<8;t++) { if(!gr_setting_ok(setting[t])) return 0;bytes[60+t]=setting[t]; }
    uint32_t crc=gr_crc(bytes,68);
    for(uint32_t i=0;i<4;i++) bytes[68+i]=(uint8_t)(crc>>(i*8));
    for(uint32_t i=0;i<GR_SHIFT_BYTES;i++) tail[GR_SHIFT_OFFSET+i]=bytes[i];
    return 1;
}
uint32_t c_gr_shift_load(const uint8_t *tail,uint8_t *shift,uint8_t *setting) {
    const uint8_t *bytes=tail+GR_SHIFT_OFFSET;
    if(bytes[0]!='G' || bytes[1]!='S' || (bytes[2]!=1 && bytes[2]!=2) || bytes[3]!=8) return 0;
    uint32_t crc=0;
    for(uint32_t i=0;i<4;i++) crc|=(uint32_t)bytes[68+i]<<(i*8);
    if(gr_crc(bytes,68)!=crc) return 0;
    for(uint32_t i=0;i<8*G_SHIFT_COUNT;i++) if(bytes[4+i]>127) return 0;
    for(uint32_t t=0;t<8;t++) if(!gr_setting_ok(bytes[60+t])) return 0;
    for(uint32_t i=0;i<8*G_SHIFT_COUNT;i++) shift[i]=bytes[4+i];
    // Version 1 has no Burst Speed: it starts at the middle.
    if(bytes[2]==1) for(uint32_t t=0;t<8;t++) shift[t*G_SHIFT_COUNT+G_SHIFT_SPEED]=G_TIMING_MIDDLE;
    for(uint32_t t=0;t<8;t++) setting[t]=bytes[60+t];
    return 1;
}

typedef struct {
    uint32_t pressed_at;
    uint8_t held,track,shown,reserved;
} GSettingsUi;
enum { G_UI_TAKEN=256,G_SETTING_CHANGED=16,G_HOLD_MS=333 };
uint32_t c_gr_ui_size(void) { return sizeof(GSettingsUi); }
void c_gr_ui_init(GSettingsUi *ui) { *ui=(GSettingsUi){0}; }
void c_gr_ui_release(GSettingsUi *ui) { ui->held=ui->shown=ui->reserved=0; }
void c_gr_ui_down(GSettingsUi *ui,uint32_t track,uint32_t now,uint32_t eligible) {
    c_gr_ui_release(ui);
    if(track>=8 || !eligible) return;
    ui->pressed_at=now;ui->track=(uint8_t)track;ui->held=1;
}
uint32_t c_gr_ui_tick(GSettingsUi *ui,uint32_t track,uint32_t now,uint32_t eligible) {
    if(!eligible || track>=8 || track!=ui->track) c_gr_ui_release(ui);
    if(ui->held && (uint32_t)(now-ui->pressed_at)>=G_HOLD_MS) {
        ui->shown=1;
#if G_LANE_ASSIGN
        ui->reserved|=1;
#endif
    }
    return ui->shown;
}
uint32_t c_gr_ui_pad(GSettingsUi *ui,GOwner *owner,uint32_t track,uint32_t pad,uint32_t serial) {
    if(!ui->shown || track>=8 || track!=ui->track || pad<16 || pad>=24) return 0;
    GTrack *state=&owner->track[track];
    if(pad==16) {
        uint32_t before=state->wanted;
        uint32_t next=before==G_TEXTURE?G_OFF:before+1;
        uint32_t actions=c_gr_owner_request(owner,track,next,serial);
        if(!state->phase && state->mode==next) state->wanted=(uint8_t)next;
        return G_UI_TAKEN|actions|(before!=state->wanted?G_SETTING_CHANGED:0);
    }
    if(pad==17 || pad==18) {
        state->settings^=1u<<(pad-17);
        return G_UI_TAKEN|G_SETTING_CHANGED;
    }
    return G_UI_TAKEN;
}

/* Live-adapter candidate: called only from guarded firmware wrappers. Existing
 * stock accessors own their transport locks. No diagnostics protocol is added.
 */
typedef struct {
    GOwner owner;GSettingsUi ui;GParameters parameters;
    uint8_t config[8];
    uint32_t magic,cursor,flags,running,scope,pending,dirty,taken,replace_depth;
    uint8_t level[8];
    uint32_t one_shot;
    uint32_t tail_at,started_at;
    uint8_t playing,tail,scan,reserved;
    uint8_t shift[8][G_SHIFT_COUNT],setting[8],sync[8];
    uint32_t tick,bpm;
#if G_LANE_ASSIGN
    uint8_t lanes[8][8],assignment[8];
    uint16_t recording_leds[8];
#endif
} GRuntime;
#if G_LANE_ASSIGN
static void gr_lane_changed(uint32_t t,uint32_t k);
#if G_EDITOR_SETTINGS
static void gr_editor_value(GRuntime *s,uint32_t t,uint32_t k,uint32_t value);
uint32_t c_gr_lane_inner(uint32_t object,uint32_t id,uint32_t value,uint32_t flag);
void c_gr_lane_touch(GRuntime *s,uint32_t t,uint32_t knob,uint32_t page);
#endif
#endif
enum { GR_MAGIC=0x31524743,GR_READY=1,GR_INITIALIZED=2,GR_STARTING=4,GR_DIRTY=8 };
/* Longest grain plus margin; a voice stays open this long after Stop so its grains finish. */
enum { G_TAIL_MS=1200,G_START_SETTLE_MS=250 };
#define GR_CONTROL 0x37400u
#define GR_SNAPSHOT 0x37420u
#define GR_POOL 0x2400u
typedef void (*GNative1)(uint32_t);
static uint32_t gr_narrow_read(uint32_t host_address) {
    uint32_t lock=0x20003688;
    ((GNative1)0x08029c8d)(lock);
    uint32_t value=((uint32_t(*)(uint32_t,uint32_t))0x08031269)(0,host_address);
    *(volatile uint32_t *)0x20003684=0xffff;
    ((void(*)(const uint32_t *))0x08030eb9)(&lock);
    return value>>8;
}
__attribute__((noinline)) uint32_t c_gr_shared_read(uint32_t address) {
    if(address>=GR_SNAPSHOT && address<GR_SNAPSHOT+64)
        return gr_narrow_read(0xab20+address-GR_SNAPSHOT);
    if(address==0x372fb || address==0x372fc)
        return gr_narrow_read(0xabe0+address-0x372fb);
    return 0;
}
__attribute__((noinline)) uint32_t c_gr_sample_read(uint32_t address) {
    uint32_t value=((uint32_t(*)(uint32_t,uint32_t))0x080314d7)(0,address)>>8;
    // Leave the stock wide writers in their usual Y bank.
    gr_narrow_read(0x8000);
    return value;
}
__attribute__((noinline)) void c_gr_dsp_write(uint32_t address,uint32_t value) {
    uint32_t host;
    if(address>=GR_CONTROL && address<GR_CONTROL+32) host=0xab00+address-GR_CONTROL;
    else if(address>=GR_POOL && address<GR_POOL+2048 && (address&255)<16)
        host=0xab60+((address-GR_POOL)>>8)*16+(address&15);
    else return;
    ((void(*)(uint32_t,uint32_t,uint32_t))0x08031201)(0,value<<8,host);
}
#define gr_write c_gr_dsp_write
static void gr_stop(uint32_t track) { ((void(*)(uint32_t))0x08040815)(track); }
static uint32_t gr_playing_now(void) {
    return *(const uint8_t *)((const void *(*)(const void *,uint32_t))0x0803fc59)((const void *)0x200122b0,0)!=0;
}
/* The Mixer's mute only blocks new sequencer notes, so Texture must check it itself. */
static uint32_t gr_muted(uint32_t track) {
    void *store=*(void **)(0x200470d4+track*0x190+0x28);
    return *(const uint8_t *)((const void *(*)(const void *,uint32_t))0x0803fc59)(store,0)!=0;
}
static void gr_texture_start(GRuntime *state,uint32_t track,uint32_t now);
/* Stock play mode of a track; 0 is One Shot. */
static uint32_t gr_play_mode(uint32_t track) {
    return (*(const uint8_t * const *)0x080408d4)[track*16+1];
}
uint32_t c_gr_runtime_size(void) { return sizeof(GRuntime); }
static void gr_shift_defaults(GRuntime *state,uint32_t track) {
    for(uint32_t k=0;k<G_SHIFT_COUNT;k++) state->shift[track][k]=k==G_SHIFT_TIMING || k==G_SHIFT_SPEED?G_TIMING_MIDDLE:0;
    state->setting[track]=0;
}
void c_gr_runtime_init(GRuntime *state) {
    if(state->magic==GR_MAGIC) return;
    c_gr_owner_init(&state->owner);c_gr_ui_init(&state->ui);c_gr_params_init(&state->parameters);
    for(uint32_t track=0;track<8;track++) { state->config[track]=0;state->level[track]=G_LEVEL_DEFAULT;state->sync[track]=0;gr_shift_defaults(state,track); }
#if G_LANE_ASSIGN
    for(uint32_t t=0;t<8;t++) { state->assignment[t]=0;state->recording_leds[t]=0;for(uint32_t k=0;k<8;k++)state->lanes[t][k]=0; }
#endif
    state->tick=state->bpm=0;
    state->tail_at=state->started_at=0;state->playing=state->tail=state->scan=0;
#if G_KNOB_PAGES
    state->reserved=0;
#endif
    state->one_shot=state->cursor=state->flags=state->running=state->scope=state->pending=state->dirty=state->taken=state->replace_depth=0;
    state->magic=GR_MAGIC;
}
static void gr_invalidate(GRuntime *state,uint32_t track) {
    gr_write(GR_CONTROL+4*track,0);
    gr_write(GR_CONTROL+4*track+1,state->owner.track[track].epoch);
    state->running&=~(1u<<track);gr_stop(track);
}
/* DSP field 14: Q23 output gain / 8, quadratic in Level; 64 gives x2. Never 0,
 * which the renderer reads as its reference level. */
uint32_t c_gr_level_word(uint32_t level) {
    return level?level*level*512:1;
}
/* Sequencer ticks (24 a beat) a step, slow to fast, eight knob values each. */
static const uint8_t gr_step_ticks[8]={48,24,16,12,8,6,4,3};
/* Timing: 63..65 is off. Above, ticks per grain. */
static uint32_t gr_timing_ticks(const GRuntime *state,uint32_t track) {
    int32_t step=(int32_t)state->shift[track][G_SHIFT_TIMING]-66;
    return step<0?0:gr_step_ticks[step/8];
}
/* With Slice on, Scan steps one slice per this many ticks: 63..65 stops, right forward, left backward. */
static uint32_t gr_slice_ticks(const GRuntime *state,uint32_t track) {
    uint32_t scan=state->parameters.knob[track][3];
    if(!gr_count(state->shift[track][G_SHIFT_SLICE])) return 0;
    return scan>65?gr_step_ticks[(scan-66)/8]:scan<63?gr_step_ticks[(62-scan)/8]:0;
}
/* Slices to add to each grain's slice, counted from the sequencer tick. */
static uint32_t gr_slice_step(const GRuntime *state,uint32_t track) {
    uint32_t ticks=gr_slice_ticks(state,track),slices=gr_count(state->shift[track][G_SHIFT_SLICE]);
    if(!ticks) return 0;
    uint32_t step=(state->tick/ticks)%slices;
    return state->parameters.knob[track][3]>65?step:(slices-step)%slices;
}
/* Samples between grains; 0 leaves spacing to Density. Below the middle: 0.5 s to 6 ms, free. */
static uint32_t gr_timing_interval(const GRuntime *state,uint32_t track) {
    uint32_t value=state->shift[track][G_SHIFT_TIMING];
    if(value<63) return (24000*(20-(63-value)%10)/20)>>((63-value)/10);
    return 120000*gr_timing_ticks(state,track)/(state->bpm?state->bpm:120);
}
/* Chance per Timing step, 8..128 of 128; follows Density. */
static uint32_t gr_timing_chance(const GRuntime *state,uint32_t track) {
    uint32_t density=c_gr_params_word(&state->parameters,track,2);
    return 8+density*(200-density)*120/10000;
}
static uint32_t gr_field(const GRuntime *state,uint32_t track,uint32_t field) {
    static const uint8_t indices[16]={255,255,255,1,0,2,3,255,255,5,6,4,7,255,255,255};
    if((field==6 || field==11) && (state->config[track]&64)) return 0;
    if(field==6 && gr_count(state->shift[track][G_SHIFT_SLICE])) return 0;
    if(field==1) return gr_timing_interval(state,track)|((uint32_t)state->sync[track]<<18);
    if(field==8) return state->shift[track][0]|((uint32_t)state->shift[track][2]<<8)|(gr_timing_chance(state,track)<<16);
    // Bit 0 notes restart grains, bit 1 Freeze, bit 3 no new grains, bit 4 Bounce, bits 5..7 Pitch Set, bits 8..14 Lock,
    // bits 15..18 slices - 1 (0 off), bits 19..22 slice step.
    if(field==13) return ((state->config[track]>>3)&1)|((state->config[track]>>5)&2)|(state->owner.track[track].mode==G_TRIGGERED)
                         |(state->owner.track[track].mode==G_TEXTURE && !((state->playing>>track)&1))|(((uint32_t)state->tail>>track&1)<<3)
                         |((state->setting[track]&1u)<<4)|((uint32_t)(state->setting[track]>>1&7)<<5)
                         |((uint32_t)state->shift[track][G_SHIFT_LOCK]<<8)|(gr_count(state->shift[track][G_SHIFT_SLICE])?gr_count(state->shift[track][G_SHIFT_SLICE])-1:0)<<15
                         |gr_slice_step(state,track)<<19;
    if(field==14) return c_gr_level_word(state->level[track]);
    if(indices[field]!=255) return c_gr_params_word(&state->parameters,track,indices[field]);
    if(field==0) return track+1;
    // Zone 127; bits 8..11 Burst grains - 1 (0 off), bits 12..18 Burst Speed, bit 19 fade, bits 20..21 pitch.
    if(field==7) { uint32_t grains=gr_count(state->shift[track][G_SHIFT_BURST]),setting=state->setting[track];
        return 127|(grains?grains-1:0)<<8|(uint32_t)state->shift[track][G_SHIFT_SPEED]<<12|(setting>>4&1)<<19|(setting>>5)<<20; }
    if(field==15) return 0x6a7a4b;
    return 0;
}
uint32_t c_gr_runtime_mode(GRuntime *state,uint32_t track,uint32_t mode) {
    if(track>=8 || mode>G_TEXTURE || state->owner.track[track].phase>=G_REPLACE) return 0;
    state->config[track]=(state->config[track]&~3u)|(uint8_t)mode;
    if(mode) state->config[track]=(state->config[track]&~32u)|(mode==G_TEXTURE?32:0);
    state->flags|=GR_DIRTY;
    return 1;
}
uint32_t c_gr_runtime_put(GRuntime *state,uint32_t track,uint32_t knob,uint32_t value) {
    uint32_t changed=c_gr_params_put(&state->parameters,track,knob,value);
    if(changed) { state->dirty|=1u<<track;state->flags|=GR_DIRTY; }
    return changed;
}
uint32_t c_gr_runtime_flags(GRuntime *state,uint32_t track,uint32_t flags) {
    if(track>=8 || flags>3) return 0;
    state->config[track]=(state->config[track]&~8u)|(uint8_t)((flags&2)<<2);
    state->flags|=GR_DIRTY;
    return c_gr_owner_set_flags(&state->owner,track,flags|1);
}
uint32_t c_gr_runtime_seq_begin(GRuntime *state,const uint8_t *player) {
    uint32_t old=state->scope;
    if(state->magic!=GR_MAGIC || !(state->flags&GR_INITIALIZED)) return old;
    const uint8_t *context=*(const uint8_t * const *)(player+0x5c);
    uint32_t id=*(const uint16_t *)(context+0x18);
    if(id>=0x10 && id<0x18) {
        void *store=*(void * const *)(player+0x60);
        uint32_t active=*(uint8_t *)((void *(*)(void *,uint32_t))0x0803fc59)(store,0);
        state->scope=(id-0x10+1)|(active<<8);
    }
    return old;
}
void c_gr_runtime_seq_end(GRuntime *state,uint32_t previous) { state->scope=previous; }
uint32_t c_gr_runtime_source(GRuntime *state,uint32_t track,uint32_t resolved) {
    track&=7;
    if(state->magic!=GR_MAGIC || !(state->flags&GR_INITIALIZED) || (state->scope&255)!=track+1) return resolved;
    return resolved;
}
uint32_t c_gr_runtime_ui_pad(GRuntime *state,uint32_t track,uint32_t pad) {
    if(track>=8) return 0;
    GTrack *owner=&state->owner.track[track];
    if(owner->phase>=G_REPLACE) return G_UI_TAKEN;
    if(!state->ui.shown || state->ui.track!=track || pad<16 || pad>=24) return 0;
    uint32_t config=state->config[track];
    if(pad==16) config=(config&~3u)|((config&3)?0:((config&32)?G_TEXTURE:G_TRIGGERED));
    else if(pad==17) {
        config^=32;
        if(config&3) config=(config&~3u)|((config&32)?G_TEXTURE:G_TRIGGERED);
    } else if(pad==18) { config^=8;state->dirty|=1u<<track; }
    else if(pad==19) { state->setting[track]^=1;state->dirty|=1u<<track; }
    else if(pad==20) { config^=64;state->dirty|=1u<<track; }
    else if(pad==21) { uint32_t set=state->setting[track];
        state->setting[track]=(uint8_t)((set&~14u)|((set>>1&7)>=4?0:(set&14)+2));state->dirty|=1u<<track; }
    else if(pad==22) { state->setting[track]^=G_BURST_FADE;state->dirty|=1u<<track; }
    else if(pad==23) { uint32_t set=state->setting[track];
        state->setting[track]=(uint8_t)((set&31)|((set>>5>=2?0:set+G_BURST_PITCH)&96));state->dirty|=1u<<track; }
    else return G_UI_TAKEN;
    state->config[track]=(uint8_t)config;
    state->flags|=GR_DIRTY;
    return G_UI_TAKEN|G_SETTING_CHANGED;
}
static void gr_texture_start(GRuntime *state,uint32_t track,uint32_t now) {
    state->flags|=GR_STARTING;
    ((void(*)(uint32_t,uint32_t,uint32_t))0x08040779)(track,60,127);
    state->flags&=~GR_STARTING;
    state->started_at=now;
}
/* Keeps Timing and Slice steps on the tempo: follows the BPM, and pulls grains to the grid about once a beat. */
static void gr_tempo_frame(GRuntime *state) {
    uint32_t locked=0,sliced=0;
    for(uint32_t track=0;track<8;track++) {
        if(gr_timing_ticks(state,track)) locked|=1u<<track;
        if(gr_slice_ticks(state,track)) sliced|=1u<<track;
    }
    if(!(locked|sliced)) return;
    const void *(*param)(const void *,uint32_t)=(const void *(*)(const void *,uint32_t))0x0803fc6d;
    uint32_t bpm=*(const uint8_t *)param((const void *)0x20012788,0);
    if(bpm<30) bpm=120;
    if(bpm!=state->bpm) { state->bpm=bpm;state->dirty|=locked; }
    uint32_t tick=*(const uint32_t *)param(*(const void * const *)0x2003c410,0);
    if(tick==state->tick) return;
    state->tick=tick;
    for(uint32_t track=0;track<8;track++) {
        if(state->owner.track[track].mode==G_OFF) continue;
        if((sliced&(1u<<track)) && !(tick%gr_slice_ticks(state,track))) gr_write(GR_POOL+256*track+13,gr_field(state,track,13));
        if(!(locked&(1u<<track))) continue;
        uint32_t ticks=gr_timing_ticks(state,track),period=ticks;
        while(period<24) period+=ticks;
        if(tick%period) continue;
        state->sync[track]=(state->sync[track]+1)&63;
        gr_write(GR_POOL+256*track+1,gr_field(state,track,1));
    }
}
void c_gr_runtime_frame(GRuntime *state,uint32_t ready,uint32_t uploading) {
    c_gr_runtime_init(state);
    if(state->replace_depth) return;
    if(!ready) {
        for(uint32_t track=0;track<8;track++) {
            GTrack *owner=&state->owner.track[track];
            if(state->flags&GR_READY) { owner->epoch=(owner->epoch+1)&0xffffff;if(!owner->epoch) owner->epoch=1; }
            owner->mode=owner->wanted=G_OFF;owner->phase=0;
        }
        state->flags&=GR_DIRTY;
        state->cursor=state->running=state->pending=0;
        return;
    }
    if(uploading) return;
    state->flags|=GR_READY;
    if(!(state->flags&GR_INITIALIZED)) {
        if(!state->cursor) {
            uint32_t requested=0;
            for(uint32_t track=0;track<8;track++) requested|=state->config[track]&3;
            if(!requested) return;
            // Leave stock playback in charge until the DSP has published status.
            uint32_t status=c_gr_shared_read(GR_SNAPSHOT);
            if(status!=0x674732 && status!=0x674331) return;
        }
        for(uint32_t budget=0;budget<8 && state->cursor<152;budget++,state->cursor++) {
            uint32_t track=state->cursor/19,index=state->cursor%19;
            if(index==0) gr_write(GR_CONTROL+4*track,0);
            else if(index==1) gr_write(GR_CONTROL+4*track+1,state->owner.track[track].epoch);
            else if(index==2) gr_write(GR_CONTROL+4*track+3,1);
            else gr_write(GR_POOL+256*track+index-3,gr_field(state,track,index-3));
        }
        if(state->cursor<152) return;
        state->flags|=GR_INITIALIZED;
        return;
    }
    uint32_t now=*(volatile uint32_t *)0x20000820,transport=gr_playing_now();
    for(uint32_t track=0;track<8;track++) {
        GTrack *owner=&state->owner.track[track];
        uint32_t bit=1u<<track;
        owner->settings=1|((state->config[track]>>2)&2);
        uint32_t action=c_gr_owner_request(&state->owner,track,state->config[track]&3,0);
        if(action&G_STOP || state->pending&(1u<<track)) {
            gr_invalidate(state,track);state->pending&=~(1u<<track);
        }
        action=c_gr_owner_poll(&state->owner,track,GR_SNAPSHOT+8*track,c_gr_shared_read);
        uint32_t texture=owner->mode==G_TEXTURE && !owner->phase;
        uint32_t playing=texture && transport && !gr_muted(track),was=(state->playing>>track)&1;
        state->playing=(uint8_t)((state->playing&~bit)|(playing?bit:0));
        if(texture && playing!=was) {
            if(playing) state->tail&=~bit;
            else if(state->running&bit) { state->tail|=bit;state->tail_at=now+G_TAIL_MS; }
            gr_write(GR_POOL+256*track+13,gr_field(state,track,13));
        }
        // While stopped, a One Shot pad press on a Texture track ends with its sample.
        uint32_t one_shot=(owner->mode==G_TRIGGERED || (texture && !playing && !(state->tail&bit))) && !gr_play_mode(track);
        if(one_shot!=((state->one_shot>>track)&1)) {
            state->one_shot^=1u<<track;
            gr_write(GR_CONTROL+4*track+3,one_shot);
        }
        if(action&G_APPLY) {
            gr_write(GR_CONTROL+4*track+3,one_shot);
            gr_write(GR_POOL+256*track+13,gr_field(state,track,13));
            gr_write(GR_CONTROL+4*track,owner->mode==G_OFF?0:0x674e31);
        }
        if(playing && !(state->running&bit)) gr_texture_start(state,track,now);
    }
    if(state->tail && (int32_t)(now-state->tail_at)>=0)
        for(uint32_t track=0;track<8;track++) if(state->tail&(1u<<track)) {
            state->tail&=~(1u<<track);state->running&=~(1u<<track);gr_stop(track);
            gr_write(GR_POOL+256*track+13,gr_field(state,track,13));
        }
    // One track a frame: a voice that ended while playing starts again on the next frame.
    if(state->playing && (uint32_t)(now-state->started_at)>=G_START_SETTLE_MS) {
        uint32_t track=state->scan=(state->scan+1)&7;
        const GTrack *owner=&state->owner.track[track];
        if((state->playing&(1u<<track)) && (state->running&(1u<<track)) &&
           c_gr_shared_read(GR_SNAPSHOT+8*track)==0x674732 && c_gr_shared_read(GR_SNAPSHOT+8*track+1)==owner->epoch)
            state->running&=~(1u<<track);
    }
    gr_tempo_frame(state);
    if(state->dirty) for(uint32_t pending_track=0;pending_track<8;pending_track++) {
#if G_LANE_ASSIGN
        uint32_t track=(state->cursor+pending_track)&7;
#else
        uint32_t track=pending_track;
#endif
        if(!(state->dirty&(1u<<track)))continue;
        static const uint8_t fields[8]={4,3,5,6,11,9,10,12};
        for(uint32_t knob=0;knob<8;knob++) gr_write(GR_POOL+256*track+fields[knob],gr_field(state,track,fields[knob]));
        gr_write(GR_POOL+256*track+1,gr_field(state,track,1));
        gr_write(GR_POOL+256*track+7,gr_field(state,track,7));
        gr_write(GR_POOL+256*track+8,gr_field(state,track,8));
        gr_write(GR_POOL+256*track+13,gr_field(state,track,13));
        gr_write(GR_POOL+256*track+14,gr_field(state,track,14));
        state->dirty&=~(1u<<track);
#if G_LANE_ASSIGN
        state->cursor=(track+1)&7;
#endif
        break;
    }
}
uint32_t c_gr_runtime_message(GRuntime *state,uint32_t *packet,uint32_t caller) {
    if(state->magic!=GR_MAGIC || !(state->flags&GR_INITIALIZED)) return 1;
    uint32_t track=packet[0]&7,command=packet[0]&0xf00000;
    uint32_t context=caller==0x080407be?G_PACKET_PRECHOKE:caller==0x0804074a?G_PACKET_SOURCECHOKE:G_PACKET_NORMAL;
    if(state->flags&GR_STARTING) context=G_PACKET_START;
    if(state->owner.track[track].mode==G_TEXTURE && (state->running&(1u<<track))) {
        uint32_t address=GR_SNAPSHOT+8*track;
        uint32_t frame=c_gr_shared_read(address+2),tag=c_gr_shared_read(address),epoch=c_gr_shared_read(address+1);
        if(tag==0x674732 && epoch==state->owner.track[track].epoch &&
           c_gr_shared_read(address)==tag && c_gr_shared_read(address+2)==frame) state->running&=~(1u<<track);
    }
    // While stopped, a Texture track plays pad notes like Triggered, including their note-offs.
    const GTrack *owner=&state->owner.track[track];
    if(owner->mode==G_TEXTURE && !owner->phase && !((state->playing>>track)&1) && command==0x800000 && packet[1]==2) {
        state->running&=~(1u<<track);
        return 1;
    }
    uint32_t accepted=c_gr_owner_packet(&state->owner,packet,context,(state->running&state->playing&(1u<<track))!=0);
    if(accepted) {
        if(command==0x800000 && packet[1]==3) state->running&=~(1u<<track);
        if(command==0x900000 && (packet[0]&0xf00000)==0x900000) {
            state->running|=1u<<track;
            if(state->tail&(1u<<track)) { state->tail&=~(1u<<track);state->dirty|=1u<<track; }
        }
    }
    return accepted;
}
uint32_t c_gr_runtime_page(const GRuntime *state,uint32_t track) {
    return track<8 && (state->config[track]&16)!=0;
}
uint32_t c_gr_runtime_granular_busy(GRuntime *state,uint32_t track) {
    c_gr_runtime_init(state);
    if(track>=8)return 0;
    const GTrack *owner=&state->owner.track[track];
    return (state->config[track]&3)!=G_OFF || owner->mode!=G_OFF ||
           owner->wanted!=G_OFF || owner->phase!=0;
}
#if G_KNOB_PAGES
/* Volatile, per-track editor layer. It is navigation, not a sound parameter,
 * and must not dirty the project or modify the granular mode. */
uint32_t c_gr_runtime_knob_page(const GRuntime *state,uint32_t track) {
    return track<8 ? (state->reserved>>track)&1 : 0;
}
/* Shift is an entry layer belonging to the active parameter page, never a
 * global granular menu. Effective native Shift includes sticky Shift. The
 * origin bit lets release close Shift entry without undoing pad-held latches. */
void c_gr_runtime_shift_layer(GRuntime *state,uint32_t track) {
#if G_LANE_ASSIGN
    uint32_t store=*(volatile uint32_t *)(0x200487c8+0x0c);
    uint32_t active=*(uint8_t *)((void *(*)(uint32_t,uint32_t))0x0803fc59)(store,0);
    if(track>=8 || (!G_EDITOR_SETTINGS && !c_gr_runtime_page(state,track))) {
        if(state->ui.reserved&2) { if(state->ui.track<8)state->assignment[state->ui.track]&=15;c_gr_ui_release(&state->ui); }
        return;
    }
    if(active) {
        if(state->ui.track!=track || (G_EDITOR_SETTINGS && (!!(state->ui.reserved&4)==!!c_gr_runtime_page(state,track)))) { if(state->ui.track<8)state->assignment[state->ui.track]&=15;c_gr_ui_release(&state->ui); }
        state->ui.track=(uint8_t)track;state->ui.shown=1;state->ui.reserved|=2;
        if(G_EDITOR_SETTINGS && !c_gr_runtime_page(state,track))state->ui.reserved|=4;
    } else if(state->ui.reserved&2) {
        state->ui.reserved&=~2u;
        if(!(state->ui.reserved&1)) { c_gr_ui_release(&state->ui);state->assignment[track]&=15; }
    }
#else
    (void)state;(void)track;
#endif
}
uint32_t c_gr_runtime_arrow(GRuntime *state,uint32_t track,uint32_t button) {
    if(G_EDITOR_SETTINGS && track<8 && !c_gr_runtime_page(state,track) && state->ui.shown)return 1;
    if(!c_gr_runtime_page(state,track) || (button!=19 && button!=20)) return 0;
#if G_LANE_ASSIGN
    if(state->ui.track==track && (state->ui.held || state->ui.shown)) {
        state->ui.shown=1;state->ui.reserved|=(state->ui.reserved&2)?2:1;
        if(button==19)state->assignment[track]|=128;
        else state->assignment[track]&=15;
        return 1;
    }
    state->assignment[track]&=15;
#endif
    if(button==19)state->reserved|=(uint8_t)(1u<<track);
    else state->reserved&=(uint8_t)~(1u<<track);
    return 1;
}
#endif
#if G_REVERSE_CYCLE
uint32_t c_gr_cycle_next(uint32_t selected,uint32_t count) {
    uint32_t store=*(volatile uint32_t *)(0x200487c8+0x0c);
    uint32_t shift=*(uint8_t *)((void *(*)(uint32_t,uint32_t))0x0803fc59)(store,0);
    /* Shift is already the access modifier while a settings/assignment page
     * is visible. It must not also reverse that page's knob selector. */
    const GRuntime *state=(const GRuntime *)G_STATE;
    if(count==16 || (state->magic==GR_MAGIC && state->ui.shown))shift=0;
    if(shift)return selected>1?selected-1:count;
    return selected<count?selected+1:1;
}
#endif
uint32_t c_gr_runtime_pad(GRuntime *state,uint32_t track,uint32_t pad) {
    if(track>=8 || pad>=32) return 0;
    uint32_t taken=0;
#if G_EDITOR_SETTINGS
    if(state->taken&(1u<<pad))return 1;
    if(pad==25) {
        if(state->config[track]&16)state->flags|=GR_DIRTY;
        state->config[track]&=~16u;state->assignment[track]&=15;
        c_gr_ui_down(&state->ui,track,*(volatile uint32_t *)0x20000820,1);
        state->ui.reserved=4;state->taken|=1u<<pad;return 1;
    } else if(!c_gr_runtime_page(state,track) && state->ui.shown && pad==24) {
        state->taken|=1u<<pad;return 1;
    } else if(!c_gr_runtime_page(state,track) && state->ui.shown && pad>=16 && pad<24) {
        if(pad<18) {state->config[track]^=pad==16?4:128;state->flags|=GR_DIRTY;}
        state->taken|=1u<<pad;return 1;
    } else if(pad>=16 && pad<24 && !state->ui.shown && (state->config[track]&4)) {
        uint32_t knob=((uint8_t *)G_MENU)[8];
        if(knob>=1 && knob<=8) {
            uint32_t value=(pad-16)*127/7;
            if((pad==19 && (state->taken&(1u<<20))) || (pad==20 && (state->taken&(1u<<19))))value=64;
            gr_editor_value(state,track,knob-1,value);
        }
        state->taken|=1u<<pad;return 1;
    }
#endif
#if G_LANE_ASSIGN
    if(c_gr_runtime_page(state,track) && (state->assignment[track]&128) && pad!=G_PAGE_PAD) {
        if(pad==24) {
#if G_REVERSE_CYCLE
            state->assignment[track]=128|(c_gr_cycle_next((state->assignment[track]&15)+1,16)-1);
#else
            state->assignment[track]=128|((state->assignment[track]+1)&15);
#endif
        }
        if(pad>=16 && pad<24) {
            uint32_t lane=pad-16,dest=(state->assignment[track]&15)+1;
            if(state->lanes[track][lane]==dest)state->lanes[track][lane]=0;
            else { for(uint32_t k=0;k<8;k++)if(state->lanes[track][k]==dest) {state->lanes[track][k]=0;gr_lane_changed(track,k);}state->lanes[track][lane]=dest; }
            gr_lane_changed(track,lane);
            state->flags|=GR_DIRTY;
        }
        if(pad>=16 && pad<=24) { state->taken|=1u<<pad;return 1; }
    }
#endif
    if(pad==G_PAGE_PAD) {
#if G_LANE_ASSIGN
        state->assignment[track]&=15;
#endif
        if(!(state->config[track]&16)) state->flags|=GR_DIRTY;
        state->config[track]|=16;
        c_gr_ui_down(&state->ui,track,*(volatile uint32_t *)0x20000820,1);taken=1;
    } else if(state->ui.shown && pad>=16 && pad<24) {
        c_gr_runtime_ui_pad(state,track,pad);taken=1;
    } else if(c_gr_runtime_page(state,track) && pad==24) taken=1;
    else if(G_LANE_ASSIGN?(pad>=25 && pad<32):(pad==25 || pad==28 || pad==30)) {
        if(state->config[track]&16) state->flags|=GR_DIRTY;
        state->config[track]&=~16u;c_gr_ui_release(&state->ui);
#if G_LANE_ASSIGN
        state->assignment[track]&=15;
#endif
    }
    if(taken) state->taken|=1u<<pad;
    return taken;
}
uint32_t c_gr_runtime_release(GRuntime *state,uint32_t pad) {
    if(pad>=32 || !(state->taken&(1u<<pad))) return 0;
    state->taken&=~(1u<<pad);
    if(pad==G_PAGE_PAD || (G_EDITOR_SETTINGS && pad==25)) {
#if G_LANE_ASSIGN
        if(state->ui.reserved) { state->ui.held=0;return 1; }
        for(uint32_t t=0;t<8;t++)state->assignment[t]&=15;
#endif
        c_gr_ui_release(&state->ui);
    }
    return 1;
}
void c_gr_runtime_ui_frame(GRuntime *state,uint32_t track,uint32_t eligible) {
    c_gr_ui_tick(&state->ui,track,*(volatile uint32_t *)0x20000820,
                 eligible && (G_EDITOR_SETTINGS || c_gr_runtime_page(state,track)));
#if G_LANE_ASSIGN
    for(uint32_t t=0;t<8;t++)if(!state->ui.shown || !state->ui.reserved || state->ui.track!=t)state->assignment[t]&=15;
#endif
}
uint32_t c_gr_runtime_turn(GRuntime *state,uint32_t track,uint32_t knob,int32_t delta) {
    if(track>=8 || knob>=8 || !c_gr_runtime_page(state,track)) return 0;
#if G_LANE_ASSIGN
    if(state->assignment[track]&128)return 1;
    state->assignment[track]=(uint8_t)knob;
#endif
    if(delta>127) delta=127;if(delta< -127) delta=-127;
    int32_t value=(int32_t)c_gr_params_get(&state->parameters,track,knob)+delta;
    if(value<0) value=0;if(value>127) value=127;
    c_gr_runtime_put(state,track,knob,(uint32_t)value);return 1;
}
#define G_PAGE_RGB 0x9eff59u
static uint32_t gr_rgb(uint32_t rgb,uint32_t level);
enum { G_CLEAR_CLICKS=40,G_CLEAR_RIGHT=0x0e,G_CLEAR_LEFT=0x55 };
/* counters[0..7] count right turns, counters[8..15] left. Returns 1 when a right
 * turn reaches the stop. The menu zeroes the counters when Clear is released. */
uint32_t c_gr_clear_step(uint8_t *counters,uint32_t knob,int32_t delta) {
    if(knob>=8 || !delta) return 0;
    uint8_t *mine=counters+knob+(delta<0?8:0),*other=counters+knob+(delta<0?0:8);
    if(*mine==G_CLEAR_CLICKS) return 0;
    uint32_t total=*mine+(delta<0?0u-(uint32_t)delta:(uint32_t)delta);
    if(total<G_CLEAR_CLICKS) { *mine=(uint8_t)total;return 0; }
    *mine=G_CLEAR_CLICKS;*other=0;
    return delta>0?1:(G_LANE_ASSIGN?2:0);
}
void c_gr_clear_draw(const GRuntime *state,uint32_t track,uint32_t *out,const uint8_t *counters) {
    if(track>=8 || !c_gr_runtime_page(state,track)) return;
    const uint32_t *colours=(const uint32_t *)0x20003974;
    uint32_t level=out[G_PAGE_PAD]&255;
    for(uint32_t i=0;i<8;i++) {
        if(counters[8+i]==G_CLEAR_CLICKS) out[60+i]=gr_rgb(colours[G_CLEAR_LEFT],level);
        else if(counters[i]==G_CLEAR_CLICKS) out[60+i]=gr_rgb(colours[G_CLEAR_RIGHT],level);
    }
}
uint32_t c_gr_runtime_clear_knob(GRuntime *state,uint32_t track,uint32_t knob,uint32_t shifted) {
    if(track>=8 || knob>=8 || !c_gr_runtime_page(state,track)) return 0;
    if(shifted) {
        if(!gr_shift_live(knob)) return 0;
        if(knob) state->shift[track][knob-1]=gr_shift_centred(knob)?G_TIMING_MIDDLE:0;
        else state->level[track]=G_LEVEL_DEFAULT;
        state->dirty|=1u<<track;state->flags|=GR_DIRTY;
        return 1;
    }
    GParameters defaults;c_gr_params_init(&defaults);
    c_gr_runtime_put(state,track,knob,defaults.knob[track][knob]);
    return 1;
}
uint32_t c_gr_runtime_shift_turn(GRuntime *state,uint32_t track,uint32_t knob,int32_t delta) {
    if(track>=8 || !gr_shift_live(knob) || !delta || !c_gr_runtime_page(state,track)) return 0;
    if(delta>127) delta=127;if(delta< -127) delta=-127;
#if G_LANE_ASSIGN
    if(state->assignment[track]&128)return 1;
    state->assignment[track]=(uint8_t)(knob+8);
#endif
    uint8_t *store=knob?&state->shift[track][knob-1]:&state->level[track];
    int32_t value=(int32_t)*store+delta;
    if(value<0) value=0;if(value>127) value=127;
    *store=(uint8_t)value;
    state->dirty|=1u<<track;state->flags|=GR_DIRTY;
    return 1;
}
void c_gr_runtime_reset(GRuntime *state,uint32_t track) {
    if(track>=8) return;
    GParameters defaults;c_gr_params_init(&defaults);
    for(uint32_t k=0;k<8;k++) state->parameters.knob[track][k]=defaults.knob[track][k];
    state->config[track]&=G_EDITOR_SETTINGS?183:51;state->level[track]=G_LEVEL_DEFAULT;gr_shift_defaults(state,track);
    c_gr_runtime_flags(state,track,0);state->dirty|=1u<<track;c_gr_ui_release(&state->ui);
}
void c_gr_runtime_track_reset(GRuntime *state,uint32_t track) {
    if(track>=8 || state->replace_depth) return;
    c_gr_runtime_reset(state,track);
    c_gr_runtime_mode(state,track,G_OFF);
#if G_LANE_ASSIGN
    state->config[track]=0;state->sync[track]=0;state->assignment[track]=0;state->recording_leds[track]=0;
    state->reserved&=(uint8_t)~(1u<<track);
    for(uint32_t k=0;k<8;k++) {if(state->lanes[track][k])gr_lane_changed(track,k);state->lanes[track][k]=0;}
#endif
}
uint32_t c_gr_runtime_store_pending(const GRuntime *state) {
    return (state->flags&GR_DIRTY) && !state->replace_depth;
}
uint32_t c_gr_runtime_clear(GRuntime *state,uint32_t track,uint32_t pad) {
    if(track>=8 || pad!=G_PAGE_PAD) return 0;
    c_gr_runtime_reset(state,track);state->taken|=1u<<pad;return 1;
}
static uint32_t gr_brightness(uint32_t rgb) {
    uint32_t value=rgb&255;if(((rgb>>8)&255)>value) value=(rgb>>8)&255;
    if(((rgb>>16)&255)>value) value=(rgb>>16)&255;return value;
}
static uint32_t gr_rgb(uint32_t rgb,uint32_t level) {
    return ((((rgb>>16)&255)*level/255)<<16)|((((rgb>>8)&255)*level/255)<<8)|((rgb&255)*level/255);
}
/* Stock-derived knob brightness, including its visible minimum. Bipolar
 * values use distance from center; no additional page-specific dimming. */
static uint32_t gr_knob_scale(uint32_t value,uint32_t centred) {
    if(centred) { value=value>=64?(value-64)*2:(64-value)*2;if(value>127) value=127; }
    return (value*0x1cc+0x1a00)>>8;
}
static uint32_t gr_shift_value(const GRuntime *state,uint32_t track,uint32_t knob) {
    return knob?state->shift[track][knob-1]:state->level[track];
}
void c_gr_runtime_draw(const GRuntime *state,uint32_t track,uint32_t *out,uint32_t knob) {
    if(track>=8) return;
    uint32_t level=gr_brightness(out[25]);
    uint32_t p=gr_brightness(out[28]);if(p>level) level=p;
    p=gr_brightness(out[30]);if(p>level) level=p;
    out[G_PAGE_PAD]=gr_rgb(G_PAGE_RGB,level/16);
    if(!c_gr_runtime_page(state,track)) {
#if G_EDITOR_SETTINGS
        if(state->ui.shown && state->ui.track==track) {
            for(uint32_t i=0;i<8;i++)out[16+i]=i<2?gr_rgb(0xffffff,level/((state->config[track]&(i?128:4))?1:8)):0;
            out[51]=out[52]=0;
        }
#endif
        return;
    }
    static const uint8_t slots[8]={0x43,0x2f,0x47,0x4b,0x37,0x25,0x12,0x3b};
    uint32_t color=((const uint32_t *)0x20003974)[slots[track]];
    /* Assignment settings stay inside this parameter pad view. Apply the
     * common track/page indicators before its early rendering return. */
    out[25]=gr_rgb(0xffffff,level/16);
#if !G_TRACK_VIEWS
    for(uint32_t i=0;i<8;i++)if(i!=track)out[32+i]=gr_rgb(G_PAGE_RGB,level/4);
#endif
    if(out[32+track])out[32+track]=gr_rgb(color,level);
#if G_LANE_ASSIGN
    if(state->assignment[track]&128) {
        uint32_t selected=(state->assignment[track]&15)+1;
        for(uint32_t k=0;k<8;k++) {
            uint32_t d=state->lanes[track][k];
            uint32_t opposite=d && ((d>8)!=(selected>8));
            out[16+k]=gr_rgb(opposite?0xff2a1a:d?G_PAGE_RGB:0xffffff,
                            level/(d==selected?1:opposite?8:d?4:8));
            uint32_t active=k==((selected-1)&7);
            out[60+k]=gr_rgb(G_PAGE_RGB,level/(active?1:8));
        }
        out[51]=gr_rgb(G_PAGE_RGB,level/(selected>8?1:32));
        out[52]=gr_rgb(G_PAGE_RGB,level/(selected<=8?1:32));
        out[24]=gr_rgb(G_PAGE_RGB,level);out[G_PAGE_PAD]=gr_rgb(G_PAGE_RGB,level);return;
    }
#endif
    out[51]=gr_rgb(G_PAGE_RGB,level/((state->reserved>>track&1)?1:32));
    out[52]=gr_rgb(G_PAGE_RGB,level/((state->reserved>>track&1)?32:1));
    uint32_t shifted=knob>=8 && knob<16;
    if(knob>=16) knob=0;
    else if(shifted) { knob-=8;if(!gr_shift_live(knob)) knob=0; }
    knob&=7;
    out[G_PAGE_PAD]=gr_rgb(G_PAGE_RGB,level);out[25]=gr_rgb(0xffffff,level/16);
    for(uint32_t i=0;i<8;i++) {
        if(i==knob) out[60+i]=gr_rgb(color,level);
        else if(shifted) out[60+i]=gr_shift_live(i)?gr_rgb(G_PAGE_RGB,level*gr_knob_scale(gr_shift_value(state,track,i),gr_shift_centred(i))/255):0;
        else out[60+i]=gr_rgb(G_PAGE_RGB,level*gr_knob_scale(state->parameters.knob[track][i],i==3)/255);
    }
    if(state->ui.shown && state->ui.track==track) {
        const GTrack *owner=&state->owner.track[track];
        uint32_t config=state->config[track];
        uint32_t blink=owner->phase==G_QUIET && (*(volatile uint32_t *)0x20000820&128);
        out[16]=gr_rgb(config&3?0x35df74:0xff3040,blink?level/8:level);
        // Green/red is on/off, white/amber a two-way choice, page color dim/bright a toggle.
        out[17]=gr_rgb(config&32?0xffa020:0xffffff,level);
        out[18]=config&32?gr_rgb(G_PAGE_RGB,config&8?level:level/4):0;
        out[19]=gr_rgb(G_PAGE_RGB,state->setting[track]&1?level:level/4);
        out[20]=gr_rgb(G_PAGE_RGB,config&64?level:level/4);
        static const uint32_t pitch_sets[5]={G_PAGE_RGB,0xffffff,0x59d6ff,0xffc859,0xff59c2};
        uint32_t set=state->setting[track],pitch=set>>5;
        out[21]=gr_rgb(pitch_sets[set>>1&7],set>>1&7?level:level/4);
        out[22]=gr_rgb(G_PAGE_RGB,set&G_BURST_FADE?level:level/4);
        static const uint32_t burst_pitches[3]={G_PAGE_RGB,0x59d6ff,0xff59c2};
        out[23]=gr_rgb(burst_pitches[pitch],pitch?level:level/4);
    } else {
        int32_t value=shifted?gr_shift_value(state,track,knob):state->parameters.knob[track][knob];
        uint32_t centred=shifted?gr_shift_centred(knob):knob==3,bar=color;
        // Timing steps by half a pad on the tempo side.
        if(shifted && knob==2 && value>=63) value=value<66?64:64+8*((value-66)/8+1);
        // Slice and Burst show their count in half pads.
        if(shifted && (knob==G_SHIFT_SLICE+1 || knob==G_SHIFT_BURST+1)) value=(int32_t)gr_count((uint32_t)value)*8;
        for(int32_t i=0;i<8;i++) {
            int32_t fill;
            if(centred) fill=value>=64?(i>=4?value-64-(i-4)*16:0):(i<4?64-value-(3-i)*16:0);
            else fill=value-i*16;
            if(fill<0) fill=0;if(fill>16) fill=16;
            out[16+i]=gr_rgb(bar,level*(uint32_t)fill/16);
            if(!fill && (centred?(i==3 || i==4):(i==0))) out[16+i]=gr_rgb(0xffffff,level/32);
        }
    }
}
/* Companion settings are self-contained. No project-tail offsets, pointers,
 * DSP epochs or transient modal state are serialized. Validate before mutation. */
uint32_t c_gr_runtime_settings_valid(const uint8_t *b) {
    if(!b || b[0]!='G' || b[1]!='S' || (b[2]!=(G_LANE_ASSIGN?(G_EDITOR_SETTINGS?4:G_NAV_PERSIST?3:2):1) && !(G_NAV_PERSIST && (b[2]==2 || (G_EDITOR_SETTINGS && b[2]==3)))) || b[3]!=8) return 0;
    if(gr_crc(b+8,G_LANE_ASSIGN?216:152)!=((uint32_t)b[4]|(uint32_t)b[5]<<8|(uint32_t)b[6]<<16|(uint32_t)b[7]<<24)) return 0;
    for(uint32_t i=8;i<72;i++) if(b[i]>127) return 0;
    for(uint32_t t=0;t<8;t++) {
        if((b[72+t]&3)>G_TEXTURE || (b[72+t]&~(G_EDITOR_SETTINGS && b[2]==4?0xefu:0x6bu)) || b[80+t]>127 || !gr_setting_ok(b[144+t])) return 0;
    }
    for(uint32_t i=88;i<144;i++) if(b[i]>127) return 0;
#if G_LANE_ASSIGN
    for(uint32_t t=0;t<8;t++) { uint32_t seen=0;for(uint32_t k=0;k<8;k++) { uint32_t d=b[152+t*8+k];if(d>16 || (d && (seen&(1u<<d))))return 0;seen|=d?1u<<d:0; } }
    for(uint32_t i=216;i<224;i++)if(b[2]>=3?b[i]>3:b[i]!=0)return 0;
#else
    for(uint32_t i=152;i<160;i++)if(b[i])return 0;
#endif
    return 1;
}
uint32_t c_gr_runtime_settings_store(GRuntime *state,uint8_t *b) {
    if(!b || state->magic!=GR_MAGIC || state->replace_depth) return 0;
    b[0]='G';b[1]='S';b[2]=G_LANE_ASSIGN?(G_EDITOR_SETTINGS?4:G_NAV_PERSIST?3:2):1;b[3]=8;
    for(uint32_t i=0;i<64;i++) b[8+i]=((uint8_t *)&state->parameters)[i];
    for(uint32_t t=0;t<8;t++) { b[72+t]=state->config[t]&(G_EDITOR_SETTINGS?0xef:0x6b);b[80+t]=state->level[t];b[144+t]=state->setting[t]; }
    for(uint32_t i=0;i<56;i++) b[88+i]=((uint8_t *)state->shift)[i];
#if G_LANE_ASSIGN
    for(uint32_t i=0;i<64;i++)b[152+i]=((uint8_t *)state->lanes)[i];
    for(uint32_t t=0;t<8;t++)b[216+t]=G_NAV_PERSIST?((state->config[t]>>4&1)|((state->reserved>>t&1)<<1)):0;
#else
    for(uint32_t i=152;i<160;i++)b[i]=0;
#endif
    uint32_t sum=gr_crc(b+8,G_LANE_ASSIGN?216:152);
    for(uint32_t i=0;i<4;i++) b[4+i]=(uint8_t)(sum>>(8*i));
    return c_gr_runtime_settings_valid(b);
}
uint32_t c_gr_runtime_store(GRuntime *state,uint8_t *tail) {
    if(state->magic!=GR_MAGIC || state->replace_depth || !tail || !(state->flags&GR_DIRTY)) return 0;
    uint32_t saved=c_gr_project_save(tail,&state->parameters,state->config);
    if(saved) saved=c_gr_levels_save(tail,state->level);
    if(saved) saved=c_gr_shift_save(tail,state->shift[0],state->setting);
    if(saved) state->flags&=~GR_DIRTY;
    return saved;
}
uint32_t c_gr_runtime_replace_needed(const GRuntime *state,uint32_t slot) {
    if(slot>=128 || state->magic!=GR_MAGIC || !(state->flags&GR_INITIALIZED)) return 0;
    if(state->replace_depth) return 1;
    uint32_t active=0;
    for(uint32_t track=0;track<8;track++) active|=state->owner.track[track].mode;
    return active && c_gr_sample_read(0x30001+4*slot)!=0;
}
uint32_t c_gr_runtime_load(GRuntime *state,const uint8_t *tail) {
    c_gr_runtime_init(state);
    if((state->flags&GR_INITIALIZED) && !c_gr_owner_held(&state->owner)) return 0;
    uint32_t loaded=!G_EDITOR_SETTINGS && tail?c_gr_project_load(tail,&state->parameters,state->config):0;
    if(loaded!=1) {
        c_gr_params_init(&state->parameters);
        for(uint32_t track=0;track<8;track++) state->config[track]=0;
    }
    if(G_EDITOR_SETTINGS || !tail || !c_gr_levels_load(tail,state->level))
        for(uint32_t track=0;track<8;track++) state->level[track]=G_LEVEL_DEFAULT;
    if(G_EDITOR_SETTINGS || !tail || !c_gr_shift_load(tail,state->shift[0],state->setting))
        for(uint32_t track=0;track<8;track++) gr_shift_defaults(state,track);
    for(uint32_t track=0;track<8;track++) {
        GTrack *owner=&state->owner.track[track];
        owner->mode=owner->wanted=G_OFF;
        owner->phase=state->replace_depth?G_HELD:0;
        owner->settings=1|((state->config[track]>>2)&2);
    }
    state->flags&=~(GR_INITIALIZED|GR_DIRTY);
    state->cursor=state->running=state->pending=state->dirty=state->scope=0;state->tail=0;
    c_gr_ui_release(&state->ui);return loaded;
}
uint32_t c_gr_runtime_settings_load(GRuntime *state,const uint8_t *b) {
    if(b && !c_gr_runtime_settings_valid(b)) return 0;
    /* Reuse the quiescence/default reset, with no legacy decoder reached. */
    c_gr_runtime_init(state);
    if((state->flags&GR_INITIALIZED) && !c_gr_owner_held(&state->owner)) return 0;
    c_gr_runtime_load(state,0);
#if G_NAV_PERSIST
    state->reserved=0;
#endif
#if G_LANE_ASSIGN
    for(uint32_t t=0;t<8;t++) {state->assignment[t]=0;state->recording_leds[t]=0;for(uint32_t k=0;k<8;k++)state->lanes[t][k]=b?b[152+t*8+k]:0;}
#endif
    if(b) {
        for(uint32_t i=0;i<64;i++) ((uint8_t *)&state->parameters)[i]=b[8+i];
        for(uint32_t t=0;t<8;t++) { state->config[t]=b[72+t];state->level[t]=b[80+t];state->setting[t]=b[144+t];state->sync[t]=0;state->owner.track[t].settings=1|((state->config[t]>>2)&2); }
        for(uint32_t i=0;i<56;i++) ((uint8_t *)state->shift)[i]=b[88+i];
#if G_NAV_PERSIST
        if(b[2]>=3)for(uint32_t t=0;t<8;t++) {
            state->config[t]|=(b[216+t]&1)<<4;
            state->reserved|=(b[216+t]>>1&1)<<t;
        }
#endif
    }
    return 1;
}
uint32_t c_gr_runtime_begin_replace(GRuntime *state,uint32_t ready,uint32_t uploading) {
    c_gr_runtime_init(state);
    if(state->replace_depth) { state->replace_depth++;return 1; }
    if(uploading) return 0;
    state->replace_depth=1;state->running=state->pending=0;state->tail=0;c_gr_ui_release(&state->ui);
    uint32_t owned=0;
    for(uint32_t track=0;track<8;track++) if(state->owner.track[track].mode!=G_OFF) owned|=1u<<track;
    c_gr_owner_quiesce(&state->owner);
    for(uint32_t track=0;track<8;track++) if(!(owned&(1u<<track))) state->owner.track[track].phase=G_PASSHELD;
    if(!ready || !(state->flags&GR_INITIALIZED)) {
        state->flags&=~(GR_INITIALIZED|GR_READY);
        for(uint32_t track=0;track<8;track++) {
            state->owner.track[track].mode=G_OFF;state->owner.track[track].phase=G_PASSHELD;
        }
        return 1;
    }
    for(uint32_t track=0;track<8;track++) if(owned&(1u<<track)) gr_invalidate(state,track);
    for(uint32_t attempt=0;attempt<100;attempt++) {
        for(uint32_t track=0;track<8;track++) c_gr_owner_poll(&state->owner,track,GR_SNAPSHOT+8*track,c_gr_shared_read);
        if(c_gr_owner_held(&state->owner)) return 1;
        ((void(*)(uint32_t))0x08024151)(1);
    }
    // Never replace memory on timeout. Restore ordinary stock operation with
    // granular routes disabled; the native caller receives its failure result.
    for(uint32_t track=0;track<8;track++) {
        GTrack *owner=&state->owner.track[track];
        owner->mode=owner->wanted=G_OFF;owner->phase=0;state->config[track]&=~3u;
    }
    state->replace_depth=0;return 0;
}
uint32_t c_gr_runtime_end_replace(GRuntime *state) {
    if(!state->replace_depth) return 0;
    if(state->replace_depth>1) { state->replace_depth--;return 1; }
    if(state->flags&GR_READY) {
        uint32_t complete=0;
        for(uint32_t attempt=0;attempt<100;attempt++) {
            if(c_gr_shared_read(0x372fb)==0 && c_gr_shared_read(0x372fc)==0) { complete=1;break; }
            ((void(*)(uint32_t))0x08024151)(1);
        }
        if(!complete) for(uint32_t track=0;track<8;track++) state->config[track]&=~3u;
    }
    state->replace_depth=0;
    return c_gr_owner_resume(&state->owner);
}

#if G_LANE_ASSIGN
/* Ownership changes never alter recorded bytes. Only native sound lanes 0..7
 * can be assigned; mixer/send lanes keep their original recording paths. */
#define GW(a) (*(volatile uint32_t *)(a))
static uint32_t gr_item(uint32_t s,uint32_t i) { return GW(((uint32_t (*)(uint32_t,uint32_t))0x0803fc59)(s,i)); }
static GRuntime *gr_lane_state(void) {
    GRuntime *s=(void *)G_STATE;
    return s->magic==GR_MAGIC && GW(0x1440)==0x31464f53 && GW(0x1444)==GW(0x2003c0cc) && GW(0x144c)==2 && GW(G_STORAGE+4*22)?s:0;
}
static uint32_t gr_dest_value(const GRuntime *s,uint32_t t,uint32_t d) {
    return d<8?s->parameters.knob[t][d]:gr_shift_value(s,t,d-8);
}
static void gr_dest_put(GRuntime *s,uint32_t t,uint32_t d,uint32_t v) {
    if(v>127)return;
    if(d<8)c_gr_runtime_put(s,t,d,v);
    else { if(d==8)s->level[t]=(uint8_t)v;else s->shift[t][d-9]=(uint8_t)v;s->dirty|=1u<<t;s->flags|=GR_DIRTY; }
}
#if G_EDITOR_SETTINGS
/* Value-bar taps are exact values, not accelerated encoder deltas. Use the
 * same manual router and recording boundary as a turn, including held locks.
 * The shared taken-pad mask detects the two center fingers without more RAM. */
static void gr_editor_value(GRuntime *s,uint32_t t,uint32_t k,uint32_t value) {
    *(uint32_t *)(G_MENU+16)=GW(0x20006f3c);
    if(c_gr_runtime_page(s,t)) {
        uint32_t page=c_gr_runtime_knob_page(s,t);
        gr_dest_put(s,t,k+8*page,value);c_gr_lane_touch(s,t,k,page);
    } else {
        c_gr_lane_inner(0x20043700,t*16+k,value,1);
        if(!s->lanes[t][k] && (gr_item(0x200122b0,1)&255)) {
            if(((uint32_t (*)(uint32_t))(G_HELD_FN|1))(t)<32)
                ((void (*)(uint32_t,uint32_t,uint32_t))0x08047d83)(GW(0x2003d380+4*t),k,value);
            else if((gr_item(0x200122b0,0)&255) && !(gr_item(0x200122b0,2)&255))
                ((void (*)(uint32_t,uint32_t,uint32_t))0x08036b07)(0x20040d88,t*16+k,value);
        }
    }
}
uint32_t c_gr_editor_silent(GRuntime *s,uint32_t t) { return t<8 && (s->config[t]&128)!=0; }
#endif
uint32_t c_gr_lane_inner(uint32_t object,uint32_t id,uint32_t value,uint32_t flag) {
    GRuntime *s=gr_lane_state();uint32_t t=id>>4,k=id&15;
    if(s && flag==3 && t<8) {
        uint32_t lane=k<8?k:k==14?1:k==15?2:8;
        if(lane<8 && s->lanes[t][lane]) { if(k<8)gr_dest_put(s,t,s->lanes[t][lane]-1,value);return 1; }
    }
    uint32_t result=((uint32_t (*)(uint32_t,uint32_t,uint32_t,uint32_t))0x08049b29)(object,id,value,flag);
    if(s && flag==1 && t<8 && k<8 && s->lanes[t][k]) {
        uint32_t player=0x200470d4+0x190*t;
        uint32_t *touch=(void *)((uint32_t (*)(uint32_t,uint32_t))0x0803fc59)(GW(player+0x34),0);
        *touch&=~(1u<<k);
    }
    return result;
}
uint32_t c_gr_lane_gate(uint32_t object,uint32_t id,uint32_t value) {
    GRuntime *s=gr_lane_state();uint32_t t=id>>4,k=id&15;
    uint32_t lane=k<8?k:k==14?1:k==15?2:8;
    if(s && t<8 && lane<8 && s->lanes[t][lane])return 0;
    return ((uint32_t (*)(uint32_t,uint32_t,uint32_t))0x08036b07)(object-4,id,value);
}
void c_gr_lane_touch(GRuntime *s,uint32_t t,uint32_t knob,uint32_t page) {
    if(t>=8 || knob>=8 || page>1 || (s->assignment[t]&128) || !gr_lane_state())return;
    uint32_t d=knob+8*page+1,lane=8;
    for(uint32_t k=0;k<8;k++)if(s->lanes[t][k]==d)lane=k;
    if(lane>=8)return;
    uint32_t held=((uint32_t (*)(uint32_t))(G_HELD_FN|1))(t);
    if(held>=32) {
        uint32_t player=0x200470d4+0x190*t;
        uint32_t *touch=(void *)((uint32_t (*)(uint32_t,uint32_t))0x0803fc59)(GW(player+0x34),0);
        *touch&=~(1u<<lane);
        ((uint16_t *)GW(player+0x4c))[lane]=0xffff;
    }
    if(!(gr_item(0x200122b0,1)&255))return;
    s->recording_leds[t]|=1u<<(d-1);
    uint32_t value=gr_dest_value(s,t,d-1),rec=GW(0x2003d380+4*t);
    if(((uint32_t (*)(uint32_t))(G_HELD_FN|1))(t)<32)
        ((void (*)(uint32_t,uint32_t,uint32_t))0x08047d83)(rec,lane,value);
    else if((gr_item(0x200122b0,0)&255) && !(gr_item(0x200122b0,2)&255))
        ((void (*)(uint32_t,uint32_t,uint32_t))0x08036b07)(0x20040d88,16*t+lane,value);
}
__attribute__((naked,noinline)) void c_gr_lane_nativeclear(uint32_t a,uint32_t b,uint32_t c,uint32_t d) { __asm__ volatile("movs r0,#0\n bx lr"); }
uint32_t c_gr_lane_stockclear(uint32_t rec,uint32_t lane,uint32_t a,uint32_t b) {
    GRuntime *s=gr_lane_state();
    if(s && lane<8)for(uint32_t t=0;t<8;t++)if(GW(0x2003d380+4*t)==rec && s->lanes[t][lane])return 0;
    c_gr_lane_nativeclear(rec,lane,a,b);return 0;
}
static void gr_lane_changed(uint32_t t,uint32_t k) {
    uint32_t player=0x200470d4+0x190*t;
    ((uint16_t *)GW(player+0x4c))[k]=0xffff;
    uint32_t automatic=GW(0x20040d88+12+4*t);
    /* Clear only the ownership-changing lane's pending live gesture and
     * interpolation state. Its saved pattern bytes remain untouched. */
    ((uint8_t *)GW(automatic+0x28))[k]=255;
    uint32_t *pending=(void *)((uint32_t (*)(uint32_t,uint32_t))0x0803fc59)(GW(automatic+0x2c),0);
    *pending&=~(1u<<k);GW(GW(automatic+0x38))&=~(1u<<k);
}
void c_gr_lane_clear(GRuntime *s,uint32_t t,uint32_t knob,uint32_t page) {
    if(t>=8 || knob>=8 || page>1 || !gr_lane_state())return;
    uint32_t d=knob+8*page+1;s->recording_leds[t]&=~(1u<<(d-1));
    for(uint32_t k=0;k<8;k++)if(s->lanes[t][k]==d) {
        uint32_t rec=GW(0x2003d380+4*t);
        c_gr_lane_nativeclear(rec,k,0,0);
    }
}
#endif

#if G_LANE_ASSIGN
uint32_t c_gr_lane_turn(GRuntime *s,uint32_t t,uint32_t k,int32_t delta) {
    if(t>=8 || k>=8)return 0;
    uint32_t page=(s->reserved>>t)&1,d=k+8*page+1,lane=8;
    for(uint32_t n=0;n<8;n++)if(s->lanes[t][n]==d)lane=n;
    if(lane<8 && gr_lane_state() && !(s->assignment[t]&128)) {
        uint32_t held=((uint32_t (*)(uint32_t))(G_HELD_FN|1))(t);
        if(held<32) {
            uint32_t rec=GW(0x2003d380+4*t),pat=gr_item(GW(rec+0x28),0)&255;
            if(pat<8) { const uint8_t *b=(void *)(GW(rec+4)+pat*0xa28+0x128+lane*192+held*6);
                for(uint32_t m=0;m<6;m++)if(b[m]<128) {gr_dest_put(s,t,d-1,b[m]);break;}
            }
        }
    }
    uint32_t result=page?c_gr_runtime_shift_turn(s,t,k,delta):c_gr_runtime_turn(s,t,k,delta);
    if(result && delta)c_gr_lane_touch(s,t,k,page);
    return result;
}
void c_gr_lane_draw(GRuntime *s,uint32_t t,uint32_t *out,uint32_t selected) {
    if(t>=8 || !gr_lane_state())return;
    if(!c_gr_runtime_page(s,t)) {
        uint32_t color=((const uint32_t *)0x20003974)[(const uint8_t[]){0x43,0x2f,0x47,0x4b,0x37,0x25,0x12,0x3b}[t]];
        for(uint32_t k=0;k<8;k++)if(s->lanes[t][k]) {
            uint32_t rgb=out[60+k];
            /* Preserve native blue Clear-reset acknowledgement. Borrowed
             * automation is never shown as stock red or granular green. */
            if((rgb&255)>(rgb>>16&255)*2 && (rgb&255)>(rgb>>8&255)*2)continue;
            out[60+k]=gr_rgb(k==selected?color:0xffffff,gr_brightness(rgb));
        }
        if(selected<8 && s->lanes[t][selected] && !(s->ui.shown && s->ui.track==t))for(uint32_t i=0;i<8;i++) {
            uint32_t rgb=out[16+i],r=rgb>>16&255,g=rgb>>8&255,b=rgb&255;
            if(r>g*4 && r>b*4)out[16+i]=gr_rgb(color,gr_brightness(rgb));
        }
        return;
    }
    if(s->assignment[t]&128)return;
    uint32_t rec=GW(0x2003d380+4*t),page=(s->reserved>>t)&1;
    uint32_t held=((uint32_t (*)(uint32_t))(G_HELD_FN|1))(t),pat=gr_item(GW(rec+0x28),0)&255;
    if(!(gr_item(0x200122b0,1)&255))s->recording_leds[t]=0;
    uint32_t owned=0;
    for(uint32_t n=0;n<8;n++)if(s->lanes[t][n])owned|=1u<<(s->lanes[t][n]-1);
    s->recording_leds[t]&=(uint16_t)owned;
    for(uint32_t k=0;k<8;k++) { uint32_t d=k+8*page+1,v=255;
        for(uint32_t n=0;n<8;n++)if(s->lanes[t][n]==d && held<32 && pat<8) {
            const uint8_t *b=(void *)(GW(rec+4)+pat*0xa28+0x128+n*192+held*6);
            for(uint32_t m=0;m<6;m++)if(b[m]<128) {v=b[m];break;}
        }
        uint32_t level=gr_brightness(out[G_PAGE_PAD]);
        if(v<128)out[60+k]=gr_rgb(G_PAGE_RGB,level*gr_knob_scale(v,page?gr_shift_centred(k):k==3)/255);
        if(v<128 || (s->recording_leds[t]&(1u<<(d-1))))out[60+k]=gr_rgb(0xff2a1a,k==selected?level:gr_brightness(out[60+k]));
        if(v<128 && k==selected && !(s->ui.shown && s->ui.track==t)) {
            uint32_t centred=page?gr_shift_centred(k):k==3;
            uint32_t color=((const uint32_t *)0x20003974)[(const uint8_t[]){0x43,0x2f,0x47,0x4b,0x37,0x25,0x12,0x3b}[t]];
            if(page && k==2 && v>=63)v=v<66?64:64+8*((v-66)/8+1);
            if(page && (k==G_SHIFT_SLICE+1 || k==G_SHIFT_BURST+1))v=gr_count(v)*8;
            for(int32_t i=0;i<8;i++) {int32_t fill=centred?(v>=64?(i>=4?(int32_t)v-64-(i-4)*16:0):(i<4?64-(int32_t)v-(3-i)*16:0)):(int32_t)v-i*16;
                if(fill<0)fill=0;if(fill>16)fill=16;
                out[16+i]=gr_rgb(color,level*(uint32_t)fill/16);
                if(!fill && (centred?(i==3 || i==4):i==0))out[16+i]=gr_rgb(0xffffff,level/32);
            }
        }
    }
}
#endif

#if G_LANE_ASSIGN
__attribute__((naked,noinline)) uint32_t c_gr_lane_nativeview(uint32_t a,uint32_t t,uint32_t k,uint32_t step) { __asm__ volatile("movs r0,#0\n bx lr"); }
uint32_t c_gr_lane_stockview(uint32_t a,uint32_t t,uint32_t k,uint32_t step) {
    GRuntime *s=gr_lane_state();
    if(s && t<8 && k<8 && s->lanes[t][k])return 0;
    return c_gr_lane_nativeview(a,t,k,step);
}
#endif

#if G_MENU_PULSE
/* Same coefficient, phase and nonzero floor as Pattern/Step Mutate. This
 * executes after value/knob drawing so only the parameter pad pulses. */
void c_gr_menu_indicator(GRuntime *s,uint32_t t,uint32_t *out) {
    if(t>=8 || (!G_EDITOR_SETTINGS && !c_gr_runtime_page(s,t)) ||
       !((s->ui.shown && s->ui.track==t) || (s->assignment[t]&128)))return;
    uint32_t coefficient=*(volatile uint32_t *)(0x20003974+4*0x0a)&255;
    uint32_t pad=c_gr_runtime_page(s,t)?G_PAGE_PAD:25;
    uint32_t level=64+((255-coefficient)*192>>8),rgb=out[pad],result=0;
    for(uint32_t shift=0;shift<24;shift+=8)result|=(((rgb>>shift&255)*(level+1))>>8)<<shift;
    out[pad]=result;
}
#endif

#if G_TRACK_VIEWS
/* Color identifies this track's remembered parameter pad view, not engine
 * enablement. The selected track and native red confirmations keep priority. */
void c_gr_track_views(GRuntime *s,uint32_t selected,uint32_t *out) {
    if(selected>=8)return;
    for(uint32_t t=0;t<8;t++)if(t!=selected) {
        uint32_t rgb=out[32+t],r=rgb>>16&255,g=rgb>>8&255,b=rgb&255;
        if(r>4*g && r>4*b)continue;
        out[32+t]=gr_rgb(c_gr_runtime_page(s,t)?G_PAGE_RGB:0xffffff,gr_brightness(rgb));
    }
}
#endif
