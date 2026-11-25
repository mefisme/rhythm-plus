"""A304: A303 with the internal pack's Plus files on the card (1:/RP_INTERNAL), so internal projects keep the Track Parameter Editor settings when a card is in."""
from build_a276 import build
if __name__ == "__main__":
    build("a304", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--release"])
