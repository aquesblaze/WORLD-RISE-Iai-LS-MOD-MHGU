/* Native rumble through the game's own vibration object, cut with the hit effect.
 *
 * The host does not run calls from the plugin into the sdk module, and the
 * vibration object is not one of the registered singletons, so the plugin learns
 * the object from the game itself: it hooks
 *
 *     sVibration::play(this)        main + 0x86eba4
 *         { if (!IsPlaying(this + 0x28)) Play(this + 0x28); }
 *     sVibration::stop(this)        main + 0x86ebd0
 *         { if (IsPlaying(this + 0x28)) Stop(this + 0x28); }
 *
 * (Rust side: `vib_play`) and remembers `this`.
 *
 * A rumble either holds for a fixed time, or - for the Helm hit - follows the
 * spawned hit flash. world_sfx_oriented() receives that effect instance and
 * records it for uids 0x3f61..0x3f63. The instance keeps its particle list at
 * +0x0B0 (176), each particle with a state byte at +125 (2 = alive) and a next
 * pointer at +4, the layout world_poly_update() already walks. The stop happens
 * on the frame no particle is left.
 */
#define WORLD_NATIVE_PLAY 0x86eba4u
#define WORLD_NATIVE_STOP 0x86ebd0u
#define WORLD_NATIVE_PROLOGUE 0xe92d4010u
#define WORLD_EFFECT_PARTICLES 176u
#define WORLD_EFFECT_STATE 125u
#define WORLD_RUMBLE_CAP 1.2f
#define WORLD_RUMBLE_MIN 0.10f
#define WORLD_RUMBLE_FALLBACK 0.30f

static u32 world_rumble_instance,world_rumble_ready;
static u32 world_rumble_effect;
static float world_rumble_left,world_rumble_elapsed;

/* Written by world_sfx_oriented(): last effect overall, and last hit flash. */
static u32 world_last_effect,world_last_hit_effect;

extern unsigned ml_vib_instance(void);

static void world_rumble_play(void)
{
    ((void (*)(void *))(uptr)(main_base+WORLD_NATIVE_PLAY))((void *)(uptr)world_rumble_instance);
}

static void world_rumble_stop(void)
{
    if(word((void *)main_base,WORLD_NATIVE_STOP)!=WORLD_NATIVE_PROLOGUE)return;
    ((void (*)(void *))(uptr)(main_base+WORLD_NATIVE_STOP))((void *)(uptr)world_rumble_instance);
}

static unsigned world_rumble_effect_live(u32 effect)
{
    if(!effect)return 0;
    u32 node=word((void *)(uptr)effect,WORLD_EFFECT_PARTICLES);
    for(unsigned i=0;i<64&&node;++i){
        if(byte((void *)(uptr)node,WORLD_EFFECT_STATE)==2)return 1;
        node=word((void *)(uptr)node,4);
    }
    return 0;
}


/* Diagnostic sweep: dump the pad block and the hooked wrapper so the real
 * vibration offset inside it can be identified. Read-only, never calls. */
static unsigned world_probe_left=60,world_probe_tick;
static void world_probe(void)
{
    if(!world_probe_left)return;
    if(++world_probe_tick<90)return;
    world_probe_tick=0;--world_probe_left;
    u32 pad=word((void *)main_base,0x2126888);
    if(pad<0x40000000u||pad>0x60000000u){log_event("world_probe_pad",pad,0,0,0);return;}
    int index=*(int *)((uptr)pad+0x6b60);
    if(index<0||index>4)index=0;
    u32 base=(u32)(uptr)((uptr)pad+(u32)index*0xb50u);
    u32 hook=(u32)ml_vib_instance();
    log_event("world_probe_pad",pad,(u32)index,base,hook);
    log_event("world_probe_vt",word((void *)(uptr)(base+0x7f0u),0),word((void *)(uptr)(base+0x890u),0),
        word((void *)(uptr)(base+0x930u),0),word((void *)(uptr)(base+0xa04u),0));
    log_event("world_probe_vt2",word((void *)(uptr)(base+0x818u),0),word((void *)(uptr)(base+0x8b8u),0),
        word((void *)(uptr)(base+0x958u),0),word((void *)(uptr)(base+0xa2cu),0));
    if(hook)log_event("world_probe_hook",hook,word((void *)(uptr)hook,0),word((void *)(uptr)hook,0x28),0);
}

static void world_rumble_init(void)
{
    if(world_rumble_ready)return;
    u32 instance=(u32)ml_vib_instance();
    if(!instance)return;
    world_rumble_instance=instance;world_rumble_ready=1;
    log_event("world_rumble_init",instance,word((void *)main_base,WORLD_NATIVE_PLAY),1,0);
    world_rumble_play();
    world_rumble_left=0.12f;world_rumble_elapsed=0.0f;world_rumble_effect=0;
}

static void world_rumble_start(float amp,float seconds)
{
    (void)amp;
    world_rumble_init();
    /* seconds < 0: follow the hit flash while it lives; otherwise hold the time. */
    unsigned follow=seconds<0.0f;
    u32 effect=follow?world_last_hit_effect:0;
    unsigned live=world_rumble_effect_live(effect);
    if(!live)effect=0;
    world_rumble_effect=effect;
    float hold=effect?WORLD_RUMBLE_CAP:(follow?WORLD_RUMBLE_FALLBACK:(seconds>0.0f?seconds:0.15f));
    log_event("world_rumble",(u32)(uptr)world.actor,world_rumble_effect,world_rumble_ready,
        (u32)(hold*1000.0f));
    if(!world_rumble_ready)return;
    world_rumble_play();
    world_rumble_left=hold;world_rumble_elapsed=0.0f;
}

static void world_rumble_tick(float dt)
{
    if(!world_rumble_ready){world_probe();world_rumble_init();return;}
    if(world_rumble_left<=0.0f)return;
    world_rumble_left-=dt;world_rumble_elapsed+=dt;
    if(world_rumble_effect&&world_rumble_elapsed>=WORLD_RUMBLE_MIN&&
       !world_rumble_effect_live(world_rumble_effect)){
        log_event("world_rumble_effect_end",world_rumble_effect,(u32)(world_rumble_elapsed*1000.0f),0,0);
        world_rumble_stop();world_rumble_left=0.0f;return;
    }
    if(world_rumble_left<=0.0f)world_rumble_stop();
}
