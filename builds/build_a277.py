"""A277: A276 with the hardware-tested DSP gap placement enabled."""

import sys

from build_a276 import build


if __name__ == '__main__':
    if '--filter-dsp-probe' in sys.argv:
        build('fp277', ['--fill-dsp-gaps', '--filter-dsp-probe'])
    else:
        build('a277', ['--fill-dsp-gaps', '--release'])
