/* Portable automation storage primitives. Not installed in any firmware build.
 * No heap, global state, DSP addresses, filesystem calls or hardware writes.
 * ARM buffers hold one DSP word per u32; only the low 24 bits are transferred.
 * Pack/unpack buffers must not overlap. Validate a decoded stream before lookup.
 */
typedef unsigned int u32;
typedef unsigned char u8;
#define NONE 65535u

static int valid(u32 e,u32 lo,u32 hi) {
 u32 pos=e&255, dest=(e>>8)&63, kind=(e>>28)&3;
 if(e>>30 || pos>=192 || kind>1 || (kind==1 && pos%6))return 0;
 return ((dest<32?lo:hi)>>(dest&31))&1;
}
static u32 key(u32 e) {return ((e&255)<<6)|((e>>8)&63);}

/* Validate the whole input before changing any destination word. */
u32 c_ap_pack(u32 *out,const u32 *in,u32 allow_lo,u32 allow_hi) {
 for(u32 i=0;i<24;i++)if(!valid(in[i],allow_lo,allow_hi))return 1;
 for(u32 i=0,j=0;i<24;i+=3,j+=4) {
  u32 a=in[i],b=in[i+1],c=in[i+2];
  out[j]=a&0xffffff;out[j+1]=(a>>24)|((b&65535)<<8);
  out[j+2]=(b>>16)|((c&255)<<16);out[j+3]=c>>8;
 }
 return 0;
}
static u32 unpack(const u32 *p,u32 n) {
 return n==0?p[0]|((p[1]&255)<<24):n==1?(p[1]>>8)|((p[2]&65535)<<16):
  (p[2]>>16)|(p[3]<<8);
}
u32 c_ap_unpack(u32 *out,const u32 *in,u32 allow_lo,u32 allow_hi) {
 for(u32 i=0;i<32;i++)if(in[i]>>24)return 1;
 for(u32 i=0;i<24;i++)if(!valid(unpack(in+(i/3)*4,i%3),allow_lo,allow_hi))return 1;
 for(u32 i=0;i<24;i++)out[i]=unpack(in+(i/3)*4,i%3);
 return 0;
}
u32 c_ap_validate_stream(const u32 *events,u32 count,u32 allow_lo,u32 allow_hi) {
 if(count>384)return 1;
 for(u32 i=0;i<count;i++)
  if(!valid(events[i],allow_lo,allow_hi) || (i && key(events[i-1])>=key(events[i])))return 1;
 return 0;
}
/* At most nine binary-search iterations for the 384-event pattern limit. */
u32 c_ap_lookup(const u32 *events,u32 count,u32 dest,u32 position) {
 if(count>384 || dest>63 || position>191)return NONE;
 u32 left=0,right=count,target=(position<<6)|dest;
 while(left<right) {
  u32 mid=left+(right-left)/2,k=key(events[mid]);
  if(k<target)left=mid+1;else right=mid;
 }
 if(left<count && key(events[left])==target)return (events[left]>>14)&16383;
 return NONE;
}
/* zlib-compatible incremental CRC32; previous=0 for the first chunk. */
u32 c_ap_crc32(const u8 *data,u32 count,u32 previous) {
 u32 crc=~previous;
 for(u32 i=0;i<count;i++) {
  crc^=data[i];
  for(u32 bit=0;bit<8;bit++)crc=(crc>>1)^((0-(crc&1))&0xedb88320);
 }
 return ~crc;
}
