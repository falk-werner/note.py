#!/usr/bin/env python3

# Copyright (c) 2022 Falk Werner
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import tkinter as tk
import ctypes
import os
import markdown
import webbrowser
from tkinterweb import HtmlFrame
from tkinter import scrolledtext
from tkinter import ttk
from tktooltip import ToolTip
from PIL import ImageFont, ImageDraw, Image, ImageTk

#-------------------------------------------
# Model
#-------------------------------------------

class ModelEvent:
    def __init__(self):
        self.subscribers = []
    
    def subscribe(self, subscriber):
        self.subscribers.append(subscriber)
    
    def unsubscribe(self, subscriber):
        self.subscribers.remove(subscriber)
    
    def fire(self):
        for subscriber in self.subscribers:
            subscriber()

class Note:
    def __init__(self, name, isvalid=True):
        self.__name = name
        self.__contents = ""
        self.name_changed = ModelEvent()
        self.contents_changed = ModelEvent()
        self.isvalid = isvalid

    def __repr__(self):
        return self.__name

    def name(self, value=None):
        if None != value:
            self.__name = value
            self.name_changed.fire()
        return self.__name

    def contents(self, value=None):
        if None != value:
            print("set contents: %s" % value)
            self.__contents = value
            self.contents_changed.fire()
        return self.__contents

    def matches(self, filter):
        return filter.lower() in self.__name.lower()

class NoteCollection:
    def __init__(self):
        self.notes = dict()
        self.on_changed = ModelEvent()
        self.on_selection_changed = ModelEvent()
        self.invalid_note = Note("", isvalid=False)
        self._selected_note = self.invalid_note
    
    def __generate_name(self):
        name = "Untitled"
        number = 0
        while name in self.notes:
            number += 1
            name = "Untitled %d" % (number)
        return name

    def query(self, filter="", reverse=False):
        notes = []
        for note in self.notes.values():
            if note.matches(filter):
                notes.append(note)
        notes.sort(key=lambda note: note.name(), reverse=reverse)
        return notes

    def add_new(self):
        name = self.__generate_name()
        self.notes[name] = Note(name)
        self.on_changed.fire()

    def selected_note(self):
        return self._selected_note

    def select(self, note_name):
        self._selected_note = self.notes[note_name] if note_name != None and note_name in self.notes else self.invalid_note
        self.on_selection_changed.fire()

class AppModel:
    def __init__(self):
        self.__name = "note.py"
        self.__geometry = "800x600"
        self.notes = NoteCollection()

    def get_name(self):
        return self.__name

    def get_geometry(self):
        return self.__geometry



#-------------------------------------------
# View
#-------------------------------------------

class Icons:
    def __init__(self, master):
        self.font = ImageFont.truetype(font="icofont.ttf", size=20)
        self.new = self.draw_text("\uefc2")
        self.search = self.draw_text("\uef7f")
        self.screenshot = self.draw_text("\ueecf")
        self.save = self.draw_text("\ueff6")
        self.delete = self.draw_text("\ueebb")

    def draw_text(self, value):
        left, top, right, bottom = self.font.getbbox(value)
        box = (right - left, bottom - top)
        image = Image.new(mode="RGBA", size=box)
        draw = ImageDraw.Draw(im=image)
        draw.text(xy=(0,0), text=value, fill='black', font=self.font, anchor="lt")
        return ImageTk.PhotoImage(image=image)


class FilterableListbox(ttk.Frame):
    def __init__(self, master, model, icons):
        tk.Frame.__init__(self, master)
        self.model = model
        self.pack()
        self.create_widgets(icons)
        self.model.on_changed.subscribe(self.update)

    def create_widgets(self, icons):
        self.new_button = tk.Button(self, image=icons.new, command=self.model.add_new)
        self.new_button.pack(side = tk.TOP, fill=tk.X)
        ToolTip(self.new_button, msg="add new note", delay=1.0)
        self.filter = tk.StringVar()
        self.filter.trace("w", lambda *args: self.update() )
        self.entry = tk.Entry(self, textvariable=self.filter)
        self.entry.pack(side=tk.TOP, fill=tk.X)
        ToolTip(self.entry, msg="filter notes", delay=1.0)
        self.label = ttk.Label(self, image=icons.search)
        self.label.pack(side=tk.TOP, fill=tk.X)
        self.listbox = tk.Listbox(self)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.scrollbar=tk.Scrollbar(self)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand= self.scrollbar.set)
        self.listbox.bind('<<ListboxSelect>>', self.onselect)
        self.scrollbar.config(command=self.listbox.yview)
        self.update()

    def update(self):
        filter = self.filter.get()
        self.listbox.delete(0, tk.END)
        items = self.model.query(filter)
        selected = self.model.selected_note().name() 
        i = 0
        selected_index = -1
        for item in items:
            self.listbox.insert(tk.END, item)
            if selected == item.name():
                selected_index = i
            i += 1
        if selected_index >= 0:
            self.listbox.select_set(selected_index)

    def onselect(self, event):
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            result = self.listbox.get(index)
            self.model.select(result)

