"""Deterministic host capacity scenarios. No claims of hardware memory ownership."""
import json
from automation_model import Bank, CapacityError


def scenario(name, tracks, patterns, continuous=0, locks=0, lock_steps=0):
    return dict(name=name, tracks=tracks, patterns=patterns, continuous=continuous,
                locks=locks, lock_steps=lock_steps)


SCENARIOS = [
    scenario("eight tracks, one dense continuous destination", 8, 1, continuous=1),
    scenario("eight tracks, two dense continuous destinations", 8, 1, continuous=2),
    scenario("eight tracks, one dense continuous + four locks on 16 steps", 8, 1,
             continuous=1, locks=4, lock_steps=16),
    scenario("all 64 patterns, one lock destination on all 32 steps", 8, 8,
             locks=1, lock_steps=32),
    scenario("all 64 patterns, two lock destinations on all 32 steps", 8, 8,
             locks=2, lock_steps=32),
    scenario("all 64 patterns, four lock destinations on eight steps", 8, 8,
             locks=4, lock_steps=8),
    scenario("four-pattern chain per track, two locks on 16 steps", 8, 4,
             locks=2, lock_steps=16),
    scenario("all 64 patterns, one fully dense continuous destination", 8, 8,
             continuous=1),
]


def measure(case, kib=24, minimum=1):
    # Whole physical blocks only, keeping the full 3KiB metadata allowance.
    blocks = (kib*1024 - 3072) // 96
    bank = Bank(blocks, minimum_blocks=minimum)
    completed = 0
    failure = None
    try:
        for track in range(case["tracks"]):
            for pattern in range(case["patterns"]):
                index = track*8 + pattern
                for step in range(32):
                    destinations = (4, 8)[:case["continuous"]]
                    if destinations:
                        bank.record_step(index, step, destinations,
                                         {(d, m): (step*619+m*83)&16383
                                          for d in destinations for m in range(6)})
                    if step < case["lock_steps"]:
                        bank.lock_step(index, step,
                                       {d: (step*619)&16383
                                        for d in (0, 1, 3, 13)[:case["locks"]]})
                completed += 1
    except CapacityError as error:
        failure = str(error)
    return dict(scenario=case["name"], budget_kib=kib, guaranteed_events=minimum*24,
                payload_blocks=blocks, physical_bank_bytes=3072+blocks*96,
                completed_patterns=completed, requested_patterns=case["tracks"]*case["patterns"],
                fits=failure is None, failure=failure, charged_blocks=bank.used_blocks,
                events=sum(len(pattern.events) for pattern in bank.patterns))


if __name__ == "__main__":
    print(json.dumps([measure(case, kib, minimum)
                      for kib in (16, 20, 24) for minimum in (1, 2)
                      for case in SCENARIOS], indent=2))
