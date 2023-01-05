#!/usr/bin/env python3

"""note.py: Yet another note taking app"""

# Copyright (c) 2022 note.py authors
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import tkinter as tk
import os
import io
import webbrowser
import base64
import uuid
import shutil
from shutil import which
from pathlib import Path
from tkinter import scrolledtext
from tkinter import ttk
from tktooltip import ToolTip
from PIL import ImageFont, ImageDraw, Image, ImageTk
from tkinterweb import HtmlFrame
import markdown
import yaml

#-------------------------------------------
# Constants
#-------------------------------------------

DEFAULT_BASE_PATH="{home}/.notepy"
DEFAULT_GEOMETRY="800x600"
DEFAULT_FONT_SIZE=20

CONFIG_TEMPLATE="""\
base_path: "{base_path}"
geometry: {geometry}
font_size: {font_size}
screenshot_command: {screenshot_command}
"""

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

CONFIG_FILE = ".notepy.yml"

#-------------------------------------------
# Shims
#-------------------------------------------

def shim_waitstatus_to_exitcode(status):
    """Transforms waitstatus to exitcode without Python 3.9 features
        (see https://bugs.python.org/issue40094 for details)
    """
    if os.WIFSIGNALED(status):
        return -os.WTERMSIG(status)
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSTOPPED(status):
        return -os.WSTOPSIG(status)
    return -1

waitstatus_to_exitcode = getattr(os, 'waitstatus_to_exitcode', shim_waitstatus_to_exitcode)

#-------------------------------------------
# Persistence
#-------------------------------------------

class Persistence:
    """Persistence handling"""

    def __init__(self):
        self.__set_defaults()
        self.__load_config_file()
        self.__basepath = self.__basepath_template.format(home=Path.home())
        self.__mkdir(self.__basepath)
        self.__notespath = os.path.join(self.__basepath, "notes")
        self.__mkdir(self.__notespath)
        self.__css = self.__load_css()

    def __find_screenshot_command(self):
        return "spectacle -rbn -o \"{filename}\"" if which("spectacle") is not None \
            else "gnome-screenshot -a -f \"{filename}\""

    def __set_defaults(self):
        self.__basepath_template = DEFAULT_BASE_PATH
        self.__geometry = DEFAULT_GEOMETRY
        self.__font_size = DEFAULT_FONT_SIZE
        self.__screenshot_command = self.__find_screenshot_command()

    def __save_config_file(self):
        config = CONFIG_TEMPLATE.format(
            base_path=self.__basepath_template,
            geometry=self.__geometry,
            font_size=self.__font_size,
            screenshot_command=self.__screenshot_command
        )
        filename = os.path.join(Path.home(), CONFIG_FILE)
        with open(filename, "wb") as config_file:
            config_file.write(config.encode('utf-8'))

    def __load_config_file(self):
        filename = os.path.join(Path.home(), CONFIG_FILE)
        if not os.path.isfile(filename):
            self.__save_config_file()
        with open(filename, 'rb') as config_file:
            config = yaml.load(config_file, yaml.SafeLoader)
        self.__basepath_template = config.get('base_path', DEFAULT_BASE_PATH)
        self.__geometry = config.get('geometry', DEFAULT_GEOMETRY)
        self.__font_size = config.get('font_size', DEFAULT_FONT_SIZE)
        self.__screenshot_command = config.get('screenshot_command', \
            self.__find_screenshot_command())

    def __load_css(self):
        css_filename = os.path.join(self.__basepath, "style.css")
        if os.path.isfile(css_filename):
            with open(css_filename, "rb") as css_file:
                css = css_file.read().decode("utf-8")
        else:
            css = DEFAULT_CSS
            with open(css_filename, "wb") as css_file:
                css_file.write(css.encode("utf-8"))
        return css

    def __mkdir(self, path):
        if not os.path.isdir(path):
            os.mkdir(path)

    def __note_filename(self, name):
        return os.path.join(self.__notespath, name, "note.md")

    def geometry(self):
        """Returns the geometry (size) of the application window"""
        return self.__geometry

    def font_size(self):
        """Returns the font size of the application"""
        return self.__font_size

    def note_path(self, name):
        """Return the directory of a given note"""
        return os.path.join(self.__notespath, name)

    def list_notes(self):
        """Returns a list of all notes"""
        notes = []
        for name in os.listdir(self.__notespath):
            notefile = self.__note_filename(name)
            if os.path.isfile(notefile):
                notes.append(name)
        return notes

    def read_note(self, name):
        """Returns the contents of a note. Non-existing notes will be created"""
        filename = self.__note_filename(name)
        if not os.path.isfile(filename):
            self.write_note(name, "")
        with open(filename, "rb") as note_file:
            data = note_file.read().decode("utf-8")
        return data

    def write_note(self, name, text):
        """Writes the contents of a note to note file."""
        self.__mkdir(self.note_path(name))
        filename = self.__note_filename(name)
        with open(filename, "wb") as note_file:
            note_file.write(text.encode("utf-8"))

    def rename_note(self, oldname, newname):
        """Renames a note in the filesystem."""
        old_path = self.note_path(oldname)
        new_path = self.note_path(newname)
        os.rename(old_path, new_path)

    def remove_note(self, name):
        """Removes a note (including all related files)."""
        note_path = self.note_path(name)
        if os.path.isdir(note_path):
            shutil.rmtree(note_path)

    def screenshot(self, name):
        """Takes a screenshot and returns it's filename."""
        filename = "screenshot_" + str(uuid.uuid4()) + ".png"
        full_filename = os.path.join(self.note_path(name), filename)
        status = os.system(self.__screenshot_command.format(filename=full_filename))
        exit_code = waitstatus_to_exitcode(status)
        return filename if 0 == exit_code else None

    def css(self):
        """Returns the CSS for the webview."""
        return self.__css

