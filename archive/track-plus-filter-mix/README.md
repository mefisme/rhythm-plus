# Archived Track+ Filter and Mix

These source snapshots preserve the A0120 Filter and Mix implementation before
their removal from the next active firmware. They are reference material, not
build inputs. Historical builds retain their original feature switches so their
behavior can still be reproduced.

Filter envelope/LFO, added filter modes/follow, volume modulation and pan/send
movement are excluded from A0121. Normal, Pitch and FX retain their pad positions.
Shared pitch articulation, sample switches, ring modulation and sample-start scan
remain active; their source helpers cannot be deleted with the archived pages.
Existing saved Filter/Mix bytes are preserved for historical compatibility and
are ignored by A0121. They are not silently repurposed for granular settings.

The unit is unchanged until a separately chosen flash. Automation remains on hold.
