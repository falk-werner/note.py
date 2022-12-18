#!/usr/bin/env python3

import fontforge
import argparse
import base64
import sys

def convert(fontname):
    glyphs = ["plus", "papers", "look", "camera", "spinner-alt-3", "bin"]

    new_name = fontname + ".min.ttf"
    base_font = fontforge.open(fontname)
    new_font = fontforge.font()

    for glyph in glyphs:
        slot = base_font.findEncodingSlot(glyph)
        base_font.selection.select(glyph)
        base_font.copy()

        glyph_name = glyph if glyph != "plus" else "plus-2"
        new_font.createChar(slot, glyph_name)
        new_font.selection.select(glyph_name)
        new_font.paste()

    base_font.close()

    new_font.fontname="notepy"
    new_font.generate(new_name)
    new_font.close()

    data = b''
    with open(new_name, "rb") as f:
        data = f.read()

    value = base64.b64encode(data).decode('utf-8')
    i = 0
    while i < len(value):
        j = i + 60
        print("\"%s\"" % value[i:j])
        i = j


def print_glyphs(fontname):
    font = fontforge.open(fontname)
    for glyph in font:
        slot = font.findEncodingSlot(glyph) 
        print("%s: %d" % (glyph, slot))

def find_glyph_names(fontname):
    slot_map = dict()
    font = fontforge.open(fontname)
    for glyph in font:
        slot = font.findEncodingSlot(glyph)
        slot_map[slot] = glyph

    slots = [ 0xefc2, 0xefb6, 0xef7f, 0xeecf, 0xeff6, 0xeebb ]
    for slot in slots:
        if slot in slot_map:
            glyph = slot_map[slot]
            print(glyph)
        else:
            print("not found")


def main():
    parser =argparse.ArgumentParser()
    parser.add_argument("-f", "--font", required=True, type=str)
    subparsers = parser.add_subparsers(dest="command", required=True)
    sub = subparsers.add_parser("print_glyphs")
    sub = subparsers.add_parser("find_glyphs")
    sub = subparsers.add_parser("convert")
    args = parser.parse_args()

    if args.command == "print_glyphs":
        print_glyphs(args.font)
    elif args.command == "find_glyphs":
        find_glyph_names(args.font)
    elif args.command == "convert":
        convert(args.font)
    else:
        print("error: unknown command")

if __name__ == "__main__":
    main()
