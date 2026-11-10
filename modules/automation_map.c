/* Candidate X-only bank mapping primitives, not installed in AD007.
 * Validate against the full build ownership ledger before enabling any bank.
 * This whitelist excludes the Grid FX workspace discovered on hardware.
 */
typedef unsigned int u32;
struct Span {u32 start,words;};
static int allowed(const struct Span *span) {
 static const u32 holes[10]={0x1420,0x1600,0x2400,0x3000,0x4000,0x4400,
                             0x4d00,0x4f80,0x4f90,0x6000};
 if(!span->words || span->words%32 || span->start>=0x6000 || span->words>0x6000-span->start)return 0;
 for(u32 i=0;i<10;i+=2)
  if(span->start>=holes[i] && span->start+span->words<=holes[i+1])return 1;
 return 0;
}
u32 c_ap_map_validate(const struct Span *spans,u32 count) {
 if(!count || count>8)return 1;
 u32 total=0;
 for(u32 i=0;i<count;i++) {
  if(!allowed(spans+i) || spans[i].words>8192-total)return 1;
  total+=spans[i].words;
  for(u32 j=0;j<i;j++)
   if(spans[i].start<spans[j].start+spans[j].words && spans[j].start<spans[i].start+spans[i].words)return 1;
 }
 return 0;
}
u32 c_ap_map_word(const struct Span *spans,u32 count,u32 index) {
 if(index>=8192 || c_ap_map_validate(spans,count))return 0xffffffff;
 for(u32 i=0;i<count;i++) {
  if(index<spans[i].words)return spans[i].start+index;
  index-=spans[i].words;
 }
 return 0xffffffff;
}
