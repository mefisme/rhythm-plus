"""A295: Ring Mod with Before/After Filter routing."""

from build_a276 import build


if __name__ == "__main__":
    build("a295", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--release"])
