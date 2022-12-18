#!/usr/bin/env python3

# Copyright (c) 2022 Falk Werner
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import tkinter as tk
import ctypes
import os
import io
import markdown
import webbrowser
import base64
import uuid
import shutil
from tkinterweb import HtmlFrame
from tkinter import scrolledtext
from tkinter import ttk
from tktooltip import ToolTip
from PIL import ImageFont, ImageDraw, Image, ImageTk
from pathlib import Path

#-------------------------------------------
# Constants
#-------------------------------------------

DEFAULT_CSS="""
table, th, td {
    border: 1px solid black;
    border-collapse: collapse;
}

blockquote {
    background-color: #e0e0e0;
}

pre code {
    background-color: #e0e0e0;
    font-family: monospace;
    display: block;
}

p code {
    font-family: monospace;
    color: #c03030;
}
"""

#-------------------------------------------
# Persistence
#-------------------------------------------

class Persistence:
    def __init__(self):
        self.__basepath = os.path.join(Path.home(), ".notepy")
        self.__mkdir(self.__basepath)
        self.__notespath = os.path.join(self.__basepath, "notes")
        self.__mkdir(self.__notespath)
        self.__css = self.__load_css()
    
    def __load_css(self):
        css_file = os.path.join(self.__basepath, "style.css")
        if os.path.isfile(css_file):
            with open(css_file, "rb") as f:
                css = f.read().decode("utf-8")
        else:
            css = DEFAULT_CSS
            with open(css_file, "wb") as f:
                f.write(css.encode("utf-8"))
        return css

    def __mkdir(self, path):
        if not os.path.isdir(path):
            os.mkdir(path)

    def __note_filename(self, name):
        return os.path.join(self.__notespath, name, "note.md")
    
    def notespath(self):
        return self._notespath

    def note_path(self, name):
        return os.path.join(self.__notespath, name)
    
    def list_notes(self):
        notes = []
        for name in os.listdir(self.__notespath):
            notefile = self.__note_filename(name)
            if os.path.isfile(notefile):
                notes.append(name)
        return notes

    def read_note(self, name):
        filename = self.__note_filename(name)
        if not os.path.isfile(filename):
            self.write_note(name, "")
        with open(filename, "rb") as f:
            data = f.read().decode("utf-8")
        return data
    
    def write_note(self, name, text):
        self.__mkdir(self.note_path(name))
        filename = self.__note_filename(name)
        with open(filename, "wb") as f:
            f.write(text.encode("utf-8"))
    
    def rename_note(self, oldname, newname):
        old_path = self.note_path(oldname)
        new_path = self.note_path(newname)
        os.rename(old_path, new_path)

    def remove_note(self, name):
        note_path = self.note_path(name)
        if os.path.isdir(note_path):
            shutil.rmtree(note_path)

    def screenshot(self, name):
        filename = "screenshot_" + str(uuid.uuid4()) + ".png"
        full_filename = os.path.join(self.note_path(name), filename)
        status = os.system('gnome-screenshot -a -f %s' % full_filename)
        exit_code = os.waitstatus_to_exitcode(status)
        return filename if 0 == exit_code else None

    def css(self):
        return self.__css

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
    def __init__(self, parent, persistence, name, isvalid=True):
        self.__parent = parent
        self.__persistence = persistence
        self.__name = name
        self.__contents = self.__persistence.read_note(self.__name) if isvalid else ""
        self.isvalid = isvalid
            

    def __repr__(self):
        return self.__name

    def name(self, value=None):
        if self.isvalid and None != value and value != self.__name:
            self.__persistence.rename_note(self.__name, value)
            self.__name = value
            self.__parent.note_changed()
        return self.__name

    def contents(self, value=None):
        if self.isvalid and None != value:
            self.__persistence.write_note(self.__name, value)
            self.__contents = value
        return self.__contents

    def matches(self, filter):
        return self.isvalid and filter.lower() in self.__name.lower()
    
    def delete(self):
        self.isvalid = False
        self.__persistence.remove_note(self.__name)
        self.__parent.note_changed()

    def screenshot(self):
        return self.__persistence.screenshot(self.__name) if self.isvalid else None

    def base_path(self):
        return self.__persistence.note_path(self.__name)
    
    def css(self):
        return self.__persistence.css()


