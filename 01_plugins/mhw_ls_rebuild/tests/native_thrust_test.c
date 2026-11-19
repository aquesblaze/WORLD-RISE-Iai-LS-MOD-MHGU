#include <assert.h>
#include <stdio.h>
#include "../c/moveset.h"
int main(void){
 MLState s={0}; MLObservation o={.actor=7,.eligible=1,.native_action=4,.motion=0x569,.held=ML_X|ML_A,.simulation_delta=1};
 for(unsigned f=0;f<150;f++){o.animation_frame=f;++o.sample_sequence;o.motion_finished=f>128;
  assert(ml_step(&s,&o).kind==ML_NO_COMMAND);assert(!s.queued);
  assert(!ml_should_filter(&s,&o,16,8));assert(!ml_should_filter(&s,&o,16,28));assert(!ml_should_filter(&s,&o,16,29));
 }
 for(unsigned n=ML_FADE_BACK;n<=ML_FADE_RIGHT;n++){
  ml_reset(&s);const MLMove*m=ml_move(n);o.native_action=m->native_action;o.motion=0x500+m->gu_clip;
  o.held=0;o.animation_frame=0;++o.sample_sequence;ml_step(&s,&o);
  o.held=ML_R;o.animation_frame=m->buffer_open;++o.sample_sequence;assert(ml_step(&s,&o).kind==ML_NO_COMMAND);
  o.animation_frame=m->execute_open;++o.sample_sequence;MLCommand c=ml_step(&s,&o);assert(c.kind==ML_COMMIT&&c.native_action==48);
 }
 puts("PASS: thrust native authority at all frames, all fade requests pass, three native fades adopt into step");
}
