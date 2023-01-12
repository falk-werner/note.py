#!/usr/bin/env python3

"""glyph_picker: Create a font from selected glyphs"""

# Copyright (c) 2023 note.py authors
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import argparse
import os
import base64
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import fontforge
from PIL import ImageFont, ImageDraw, Image, ImageTk
import yaml

def create_font(source_filename, target_filename, glyphs):
    """
    Creates a font from selected glyphs.

    :param str source_filename: filename of the source font
    :param str target_filename: filename of the new font
    :param glyphs: list of glyph definitions
    """

    source_font = fontforge.open(source_filename)
    target_font = fontforge.font()

    for glyph in glyphs:
        source_name, target_name = glyph
        slot = source_font.findEncodingSlot(source_name)
        source_font.selection.select(source_name)
        source_font.copy()

        target_font.createChar(slot, target_name)
        target_font.selection.select(target_name)
        target_font.paste()

    source_font.close()

    target_font.fontname = "notepy"
    target_font.generate(target_filename)
    target_font.close()

class GlyphImageProvider:
    """Provides images of single glyphs."""

    def __init__(self, font_filename, size=24):
        """
        Creates a new instance.

        :param str font_filename: filename of the font
        :param int size: size of the font
        """
        self.font = ImageFont.truetype(font=font_filename, size=size)

    def get_image(self, text, color='black'):
        """
        Returns an image of the given text.

        :param str text: text to render
        :param str color: text color
        """
        left, top, right, bottom = self.font.getbbox(text)
        box = (right - left, bottom - top)
        image = Image.new(mode="RGBA", size=box)
        draw = ImageDraw.Draw(im=image)
        draw.text(xy=(0,0), text=text, fill=color, font=self.font, anchor="lt")
        return ImageTk.PhotoImage(image=image)