class NoteCollection:
    def __init__(self, persistence):
        self.__persistence = persistence
        self.notes = dict()
        note_names = self.__persistence.list_notes()
        for name in note_names:
            note = Note(self, self.__persistence, name)
            self.notes[name] = note
        self.on_changed = ModelEvent()
        self.on_selection_changed = ModelEvent()
        self.invalid_note = Note(self, self.__persistence, "", isvalid=False)
        self._selected_note = self.invalid_note
    
    def _generate_name(self):
        name = "Untitled"
        number = 0
        while name in self.notes:
            number += 1
            name = "Untitled %d" % (number)
        return name

    def _rebuild_index(self):
        notes = dict()
        for note in self.notes.values():
            notes[note.name()] = note
        self.notes = notes

    def query(self, filter="", reverse=False):
        notes = []
        for note in self.notes.values():
            if note.matches(filter):
                notes.append(note)
        notes.sort(key=lambda note: note.name(), reverse=reverse)
        return notes

    def add_new(self):
        name = self._generate_name()
        note = Note(self, self.__persistence, name)
        self.notes[name] = note
        self.on_changed.fire()

    def note_changed(self):
        self._rebuild_index()
        self.on_changed.fire()
    
    def selected_note(self):
        return self._selected_note

    def select(self, note_name):
        self._selected_note = self.notes[note_name] if note_name != None and note_name in self.notes else self.invalid_note
        self.on_selection_changed.fire()

class AppModel:
    def __init__(self, persistence=Persistence()):
        self.__name = "note.py"
        self.__geometry = "800x600"
        self.__persistence = persistence
        self.notes = NoteCollection(persistence)

    def get_name(self):
        return self.__name

    def get_geometry(self):
        return self.__geometry



#-------------------------------------------
# Widgets
#-------------------------------------------

class Icons:
    def __init__(self, master):
        font_data = base64.b64decode(ICONFONT)
        self.font = ImageFont.truetype(font=io.BytesIO(font_data), size=64)
        self.app = self.draw_text("\uefb6", color="white")
        self.font = ImageFont.truetype(font=io.BytesIO(font_data), size=20)
        self.new = self.draw_text("\uefc2")
        self.search = self.draw_text("\uef7f")
        self.screenshot = self.draw_text("\ueecf")
        self.save = self.draw_text("\ueff6")
        self.delete = self.draw_text("\ueebb")

    def draw_text(self, value, color='black'):
        left, top, right, bottom = self.font.getbbox(value)
        box = (right - left, bottom - top)
        image = Image.new(mode="RGBA", size=box)
        draw = ImageDraw.Draw(im=image)
        draw.text(xy=(0,0), text=value, fill=color, font=self.font, anchor="lt")
        return ImageTk.PhotoImage(image=image)


