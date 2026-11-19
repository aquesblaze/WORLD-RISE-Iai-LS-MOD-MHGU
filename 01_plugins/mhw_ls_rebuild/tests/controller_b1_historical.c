#include <assert.h>
#include <stdio.h>
#include "../c/moveset.h"

static MLObservation base(void)
{
    return (MLObservation){.actor=7,.epoch=2,.sample_sequence=1,.eligible=1,
        .native_action=4,.motion=0x569,.phase=1,.gauge=100,.magnitude=100,.simulation_delta=1};
}
static MLCommand tick(MLState *s,MLObservation *o,unsigned keys,float frame)
{++o->sample_sequence;o->held=keys;o->animation_frame=frame;return ml_step(s,o);}
static void bind(MLState *s,MLObservation *o,unsigned semantic)
{
    const MLMove *m=ml_move(semantic);assert(m);
    o->native_action=m->native_action;o->motion=0x500+m->gu_clip;
    ++o->bind_generation;o->animation_frame=0;
    ml_observe(s,o);assert(s->phase==ML_PLAYING&&s->current==semantic);
}
int main(void)
{
    assert(ml_move(ML_FADE_LEFT)->native_action==29);
    assert(ml_move(ML_FADE_RIGHT)->native_action==28);
    assert(ml_move(ML_SPIRIT_STEP)->native_action==48);
    for(unsigned heading=0;heading<65536;heading+=4096){
        assert(ml_choose_fade(heading,(heading+0x4000)&65535,100)==ML_FADE_LEFT);
        assert(ml_choose_fade(heading,(heading+0xc000)&65535,100)==ML_FADE_RIGHT);
        assert(ml_choose_fade(heading,heading,100)==ML_FADE_BACK);
        assert(ml_choose_fade(heading,(heading+0x4000)&65535,49)==ML_FADE_BACK);
    }
    MLState s={0};MLObservation o=base();
    assert(ml_step(&s,&o).kind==ML_NO_COMMAND);
    o.input_heading=0x4000;
    assert(tick(&s,&o,ML_X|ML_A,10).kind==ML_NO_COMMAND);
    assert(tick(&s,&o,ML_X|ML_A,18).kind==ML_NO_COMMAND);
    o.input_heading=0xc000; /* after buffer capture, direction cannot flip */
    assert(tick(&s,&o,ML_X|ML_A,37).kind==ML_NO_COMMAND);
    MLCommand c=tick(&s,&o,ML_X|ML_A,38);
    assert(c.kind==ML_COMMIT&&c.semantic==ML_FADE_LEFT&&c.native_action==29);
    assert(c.input_heading==0x4000&&c.heading==0&&c.transaction==1);
    for(unsigned i=0;i<5;++i)assert(ml_step(&s,&o).kind==ML_NO_COMMAND);
    assert(s.phase==ML_WAIT_BIND);
    o.native_action=29; /* state write alone is not a playback acknowledgement */
    assert(ml_step(&s,&o).kind==ML_NO_COMMAND&&s.phase==ML_WAIT_BIND);
    assert(ml_should_filter(&s,&o,16,16));
    assert(!ml_should_filter(&s,&o,64,33)); /* system fall */
    assert(!ml_should_filter(&s,&o,1,6)); /* native dodge */
    bind(&s,&o,ML_FADE_LEFT);
    assert(ml_step(&s,&o).kind==ML_NO_COMMAND);
    assert(tick(&s,&o,0,20).kind==ML_NO_COMMAND);
    assert(tick(&s,&o,ML_R,50).kind==ML_NO_COMMAND);
    assert(tick(&s,&o,ML_R,71).kind==ML_NO_COMMAND);
    c=tick(&s,&o,ML_R,72);assert(c.semantic==ML_SPIRIT_STEP&&c.native_action==48&&c.transaction==2);
    bind(&s,&o,ML_SPIRIT_STEP);
    assert(tick(&s,&o,ML_R,60).kind==ML_NO_COMMAND); /* holding R cannot double commit */
    assert(tick(&s,&o,0,20).kind==ML_NO_COMMAND);
    assert(tick(&s,&o,ML_R,38).kind==ML_NO_COMMAND);
    c=tick(&s,&o,ML_R,58);assert(c.semantic==ML_SPIRIT_III&&c.native_action==26);
    bind(&s,&o,ML_SPIRIT_III);
    tick(&s,&o,0,60);assert(tick(&s,&o,ML_R,75).kind==ML_NO_COMMAND);
    assert(tick(&s,&o,ML_R,94).kind==ML_NO_COMMAND);
    c=tick(&s,&o,ML_R,95);assert(c.semantic==ML_ROUND&&c.native_action==30);

    /* Full chain for all three directions, including early released taps. */
    for(unsigned side=0;side<3;++side){
        ml_reset(&s);o=base();ml_step(&s,&o);
        o.input_heading=side==0?0:side==1?0x4000:0xc000;
        tick(&s,&o,ML_X|ML_A,20);tick(&s,&o,0,21);
        c=tick(&s,&o,0,38);unsigned semantic=side==0?ML_FADE_BACK:side==1?ML_FADE_LEFT:ML_FADE_RIGHT;
        assert(c.semantic==semantic);bind(&s,&o,semantic);
        const MLMove *m=ml_move(semantic);
        tick(&s,&o,ML_R,m->buffer_open);tick(&s,&o,0,m->buffer_open+1);
        c=tick(&s,&o,0,m->execute_open);assert(c.semantic==ML_SPIRIT_STEP&&c.native_action==48);
    }
    /* Startup taps expire; near-simultaneous X then A merge before execution. */
    ml_reset(&s);o=base();ml_step(&s,&o);tick(&s,&o,ML_X|ML_A,2);tick(&s,&o,0,3);
    assert(tick(&s,&o,0,38).kind==ML_NO_COMMAND);
    ml_reset(&s);o=base();ml_step(&s,&o);tick(&s,&o,ML_X,38);o.input_heading=0xc000;
    c=tick(&s,&o,ML_X|ML_A,39);assert(c.semantic==ML_FADE_RIGHT);
    ml_reset(&s);o=base();ml_step(&s,&o);tick(&s,&o,ML_X,38);
    assert(tick(&s,&o,0,39).kind==ML_NO_COMMAND);
    c=tick(&s,&o,0,40);assert(c.semantic==ML_UPPER);

    /* Waiting is measured in simulation units, not callback count. */
    ml_reset(&s);o=base();ml_step(&s,&o);c=tick(&s,&o,ML_X|ML_A,38);assert(c.kind==ML_COMMIT);
    o.simulation_delta=0;
    for(unsigned i=0;i<100;++i)assert(tick(&s,&o,ML_X|ML_A,38).kind==ML_NO_COMMAND);
    o.simulation_delta=1;
    for(unsigned i=0;i<12;++i)assert(tick(&s,&o,ML_X|ML_A,38).kind==ML_NO_COMMAND);
    assert(tick(&s,&o,ML_X|ML_A,38).kind==ML_BIND_TIMEOUT);
    assert(s.phase==ML_OFF);
    ml_reset(&s);o=base();ml_step(&s,&o);tick(&s,&o,ML_X|ML_A,20);
    o.eligible=0;assert(!ml_should_filter(&s,&o,16,8));ml_step(&s,&o);assert(s.phase==ML_OFF);
    o=base();ml_step(&s,&o);tick(&s,&o,ML_X|ML_A,38);
    o.actor=8;o.native_action=4;o.motion=0x569;o.held=ML_R;
    assert(!ml_should_filter(&s,&o,16,16)); /* old actor's pending bind owns nothing here */
    /* Gauge denial cannot become a delayed unconditional native request. */
    ml_reset(&s);o=base();o.native_action=48;o.motion=0x582;o.gauge=0;
    ml_step(&s,&o);assert(tick(&s,&o,ML_R,58).kind==ML_NO_COMMAND);
    assert(!s.queued);
    ml_reset(&s);o=base();o.native_action=26;o.motion=0x56c;o.gauge=24;
    ml_step(&s,&o);assert(tick(&s,&o,ML_R,95).kind==ML_NO_COMMAND);
    assert(!s.queued);
    /* Physical ZR is not the R gesture, and cannot enter a managed branch. */
    ml_reset(&s);o=base();ml_step(&s,&o);
    assert(tick(&s,&o,ML_ZR,38).kind==ML_NO_COMMAND&&!s.queued);
    assert(!ml_should_filter(&s,&o,16,16));
    /* Area changes invalidate a queued intent and an outstanding bind. */
    ml_reset(&s);o=base();ml_step(&s,&o);tick(&s,&o,ML_X|ML_A,20);
    ++o.epoch;o.held=0;
    assert(tick(&s,&o,0,38).kind==ML_NO_COMMAND&&!s.queued);
    c=tick(&s,&o,ML_X|ML_A,38);assert(c.kind==ML_COMMIT);
    ++o.epoch;ml_observe(&s,&o);assert(s.phase==ML_OFF);
    puts("PASS: left/right/back chains, verified action48 step, captured direction, explicit bind transaction, duplicate callbacks, chord grace/released taps, final Spirit III window, simulation-time timeout and scope/system passthrough");
}
