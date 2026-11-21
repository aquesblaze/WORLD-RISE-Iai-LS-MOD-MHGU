#include <assert.h>
#include <stdio.h>
#include "../c/world_core.h"
static WState s;
static WObservation o;
static WDecision tick(float frame,unsigned held)
{
    o.base.animation_frame=frame;o.base.held=held;++o.base.sample_sequence;
    WDecision d=w_step(&s,&o);w_input_finish(&s,&o,d);return d;
}
static void reset(unsigned idle)
{
    s=(WState){0};o=(WObservation){.base={.actor=1,.epoch=1,.sample_sequence=0,
        .native_action=idle?0:4,.motion=idle?0x501:0x569,.simulation_delta=1,.gauge=100},
        .state=idle?1:16,.drawn=1,.alive=1,.grounded=1,.rank=3,.resources_ready=1};
    tick(0,0);tick(0,0);tick(0,0);
}
static void bind(WDecision d)
{
    assert(d.kind==W_ENTER||d.kind==W_MOTION);
    o.state=16;o.base.native_action=w_action(d.move);o.base.motion=0x500+d.slot;
    o.base.animation_frame=d.motion_contract?d.start:0;o.base.motion_finished=0;
    int gauge=(int)o.base.gauge+d.gauge_delta;o.base.gauge=gauge<0?0:(unsigned)gauge;
}
static WDecision press(unsigned at,unsigned execute,unsigned keys)
{
    WDecision d={0};
    for(unsigned f=at;f<=execute;++f){
        d=tick((float)f,f<at+5?keys:0);
        if(f<execute)assert(d.kind==W_KEEP);
    }
    return d;
}
/* R needs both its maturation frames and source 306's execute bit at F80. */
static WDecision press_r(unsigned at,unsigned execute)
{
    WDecision d={0};
    for(unsigned f=at;f<=execute;++f){
        d=tick((float)f,ML_R);
        if(f<execute)assert(d.kind==W_KEEP);
    }
    return d;
}
/* A solo landing ZR waits W_LAND_CHORD_GRACE frames for a partner chord. */
static WDecision land_solo(unsigned start)
{
    WDecision d=tick((float)start,ML_R);
    assert(d.kind==W_KEEP);
    for(unsigned f=start+1;f<start+W_LAND_CHORD_GRACE;++f)
        assert(tick((float)f,0).kind==W_KEEP);
    return tick((float)(start+W_LAND_CHORD_GRACE),0);
}
int main(void)
{
    /* GU owns the actual gauge debit. A normal opener must start at I. */
    WDecision d;
    for(unsigned gauge=0;gauge<=100;++gauge){
        reset(0);o.base.gauge=gauge;d=press(22,38,ML_R);
        assert(d.kind==W_NATIVE && d.native_action==(gauge>=15?16u:17u));
        assert(!s.move && !d.gauge_delta && !d.gauge_clear);
    }
    reset(0);d=press(1,42,ML_R);assert(d.kind==W_KEEP);
    reset(0);d=press(22,38,ML_A);assert(d.kind==W_KEEP&&!s.move);
    reset(0);d=press(22,38,ML_X);assert(d.kind==W_NATIVE&&d.native_action==25);
    o.base.native_action=25;o.base.motion=0x56b;tick(0,0);
    d=press(25,42,ML_A);assert(d.kind==W_NATIVE&&d.native_action==4);
    reset(0);o.base.native_action=22;o.base.motion=0x569;tick(0,0);
    d=press(28,38,ML_X);assert(d.kind==W_NATIVE&&d.native_action==25);
    for(unsigned previous=0;previous<3;++previous){
        reset(0);o.base.native_action=25;o.base.motion=0x56b;
        o.previous_weapon_action=(unsigned[]){4,22,23}[previous];tick(0,0);
        d=press(25,42,ML_R);
        if(previous==2)assert(d.kind==W_KEEP); /* GU owns Spirit II -> upper -> III. */
        else assert(d.kind==W_NATIVE&&d.native_action==16);
    }
    for(unsigned spirit=0;spirit<2;++spirit){
        reset(0);o.base.native_action=spirit?76:69;o.base.motion=spirit?0x568:0x565;
        tick(0,0);d=press(spirit?5:60,spirit?10:70,ML_R|ML_A);
        assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
        reset(0);o.base.native_action=spirit?76:69;o.base.motion=spirit?0x568:0x565;
        tick(0,0);d=press(spirit?5:60,spirit?10:70,ML_R|ML_B);
        assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
        reset(0);o.base.native_action=spirit?76:69;o.base.motion=spirit?0x598:0x596;
        o.grounded=0;d=press(60,70,ML_R|ML_A);assert(d.kind==W_KEEP);
        d=press(80,90,ML_R|ML_B);assert(d.kind==W_KEEP);
    }
    reset(0);o.base.native_action=69;o.base.motion=0x565;tick(0,0);
    d=press(35,75,ML_R|ML_B);assert(d.kind==W_KEEP);
    /* A fresh airborne spirit chord may bridge the landing motion, but it
     * never starts a grounded sheath while the hunter is still airborne. */
    reset(0);o.base.native_action=74;o.base.motion=0x59b;o.grounded=0;
    for(unsigned f=0;f<6;++f)assert(tick(f,f==1?ML_R|ML_B:0).kind==W_KEEP);
    o.grounded=1;o.base.motion=0x59c;
    assert(tick(5,0).kind==W_KEEP);
    d=tick(10,0);assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    reset(0);o.base.native_action=76;o.base.motion=0x598;o.grounded=0;
    for(unsigned f=0;f<30;++f)assert(tick(f,f==1?ML_R|ML_B:0).kind==W_KEEP);
    o.grounded=1;o.base.motion=0x568;assert(tick(10,0).kind==W_KEEP);
    reset(0);o.base.native_action=76;o.base.motion=0x598;o.grounded=0;
    tick(1,ML_R|ML_B);o.base.epoch=2;tick(2,0);
    o.grounded=1;o.base.motion=0x568;assert(tick(10,0).kind==W_KEEP);
    reset(0);o.base.native_action=69;o.base.motion=0x565;tick(128,0);
    d=tick(135,ML_R|ML_B);assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    reset(0);o.base.native_action=76;o.base.motion=0x568;tick(60,0);
    d=press(61,71,ML_R|ML_B);assert(d.kind==W_KEEP);
    reset(0);o.base.native_action=16;o.base.motion=0x568;tick(0,0);
    d=press(36,56,ML_R|ML_B);assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    reset(0);o.base.native_action=41;o.base.motion=0x56b;tick(20,0);
    d=press(25,42,ML_A);assert(d.kind==W_NATIVE&&d.native_action==4);
    for(unsigned late=0;late<2;++late){
        reset(0);d=press(22,38,ML_R|ML_A);bind(d);tick(0,0);
        unsigned start=late?54:18,end=late?90:40;
        for(unsigned f=start;f<=end;++f){
            d=tick(f,f==start?ML_R|ML_B:0);
            if(f<end)assert(d.kind==W_KEEP);
        }
        assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    }
    for(unsigned i=0;i<3;++i){
        reset(0);o.base.native_action=(unsigned[]){7,25,41}[i];o.base.motion=0x56b;tick(20,0);
        d=press(25,42,ML_X);assert(d.kind==W_NATIVE&&d.native_action==5);
    }
    reset(0);d=tick(45,ML_R|ML_B);bind(d);d=press(65,80,ML_X);bind(d);
    d=press(30,50,ML_R|ML_A);assert(d.move==W_FORESIGHT);
    /* A Hunter Art can retain the previous weapon pose at entry. */
    for(unsigned art=51;art<=62;++art){
        reset(0);o.base.native_action=art;d=press(22,38,ML_R|ML_A);
        assert(d.kind==W_KEEP && !s.move);
    }
    reset(0);o.drawn=0;d=tick(0,0);assert(d.kind==W_KEEP);
    /* R+A is promoted before solo R. Both commands can be pending; the
     * original node4 edge order selects Foresight at the shared window. */
    reset(0);
    for(unsigned f=22;f<=38;++f){
        unsigned keys=f<27?ML_R:0;if(f>=23&&f<28)keys|=ML_A;
        d=tick((float)f,keys);if(f<38)assert(d.kind==W_KEEP);
    }
    assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
    for(unsigned i=0;i<4;++i){
        unsigned partner=i&1?ML_A:ML_X;
        unsigned first=i&2?partner:ML_R,second=i&2?ML_R:partner;
        reset(0);o.base.simulation_delta=1.000003f;
        for(unsigned f=22;f<=38;++f){
            unsigned keys=(f<28?first:0)|(f>=24&&f<28?second:0);
            d=tick((float)f,keys);if(f<38)assert(d.kind==W_KEEP);
        }
        assert(d.kind==W_ENTER&&d.move==(partner==ML_A?W_FORESIGHT:W_THRUST));
    }
    /* Dedicated post-small-Iai route, including both Spirit insertions.
     * Entry clocks are the source MBD contract, not GU native attack IDs. */
    reset(0);d=tick(45,ML_R|ML_B);assert(d.move==W_SHEATHE);bind(d);
    d=press(65,80,ML_X);assert(d.source==307);bind(d);
    d=press(30,50,ML_R);assert(d.source==363);bind(d);
    tick(0,0);d=tick(42,0);assert(d.kind==W_MOTION&&d.source==104&&d.start==42);bind(d);
    d=press(44,56,ML_A);
    assert(d.kind==W_NATIVE && d.native_action==22 && !s.move);
    assert(o.base.gauge==85);
    /* Iai stance: the B that opened the stance is consumed. A fresh B before
     * source 306's phase1 (F73) must not cut off the sheathing animation; only
     * once the stance is settled does B roll, following the analog heading. */
    reset(0);d=tick(45,ML_R|ML_B);assert(d.kind==W_ENTER&&d.move==W_SHEATHE);bind(d);
    assert(tick(65,ML_B).kind==W_KEEP);
    assert(tick(72,0).kind==W_KEEP);
    o.base.heading=1000;o.base.input_heading=30000;o.base.magnitude=100;
    d=tick(73,ML_B);
    assert(d.kind==W_ROLL&&d.heading==30000&&!s.move);
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(65,0).kind==W_KEEP);
    o.base.heading=1000;o.base.input_heading=30000;o.base.magnitude=0;
    d=tick(73,ML_B);
    assert(d.kind==W_ROLL&&d.heading==1000&&!s.move);
    /* Rise-style ISS follow-ups. Every follow-up (special sheath, roll,
     * Foresight, Spirit III) requires a successful counter; a whiff only
     * returns to the normal recovery. */
    reset(0);d=tick(45,ML_R|ML_B);assert(d.move==W_SHEATHE);bind(d);
    assert(tick(60,0).kind==W_KEEP); /* release the chord before a fresh ZR */
    d=press_r(65,80);assert(d.kind==W_ENTER&&d.move==W_BIG);bind(d);
    o.counter=1;d=tick(10,0);assert(d.rank_delta==1&&!d.gauge_clear);
    assert(tick(20,ML_R|ML_B).kind==W_KEEP); /* needs 2 stable frames */
    assert(tick(21,ML_R|ML_B).kind==W_KEEP);
    assert(tick(69,0).kind==W_KEEP);
    d=tick(70,0);
    assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    /* A successful counter can roll with a fresh solo B at the same F70. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    o.base.heading=1000;o.base.input_heading=30000;o.base.magnitude=100;
    assert(tick(20,ML_B).kind==W_KEEP); /* needs 2 stable frames */
    assert(tick(21,ML_B).kind==W_KEEP);
    assert(tick(69,0).kind==W_KEEP);
    for(unsigned f=70;f<70+W_ISS_CHORD_GRACE;++f)
        assert(tick((float)f,0).kind==W_KEEP);
    d=tick(70+W_ISS_CHORD_GRACE,0);
    assert(d.kind==W_ROLL&&d.heading==30000&&!s.move);
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    assert(tick(10,0).rank_delta==0);
    assert(tick(20,ML_B).kind==W_KEEP);
    assert(tick(70,0).kind==W_KEEP); /* a whiff cannot roll out */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;d=tick(10,0);assert(d.rank_delta==1);
    d=tick(70,ML_R|ML_A);assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    d=tick(10,0);assert(d.rank_delta==0);
    assert(tick(20,ML_R|ML_B).kind==W_KEEP);
    assert(tick(70,0).kind==W_KEEP); /* a whiff cannot re-sheathe either */
    /* A whiff cannot follow up with Foresight either; only a successful
     * counter opens the ZR+A follow-up. */
    assert(tick(71,ML_R|ML_A).kind==W_KEEP);
    /* A quick ZR+A during the counter is buffered until the F70 recovery. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    assert(tick(15,ML_R|ML_A).kind==W_KEEP);
    assert(tick(16,0).kind==W_KEEP);
    assert(tick(69,0).kind==W_KEEP);
    d=tick(70,0);assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
    /* The old source-backed Spirit III helper is no longer used after ISS;
     * the native Valor follow-up tests below own this transition. */
    /* Spirit III after ISS always uses the native Valor Spirit Slash III. A
     * stationary ZR uses the planted action; analog direction uses the
     * traveling action and steers with the sampled input heading. */
    reset(0);o.base.heading=1000;o.base.input_heading=30000;
    d=tick(45,ML_R|ML_B);assert(d.move==W_SHEATHE);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.kind==W_ENTER&&d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    assert(tick(20,ML_R).kind==W_KEEP);
    for(unsigned f=70;f<70+W_ISS_CHORD_GRACE;++f)
        assert(tick((float)f,0).kind==W_KEEP);
    o.base.magnitude=0;o.base.input_heading=30000;
    d=tick(70+W_ISS_CHORD_GRACE,0);
    assert(d.kind==W_NATIVE&&d.native_action==W_VALOR_SPIRIT_III);
    assert(d.heading==1000&&!d.gauge_delta&&!s.move);
    reset(0);o.base.heading=1000;o.base.input_heading=30000;
    d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    assert(tick(20,ML_R).kind==W_KEEP);
    for(unsigned f=70;f<70+W_ISS_CHORD_GRACE;++f)
        assert(tick((float)f,0).kind==W_KEEP);
    o.base.magnitude=100;o.base.input_heading=30000;
    d=tick(70+W_ISS_CHORD_GRACE,0);
    assert(d.kind==W_NATIVE&&d.native_action==W_VALOR_SPIRIT_III_DASH);
    assert(d.heading==30000&&!d.gauge_delta&&!s.move);
    /* Adept ISS now shares the same native Valor Spirit III follow-up; the
     * style3-only Roundslash bypass still applies to the native combo below. */
    /* The actual Adept combo is native (no plugin W_GROUND move): action26 /
     * motion56C still resolves to node2, so the same buffering applies. */
    reset(1);o.style=3;o.base.gauge=50;o.state=16;o.base.native_action=26;o.base.motion=0x56C;
    assert(tick(4,ML_R).kind==W_KEEP);
    assert(tick(90,0).kind==W_KEEP);
    d=tick(W_ADEPT_ROUNDSLASH_FRAME,0);assert(d.kind==W_NATIVE&&d.native_action==30);
    /* A partner key cancels the buffered ZR; a fresh ZR after the delay still works. */
    reset(1);o.style=3;o.base.gauge=50;o.state=16;o.base.native_action=26;o.base.motion=0x56C;
    assert(tick(4,ML_R).kind==W_KEEP);
    assert(tick(5,ML_R|ML_B).kind==W_KEEP);
    assert(tick(90,0).kind==W_KEEP);
    assert(tick(W_ADEPT_ROUNDSLASH_FRAME,0).kind==W_KEEP);
    d=tick(W_ADEPT_ROUNDSLASH_FRAME,ML_R);assert(d.kind==W_NATIVE&&d.native_action==30);
    reset(1);o.base.gauge=50;o.state=16;o.base.native_action=26;o.base.motion=0x56C;
    assert(tick(4,ML_R).kind==W_KEEP); /* Guild keeps the TIML-owned window */
    assert(tick(90,0).kind==W_KEEP);
    assert(tick(W_ADEPT_ROUNDSLASH_FRAME,0).kind==W_KEEP);
    /* Only Adept Spirit Reckoning (action 0x43) opens the World chords. Solo
     * ZR is left native, and the partner may arrive first or second. */
    for(unsigned phase=0;phase<2;++phase){
        static const unsigned mots[]={0x5B9,0x5BA};
        reset(1);o.style=3;o.state=16;
        o.base.native_action=0x43;o.base.motion=mots[phase];
        assert(press(10,14,ML_R).kind==W_KEEP);
        reset(1);o.style=3;o.state=16;
        o.base.native_action=0x43;o.base.motion=mots[phase];
        d=press(10,14,ML_R|ML_B);assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
        reset(1);o.style=3;o.state=16;
        o.base.native_action=0x43;o.base.motion=mots[phase];
        d=press(10,14,ML_R|ML_A);assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
        reset(1);o.style=3;o.state=16;
        o.base.native_action=0x43;o.base.motion=mots[phase];
        d=press(10,14,ML_R|ML_X);assert(d.kind==W_ENTER&&d.move==W_THRUST);
        reset(1);o.style=3;o.state=16;
        o.base.native_action=0x43;o.base.motion=mots[phase];
        assert(tick(10,ML_B).kind==W_KEEP);
        d=press(14,18,ML_R|ML_B);assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    }
    /* Cut-In stays native: no World chord after X. */
    reset(1);o.style=3;o.state=1;
    o.base.native_action=0xAE;o.base.motion=0x5B6;
    assert(press(10,14,ML_R|ML_B).kind==W_KEEP);
    reset(1);o.style=3;o.state=16;
    o.base.native_action=0x55;o.base.motion=0x5B9;
    assert(press(10,14,ML_R|ML_X).kind==W_KEEP);
    /* A ZR held from Cut-In into Reckoning must not steal the Reckoning pose;
     * a fresh chord after releasing ZR is required. */
    reset(1);o.style=3;o.state=16;o.base.native_action=0x55;o.base.motion=0x5B9;
    for(unsigned f=8;f<=12;++f)assert(tick((float)f,ML_R).kind==W_KEEP);
    o.base.native_action=0x43;o.base.motion=0x5B9;
    for(unsigned f=13;f<=17;++f)assert(tick((float)f,ML_R|ML_B).kind==W_KEEP);
    for(unsigned f=18;f<=19;++f)assert(tick((float)f,0).kind==W_KEEP);
    d=press(20,24,ML_R|ML_B);assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    /* Valor Spirit III is native-only too. A fresh solo ZR requests native
     * Reckoning; ZR held from the move that started it must not retrigger. */
    for(unsigned dash=0;dash<2;++dash){
        reset(1);o.state=16;
        o.base.native_action=dash?W_VALOR_SPIRIT_III_DASH:W_VALOR_SPIRIT_III;
        o.base.motion=0x5B9;
        d=tick(10,ML_R);
        assert(d.kind==W_NATIVE&&d.native_action==W_VALOR_RECKONING);
    }
    /* The earlier cut-in frames must not be cancelled by a fast ZR. */
    for(unsigned pre=0;pre<2;++pre){
        reset(1);o.state=16;
        o.base.native_action=pre?W_VALOR_SPIRIT_III_DASH:W_VALOR_SPIRIT_III;
        o.base.motion=pre?0x5C2:0x5BF;
        assert(tick(10,ML_R).kind==W_KEEP);
    }
    reset(1);o.state=16;o.base.native_action=W_VALOR_SPIRIT_III;o.base.motion=0x5B9;
    s.native_r_clear=0; /* ZR is still held from the move that started Spirit III */
    for(unsigned f=8;f<=12;++f)assert(tick((float)f,ML_R).kind==W_KEEP);
    for(unsigned f=13;f<=14;++f)assert(tick((float)f,0).kind==W_KEEP);
    d=tick(15,ML_R);
    assert(d.kind==W_NATIVE&&d.native_action==W_VALOR_RECKONING);
    /* Both Valor Spirit III and Valor Reckoning accept the World shortcuts. */
    for(unsigned phase=0;phase<2;++phase){
        static const unsigned mots[]={0x5B9,0x5BA};
        reset(1);o.state=16;o.base.native_action=W_VALOR_SPIRIT_III;o.base.motion=0x5B9;
        d=press(10,14,ML_R|ML_B);assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
        reset(1);o.state=16;o.base.native_action=W_VALOR_SPIRIT_III;o.base.motion=0x5B9;
        d=press(10,14,ML_R|ML_A);assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
        reset(1);o.state=16;o.base.native_action=W_VALOR_SPIRIT_III;o.base.motion=0x5B9;
        d=press(10,14,ML_R|ML_X);assert(d.kind==W_ENTER&&d.move==W_THRUST);
        reset(1);o.state=16;o.base.native_action=W_VALOR_RECKONING;o.base.motion=mots[phase];
        assert(press(10,14,ML_R).kind==W_KEEP);
        reset(1);o.state=16;o.base.native_action=W_VALOR_RECKONING;o.base.motion=mots[phase];
        d=press(10,14,ML_R|ML_B);assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
        reset(1);o.state=16;o.base.native_action=W_VALOR_RECKONING;o.base.motion=mots[phase];
        d=press(10,14,ML_R|ML_A);assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
        reset(1);o.state=16;o.base.native_action=W_VALOR_RECKONING;o.base.motion=mots[phase];
        d=press(10,14,ML_R|ML_X);assert(d.kind==W_ENTER&&d.move==W_THRUST);
    }
    /* Other styles and unrecognised native moves keep their native path. */
    reset(1);o.state=16;o.base.native_action=0x43;o.base.motion=0x5B9;
    assert(press(10,14,ML_R|ML_B).kind==W_KEEP);
    reset(1);o.style=3;o.state=16;o.base.native_action=0x43;o.base.motion=0x5B9;
    assert(press(10,14,ML_R|ML_Y).kind==W_KEEP);
    /* The native finisher needs 20 gauge; no source move is entered. */
    reset(0);o.base.gauge=15;d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    assert(tick(20,ML_R).kind==W_KEEP);
    for(unsigned f=70;f<=70+W_ISS_CHORD_GRACE;++f)
        assert(tick((float)f,0).kind==W_KEEP); /* 15 < 20: no finisher */
    reset(0);o.base.gauge=30;d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    assert(tick(20,ML_R).kind==W_KEEP);
    for(unsigned f=70;f<70+W_ISS_CHORD_GRACE;++f)
        assert(tick((float)f,0).kind==W_KEEP);
    d=tick(70+W_ISS_CHORD_GRACE,0);
    assert(d.kind==W_NATIVE&&d.native_action==W_VALOR_SPIRIT_III&&
           !d.gauge_delta&&!s.move);
    /* A solo ZR tapped before F20 is buffered until the counter is seen. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    assert(tick(10,0).kind==W_KEEP);
    assert(tick(15,ML_R).kind==W_KEEP);
    assert(tick(16,0).kind==W_KEEP);
    o.counter=1;assert(tick(20,0).kind==W_KEEP);
    for(unsigned f=70;f<70+W_ISS_CHORD_GRACE;++f)
        assert(tick((float)f,0).kind==W_KEEP);
    d=tick(70+W_ISS_CHORD_GRACE,0);
    assert(d.kind==W_NATIVE&&d.native_action==W_VALOR_SPIRIT_III);
    /* The ZR held from entering ISS is not a finisher press. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,ML_R).rank_delta==1);
    assert(tick(20,ML_R).kind==W_KEEP);
    /* A whiff cannot enter the finisher, and no longer opens Foresight; chords
     * keep their priority for a successful counter. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    assert(tick(10,0).rank_delta==0);
    assert(tick(20,ML_R).kind==W_KEEP);
    assert(tick(71,ML_R|ML_A).kind==W_KEEP);
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    assert(tick(20,ML_R|ML_B).kind==W_KEEP);
    assert(tick(21,ML_R|ML_B).kind==W_KEEP);
    d=tick(70,0);assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    /* One-frame taps are filtered out by the ZR/B debounce. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    assert(tick(20,ML_R|ML_B).kind==W_KEEP);
    assert(tick(21,0).kind==W_KEEP);
    assert(tick(70,0).kind==W_KEEP);
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    assert(tick(20,ML_B).kind==W_KEEP);
    assert(tick(21,0).kind==W_KEEP);
    assert(tick(70,0).kind==W_KEEP);
    for(unsigned extra=0;extra<3;++extra){
        reset(0);d=tick(45,ML_R|ML_B);bind(d);
        assert(tick(60,0).kind==W_KEEP);
        d=press_r(65,80);assert(d.move==W_BIG);bind(d);
        o.counter=1;assert(tick(10,0).rank_delta==1);
        unsigned keys=ML_R|(extra==0?ML_X:extra==1?ML_Y:ML_ZR);
        assert(tick(20,keys).kind==W_KEEP);
    }
    /* Chord race: ZR pressed a few frames before B must still become ZR+B.
     * The solo finisher waits W_ISS_CHORD_GRACE so the late B can win. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    for(unsigned f=20;f<68;++f)assert(tick((float)f,0).kind==W_KEEP);
    assert(tick(68,ML_R).kind==W_KEEP);
    assert(tick(69,ML_R).kind==W_KEEP);
    assert(tick(70,ML_R).kind==W_KEEP);
    assert(tick(71,ML_R).kind==W_KEEP);
    assert(tick(72,ML_R|ML_B).kind==W_KEEP);
    d=tick(73,ML_R|ML_B);
    assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    /* The mirrored race: B first, ZR a few frames later, is also a sheathe
     * instead of a solo B roll. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    for(unsigned f=20;f<68;++f)assert(tick((float)f,0).kind==W_KEEP);
    assert(tick(68,ML_B).kind==W_KEEP);
    assert(tick(69,ML_B).kind==W_KEEP);
    assert(tick(70,ML_B).kind==W_KEEP);
    assert(tick(71,ML_B).kind==W_KEEP);
    assert(tick(72,ML_R|ML_B).kind==W_KEEP);
    d=tick(73,ML_R|ML_B);
    assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    /* ZR + late A inside the same window becomes Foresight, not Spirit III. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    for(unsigned f=20;f<68;++f)assert(tick((float)f,0).kind==W_KEEP);
    assert(tick(68,ML_R).kind==W_KEEP);
    assert(tick(69,ML_R).kind==W_KEEP);
    assert(tick(70,ML_R).kind==W_KEEP);
    assert(tick(71,ML_R).kind==W_KEEP);
    assert(tick(72,ML_R).kind==W_KEEP);
    d=tick(73,ML_R|ML_A);
    assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
    /* A partner that arrives after the old 6-frame gate window still wins:
     * the solo ZR grace is measured from the ZR press, not only from F70.
     * ZR at F70, B at F76 -> special sheathe (not Spirit III). */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    for(unsigned f=20;f<70;++f)assert(tick((float)f,0).kind==W_KEEP);
    for(unsigned f=70;f<76;++f)assert(tick((float)f,ML_R).kind==W_KEEP);
    assert(tick(76,ML_R|ML_B).kind==W_KEEP);
    d=tick(77,ML_R|ML_B);
    assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    /* A ZR pressed after F70 also gets the full grace: ZR at F72, B at F80. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    for(unsigned f=20;f<72;++f)assert(tick((float)f,0).kind==W_KEEP);
    for(unsigned f=72;f<80;++f)assert(tick((float)f,ML_R).kind==W_KEEP);
    assert(tick(80,ML_R|ML_B).kind==W_KEEP);
    d=tick(81,ML_R|ML_B);
    assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    /* The same late-partner grace applies to Foresight: ZR at F70, A at F78. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    for(unsigned f=20;f<70;++f)assert(tick((float)f,0).kind==W_KEEP);
    for(unsigned f=70;f<78;++f)assert(tick((float)f,ML_R).kind==W_KEEP);
    d=tick(78,ML_R|ML_A);
    assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
    /* The mirrored order also works: A held first, then ZR at F71. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    for(unsigned f=20;f<70;++f)assert(tick((float)f,0).kind==W_KEEP);
    assert(tick(70,ML_A).kind==W_KEEP);
    d=tick(71,ML_R|ML_A);
    assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
    /* Even a partner pressed exactly when the solo grace expires wins: ZR at
     * F70, B at F80. The solo ZR must not fire while B is held. */
    reset(0);d=tick(45,ML_R|ML_B);bind(d);
    assert(tick(60,0).kind==W_KEEP);
    d=press_r(65,80);assert(d.move==W_BIG);bind(d);
    o.counter=1;assert(tick(10,0).rank_delta==1);
    for(unsigned f=20;f<70;++f)assert(tick((float)f,0).kind==W_KEEP);
    for(unsigned f=70;f<80;++f)assert(tick((float)f,ML_R).kind==W_KEEP);
    assert(tick(80,ML_R|ML_B).kind==W_KEEP);
    d=tick(81,ML_R|ML_B);
    assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    /* World/Outlanders Sakura Slash I landing follow-up. A fresh solo ZR
     * during the Helm landing dispatches the native Long Sword art action
     * directly, with GU's own art request flags, without an equipped slot or
     * an art gauge. Wilds-style: only yellow (2) is accepted, which is the
     * level a red Helm Breaker leaves behind. The whole dispatch stays in the
     * tree behind W_SAKURA_LANDING_ENABLED; disabled is the current default. */
