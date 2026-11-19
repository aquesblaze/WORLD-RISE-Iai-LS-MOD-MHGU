#include "../c/world_input_vm.h"
#include "../c/world_gesture_vm.h"
#include "../c/world_controls.h"
#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif
EXPORT void button_tick(WButton *b,float seconds){w_button_tick(b,seconds);}
EXPORT void command_collect(WCommands *c,unsigned id,unsigned p,unsigned g,
                            unsigned p2,unsigned g2,unsigned layer)
{w_command_collect(c,id,p,g,p2,g2,layer);}
EXPORT void command_promote(WCommands *c,unsigned id){w_command_promote(c,id);}
EXPORT unsigned command_query(const WCommands *c,WCommandQueries *q,unsigned id,
    unsigned kind,unsigned mode,unsigned allowed,unsigned execute)
{return w_command_query(c,q,id,kind,mode,allowed,execute);}
EXPORT void gestures(WGestures *out,const WButton *buttons,unsigned stick,unsigned direction,unsigned roll_direction)
{*out=w_gestures(buttons,buttons+1,buttons+2,buttons+3,stick,direction,roll_direction);}
EXPORT void command_prune(WCommands *c,WCommandQueries *q,uint32_t *previous,
    const uint32_t *primary,const uint32_t *secondary,unsigned force,unsigned changed_primary,unsigned changed_secondary)
{w_command_prune(c,q,previous,primary,secondary,force,changed_primary,changed_secondary);}
EXPORT void command_conflicts(WCommands *c,const WCommandQueries *q,const uint32_t *previous)
{w_command_conflicts(c,q,previous);}
EXPORT unsigned controls_size(void){return sizeof(WControls);}
EXPORT void controls_tick(WControls *s,unsigned actor,unsigned epoch,unsigned sample,unsigned held,
    float seconds,const uint32_t *permission,const float *direction,unsigned stick,unsigned face,unsigned roll)
{w_controls_tick(s,actor,epoch,sample,held,seconds,permission,direction,stick,face,roll);}
EXPORT unsigned controls_query(WControls *s,unsigned id,unsigned edge,unsigned mode)
{return w_controls_query(s,id,edge,mode);}
EXPORT void controls_bind(WControls *s){w_controls_bind(s);}
EXPORT void controls_finish(WControls *s,const uint32_t *p){w_controls_finish(s,p);}
EXPORT void controls_snapshot(const WControls *s,void *out)
{
    unsigned char *p=out;const unsigned char *parts[]={
        (const void *)s->buttons,(const void *)&s->commands,
        (const void *)&s->queries,(const void *)s->previous_queries};
    const unsigned sizes[]={160,172,60,20};
    for(unsigned part=0;part<4;++part)for(unsigned i=0;i<sizes[part];++i)*p++=parts[part][i];
}