#-------------------------------------------
# Model
#-------------------------------------------

class ModelEvent:
    """Basic model event."""
    def __init__(self):
        self.subscribers = []

    def subscribe(self, subscriber):
        """Subscribe to the event."""
        self.subscribers.append(subscriber)

    def unsubscribe(self, subscriber):
        """Revoke subscription."""
        self.subscribers.remove(subscriber)

    def fire(self):
        """Inform all subscibers-"""
        for subscriber in self.subscribers:
            subscriber()

class Note:
    """Contains all business logic of a note."""
    def __init__(self, parent, persistence, name, isvalid=True):
        self.__parent = parent
        self.__persistence = persistence
        self.__name = name
        self.__contents = self.__persistence.read_note(self.__name) if isvalid else ""
        self.isvalid = isvalid


    def __repr__(self):
        return self.__name

    def name(self, value=None):
        """Reads or sets the name of a note."""
        if self.isvalid and value is not None and value != self.__name:
            self.__persistence.rename_note(self.__name, value)
            self.__name = value
            self.__parent.note_changed()
        return self.__name

    def contents(self, value=None):
        """Reads or writes the contents of a note."""
        if self.isvalid and value is not None:
            self.__persistence.write_note(self.__name, value)
            self.__contents = value
        return self.__contents

    def matches(self, note_filter):
        """"Returns True, when the notes name or content matches the filter."""
        result = False
        if self.isvalid:
            if note_filter.lower() in self.__name.lower():
                result = True
            elif note_filter.lower() in self.__contents.lower():
                result = True
        return result

    def delete(self):
        """Deletes the note and all related files."""
        self.isvalid = False
        self.__persistence.remove_note(self.__name)
        self.__parent.note_changed()

    def screenshot(self):
        """Takes a screenshot and return the filename."""
        return self.__persistence.screenshot(self.__name) if self.isvalid else None

    def base_path(self):
        """Returns the directory of the note."""
        return self.__persistence.note_path(self.__name)

    def css(self):
        """Returns the CSS for the note.
        All notes share the same CSS yet, but this may change in future."""
        return self.__persistence.css()


