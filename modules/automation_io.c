/* Checked bounded file I/O for a future serialized worker. No driver is installed.
 * Actual sidecar opens must use exclusive creation, not stock's mode 0x13.
 */
typedef unsigned int u32;
typedef unsigned char u8;
struct FileOps {
 u32 (*seek)(u32,u32);
 u32 (*read)(u32,u8 *,u32,u32 *);
 u32 (*write)(u32,const u8 *,u32,u32 *);
 u32 (*sync)(u32);
 u32 (*tell)(u32);
};
struct Transfer {u32 offset,count,actual;};
static u32 transfer(const struct FileOps *ops,u32 context,u8 *buffer,struct Transfer *t,u32 write) {
 t->actual=0;
 if(t->count>512 || t->offset>0xffffffffu-t->count || !ops->seek || !ops->tell ||
    (write?!ops->write:!ops->read))return 4;
 if(!t->count)return 0;
 if(ops->tell(context)!=t->offset) {
  if(ops->seek(context,t->offset) || ops->tell(context)!=t->offset)return 1;
 }
 u32 result=write?ops->write(context,buffer,t->count,&t->actual):
                  ops->read(context,buffer,t->count,&t->actual);
 if(result)return 2;
 if(t->actual!=t->count)return 3;
 if(ops->tell(context)!=t->offset+t->count)return 2;
 return 0;
}
u32 c_ap_file_read(const struct FileOps *ops,u32 context,u8 *buffer,struct Transfer *t) {
 return transfer(ops,context,buffer,t,0);
}
u32 c_ap_file_write(const struct FileOps *ops,u32 context,u8 *buffer,struct Transfer *t) {
 return transfer(ops,context,buffer,t,1);
}
u32 c_ap_file_sync(const struct FileOps *ops,u32 context) {
 if(!ops->sync)return 4;
 return ops->sync(context)?2:0;
}
