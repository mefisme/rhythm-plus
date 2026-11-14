/* Four 129-state cells in 29 bits. Exact for 0..127 plus absent=255.
 * 4608 cells -> 4176 bytes. No heap, cache, compression ratio or capacity cap.
 * Byte loads avoid assumptions about unaligned word access. */
#include <stdint.h>
typedef uint32_t P_U;typedef uint8_t P_B;
#define P_CELLS 4608u
#define P_BYTES 4176u
#define P_MAX 276922880u /* 129^4 - 1 */
static P_U group_get(const P_B *b,P_U g){
    P_U bit=g*29,at=bit>>3,shift=bit&7;
    P_U v=(P_U)b[at]|(P_U)b[at+1]<<8|(P_U)b[at+2]<<16|(P_U)b[at+3]<<24;
    v>>=shift;if(shift>3)v|=(P_U)b[at+4]<<(32-shift);
    return v&0x1fffffffu;
}
static void group_put(P_B *b,P_U g,P_U v){
    P_U bit=g*29,at=bit>>3,shift=bit&7;
    P_U old=(P_U)b[at]|(P_U)b[at+1]<<8|(P_U)b[at+2]<<16|(P_U)b[at+3]<<24;
    old=(old&~(0x1fffffffu<<shift))|(v<<shift);
    for(P_U i=0;i<4;i++)b[at+i]=(P_B)(old>>(i*8));
    if(shift>3){P_U mask=(1u<<(shift-3))-1;b[at+4]=(P_B)((b[at+4]&~mask)|(v>>(32-shift)));}
}
P_U c_pk_get(const P_B *b,P_U index){
    if(index>=P_CELLS)return 255;
    P_U g=index/4,v=group_get(b,g),n=index&3;
    while(n--)v/=129;v%=129;return v==128?255:v;
}
void c_pk_set(P_B *b,P_U index,P_U value){
    if(index>=P_CELLS || (value>127 && value!=255))return;
    static const P_U powers[4]={1,129,16641,2146689};
    P_U g=index/4,p=powers[index&3],v=group_get(b,g),old=v/p%129;
    P_U digit=value==255?128:value;
    group_put(b,g,v-old*p+digit*p);
}
void c_pk_init(P_B *b){
    for(P_U i=0;i<P_BYTES;i++)b[i]=0;
    for(P_U g=0;g<P_CELLS/4;g++)group_put(b,g,P_MAX);
}
P_U c_pk_valid(const P_B *b){
    for(P_U g=0;g<P_CELLS/4;g++)if(group_get(b,g)>P_MAX)return 0;
    return 1;
}
P_U c_pk_empty(const P_B *b){
    for(P_U g=0;g<P_CELLS/4;g++)if(group_get(b,g)!=P_MAX)return 0;
    return 1;
}
P_U c_pk_import(P_B *out,const P_B *raw){
    for(P_U i=0;i<P_CELLS;i++)if(raw[i]>127 && raw[i]!=255)return 1;
    for(P_U g=0;g<P_CELLS/4;g++){
        P_U v=0;for(P_U j=4;j;j--){P_U x=raw[g*4+j-1];v=v*129+(x==255?128:x);}group_put(out,g,v);
    }
    return 0;
}
void c_pk_export(P_B *out,const P_B *packed){for(P_U i=0;i<P_CELLS;i++)out[i]=(P_B)c_pk_get(packed,i);}
