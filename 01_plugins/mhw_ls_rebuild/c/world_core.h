#pragma once
#include "moveset.h"
#include "world_events.h"
#include "world_inputs.h"
#include "world_controls.h"

enum { W_NONE,W_FORESIGHT,W_THRUST,W_RISE,W_AIR,W_DOWN,W_LAND,W_SHEATHE,W_SMALL,W_BIG,W_SHEATHE_END,W_GROUND };
enum { W_KEEP,W_ENTER,W_NATIVE,W_IDLE,W_ROLL,W_ABORT,W_NATIVE_R,W_MOTION };
/* Back rolls keep facing the attacker: GU's native roll is rebound to this
 * appended motion slot while the pre-attack heading is restored. */
enum { WORLD_BACK_ROLL_SLOT=135, WORLD_BACK_ROLL_MOTION=0x500+WORLD_BACK_ROLL_SLOT };

static inline unsigned world_attack_back(const MLObservation *o)
{
    unsigned angle=(o->input_heading-o->heading)&65535u;
    return o->magnitude>=50&&angle>24576&&angle<40960;
}

typedef struct {
    unsigned actor,epoch,sample,held,waiting,ready;
    float remaining[3];
} WKeys;
void w_keys_tick(WKeys *keys,const MLObservation *o);
typedef struct {
    MLObservation base;
    unsigned state,drawn,alive,grounded,rank,contact,counter,resources_ready;
    unsigned previous_weapon_action,style;
} WObservation;
typedef struct {
    unsigned kind,move,source,slot,native_action,heading;
    int rank_delta,gauge_delta;
    unsigned gauge_clear,gauge_fill,regen_seconds,gauge_hold;
    unsigned motion_contract;
    unsigned native_flags; /* explicit request flags;0 keeps the legacy mapping */
    float start,blend,speed;
} WDecision;
/* Native Long Sword Hunter Art dispatch. Action51 is the art activation that
 * GU submits with request flags0x40; the action handler owns the animation and
 * its follow-up stages, so the adapter only has to reproduce that request.
 * The same handler chains action54 and action62 for the two sweeps. */
enum { W_ART_SAKURA_SLASH=51, W_ART_SAKURA_SWEEP=54, W_ART_SAKURA_FINISH=62,
       W_ART_SAKURA_FLAGS=0x40 };
/* A solo-ZR / solo-B ISS follow-up waits this many frames after the F70 gate
 * so a slightly late partner button can still complete its chord (ZR+B or
 * ZR+A) instead of the solo move winning the race. The solo ZR grace is also
 * measured from its own press, so a ZR pressed after F70 still gets the full
 * window. */
enum { W_ISS_CHORD_GRACE=10 };
/* Native Valor Spirit Slash III action ids. Requested directly after a
 * successful ISS for every style, so the planted/dash follow-up and its native
 * Reckoning chain are shared instead of using the source-backed Spirit III. */
enum { W_VALOR_SPIRIT_III=0x74, W_VALOR_SPIRIT_III_DASH=0x87,
       W_VALOR_RECKONING=0x75 };
/* Iai Spirit Slash (W_BIG) physical damage scale. 0.30 keeps 30% of the native
 * hit, i.e. a 70% reduction. Override at build time with
 * -DW_ISS_DAMAGE_SCALE=<float> if a different balance is wanted. */
#ifndef W_ISS_DAMAGE_SCALE
#define W_ISS_DAMAGE_SCALE 0.30f
#endif
/* Red Spirit Helm Breaker motion value per hit. The generated source HDP keeps
 * World's 25 MV; the plugin patches only owned red Helm shells at dispatch so
 * no ARC regeneration is needed. Override with -DW_HELM_RED_MV=<n>. */
#ifndef W_HELM_RED_MV
#define W_HELM_RED_MV 20u
#endif
/* Iai Spirit Slash counter-detector lifetime in seconds. The source shell is
 * 0.2s (12 frames at 60fps); 0.30 widens the perfect-counter window to 18
 * frames. Override at build time with -DW_ISS_COUNTER_WINDOW=<float>. The
 * iframe window comes from TIML event flags and is deliberately untouched. */