class NoteCollection:
    """Business logic of a collection of notes."""
    def __init__(self, persistence):
        self.__persistence = persistence
        self.notes = {}
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
            name = f"Untitled {number}"
        return name

    def _rebuild_index(self):
        notes = {}
        for note in self.notes.values():
            notes[note.name()] = note
        self.notes = notes

    def query(self, note_filter="", reverse=False):
        """Returns an ordered list of all notes that matches the filter."""
        notes = []
        for note in self.notes.values():
            if note.matches(note_filter):
                notes.append(note)
        notes.sort(key=lambda note: note.name(), reverse=reverse)
        return notes

    def add_new(self):
        """Add a new note to the collection."""
        name = self._generate_name()
        note = Note(self, self.__persistence, name)
        self.notes[name] = note
        self.on_changed.fire()

    def note_changed(self):
        """Is called by notes only to inform about changes."""
        self._rebuild_index()
        self.on_changed.fire()

    def selected_note(self):
        """Returns the currently selected note."""
        return self._selected_note

    def select(self, note_name):
        """Selects a note."""
        self._selected_note = self.notes[note_name] \
            if note_name is not None and note_name in self.notes else self.invalid_note
        self.on_selection_changed.fire()

class AppModel:
    """Business logic of the application itself."""
    def __init__(self, persistence=Persistence()):
        self.__name = "note.py"
        self.__geometry = persistence.geometry()
        self.__font_size = persistence.font_size()
        self.notes = NoteCollection(persistence)

    def get_name(self):
        """Returns the name of the app."""
        return self.__name

    def get_geometry(self):
        """Returns the size of the main window."""
        return self.__geometry

    def get_font_size(self):
        """Returns the font size of the application."""
        return self.__font_size



#-------------------------------------------
# Widgets
#-------------------------------------------

# pylint: disable-next=too-few-public-methods
class Icons:
    """Namespace for icons"""
    def __init__(self, master, font_size):
        _ = master
        font_data = base64.b64decode(ICONFONT)
        self.font = ImageFont.truetype(font=io.BytesIO(font_data), size=64)
        self.app = self.__draw_text("\uefb6", color="white")
        self.font = ImageFont.truetype(font=io.BytesIO(font_data), size=font_size)
        self.new = self.__draw_text("\uefc2")
        self.search = self.__draw_text("\uef7f")
        self.screenshot = self.__draw_text("\ueecf")
        self.save = self.__draw_text("\ueff6")
        self.delete = self.__draw_text("\ueebb")

    def __draw_text(self, value, color='black'):
        left, top, right, bottom = self.font.getbbox(value)
        box = (right - left, bottom - top)
        image = Image.new(mode="RGBA", size=box)
        draw = ImageDraw.Draw(im=image)
        draw.text(xy=(0,0), text=value, fill=color, font=self.font, anchor="lt")
        return ImageTk.PhotoImage(image=image)

# pylint: disable-next=too-many-instance-attributes,too-many-ancestors
class FilterableListbox(ttk.Frame):
    """Widget to display a filterable list of notes."""
    def __init__(self, master, model, icons):
        ttk.Frame.__init__(self, master)
        self.model = model
        self.pack()
        self.__create_widgets(icons)
        self.model.on_changed.subscribe(self.update)

    def __create_widgets(self, icons):
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
        """Updates the displayed list of notes."""
        note_filter = self.filter.get()
        self.listbox.delete(0, tk.END)
        items = self.model.query(note_filter)
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
        """Callback when a note is selected. Used internally only."""
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            result = self.listbox.get(index)
            self.model.select(result)