#if W_SAKURA_LANDING_ENABLED
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    d=land_solo(1);
    assert(d.kind==W_NATIVE&&d.native_action==W_ART_SAKURA_SLASH&&
           d.native_flags==W_ART_SAKURA_FLAGS&&!s.move);
#else
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    d=land_solo(1);
    assert(d.kind==W_KEEP&&s.move==W_LAND&&!s.sakura_stage&&!s.sakura_denied);
#endif
    /* A late partner inside the landing grace completes the chord instead of
     * the art: ZR+B is the special sheathe, ZR+A is Foresight. This is the
     * Helm-landing misclick (ZR pressed a few frames before B/A). */
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    assert(tick(1,ML_R).kind==W_KEEP);
    d=tick(2,ML_R|ML_B);
    assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    assert(tick(1,ML_R).kind==W_KEEP);
    d=tick(2,ML_R|ML_A);
    assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
    /* The mirrored landing order: B/A held first, then ZR. */
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    assert(tick(1,ML_B).kind==W_KEEP);
    d=tick(2,ML_R|ML_B);
    assert(d.kind==W_ENTER&&d.move==W_SHEATHE);
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    assert(tick(1,ML_A).kind==W_KEEP);
    d=tick(2,ML_R|ML_A);
    assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
    /* Holding the ZR that started the dive cannot fire it; the button has to
     * be released before the landing press is accepted. The debounce is kept
     * even while the art itself is disabled. */
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;s.land_r_clear=0;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,ML_R).kind==W_KEEP);
    assert(tick(1,ML_R).kind==W_KEEP);
    assert(tick(2,ML_R).kind==W_KEEP&&s.move==W_LAND);
    assert(tick(3,0).kind==W_KEEP);
    assert(tick(4,0).kind==W_KEEP);
    d=land_solo(5);
