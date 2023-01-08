#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import tkinter.filedialog
from tkinter import messagebox
from PIL import ImageFont, ImageDraw, Image, ImageTk
import fontforge
import yaml
import os

class GlyphImageProvider:
    def __init__(self, font_filename, size=24):
        self.font = ImageFont.truetype(font=font_filename, size=size)
    
    def get_image(self, text, color='black'):
        left, top, right, bottom = self.font.getbbox(text)
        box = (right - left, bottom - top)
        image = Image.new(mode="RGBA", size=box)
        draw = ImageDraw.Draw(im=image)
        draw.text(xy=(0,0), text=text, fill=color, font=self.font, anchor="lt")
        return ImageTk.PhotoImage(image=image)

class App:
    def __init__(self):
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

    def __create_selected_widgets(self):
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
        frame = tk.Frame(self.root)
        frame.grid(column=1,row=1,sticky=tk.NSEW)
        add_button = tk.Button(frame, text='Add >>', command=self.on_add)
        add_button.grid(column=0, row=0, sticky=tk.EW)
        remove_button = tk.Button(frame, text="<< Remove", command=self.on_remove)
        remove_button.grid(column=0, row=1, sticky=tk.EW)

    def __load_font(self, filename):
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
        for id in self.sel_treeview.get_children():
            item = self.sel_treeview.item(id)
            item_name, _, _ = item.get('values')
            if name == item_name:
                return True
        return False

    def run(self):
        self.root.mainloop()

    def open_font(self):
        font_filename = tk.filedialog.askopenfilename(
            title="Open Font",
            filetypes=(("Fonts", "*.ttf"), ("All", "*")))
        if font_filename:
            self.__load_font(font_filename)
    
    def on_add(self):
        selected_ids = self.treeview.selection()
        for id in selected_ids:
            item = self.treeview.item(id)
            name, slot = item.get('values')
            if not self.__is_selected(name):
                image = self.__glyph_cache[slot]
                self.sel_treeview.insert('', tk.END, image=image, values=(name, slot, ''))

    def on_remove(self):
        selected_ids = self.sel_treeview.selection()
        for id in selected_ids:
            self.sel_treeview.delete(id)

    def change_name(self, event):
        selected_id = self.sel_treeview.identify_row(event.y)
        if selected_id:
            item = self.sel_treeview.item(selected_id)
            name, slot, _ = item.get('values')
            value = tk.simpledialog.askstring(title='Change name', prompt=f"New name of \'{name}\':")
            if value:
                self.sel_treeview.item(selected_id, values=(name, slot, value))

    def export_ttf(self):
        pass

    def export_b64(self):
        pass

    def save_config(self):
        if None == self.font_filename:
            tk.messagebox.showerror('Save failed', 'No font loaded.')
            return
        filename = tk.filedialog.asksaveasfilename(
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
        filename = tk.filedialog.askopenfilename(
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

if __name__ == "__main__":
    app = App()
    app.run()
