#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import tkinter.filedialog
from tkscrolledframe import ScrolledFrame
from PIL import ImageFont, ImageDraw, Image, ImageTk
import fontforge

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


class GlyphBox(tk.Frame):
    def __init__(self, master, image_provider, name, slot):
        tk.Frame.__init__(self, master)
        self.background = "white"
        self.selectedbackground = "pale green"

        self.bind("<Button-1>", lambda e: self.state_changed())
        self.image = image_provider.get_image(chr(slot))
        self.icon = tk.Label(self, image=self.image)
        self.icon.grid(column=1, row=0)
        self.icon.bind("<Button-1>", lambda e: self.state_changed())
        self.label = tk.Label(self, text=name)
        self.label.grid(column=2,row=0,sticky=tk.W)
        self.label.bind("<Button-1>", lambda e: self.state_changed())
        self.selected = False
        self.__update_view()
    
    def __update_view(self):
        if self.selected:
            self.config(bg=self.selectedbackground)
            self.icon.config(bg=self.selectedbackground)
            self.label.config(bg=self.selectedbackground)
        else:
            self.config(bg=self.background)
            self.icon.config(bg=self.background)
            self.label.config(bg=self.background)

    def state_changed(self):
        self.selected = not self.selected
        self.__update_view()

class GridPos:
    def __init__(self, limit=5):
        self.limit = limit
        self.col = 0
        self.row = 0
    
    def next(self):
        self.col += 1
        if self.col >= self.limit:
            self.row += 1
            self.col = 0

class App:
    def __init__(self):
        self.root = tk.Tk(className='GlyphPicker')
        self.root.title("GlyphPicker")
        sf = ScrolledFrame(self.root, scrollbars="vertical")
        sf.pack(side="top", expand=1, fill="both")
        self.frame = sf.display_widget(tk.Frame)
        self.__create_menu()

        
    def __create_menu(self):
        menu = tk.Menu(self.root)
        self.root.config(menu=menu)

        file_menu = tk.Menu(menu)
        menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Font...", command=self.open_font)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

    def run(self):
        self.root.mainloop()

    def open_font(self):
        font_filename = tk.filedialog.askopenfilename(
            title="Open Font",
            filetypes=(("Fonts", "*.ttf"), ("All", "*")))
        if font_filename:
            print(font_filename)
            font = fontforge.open(font_filename)
            image_provider = GlyphImageProvider(font_filename)
            pos = GridPos(1)
            for glyph in font:
                    slot = font.findEncodingSlot(glyph) 
                    if slot < 0xffff:
                        box = GlyphBox(self.frame, image_provider, str(glyph), slot)
                        box.grid(column=pos.col, row=pos.row, sticky=tk.EW)
                        pos.next()


if __name__ == "__main__":
    app = App()
    app.run()