#if W_SAKURA_LANDING_ENABLED
    assert(d.kind==W_NATIVE&&d.native_action==W_ART_SAKURA_SLASH&&!s.move);
#else
    assert(d.kind==W_KEEP&&s.move==W_LAND&&!s.sakura_stage);
#endif
    /* A partner keeps the existing landing chord; the art is solo ZR only. */
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    d=tick(1,ML_R|ML_A);
    assert(!(d.kind==W_NATIVE&&d.native_action==W_ART_SAKURA_SLASH));
#if W_SAKURA_LANDING_ENABLED
    /* The native art raises the spirit level; the follow-up converts that to
     * a one-level cost. The raise is cancelled and the cost is paid on the
     * activation frame, so the level drops with the move instead of after it. */
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    d=land_solo(1);
    assert(d.kind==W_NATIVE&&d.native_action==W_ART_SAKURA_SLASH);
    unsigned f0=1+W_LAND_CHORD_GRACE;
    /* First sweep starts and the native handler raises rank 2 -> 3. */
    o.base.native_action=W_ART_SAKURA_SLASH;o.base.motion=0x701;o.rank=3;
    d=tick((float)(f0+1),0);
    /* Cancel the raise back to 2 and pay 2 -> 1 in the same decision. */
    assert(d.rank_delta==-2&&s.sakura_paid&&s.sakura_rank==1);
    o.rank=1;
    assert(tick((float)(f0+2),0).rank_delta==0);
    o.base.native_action=W_ART_SAKURA_SWEEP;o.base.motion=0x702;
    assert(tick((float)(f0+3),0).rank_delta==0);
    o.base.native_action=W_ART_SAKURA_FINISH;o.base.motion=0x703;
    assert(tick((float)(f0+4),0).rank_delta==0);
    /* Chain ends: nothing more is charged, the cost was already paid. */
    o.base.native_action=4;o.base.motion=0x569;
    for(unsigned f=f0+5;f<f0+10;++f)assert(tick((float)f,0).rank_delta==0);
    d=tick((float)(f0+10),0);
    assert(d.rank_delta==0&&!s.sakura_stage);
    /* A red start still has the Helm landing cost queued when ZR arrives; the
     * gate judges the level after it (yellow), and the baseline follows it so
     * the two costs stack: red -> yellow -> white. */
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;s.rank=3;o.rank=3;
    s.helm_cost_pending=1;s.helm_cost_seconds=.5f;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    d=land_solo(1);
    assert(d.kind==W_NATIVE&&d.rank_delta==-1); /* Helm landing cost */
    assert(s.sakura_rank==2);
    o.rank=2; /* world_pay applied the Helm cost */
    o.base.native_action=W_ART_SAKURA_SLASH;o.base.motion=0x701;o.rank=3;
    assert(tick((float)(f0+1),0).rank_delta==-2); /* cancel native raise + pay the cost */
    o.rank=1;
    o.base.native_action=4;o.base.motion=0x569;
    for(unsigned f=f0+2;f<f0+7;++f)assert(tick((float)f,0).rank_delta==0);
    d=tick((float)(f0+7),0);
    assert(d.rank_delta==0&&!s.sakura_stage);
    /* A refused request never charges: no native art chain, no cost. */
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    assert(land_solo(1).kind==W_NATIVE);
    o.base.native_action=4;o.base.motion=0x569;
    for(unsigned f=f0+1;f<f0+91;++f)assert(tick((float)f,0).rank_delta==0);
    assert(!s.sakura_stage);
    /* Wilds-style gate: only yellow may start the art. None (0), white (1)
     * and red (3, i.e. before the Helm cost is accounted for) are refused
     * without dispatching or charging; the refusal is recorded so the adapter
     * can log it. */
    for(unsigned rank=0;rank<4;++rank){
        if(rank==2)continue;
        reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=rank;
        o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
        assert(tick(0,0).kind==W_KEEP);
        d=land_solo(1);
        assert(!(d.kind==W_NATIVE&&d.native_action==W_ART_SAKURA_SLASH));
        assert(s.move==W_LAND&&!s.sakura_stage&&s.sakura_denied==rank+1);
        for(unsigned f=f0+1;f<f0+8;++f)assert(tick((float)f,0).rank_delta==0);
    }
    /* A one-frame drawn/resource flicker at chain end must neither swallow nor
     * repeat the charge: the cost is paid at activation, and the stage still
     * has to finish cleanly. */
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    assert(land_solo(1).kind==W_NATIVE);
    o.base.native_action=W_ART_SAKURA_SLASH;o.base.motion=0x701;
    d=tick((float)(f0+1),0);
    assert(d.kind==W_KEEP&&d.rank_delta==-1&&s.sakura_paid);
    o.rank=1;
    o.base.native_action=4;o.base.motion=0x569;
    o.drawn=0;o.resources_ready=0;          /* transient gate drop */
    assert(tick((float)(f0+2),0).kind==W_KEEP);
    o.drawn=1;o.resources_ready=1;
    for(unsigned f=f0+3;f<f0+7;++f)assert(tick((float)f,0).rank_delta==0);
    d=tick((float)(f0+7),0);
    assert(d.rank_delta==0&&!s.sakura_stage);
