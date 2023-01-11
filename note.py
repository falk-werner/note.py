#!/usr/bin/env python3

"""note.py: Yet another note taking app"""

# Copyright (c) 2022-2023 note.py authors
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
from ttkthemes import ThemedTk
from PIL import ImageFont, ImageDraw, Image, ImageTk
from tkinterweb import HtmlFrame
import markdown
import yaml


#-------------------------------------------
# Constants
#-------------------------------------------

DEFAULT_THEME="arc"
DEFAULT_BASE_PATH="{home}/.notepy"
DEFAULT_GEOMETRY="800x600"
DEFAULT_FONT_SIZE=20

CONFIG_TEMPLATE="""\
base_path: "{base_path}"
geometry: {geometry}
font_size: {font_size}
screenshot_command: {screenshot_command}
theme: {theme}
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

# pylint: disable-next=too-many-instance-attributes
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
        self.__theme=DEFAULT_THEME

    def __save_config_file(self):
        config = CONFIG_TEMPLATE.format(
            base_path=self.__basepath_template,
            geometry=self.__geometry,
            font_size=self.__font_size,
            screenshot_command=self.__screenshot_command,
            theme=self.__theme
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
        self.__theme = config.get('theme', DEFAULT_THEME)

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

    def theme(self):
        """Return the theme of the application"""
        return self.__theme

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
        """Inform all subscibers."""
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
        self.select(name)
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
        self.__theme = persistence.theme()
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

    def get_theme(self):
        """Returns the theme of the application."""
        return self.__theme

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
        ToolTip(self.new_button, msg="add new note (Ctrl+N)", delay=1.0)
        self.label = ttk.Label(self.commandframe, image=icons.search)
        self.label.pack(side=tk.RIGHT, fill=tk.X)
        self.filter = tk.StringVar()
        self.filter.trace("w", lambda *args: self.update() )
        self.entry = ttk.Entry(self.commandframe, textvariable=self.filter)
        self.entry.pack(fill=tk.X, expand=True, padx=5)
        ToolTip(self.entry, msg="filter notes (Ctrl+F)", delay=1.0)
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
        ToolTip(deletebutton, msg="delete this note (Ctrl+D)", delay=1.0)
        updatebutton = ttk.Button(commandframe, image=icons.save, command = self.save)
        updatebutton.pack(side=tk.RIGHT)
        ToolTip(updatebutton, msg="sync changes (Ctrl+S)", delay=1.0)
        screenshotbutton = ttk.Button(commandframe, image=icons.screenshot, \
            command = self.screenshot)
        screenshotbutton.pack(side=tk.RIGHT, padx=5)
        ToolTip(screenshotbutton, msg="take screenshot (Ctrl+F)", delay=1.0)
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
        if new_tab == 1:
            self.text.focus_set()


class App:
    """Main class that runs the app."""
    def __init__(self, model=AppModel()):
        self.root = ThemedTk(theme=model.get_theme(), className=model.get_name())
        self.icons = Icons(self.root, model.get_font_size())
        self.root.title(model.get_name())
        self.root.tk.call('wm','iconphoto', self.root._w, self.icons.app)
        self.root.geometry(model.get_geometry())

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
        self.root.bind("<Control-d>", lambda e: self.noteframe.delete())

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
    "gAFaAwAAJSFQUy1BZG9iZUZvbnQtMS4wOiBub3RlcHkgMDAxLjAwMAolJVRp"
    "dGxlOiBub3RlcHkKJVZlcnNpb246IDAwMS4wMDAKJSVDcmVhdGlvbkRhdGU6"
    "IFR1ZSBKYW4gMTAgMjI6MjY6MTYgMjAyMwolJUNyZWF0b3I6IHVzZXIKJUNv"
    "cHlyaWdodDogQ29weXJpZ2h0IChjKSAyMDIzLCB1c2VyCiUgMjAyMy0xLTEw"
    "OiBDcmVhdGVkIHdpdGggRm9udEZvcmdlIChodHRwOi8vZm9udGZvcmdlLm9y"
    "ZykKJSBHZW5lcmF0ZWQgYnkgRm9udEZvcmdlIDIwMjAxMTA3IChodHRwOi8v"
    "Zm9udGZvcmdlLnNmLm5ldC8pCiUlRW5kQ29tbWVudHMKCjEwIGRpY3QgYmVn"
    "aW4KL0ZvbnRUeXBlIDEgZGVmCi9Gb250TWF0cml4IFswLjAwMSAwIDAgMC4w"
    "MDEgMCAwIF1yZWFkb25seSBkZWYKL0ZvbnROYW1lIC9ub3RlcHkgZGVmCi9G"
    "b250QkJveCB7NjIgLTg4IDkzOCA3ODggfXJlYWRvbmx5IGRlZgovUGFpbnRU"
    "eXBlIDAgZGVmCi9Gb250SW5mbyA5IGRpY3QgZHVwIGJlZ2luCiAvdmVyc2lv"
    "biAoMDAxLjAwMCkgcmVhZG9ubHkgZGVmCiAvTm90aWNlIChDb3B5cmlnaHQg"
    "XDA1MGNcMDUxIDIwMjMsIHVzZXIpIHJlYWRvbmx5IGRlZgogL0Z1bGxOYW1l"
    "IChVbnRpdGxlZDEpIHJlYWRvbmx5IGRlZgogL0ZhbWlseU5hbWUgKFVudGl0"
    "bGVkMSkgcmVhZG9ubHkgZGVmCiAvV2VpZ2h0IChSZWd1bGFyKSByZWFkb25s"
    "eSBkZWYKIC9JdGFsaWNBbmdsZSAwIGRlZgogL2lzRml4ZWRQaXRjaCB0cnVl"
    "IGRlZgogL1VuZGVybGluZVBvc2l0aW9uIC0xMDAgZGVmCiAvVW5kZXJsaW5l"
    "VGhpY2tuZXNzIDUwIGRlZgplbmQgcmVhZG9ubHkgZGVmCi9FbmNvZGluZyBT"
    "dGFuZGFyZEVuY29kaW5nIGRlZgpjdXJyZW50ZGljdCBlbmQKY3VycmVudGZp"
    "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"
    "7DQp2hTbujsOwxZU9AeJ/vdsWBVCeN/g/HRmllXasS8quPZfSrzDfWshE9+l"
    "zOKymkUfEzyBz2QxEB52tE1/zhrHEHcgBIJz0cKkCFcn5Ly/jvaZES4lwVsB"
    "nBm8j520gl6LixWaMRO5eCw0fvBGjbqj0TiiuI8eqaNoW1w4FfTAUvQWo5Ky"
    "Gy0MLQ8kKBDOOixUJ7aJSciddlQE3fBHah5C2NTjDL71MZCZa9fNK3seGzJv"
    "XoE3ZGwl5EcmwU7GQ8DHzi3r9JtnyvaM26trXzuijpnVCeGAubezRkb7bzjY"
    "v+r1vDdZzgUfchCmpow6jUSrnDPVAwyXNQ/hnD344UsMbZEUIiJFqda8GzBs"
    "267XaoJEwLatbiwLbcfCWMnUpRayxPiRpcXe7/91N0XBUcdqFjsdpQW3cGhn"
    "rp+vNjkZ36JmOGUONo8XIvrhdowsu5f/+CJCYjGbEDsV72Iaf3/2Flaj6YJJ"
    "Tm/Xb3j4ra6z+1YExvK9n8ecXsKxS4crMPiCaY4nxd1/44v1AkMs1WgrDA7X"
    "gmXD2QDG2vIcHHsnkD5TXZZwc2UZPwd0wD+VrxP3gicxd8RAs4eMrLBdVMvh"
    "C0WRvpt9PAWV5wKBUKQUruwer5zDrMN1bnagzFhpKqWqsO2wgqMsW3Haz/HS"
    "31l8k+T08nrHVxG4NnmoxSrrbEVawUf5OFDMnQWj0JVPYNXjSOUFr9rFO3h5"
    "TsjSOt7zxCRZ3ifvcaVE2f+Rmx3I8sdxDs645/SKrqhmNKENOGZepy/27Vdn"
    "wxGbyiNsLX0rgW5xY3oUGZJu4VU/KU+z9+v41gVgp3GO5vMg64iWZCKdsiy2"
    "XhMX3kShsmhYg02Qw7MQx+rK+ekLsA2ZC2X45x8ioAYWsoSt6Udd/0Zn7aCd"
    "h8G4RUC9zllgP5S0raxr8Mrp6AKs+tEiSTS1JkinfLDS/MiigCUfhLwPd1Lu"
    "DJ6Snull4W/1Addqmu0GtutKHcBGEzBb/YQATNEd0nZGKQS74RDh9r/nQM4O"
    "W+EmvBxxKQr8JWinE7aCxXTjD3k/CTrvdVxlDg5xdeihiAERDniomNZTqws7"
    "xw3de26RpMs0a/pbbcNYR7ILfaMuhONm9pthHRzZZVB4nUHBqc7FNscOKANA"
    "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"
    "JAXK9/ApmNTF55VeKrUOme7ptb63Sb2VSpgZ1aWJqV+hybPCDS2fZxmQaNGp"
    "pEb9laICnbJ6sYiwX71zhUhXqRNcP3s41esvsGWeMuIusB8LzzdRCANjpN9J"
    "gmTQLYpMXrSbHAC0g9yWfD7SWSELFm789qkJrtJrbjGlyqHq1FfftBoz3Y+Y"
    "mNNr5t5PyyUQgdnxPa2QGe4K0CHhbAAqbu71HUMG31ALaz0/Jl7FcTYkxl68"
    "OpmbCg//RMVZlxy8HIvwUhWev4mC0N2YAu2KeSPZrBZk31T9Z9UySvh6WRdt"
    "ed5mHaooU5NXEHYQj2NBqHiM8TpLY4OQ5bRE3QReEQ3gEIuChM+8usun2wmg"
    "VND9+9l5qyItATbUMwhF02RzAdMbs3XtGeH8rDkiZ0UkyN4Dro+GjbbrsQxh"
    "maBhdtofrRWtGSlS2KnWEXM6TszvVQDiYgnBktFPteaGVpu2B3lKzfbPopJt"
    "bTqFIfmPuBkaexrO7AxmT6REfMNSqgXr4lPByPXTpHMey4ogLnro0hP0tzuQ"
    "nWTUsmdF8OHkvvHToK5slHSlR5Yajfmzs7QQQ3gAxJcwXgrFi5iBh5M8vt2z"
    "b5et4CQTQ9Uz8Ih38nwpOyHDEjk5H5Ey8yXVfZGXcVKEUvNqnFNb7PhMHCim"
    "zthJuaNBhLzyuBuU68yYLiacLUUsbR/qtaLK3Vo/lmHDAfAFsSvIniR4ct4v"
    "IFueahLiPxTNgmVoCtsl0aG06OtX+vRGSGlCDDNoPt8MI93jHP0Gv4a1iPsd"
    "+sK4JJhvfBoGdzAir7a95D/eVbo0W0aMRL8Gr/GqQe4hV1zcgPKPLma8NLIm"
    "4YABFQIAAAowMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw"
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwCjAwMDAwMDAwMDAwMDAwMDAw"
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw"
    "MDAKMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw"
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMAowMDAwMDAwMDAwMDAwMDAwMDAwMDAw"
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwCjAw"
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw"
    "MDAwMDAwMDAwMDAwMDAwMDAKMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw"
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMAowMDAwMDAw"
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw"
    "MDAwMDAwMDAwMDAwCjAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAw"
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAKY2xlYXJ0b21hcmsK"
    "gAM=")

if __name__ == "__main__":
    app = App()
    app.run()