#ifndef W_ISS_COUNTER_WINDOW
#define W_ISS_COUNTER_WINDOW 0.30f
#endif
/* The Helm landing follow-up uses the same idea: a solo ZR waits this many
 * frames before it becomes Sakura Slash, so a late B/A can still complete
 * ZR+B (special sheathe) or ZR+A (Foresight). */
enum { W_LAND_CHORD_GRACE=10 };
/* Adept's native Spirit III has no TIML window, so the style3 bypass waits
 * until the ground slash has landed before starting Roundslash. The source
 * permission opens at F90; this adds a short tail to the slash animation. */
enum { W_ADEPT_ROUNDSLASH_FRAME=105 };
/* Sakura Slash I after a Spirit Helm Breaker landing. The native-art dispatch
 * and rank gate are fully implemented but currently compiled out. Set this to
 * 1 (or pass -DW_SAKURA_LANDING_ENABLED=1) to restore the follow-up without
 * rewriting the state machine. The cost tracking in w_step() stays compiled
 * and is simply inert while no art request is issued. Landing ZR+B / ZR+A
 * chords are always kept, independent of this toggle. */
#ifndef W_SAKURA_LANDING_ENABLED
#define W_SAKURA_LANDING_ENABLED 0
#endif
typedef struct {
    unsigned actor,epoch,move,source,slot,heading,rank,previous_held,sample;
    WKeys keys;
    WControls controls;
    unsigned input_motion,gu_chord_wait;
    unsigned air_sheathe_sample,air_sheathe_held;
    float air_sheathe_buffer;
    unsigned bound,consumed,queued,queued_mask,queued_source,foresight_gauge;
    unsigned queued_word,queued_shift,queued_heading;
    unsigned counter_success,hit_success,rank_paid,follow_ready;
    unsigned iss_r_held,iss_r_clear,iss_b_held; /* debounce ZR+B vs solo B */
    unsigned iss_zr_frame; /* frame the solo-ZR follow-up was latched */
    unsigned land_r_clear; /* samples since ZR was last held; gates the landing follow-up */
    unsigned land_zr_wait; /* landing solo-ZR chord grace countdown */
    /* Native-only Spirit III / Reckoning chords (no World source/TIML window). */
    unsigned native_chord,native_chord_wait,native_r_clear,adept_round_pending;
    /* Sakura Slash I follow-up: 0 off, 1 waiting for the native chain,
     * 2 playing. The native art raises the spirit level; the follow-up turns
     * that into a one-level cost, paid on the frame the chain starts so the
     * level drops with the move instead of after it. */
    unsigned sakura_stage,sakura_rank,sakura_frames,sakura_grace,sakura_paid;
    /* Set to rank+1 when a landing ZR was refused because the effective
     * spirit level was not yellow; the adapter logs it once. */
    unsigned sakura_denied;
    unsigned helm_cost_pending;
    unsigned ground_node,main_source,spirit_paid;
    float entry_start;
    unsigned turn_seen,turn_sample,turn_origin;
    int turn_delta;
    float turn_age,turn_duration,turn_fraction;
    float queue_until,hold_seconds,last_frame,helm_cost_seconds,solo_age;
    /* 登龙腾空段：R 松开过一次后才允许“再按 R 直接下劈”。 */
    unsigned helm_air_armed;
} WState;
const WClip *w_clip(unsigned source);
const WEvent *w_event(unsigned source,float frame);
enum {W_FLOAT_SPEED,W_FLOAT_TURN,W_FLOAT_CAMERA};
float w_float(unsigned source,unsigned channel,float frame);
unsigned w_source(unsigned motion);
unsigned w_foresight_stage(unsigned source,const WEvent *event);
unsigned w_action(unsigned move);
unsigned w_guild_attack(unsigned action);
unsigned w_guild_source(unsigned state,unsigned action,unsigned motion);
unsigned w_guild_spirit_opener(unsigned action,unsigned motion,unsigned previous);
unsigned w_private(unsigned state,unsigned action);
void w_reset(WState *s);
WDecision w_step(WState *s,const WObservation *o);
WDecision w_leave(WState *s);
void w_input_finish(WState *s,const WObservation *o,WDecision decision);
unsigned w_rotation(WState *s,const WObservation *o,unsigned *heading);
int w_root_heading(unsigned source,float frame);