class FilterableListbox(ttk.Frame):
    def __init__(self, master, model, icons):
        tk.Frame.__init__(self, master)
        self.model = model
        self.pack()
        self.create_widgets(icons)
        self.model.on_changed.subscribe(self.update)

    def create_widgets(self, icons):
        self.commandframe = ttk.Frame(self)
        self.new_button = ttk.Button(self.commandframe, image=icons.new, command=self.model.add_new)
        self.new_button.pack(side = tk.RIGHT, fill=tk.X)
        ToolTip(self.new_button, msg="add new note", delay=1.0)
        self.label = ttk.Label(self.commandframe, image=icons.search)
        self.label.pack(side=tk.RIGHT, fill=tk.X)
        self.filter = tk.StringVar()
        self.filter.trace("w", lambda *args: self.update() )
        self.entry = ttk.Entry(self.commandframe, textvariable=self.filter)
        self.entry.pack(fill=tk.X, expand=True, padx=5)
        ToolTip(self.entry, msg="filter notes", delay=1.0)
        self.commandframe.pack(side = tk.TOP, fill=tk.X)

        self.listbox = tk.Listbox(self)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar=ttk.Scrollbar(self)
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
        self.frame.on_link_click(self.link_clicked)
        self.frame.load_html("")
        self.frame.pack(fill=tk.BOTH, expand=1)
        self.notebook.add(self.frame, text='View')

        editframe = tk.Frame(self.notebook)
        commandframe = ttk.Frame(editframe)
        deletebutton = ttk.Button(commandframe, image=icons.delete, command = self.delete)
        deletebutton.pack(side=tk.RIGHT)
        ToolTip(deletebutton, msg="remove this note", delay=1.0)
        updatebutton = ttk.Button(commandframe, image=icons.save, command = self.save)
        updatebutton.pack(side=tk.RIGHT)
        ToolTip(updatebutton, msg="sync changes", delay=1.0)
        screenshotbutton = ttk.Button(commandframe, image=icons.screenshot, command = self.screenshot)
        screenshotbutton.pack(side=tk.RIGHT, padx=5)
        ToolTip(screenshotbutton, msg="take screenshot", delay=1.0)
        self.namevar = tk.StringVar()
        nameedit = tk.Entry(commandframe, textvariable=self.namevar)
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
        html = markdown.markdown(contents, extensions=['tables'])
        self.frame.load_html(html, base_url="file://%s/" % self.note.base_path())
        self.frame.add_css(self.nore.css())

    def update(self):
        self.save()
        self.note = self.model.selected_note()
        if self.note.isvalid:
            self.enable(True)
            contents = self.note.contents()
            html = markdown.markdown(contents, extensions=['tables'])
            self.frame.load_html(html, base_url="file://%s/" % self.note.base_path())
            self.frame.add_css(self.note.css())
            self.text.delete(1.0, tk.END)
            self.text.insert(tk.END, contents)
            self.namevar.set(self.note.name())
        else:
            self.frame.load_html("")
            self.namevar.set("")
            self.text.delete(1.0, tk.END)
            self.enable(False)

    def save(self):
        if self.note != None and self.note.isvalid:
            contents = self.text.get(1.0, tk.END)
            self.note.contents(contents)
            self.note.name(self.namevar.get())

    def delete(self):
        confirmed = tk.messagebox.askyesno(title="note.py", message="Do you want to remove this note?")
        if confirmed:
            self.note.delete()
            self.update()

    def screenshot(self):
        filename = self.note.screenshot()
        if None != filename:
            self.text.insert(tk.INSERT, "![screenshot](%s)\n\n" % filename)
            self.update_view()
            self.text.focus_set()
        else:
            tk.messagebox.showerror(title="note.py", message="Failed to create screenshot.\nCheck that gnome-screenshot is installed.")

    def link_clicked(self, url):
        webbrowser.open(url)


class App:
    def __init__(self, model=AppModel()):
        self.root = tk.Tk(className=model.get_name())
        self.icons = Icons(self.root)
        self.root.title(model.get_name())
        self.root.tk.call('wm','iconphoto', self.root._w, self.icons.app)
        self.root.geometry(model.get_geometry())

        self.splitPane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.splitPane.pack(fill=tk.BOTH, expand=True)

        self.listbox = FilterableListbox(self.splitPane, model.notes, self.icons)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.splitPane.add(self.listbox)

        self.noteframe = NoteFrame(self.splitPane, model.notes, self.icons)
        self.noteframe.pack(fill=tk.BOTH, expand=True)
        self.splitPane.add(self.noteframe)

        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<Control-n>", lambda e: model.notes.add_new())
        self.root.bind("<Control-s>", lambda e: self.noteframe.save())
        self.root.bind("<Control-p>", lambda e: self.noteframe.screenshot())

    def onclose(self):
        try:
            self.noteframe.save()
        except:
            print("error: failed to save note")
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.onclose)
        self.root.mainloop()