class App:
    """UI Application"""

    def __init__(self):
        """Creates a new UI application window."""

        self.root = tk.Tk(className='GlyphPicker')
        self.root.title("GlyphPicker")
        self.root.geometry("1024x768")
        self.font_filename = None
        self.__create_menu()
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(2, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.__create_available_widgets()
        self.__create_selected_widgets()
        self.__create_command_widgets()
        self.__glyph_cache = {}

    def __create_menu(self):
        """Creates the application menu."""

        menu = tk.Menu(self.root)
        self.root.config(menu=menu)

        file_menu = tk.Menu(menu)
        menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Font...", command=self.open_font)
        file_menu.add_command(label="Open Config...", command=self.load_config)
        file_menu.add_separator()
        file_menu.add_command(label="Save Config...", command=self.save_config)
        file_menu.add_separator()
        file_menu.add_command(label="Export as TTF...", command=self.export_ttf)
        file_menu.add_command(label="Export as Base64...", command=self.export_b64)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

    def __create_available_widgets(self):
        """Creates the widgets of the available gylphs (left side of app)."""

        available_label = tk.Label(self.root, text="Available Glyphs")
        available_label.grid(column=0, row=0)
        frame = tk.Frame(self.root)
        frame.grid(column=0, row=1, sticky=tk.NSEW)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.treeview = ttk.Treeview(frame, columns=('name', 'codepoint'))
        self.treeview.column('#0', width=100)
        self.treeview.column('#1', width=100)
        self.treeview.column('#2', width=100)
        self.treeview.heading('name', text='Name')
        self.treeview.heading('codepoint', text='Code Point')
        self.treeview.grid(column=0,row=0,sticky=tk.NSEW)
        scroller = tk.Scrollbar(frame, orient='vertical', command=self.treeview.yview)
        scroller.grid(column=1,row=0,sticky=tk.NS)
        self.treeview.configure(yscrollcommand=scroller.set)
        self.treeview.bind('<Double-Button-1>', self.add_glyph)


    def __create_selected_widgets(self):
        """Creates the widgets of the selected gylphs (right side of app)."""

        selected_label = tk.Label(self.root, text="Selected Glyphs")
        selected_label.grid(column=2, row=0)
        frame = tk.Frame(self.root)
        frame.grid(column=2, row=1, sticky=tk.NSEW)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.sel_treeview = ttk.Treeview(frame, columns=('name', 'codepoint', "new_name"))
        self.sel_treeview.column('#0', width=100)
        self.sel_treeview.column('#1', width=100)
        self.sel_treeview.column('#2', width=100)
        self.sel_treeview.column('#3', width=100)
        self.sel_treeview.heading('name', text='Name')
        self.sel_treeview.heading('codepoint', text='Code Point')
        self.sel_treeview.heading('new_name', text='New Name')
        self.sel_treeview.grid(column=0,row=0,sticky=tk.NSEW)
        scroller = tk.Scrollbar(frame, orient='vertical', command=self.sel_treeview.yview)
        scroller.grid(column=1,row=0,sticky=tk.NS)
        self.sel_treeview.configure(yscrollcommand=scroller.set)
        self.sel_treeview.bind('<Double-Button-1>', self.change_name)

    def __create_command_widgets(self):
        """Creates the widgets of the command area (center of app)."""

        frame = tk.Frame(self.root)
        frame.grid(column=1,row=1,sticky=tk.NSEW)
        add_button = tk.Button(frame, text='Add >>', command=self.on_add)
        add_button.grid(column=0, row=0, sticky=tk.EW)
        remove_button = tk.Button(frame, text="<< Remove", command=self.on_remove)
        remove_button.grid(column=0, row=1, sticky=tk.EW)

    def __load_font(self, filename):
        """
        Loads a font.

        This will reset the application state.

        :param str filename: name of the font to loads
        """
        self.font_filename = filename
        self.__glyph_cache = {}
        for row in self.treeview.get_children():
            self.treeview.delete(row)
        for row in self.sel_treeview.get_children():
            self.sel_treeview.delete(row)

        font = fontforge.open(filename)
        image_provider = GlyphImageProvider(filename)
        for glyph in font:
            slot = font.findEncodingSlot(glyph)
            if slot < 0xffff:
                image = image_provider.get_image(chr(slot))
                self.__glyph_cache[slot] = image
                self.treeview.insert('', tk.END, image=image, values=(str(glyph), slot))

    def __is_selected(self, name):
        """Returns True if the glyph part of the current selection."""

        for id in self.sel_treeview.get_children():
            item = self.sel_treeview.item(id)
            item_name, _, _ = item.get('values')
            if name == item_name:
                return True
        return False

    def run(self):
        """Runs the main loop."""
        self.root.mainloop()

    def open_font(self):
        """Opens a font via dialog (menu option)."""
        font_filename = filedialog.askopenfilename(
            title="Open Font",
            filetypes=(("Fonts", ".ttf"), ("All", "*")))
        if font_filename:
            self.__load_font(font_filename)

    def on_add(self):
        """Adds all currently selected fonts to the current selection."""
        selected_ids = self.treeview.selection()
        for id in selected_ids:
            item = self.treeview.item(id)
            name, slot = item.get('values')
            if not self.__is_selected(name):
                image = self.__glyph_cache[slot]
                self.sel_treeview.insert('', tk.END, image=image, values=(name, slot, ''))

    def on_remove(self):
        """Remove all selected fonts from the current selection."""
        selected_ids = self.sel_treeview.selection()
        for id in selected_ids:
            self.sel_treeview.delete(id)

    def add_glyph(self, event):
        """Adds a single glyph via double click."""
        selected_id = self.treeview.identify_row(event.y)
        if selected_id:
            item = self.treeview.item(selected_id)
            name, slot = item.get('values')
            if not self.__is_selected(name):
                image = self.__glyph_cache[slot]
                self.sel_treeview.insert('', tk.END, image=image, values=(name, slot, ''))

    def change_name(self, event):
        """Change the name of a glyph in the current selection."""
        selected_id = self.sel_treeview.identify_row(event.y)
        if selected_id:
            item = self.sel_treeview.item(selected_id)
            name, slot, _ = item.get('values')
            value = tk.simpledialog.askstring(title='Change name', \
                prompt=f"New name of \'{name}\':")
            if value:
                self.sel_treeview.item(selected_id, values=(name, slot, value))

    def export_ttf(self):
        """Export all currently selected glyphs as TTF."""

        if None == self.font_filename:
            messagebox.showerror('Export failed', 'No font loaded.')
            return
        filename = filedialog.asksaveasfilename(
            title="Export TTF",
            filetypes=(("Fonts", ".ttf"), ("All", "*")))
        if filename:
            glyphs = []
            for id in self.sel_treeview.get_children():
                item = self.sel_treeview.item(id)
                name, _, new_name = item.get('values')
                glyphs.append((name, new_name if new_name != "" else name))
            create_font(self.font_filename, filename, glyphs)

    def export_b64(self):
        """Exports all currently selected glyphs as Base64."""

        if None == self.font_filename:
            messagebox.showerror('Export failed', 'No font loaded.')
            return
        filename = filedialog.asksaveasfilename(
            title="Export Base64",
            filetypes=(("Text", ".txt"), ("All", "*")))
        if filename:
            ttf_filename = filename + ".ttf"
            glyphs = []
            for id in self.sel_treeview.get_children():
                item = self.sel_treeview.item(id)
                name, _, new_name = item.get('values')
                glyphs.append((name, new_name if new_name != "" else name))
            create_font(self.font_filename, ttf_filename, glyphs)

            data = b''
            with open(ttf_filename, "rb") as f:
                data = f.read()
            os.remove(ttf_filename)

            data = base64.b64encode(data).decode('utf-8')
            with open(filename, "w") as f:
                i = 0
                while i < len(data):
                    j = i + 60
                    print("\"%s\"" % data[i:j], file=f)
                    i = j


    def save_config(self):
        """Saves the application state to a config file."""

        if None == self.font_filename:
            tk.messagebox.showerror('Save failed', 'No font loaded.')
            return
        filename = filedialog.asksaveasfilename(
            title="Save Config",
            filetypes=(("Yaml", ".yml .yaml"), ("All", "*")))
        if filename:
            glyphs = []
            for id in self.sel_treeview.get_children():
                item = self.sel_treeview.item(id)
                name, slot, new_name = item.get('values')
                glyph = {'name': name, 'slot': slot, 'new_name': new_name}
                glyphs.append(glyph)
            contents = {}
            contents['font'] = os.path.relpath(self.font_filename)
            contents['glyphs'] = glyphs
            with open(filename, 'w') as config_file:
                yaml.dump(contents, config_file)

    def load_config(self):
        """Loads a previously saved application state from a config file."""

        filename = filedialog.askopenfilename(
            title="Load Config",
            filetypes=(("Yaml", ".yml .yaml"), ("All", "*")))
        if filename:
            with open(filename, 'r') as config_file:
                config = yaml.load(config_file, yaml.SafeLoader)
            filename = config.get('font')
            self.__load_font(filename)
            glyphs = config.get('glyphs')
            for glyph in glyphs:
                name = glyph.get('name')
                slot = glyph.get('slot')
                new_name = glyph.get('new_name')
                image = self.__glyph_cache[slot]
                self.sel_treeview.insert('', tk.END, image=image, values=(name, slot, new_name))

def convert(filename):
    """Create a font and print it's Base64 represenation from a config file."""

    with open(filename, 'r') as config_file:
        config = yaml.load(config_file, yaml.SafeLoader)
    filename = config.get('font')
    ttf_filename = filename + ".min.ttf"
    glyphs = []
    for glyph in config.get('glyphs'):
        name = glyph.get('name')
        new_name = glyph.get('new_name')
        glyphs.append((name, new_name if new_name != "" else name))
    create_font(filename, ttf_filename, glyphs)

    data = b''
    with open(ttf_filename, "rb") as f:
        data = f.read()

    data = base64.b64encode(data).decode('utf-8')
    i = 0
    while i < len(data):
        j = i + 60
        print(f"\"{data[i:j]}\"")
        i = j


def main():
    """main"""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=False)
    sub = subparsers.add_parser("convert")
    sub.add_argument("-c", "--config", required=True, type=str)
    args = parser.parse_args()

    if args.command == "convert":
        convert(args.config)
    else:
        app = App()
        app.run()

if __name__ == "__main__":
    main()