#else
    /* Disabled by default: no native request, no rank gate, no cost. The
     * solo ZR still consumes its chord grace, so a late B/A keeps working.
     * The cost tracker stays inert even if the art animation appears from
     * elsewhere, because no Sakura request was issued by this driver. */
    unsigned f0=1+W_LAND_CHORD_GRACE;
    reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=2;
    o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
    assert(tick(0,0).kind==W_KEEP);
    d=land_solo(1);
    assert(d.kind==W_KEEP&&s.move==W_LAND&&!s.sakura_stage&&!s.sakura_denied);
    o.base.native_action=W_ART_SAKURA_SLASH;o.base.motion=0x701;o.rank=3;
    for(unsigned f=f0+1;f<f0+10;++f)assert(tick((float)f,0).rank_delta==0);
    assert(!s.sakura_stage&&!s.sakura_paid);
    for(unsigned rank=0;rank<4;++rank){
        reset(0);s.move=W_LAND;s.source=174;s.slot=229;o.rank=rank;
        o.state=16;o.base.native_action=w_action(W_LAND);o.base.motion=0x500+229;
        assert(tick(0,0).kind==W_KEEP);
        d=land_solo(1);
        assert(d.kind==W_KEEP&&s.move==W_LAND&&!s.sakura_stage&&!s.sakura_denied);
    }
#endif
    puts("PASS: Guild ownership, art pass-through, World chord, Iai settled roll, ISS follows, Spirit finish and native return");
}