ICONFONT = (
    "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"
    "Ig4BFB4BMj4BNC4BAzN8HBT+2hQcfzFCQjECgg4HLDVD/hUXEKIQFxcQohAX"
    "djZcNTdcblw1N101JD8lJD9IPyUkPgI3RBgiIhhEQjH+tzJCAgdALQFENEIu"
    "EBcXEAgQFxcQ/fk3XW1cNTdcbV01AVAkPUk/JiU/ST4kAAAAAAIANP+9A7UC"
    "/gAqAFUAAAEiBh0BFBYzFhcWFxYXFgcGIi8BJgYVFxQWMzI3MjYvASY0NzY3"
    "NicmJyYFNjIfARY2PQE0JisBIgYXFhceAQcGBwYXFhcWFx4BNzI2NTQ3NCYj"
    "JicmAf0EBQYEU0U/LCgOJ3gDCANLAwQBBgSYTQQCA0cDAmoNDVY7XFj+jwMI"
    "A0sDBAYE5QQCAy8ZAgEDSxwaEQ8wKj47hTwEBgEGBOpIPQL+BQRTBAYEKCM7"
    "Nz+siAMDSgMCBOMEBgEEAkgCCQOChYuLXzIwoQMDSwIBBOMEBQQDLxgDCANS"
    "Z11hXEk/LywtAwYFNBoEBxbPswAAAAAFAK7/qAM6AxQACQAZACkAOQBNAAAX"
    "HgEzITI2NxMhBTQ2OwEyFhURFAYrASImNQM0NjsBMhYVERQGKwEiJjUDNDY7"
    "ATIWFREUBisBIiY1ASM1NCYrASIGHQEjIgYdASE1NCb7ARkSAZsRGgEd/dIB"
    "dAsHHQcLCwcdBwt9CwcdBwoKBx0HC30LBxwHCwsHHAcLAci+BQTHBAa9CxEC"
    "jBAtEhkZEgJsmgcKCgf+nQcKCgcBYwcKCgf+nQcKCgcBYwcKCgf+nQcKCgcC"
    "pCQEBgYEJBALV1cLEAAAAA4ArgABAAAAAAAAABgAMgABAAAAAAABAAkAXwAB"
    "AAAAAAACAAcAeQABAAAAAAADACYAzwABAAAAAAAEAAkBCgABAAAAAAAFABAB"
    "NgABAAAAAAAGAAYBVQADAAEECQAAADAAAAADAAEECQABABIASwADAAEECQAC"
    "AA4AaQADAAEECQADAEwAgQADAAEECQAEABIA9gADAAEECQAFACABFAADAAEE"
    "CQAGAAwBRwBDAG8AcAB5AHIAaQBnAGgAdAAgACgAYwApACAAMgAwADIAMgAs"
    "ACAAdQBzAGUAcgAAQ29weXJpZ2h0IChjKSAyMDIyLCB1c2VyAABVAG4AdABp"
    "AHQAbABlAGQAMQAAVW50aXRsZWQxAABSAGUAZwB1AGwAYQByAABSZWd1bGFy"
    "AABGAG8AbgB0AEYAbwByAGcAZQAgADIALgAwACAAOgAgAFUAbgB0AGkAdABs"
    "AGUAZAAxACAAOgAgADEAOAAtADEAMgAtADIAMAAyADIAAEZvbnRGb3JnZSAy"
    "LjAgOiBVbnRpdGxlZDEgOiAxOC0xMi0yMDIyAABVAG4AdABpAHQAbABlAGQA"
    "MQAAVW50aXRsZWQxAABWAGUAcgBzAGkAbwBuACAAMAAwADEALgAwADAAMAAg"
    "AABWZXJzaW9uIDAwMS4wMDAgAABuAG8AdABlAHAAeQAAbm90ZXB5AAAAAAIA"
    "AAAAAAD/tQAyAAAAAQAAAAAAAAAAAAAAAAAAAAAACQAAAAEAAgECAQMBBAEF"
    "AQYBBwZwbHVzLTIGcGFwZXJzBGxvb2sGY2FtZXJhDXNwaW5uZXItYWx0LTMD"
    "YmluAAAAAf//AAIAAAABAAAAAN4GKm4AAAAA38SxUQAAAADfxLFR")

if __name__ == "__main__":
    app = App()
    app.run()
