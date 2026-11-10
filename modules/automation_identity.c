/* Proposed 20-byte project-tail identity. No firmware hooks install this yet. */
typedef unsigned int u32;
typedef unsigned char u8;
extern u32 c_ap_crc32(const u8 *,u32,u32);

/* Caller supplies non-overlapping buffers: out[20], token[12]. */
u32 c_ap_identity_encode(u8 *out,const u8 *token) {
 u32 any=0;
 for(u32 i=0;i<12;i++)any|=token[i];
 if(!any)return 4;
 out[0]='A';out[1]='T';out[2]=1;out[3]=0;
 for(u32 i=0;i<12;i++)out[4+i]=token[i];
 u32 crc=c_ap_crc32(out,16,0);
 for(u32 i=0;i<4;i++)out[16+i]=(u8)(crc>>(i*8));
 return 0;
}
/* 0 valid, 1 absent legacy marker, 2 unsupported, 3 corrupt. No output on error. */
u32 c_ap_identity_decode(u8 *token,const u8 *in) {
 if(in[0]!='A' || in[1]!='T')return 1;
 if(in[2]!=1 || in[3])return 2;
 u32 any=0,expected=0;
 for(u32 i=0;i<12;i++)any|=in[4+i];
 for(u32 i=0;i<4;i++)expected|=(u32)in[16+i]<<(i*8);
 if(!any || expected!=c_ap_crc32(in,16,0))return 3;
 for(u32 i=0;i<12;i++)token[i]=in[4+i];
 return 0;
}
