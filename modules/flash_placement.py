"""Write assembled code at its linked flash address."""


def emit_code(image, flash_base, address, code, placement_end=None):
    offset = address - flash_base
    if placement_end is None:
        assert offset >= len(image)
        image.extend(b'\xff' * (offset - len(image)) + code)
        image.extend(b'\xff' * (-len(image) % 4))
        return

    end = offset + len(code)
    assert 0 <= offset <= end <= placement_end - flash_base <= len(image)
    assert image[offset:end] == b'\xff' * len(code)
    image[offset:end] = code