class NoteFrame(ttk.Frame):
    def __init__(self, master, model, icons):
        tk.Frame.__init__(self, master)
        self.note = None
        self.model = model
        self.pack()
        self.create_widgets(icons)
        model.on_selection_changed.subscribe(self.update)

    def create_widgets(self, icons):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.frame = HtmlFrame(self.notebook, messages_enabled=False)
        #frame.on_link_click(clicked)
        html = markdown.markdown('')
        self.frame.load_html(html)
        self.frame.pack(fill=tk.BOTH, expand=1)
        self.notebook.add(self.frame, text='View')

        editframe = tk.Frame(self.notebook)
        commandframe = ttk.Frame(editframe)
        deletebutton = ttk.Button(commandframe, image=icons.delete)
        deletebutton.pack(side=tk.RIGHT)
        ToolTip(deletebutton, msg="remove this note", delay=1.0)
        updatebutton = ttk.Button(commandframe, image=icons.save, command = self.save)
        updatebutton.pack(side=tk.RIGHT)
        ToolTip(updatebutton, msg="sync changes", delay=1.0)
        screenshotbutton = ttk.Button(commandframe, image=icons.screenshot)
        screenshotbutton.pack(side=tk.RIGHT, padx=5)
        ToolTip(screenshotbutton, msg="take screenshot", delay=1.0)
        namevar = tk.StringVar()
        nameedit = tk.Entry(commandframe, textvariable=namevar)
        nameedit.pack(fill=tk.BOTH, expand=True)
        ToolTip(nameedit, msg="change title", delay=1.0)

        commandframe.pack(fill=tk.X, side=tk.TOP)

        self.text = scrolledtext.ScrolledText(editframe)
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.bind('<KeyRelease>', lambda e: self.update_view())
        self.notebook.add(editframe, text='Edit')
        self.activateable_widgets = [ updatebutton, deletebutton, screenshotbutton, nameedit, self.text]
        self.enable(False)

    def enable(self, value=True):
        for widget in self.activateable_widgets:
            widget.configure(state="normal" if value == True else "disabled")

    def update_view(self):
        contents = self.text.get(1.0, tk.END)
        html = markdown.markdown(contents)
        self.frame.load_html(html)

    def update(self):
        self.note = self.model.selected_note()
        if self.note.isvalid:
            self.enable(True)
            contents = self.note.contents()
            html = markdown.markdown(contents)
            self.frame.load_html(html)
            self.text.delete(1.0, tk.END)
            self.text.insert(tk.END, contents)
        else:
            self.frame.load("")
            self.text.delete(1.0, tk.END)
            self.enable(False)

    def save(self):
        contents = self.text.get(1.0, tk.END)
        self.note.contents(contents)



class App:
    def __init__(self, model=AppModel()):
        self.root = tk.Tk()
        self.icons = Icons(self.root)
        self.root.title(model.get_name())
        self.root.geometry(model.get_geometry())

        self.splitPane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.splitPane.pack(fill=tk.BOTH, expand=True)

        self.listbox = FilterableListbox(self.splitPane, model.notes, self.icons)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.splitPane.add(self.listbox)

        self.noteframe = NoteFrame(self.splitPane, model.notes, self.icons)
        self.noteframe.pack(fill=tk.BOTH, expand=True)
        self.splitPane.add(self.noteframe)

    def run(self):
        self.root.mainloop()   


if __name__ == "__main__":
    app = App()
    app.run()
