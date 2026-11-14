/* Lossless 192-cell 7-bit lane codec prototype. Not installed in firmware.
 * FF is an absent event, distinct from an explicitly repeated value.
 * No heap or mutable globals; caller owns buffers. Decode publishes only after
 * complete validation. Input/output must not overlap. Maximum encoded lane 193.
 * Modes: raw, bitmap+7 bits, runs, delta varints, bitmap+deltas, dense 7 bits. */
#include <stdint.h>
typedef uint32_t U;typedef uint8_t B;
#define BAD 0xffffffffu
static int valid(B v){return v<=127 || v==255;}
static U varlen(U v){return v>=128?2:1;}
static U putvar(B *b,U at,U v){if(v>=128)b[at++]=(B)(v|128),v>>=7;b[at++]=(B)v;return at;}
static U getvar(const B *b,U n,U *p){
    if(*p>=n)return BAD;U v=b[(*p)++];if(v<128)return v;
    if(*p>=n || b[*p]>=4)return BAD;return (v&127)|((U)b[(*p)++]<<7);
}
static void bits_put(B *b,U at,U width,U value){
    for(U j=0;j<width;j++)if(value>>j&1)b[(at+j)>>3]|=1u<<((at+j)&7);
}
static U bits_get(const B *b,U at,U width){
    U v=0;for(U j=0;j<width;j++)v|=((b[(at+j)>>3]>>((at+j)&7))&1)<<j;return v;
}
static U zz(int d){return d<0?(U)(-d*2-1):(U)d*2;}
U c_lc_encode(B *out,U cap,const B *in){
    U count=0,runlen=1,deltalen=1,width=0,previous=0,first=0;
    for(U i=0;i<192;i++){
        if(!valid(in[i]))return BAD;
        if(in[i]!=255){
            U z=zz((int)in[i]-(int)previous);
            if(count){U w=0,v=z;while(v){w++;v>>=1;}if(w>width)width=w;}else first=in[i];
            previous=in[i];count++;
        }
    }
    if(!count)return 0;
    previous=0;
    for(U i=0;i<192;){
        U end=i+1;while(end<192 && in[end]==in[i])end++;
        runlen+=varlen(((end-i)<<1)|(in[i]!=255))+(in[i]!=255);i=end;
    }
    for(U i=0;i<192;){
        if(in[i]==255){U end=i+1;while(end<192 && in[end]==255)end++;deltalen+=varlen((end-i)<<1);i=end;}
        else {deltalen+=varlen((zz((int)in[i]-(int)previous)<<1)|1);previous=in[i++];}
    }
    U lengths[6]={193,25+(count*7+7)/8,runlen,deltalen,27+((count-1)*width+7)/8,count==192?169:BAD};
    U mode=0;for(U i=1;i<6;i++)if(lengths[i]<lengths[mode])mode=i;
    U n=lengths[mode];if(cap<n)return BAD;
    for(U i=0;i<n;i++)out[i]=0;out[0]=(B)mode;
    if(!mode){for(U i=0;i<192;i++)out[i+1]=in[i];return n;}
    if(mode==5){for(U i=0;i<192;i++)bits_put(out+1,i*7,7,in[i]);return n;}
    if(mode==1 || mode==4){
        U pos=0;previous=first;
        if(mode==4){out[25]=(B)width;out[26]=(B)first;}
        for(U i=0;i<192;i++)if(in[i]!=255){
            out[1+(i>>3)]|=1u<<(i&7);
            if(mode==1)bits_put(out+25,pos++*7,7,in[i]);
            else {if(pos)bits_put(out+27,(pos-1)*width,width,zz((int)in[i]-(int)previous));previous=in[i];pos++;}
        }
        return n;
    }
    U at=1;previous=0;
    for(U i=0;i<192;){
        if(mode==2 || in[i]==255){
            U end=i+1;while(end<192 && in[end]==in[i])end++;
            at=putvar(out,at,((end-i)<<1)|(in[i]!=255));
            if(in[i]!=255)out[at++]=in[i];i=end;
        }else {at=putvar(out,at,(zz((int)in[i]-(int)previous)<<1)|1);previous=in[i++];}
    }
    return at;
}
U c_lc_decode(B *out,const B *in,U n){
    B tmp[192];for(U i=0;i<192;i++)tmp[i]=255;
    if(n>193)return 1;
    if(n){
        U mode=in[0];if(mode>5)return 1;
        if(!mode){if(n!=193)return 1;for(U i=0;i<192;i++){if(!valid(in[i+1]))return 1;tmp[i]=in[i+1];}}
        else if(mode==5){if(n!=169)return 1;for(U i=0;i<192;i++)tmp[i]=(B)bits_get(in+1,i*7,7);}
        else if(mode==1 || mode==4){
            if(n<(mode==1?25u:27u))return 1;
            U count=0;for(U i=0;i<192;i++)if(in[1+(i>>3)]>>(i&7)&1)count++;
            if(!count)return 1;
            U width=mode==1?7:in[25],start=mode==1?25:27;
            if(width>8 || (mode==4 && in[26]>127))return 1;
            U total=(mode==1?count:count-1)*width;
            if(n!=start+(total+7)/8)return 1;
            if((total&7) && (in[n-1]>>(total&7)))return 1;
            U pos=0;int previous=mode==1?0:in[26];
            for(U i=0;i<192;i++)if(in[1+(i>>3)]>>(i&7)&1){
                if(mode==1)tmp[i]=(B)bits_get(in+start,pos*width,width);
                else {if(pos){U z=bits_get(in+start,(pos-1)*width,width);previous+=z&1?-(int)(z/2)-1:(int)(z/2);}
                    if(previous<0 || previous>127)return 1;tmp[i]=(B)previous;}
                pos++;
            }
        }else {
            U at=1,i=0;int previous=0;
            while(i<192){
                U token=getvar(in,n,&at);if(token==BAD)return 1;
                if(mode==2 || !(token&1)){
                    U run=token>>1;if(!run || run>192-i)return 1;B v=255;
                    if(token&1){if(at>=n || in[at]>127)return 1;v=in[at++];}
                    while(run--)tmp[i++]=v;
                }else {U z=token>>1;previous+=z&1?-(int)(z/2)-1:(int)(z/2);
                    if(previous<0 || previous>127)return 1;tmp[i++]=(B)previous;}
            }
            if(at!=n)return 1;
        }
    }
    for(U i=0;i<192;i++)out[i]=tmp[i];return 0;
}
