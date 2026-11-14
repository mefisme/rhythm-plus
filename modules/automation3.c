/* Three private 7-bit lanes, eight patterns, six cells per step.
 * ROM timing/interpolation tables and quantization match native Rhythm 5706.
 * This core has no filesystem, DSP, project-tail or native lane writes.
 */
#include "automation3.h"
typedef a3_u32 U;typedef a3_u16 H;typedef a3_u8 B;
#if COW7
#define bank_get(b,i) c_a3_bankget(b,i)
#define bank_set(b,i,v) c_a3_bankset(b,i,v)
#elif PACK129
#define bank_get(b,i) c_pk_get(b,i)
#define bank_set(b,i,v) c_pk_set(b,i,v)
#else
#define bank_get(b,i) ((b)[i])
#define bank_set(b,i,v) ((b)[i]=(B)(v))
#endif
static U at(U k,U p,U step,U micro){return (k*8+p)*192+step*6+micro;}
static U value(B b){return b==255?A3_NONE:b;}
static U valid_pos(U p,U step,U pulse,U rate){return p<8 && step<32 && rate<8 && pulse<((const U *)0x08068d9c)[rate];}
static void cell(struct a3_state *s,B *bank,U index,U v){
    if(index>=A3_CELLS || (v>127 && v!=A3_NONE))return;
    B b=v==A3_NONE?255:(B)v;
    if(bank_get(bank,index)!=b){bank_set(bank,index,b);s->generation++;s->writes++;}
}
void c_a3_disarm(struct a3_state *s){
    s->touched=0;for(U k=0;k<3;k++){s->pending[k]=A3_NONE;s->prev_valid[k]=0;}
}
void c_a3_reset(struct a3_state *s){
    c_a3_disarm(s);for(U k=0;k<3;k++)s->held[k]=s->last[k]=A3_NONE;
}
void c_a3_init(struct a3_state *s,B *bank){
#if COW7
    U epoch=s->magic==0x31533341 && s->guard==0x31533341?s->epoch+1:1;
#endif
    for(U i=0;i<sizeof(*s);i++)((B *)s)[i]=0;
#if COW7
    c_a3_bankinit();
#elif PACK129
    c_pk_init(bank);
#else
    for(U i=0;i<A3_CELLS;i++)bank[i]=255;
#endif
    s->magic=s->guard=0x31533341;s->fx=255;
#if COW7
    s->epoch=epoch;
#endif
    c_a3_reset(s);for(U k=0;k<3;k++)s->output[k]=A3_NONE;
}
void c_a3_manual(struct a3_state *s,U k,U v,U recording){
    if(k>=3 || v>127)return;
    s->output[k]=(H)v;
    if(recording){s->pending[k]=(H)v;s->touched|=1u<<k;}
    else {s->pending[k]=A3_NONE;s->prev_valid[k]=0;s->touched&=~(1u<<k);}
}
U c_a3_clear(struct a3_state *s,B *bank,U k,U p,U step){
    if(k>=3 || p>=8)return 1;
    U first=step<32?step*6:0,count=step<32?6:192;
    for(U i=0;i<count;i++)cell(s,bank,(k*8+p)*192+first+i,A3_NONE);
    s->held[k]=s->last[k]=s->pending[k]=s->output[k]=A3_NONE;
    s->prev_valid[k]=0;s->touched&=~(1u<<k);return 0;
}
U c_a3_lock(struct a3_state *s,B *bank,U k,U p,U step,U v){
    if(k>=3 || p>=8 || step>=32 || v>127)return 1;
    cell(s,bank,at(k,p,step,0),v);
    for(U i=1;i<6;i++)cell(s,bank,at(k,p,step,i),A3_NONE);
    c_a3_manual(s,k,v,0);return 0;
}
U c_a3_bulk(struct a3_state *s,B *bank,U op,U sp,U ss,U dp,U ds){
    if(op>4 || (op<4 && dp>=8) || ((op==0 || op==2) && sp>=8) ||
       ((op==2 || op==3) && ds>=32) || (op==2 && ss>=32))return 1;
    if((op==0 && sp==dp) || (op==2 && sp==dp && ss==ds))return 0;
#if COW7
    U error=c_a3_bankbulk(op,sp,ss,dp,ds);if(error)return error;
    s->generation++;
#else
    U count=op==4?1536:(op==2 || op==3)?6:192,changed=0;
    for(U k=0;k<3;k++){
        U dest=op==4?k*1536:(k*8+dp)*192+((op==2 || op==3)?ds*6:0);
        U src=(k*8+sp)*192+(op==2?ss*6:0);
        for(U i=0;i<count;i++){
            B v=op==0 || op==2?bank_get(bank,src+i):255;
            if(bank_get(bank,dest+i)!=v){bank_set(bank,dest+i,v);changed++;}
        }
    }
    if(changed){s->generation++;s->writes+=changed;}
#endif
    /* A bulk edit invalidates interpolation/touch state, but holds the current
     * sound until a subsequent automation value or manual move replaces it. */
    c_a3_reset(s);s->padding[0]=0;return 0;
}
void c_a3_record(struct a3_state *s,B *bank,U p,U step,U pulse,U rate){
    if(!valid_pos(p,step,pulse,rate))return;
    U micro=((U (*)(U,U))0x0804ab25)(pulse,rate);
    if(micro>=6)return;
    for(U k=0;k<3;k++)if(s->touched&(1u<<k)){
        U v=s->pending[k];s->pending[k]=A3_NONE;
        if(s->prev_valid[k]){
            U r=s->prev_rate[k],m=s->prev_micro[k];
            U n=r==0?2:r==1?1:r==2 && (m==0 || m==3)?1:0;
            for(U j=1;j<=n;j++){
                U bridge=A3_NONE,old=s->previous[k];
                if(old!=A3_NONE && v!=A3_NONE)bridge=n==1?(old+v)/2:j==1?(old*2+v)/3:(old+v*2)/3;
                U index=s->prev_step[k]*6+m+j;
                if(index<192)cell(s,bank,(k*8+s->prev_pattern[k])*192+index,bridge);
            }
        }
        cell(s,bank,at(k,p,step,micro),v);
        s->prev_valid[k]=(B)(rate<3);s->previous[k]=(H)v;
        s->prev_pattern[k]=(B)p;s->prev_step[k]=(B)step;s->prev_micro[k]=(B)micro;s->prev_rate[k]=(B)rate;
    }
}
U c_a3_value(struct a3_state *s,const B *bank,U k,U p,U step,U pulse,U rate,U next){
    if(k>=3 || !valid_pos(p,step,pulse,rate))return A3_NONE;
    U v=A3_NONE,offset=(k*8+p)*192+step*6;
    if(rate<4){U m=((const B *)0x0806651c)[rate*24+pulse];if(m<6)v=value(bank_get(bank,offset+m));}
    else {
        U length=((const U *)0x08068d9c)[rate],m=pulse*6/length;
        U a=value(bank_get(bank,offset+m)),b=m<5?value(bank_get(bank,offset+m+1)):next;
        if(a!=A3_NONE){
            if(b!=A3_NONE){const B *w=(const B *)0x0806645c+(rate-4)*48+pulse*2;v=(a*w[0]+b*w[1])>>3;}
            else if(!pulse || (pulse-1)*6/length!=m)v=a;
        }
    }
    if(v==A3_NONE)v=s->held[k];s->held[k]=A3_NONE;
    if(rate<3){
        U m=rate==0?pulse*3+2:rate==1?pulse*2+1:pulse==0?1:pulse==2?4:192;
        if(m<6)s->held[k]=(H)value(bank_get(bank,offset+m));
        if(rate==0 && s->held[k]==A3_NONE)s->held[k]=(H)value(bank_get(bank,offset+pulse*3+1));
    }
    if(v!=A3_NONE && v!=s->last[k] && !(s->touched&(1u<<k))){s->output[k]=(H)v;s->applies++;}
    s->last[k]=(H)v;
    return s->output[k];
}