# pylint: disable-next=too-many-ancestors
class NoteFrame(ttk.Frame):
    """Widget to view and edit a single note."""
    def __init__(self, master, model, icons):
        ttk.Frame.__init__(self, master)
        self.note = None
        self.model = model
        self.pack()
        self.__create_widgets(icons)
        model.on_selection_changed.subscribe(self.update)
        first_note = list(self.model.notes.keys())[0] if len(self.model.notes) > 0 else None
        self.model.select(first_note)

    def __create_widgets(self, icons):
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
        screenshotbutton = ttk.Button(commandframe, image=icons.screenshot, \
            command = self.screenshot)
        screenshotbutton.pack(side=tk.RIGHT, padx=5)
        ToolTip(screenshotbutton, msg="take screenshot", delay=1.0)
        self.namevar = tk.StringVar()
        nameedit = tk.Entry(commandframe, textvariable=self.namevar)
        nameedit.pack(fill=tk.BOTH, expand=True)
        ToolTip(nameedit, msg="change title", delay=1.0)

        commandframe.pack(fill=tk.X, side=tk.TOP)

        self.text = scrolledtext.ScrolledText(editframe)
        self.text.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(editframe, text='Edit')
        self.activateable_widgets = [ updatebutton, deletebutton, \
            screenshotbutton, nameedit, self.text]
        self.enable(False)

        self.notebook.bind("<<NotebookTabChanged>>", self.tab_changed)

    def enable(self, value=True):
        """Enables or disables all activatable sub-widgets."""
        for widget in self.activateable_widgets:
            widget.configure(state="normal" if value is True else "disabled")

    def update_view(self):
        """Updates the view of a note without saving it."""
        if self.note is not None:
            contents = self.text.get(1.0, tk.END)
            html = markdown.markdown(contents, extensions=['tables'])
            self.frame.load_html(html, base_url=f"file://{self.note.base_path()}/")
            self.frame.add_css(self.note.css())

    def update(self):
        """Update the selected note (e.g. a new note is selected)."""
        self.save()
        self.note = self.model.selected_note()
        if self.note.isvalid:
            self.enable(True)
            contents = self.note.contents()
            html = markdown.markdown(contents, extensions=['tables'])
            self.frame.load_html(html, base_url=f"file://{self.note.base_path()}/")
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
        """Saves the name and contents of a note."""
        if self.note is not None and self.note.isvalid:
            contents = self.text.get(1.0, tk.END)
            self.note.contents(contents)
            self.note.name(self.namevar.get())
            self.update_view()

    def delete(self):
        """Asks, if the current note should be deleted and deletes it."""
        confirmed = tk.messagebox.askyesno(title="note.py", \
            message="Do you want to remove this note?")
        if confirmed:
            self.note.delete()
            self.update()

    def screenshot(self):
        """Takes a screenshot and insert it to the current note's contents."""
        filename = self.note.screenshot()
        if filename is not None:
            self.text.insert(tk.INSERT, \
                f"![screenshot]({filename})\n\n")
            self.text.focus_set()
        else:
            tk.messagebox.showerror(title="note.py", \
                message="Failed to create screenshot.\nCheck that gnome-screenshot is installed.")

    def link_clicked(self, url):
        """Opens a link in the default web-browser."""
        webbrowser.open(url)

    def tab_changed(self, _):
        """Saves the contents of the currently selected note,
        when switched from edit to view mode (tab)."""
        tab = self.notebook.index(self.notebook.select())
        if tab == 0:
            self.save()

    def change_tab(self, _):
        """Changes from view to edit tab or vice versa. Bound to Control-e."""
        tab = self.notebook.index(self.notebook.select())
        new_tab = 0 if tab == 1 else 1
        self.notebook.select(new_tab)


class App:
    """Main class that runs the app."""
    def __init__(self, model=AppModel()):
        self.root = tk.Tk(className=model.get_name())
        self.icons = Icons(self.root, model.get_font_size())
        self.root.title(model.get_name())
        self.root.tk.call('wm','iconphoto', self.root._w, self.icons.app)
        self.root.geometry(model.get_geometry())

        self.root.tk.call('source', './themes/Forest-ttk-theme-master/forest-light.tcl')
        ttk.Style().theme_use("forest-light")
        ttk.Style().configure("TButton", padding=2)

        self.split_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.split_pane.pack(fill=tk.BOTH, expand=True)

        self.listbox = FilterableListbox(self.split_pane, model.notes, self.icons)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.split_pane.add(self.listbox)

        self.noteframe = NoteFrame(self.split_pane, model.notes, self.icons)
        self.noteframe.pack(fill=tk.BOTH, expand=True)
        self.split_pane.add(self.noteframe)

        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<Control-n>", lambda e: model.notes.add_new())
        self.root.bind("<Control-s>", lambda e: self.noteframe.save())
        self.root.bind("<Control-p>", lambda e: self.noteframe.screenshot())
        self.root.bind("<Control-e>", self.noteframe.change_tab)
        self.root.bind("<Control-f>", lambda e: self.listbox.entry.focus_set())

    def onclose(self):
        """Saves the current note and closes the app."""
        try:
            self.noteframe.save()
        # pylint: disable-next=bare-except
        except:
            print("error: failed to save note")
        self.root.destroy()

    def run(self):
        """Runs the app."""
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
