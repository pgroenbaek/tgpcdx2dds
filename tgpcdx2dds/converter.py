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

from .dds_writer import write_dds
from .tgpcdx_parser import parse_texture_xml


def convert_tgpcdx_xml_to_dds(xml_path, output_dir=None, mip_width=None):
    print()
    print("=" * 70)
    print(f"Converting: {xml_path}")
    print("=" * 70)

    mip_levels = parse_texture_xml(xml_path)

    print("Available mip levels:")

    for i, mip_level in enumerate(mip_levels):
        print(f"  {i}: {mip_level['width']}x{mip_level['height']} {mip_level['format']}")

    if mip_width is not None:
        mip_levels = [mip_level for mip_level in mip_levels if mip_level["width"] == mip_width]

        if not mip_levels:
            raise ValueError(f"No mip with width {mip_width} found.")

        mip_levels = [mip_levels[0]]

    filename = xml_path.name
    suffix = ".TgPcDx.xml"

    if filename.lower().endswith(suffix.lower()):
        texture_name = filename[:-len(suffix)]
    else:
        texture_name = xml_path.stem

    if output_dir is None:
        destination = xml_path.parent
    else:
        destination = output_dir

    output_path = destination / f"{texture_name}.dds"

    write_dds(mip_levels, output_path)
