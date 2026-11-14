/* Memory-only task serialization. Native input IRQs never access this pool;
 * Main and Content do. Match the native FreeRTOS BASEPRI ceiling (0xc0),
 * keeping peripheral IRQs serviceable while preventing a task switch.
 * Never hold this guard across native I/O, a wait, or an explicit yield.
 */
#ifndef RP_TASK_GUARD_H
#define RP_TASK_GUARD_H
#include <stdint.h>
static inline uint32_t rp_task_lock(void) {
    uint32_t irq,base,ceiling=0xc0;
    __asm__ volatile("mrs %0,primask\n cpsid i\n mrs %1,basepri\n"
                     "msr basepri_max,%2\n dsb sy\n isb sy\n msr primask,%0"
                     :"=&r"(irq),"=&r"(base):"r"(ceiling):"memory");
    return (base<<8)|(irq&1);
}
static inline void rp_task_unlock(uint32_t token) {
    uint32_t base=token>>8;
    __asm__ volatile("msr basepri,%0\n dsb sy\n isb sy"::"r"(base):"memory");
}
#endif
