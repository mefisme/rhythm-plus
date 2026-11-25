"""A313: A312 + hold a step to flash its cue slot, no delete while a jump waits, tap a waiting cue to cancel, tap the playhead to follow it, reverse and ping-pong patterns."""
from build_a276 import build
if __name__ == "__main__":
    build("a313", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--cues2", "--mm-gap", "--stretch-gap", "--k1-edge", "--cue-plus", "--release"])
