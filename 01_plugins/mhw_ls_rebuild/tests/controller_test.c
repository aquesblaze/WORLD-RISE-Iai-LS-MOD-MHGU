#include <assert.h>
#include <stdio.h>
#include "../c/moveset.h"
static MLCommand tick(MLState*s,MLObservation*o,unsigned keys,float f){o->held=keys;o->animation_frame=f;++o->sample_sequence;return ml_step(s,o);}
static void bind(MLState*s,MLObservation*o,unsigned n){const MLMove*m=ml_move(n);o->native_action=m->native_action;o->motion=0x500+m->gu_clip;++o->bind_generation;ml_observe(s,o);assert(s->phase==ML_PLAYING);}
int main(void){
 for(unsigned side=0;side<3;++side){
  MLState s={0};MLObservation o={.actor=7,.epoch=2,.eligible=1,.native_action=4,.motion=0x569,.gauge=100,.simulation_delta=1,.magnitude=127};
  unsigned desired=side==0?ML_FADE_BACK:side==1?ML_FADE_RIGHT:ML_FADE_LEFT;
  o.input_heading=side==0?0:side==1?0x4000:0xc000;
  tick(&s,&o,0,0);assert(tick(&s,&o,ML_X|ML_A,10).kind==ML_NO_COMMAND);
  assert(tick(&s,&o,ML_X|ML_A,17).kind==ML_NO_COMMAND);
  assert(tick(&s,&o,ML_X|ML_A,18).kind==ML_NO_COMMAND); assert(tick(&s,&o,0,38).kind==ML_NO_COMMAND); assert(tick(&s,&o,0,130).kind==ML_NO_COMMAND); o.motion_finished=1; MLCommand c=tick(&s,&o,0,131);assert(c.kind==ML_COMMIT&&c.semantic==desired);
  assert(ml_step(&s,&o).kind==ML_NO_COMMAND);
  assert(!ml_should_filter(&s,&o,64,33));
  o.simulation_delta=0;for(unsigned i=0;i<100;i++)assert(tick(&s,&o,ML_X|ML_A,18).kind==ML_NO_COMMAND);
  o.simulation_delta=1;bind(&s,&o,desired);
  tick(&s,&o,0,0);const MLMove*m=ml_move(desired);
  assert(tick(&s,&o,ML_R,m->buffer_open).kind==ML_NO_COMMAND);
  tick(&s,&o,0,m->buffer_open+1);
  c=tick(&s,&o,0,m->execute_open);assert(c.semantic==ML_SPIRIT_STEP);bind(&s,&o,ML_SPIRIT_STEP);
  tick(&s,&o,0,0);o.gauge=19;assert(tick(&s,&o,ML_R,58).kind==ML_NO_COMMAND);
  o.gauge=100;c=tick(&s,&o,ML_R,58);assert(c.semantic==ML_SPIRIT_III);bind(&s,&o,ML_SPIRIT_III);
  assert(tick(&s,&o,ML_R,95).kind==ML_NO_COMMAND);
  tick(&s,&o,0,60);assert(tick(&s,&o,ML_R,75).kind==ML_NO_COMMAND);
  c=tick(&s,&o,ML_R,95);assert(c.semantic==ML_ROUND);
  ++o.epoch;ml_observe(&s,&o);assert(s.phase==ML_OFF);
 }
 MLState s={0};MLObservation o={.actor=7,.eligible=1,.native_action=4,.motion=0x569,.simulation_delta=1};
 tick(&s,&o,0,0);tick(&s,&o,ML_X|ML_A,2);tick(&s,&o,0,3);assert(tick(&s,&o,0,18).kind==ML_NO_COMMAND);
 assert(tick(&s,&o,ML_ZR,38).kind==ML_NO_COMMAND);assert(!ml_should_filter(&s,&o,16,16));
 tick(&s,&o,0,38);assert(tick(&s,&o,ML_X,38).kind==ML_NO_COMMAND);
 assert(tick(&s,&o,ML_X|ML_A,39).kind==ML_NO_COMMAND); o.motion_finished=1; assert(tick(&s,&o,0,131).kind==ML_COMMIT);
 for(unsigned i=0;i<12;i++)assert(tick(&s,&o,ML_X|ML_A,39).kind==ML_NO_COMMAND);
 assert(tick(&s,&o,ML_X|ML_A,39).kind==ML_BIND_TIMEOUT);
 o.eligible=0;ml_step(&s,&o);assert(s.phase==ML_OFF);
 puts("PASS b3: native completion gate, direction selection, full chain, released buffer, held-key consumption, gauge, bind/hitstop/timeout, scope, ZR and chord");
}
