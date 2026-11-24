"""
This file is part of TgPcDx2Dds.

Copyright (C) 2026 Peter Grønbæk Andersen <peter@grnbk.io>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import struct

from .formats import FORMATS

# DDS header flags
DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PIXELFORMAT = 0x1000
DDSD_LINEARSIZE = 0x80000
DDSD_MIPMAPCOUNT = 0x20000

# DDS pixel format flags
DDPF_FOURCC = 0x4

# DDS caps
DDSCAPS_COMPLEX = 0x8
DDSCAPS_TEXTURE = 0x1000
DDSCAPS_MIPMAP = 0x400000


def make_dds_header(width, height, fourcc, block_size, mip_count):
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4

    linear_size = blocks_x * blocks_y * block_size

    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE
    caps = DDSCAPS_TEXTURE

    if mip_count > 1:
        flags |= DDSD_MIPMAPCOUNT
        caps |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP

    # DDS_PIXELFORMAT structure: 32 bytes.
    pixel_format = struct.pack(
        "<8I",
        32, # dwSize
        DDPF_FOURCC, # dwFlags
        int.from_bytes(fourcc, "little"),
        0, # dwRGBBitCount
        0, # dwRBitMask
        0, # dwGBitMask
        0, # dwBBitMask
        0, # dwABitMask
    )

    # DDS_HEADER structure: 124 bytes.
    header = struct.pack(
        "<7I",
        124, # dwSize
        flags, # dwFlags
        height, # dwHeight
        width, # dwWidth
        linear_size, # dwPitchOrLinearSize
        0, # dwDepth
        mip_count, # dwMipMapCount
    )

    reserved = struct.pack("<11I", *([0] * 11))

    caps_data = struct.pack(
        "<5I",
        caps, # dwCaps
        0, # dwCaps2
        0, # dwCaps3
        0, # dwCaps4
        0, # dwReserved2
    )

    return b"DDS " + header + reserved + pixel_format + caps_data


def write_dds(mip_levels, output_path):
    if not mip_levels:
        raise ValueError("No mip levels supplied.")

    mip_format = mip_levels[0]["format"]

    for mip_level in mip_levels:
        if mip_level["format"] != mip_format:
            raise ValueError("Mip levels use different formats. They cannot be combined into one DDS mip chain.")

    format_info = FORMATS[mip_format]
    dds_type = format_info["dds_type"]
    color_offset = format_info["color_offset"]

    width = mip_levels[0]["width"]
    height = mip_levels[0]["height"]

    dds_block_size = 8 if dds_type == "DXT1" else 16

    header = make_dds_header(
        width,
        height,
        dds_type.encode("ascii"),
        dds_block_size,
        len(mip_levels)
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("wb") as f:
        f.write(header)

        for index, mip_level in enumerate(mip_levels):
            if mip_format == "HC_IMAGE_FORMAT_COMPRESSED":
                # Preserve original data blocks.
                mip_data = mip_level["data"]
            else:
                # Extract the BC1 colour block from each 16-byte block.
                # TODO: Actually figure out how the alpha channel works with INTERP_ALPHA and EXPL_ALPHA
                #       This is a bit of a temporary workaround. Its got something more than just alpha, so
                #       using the alpha channel as alpha directly makes the texture look completely wrong.
                #       Until then we just ignore the alpha channel for INTERP_ALPHA and EXPL_ALPHA.
                block_count = len(mip_level["data"]) // 16

                mip_data = b"".join(
                    mip_level["data"][i * 16 + color_offset:i * 16 + color_offset + 8]
                    for i in range(block_count)
                )

            f.write(mip_data)

            print(f"Written mip {index}: {mip_level['width']}x{mip_level['height']} ({len(mip_data):,} bytes)")

    print()
    print("Finished.")
    print(f"RailWorks format: {mip_format}")
    print(f"DDS format: {dds_type}")
    print(f"Mip levels: {len(mip_levels)}")
    print(f"Output: {output_path}")
