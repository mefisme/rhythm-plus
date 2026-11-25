"""A316: A315 + K2 one step for each 2 clicks, Shift pulses green while latched, a cue past the song end jumps to its last step."""
from build_a276 import build
if __name__ == "__main__":
    build("a316", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--cues2", "--mm-gap", "--stretch-gap", "--k1-edge", "--cue-plus", "--cue-latch", "--latch-tap", "--cue-tune", "--release"])
