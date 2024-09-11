#!/usr/bin/env python3

"""note.py: Yet another note taking app"""

# Copyright (c) 2022-2023 note.py authors
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# pylint: disable=too-many-lines

import tkinter as tk
import os
import platform
import io
import webbrowser
import base64
import uuid
import shutil
import urllib
from shutil import which
from pathlib import Path
from tkinter import scrolledtext
from tkinter import ttk
from tktooltip import ToolTip
from ttkthemes import ThemedTk
from PIL import ImageFont, ImageDraw, Image, ImageTk, ImageGrab
from tkinterweb import HtmlFrame
import cmarkgfm
from cmarkgfm.cmark import Options as cmarkgfmOptions
import yaml

#-------------------------------------------
# Constants
#-------------------------------------------

APP_NAME = "note.py"

PERSISTENCE_VERSION=3

DEFAULT_THEME="arc"
DEFAULT_BASE_PATH="{home}/.notepy"
DEFAULT_GEOMETRY="800x600"
DEFAULT_FONT_SIZE=20

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

        :param status: status code as returned by os.system
        :type status: int

        :return: exit code
        :rtype: int
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

def quote(value):
    """Quotes special characters that are not allowed in file names.
    
    Special characters are URL encoded.
    """
    return value.translate(str.maketrans({
        "<":"%3C", ">": "%3E", ":": "%3A", "\"": "%22",
        "/": "%2F", "\\":"%5C", "|": "%7C", "?": "%3F",
        "*": "%2A", "%": "%25"}))

# pylint: disable-next=too-many-instance-attributes
class Persistence:
    """Persistence handling.

    All file operations are handled by the Persistence class.
    """

    def __init__(self, config_file=CONFIG_FILE):
        self.__config_file = config_file
        self.__set_defaults()
        self.__load_config_file()
        self.__basepath = self.__basepath_template.format(home=Path.home())
        self.__mkdir(self.__basepath)
        self.__css = self.__load_css()
        self.__migrate()

    def __migrate(self):
        if self.__version < 3:
            print("info: migrate from notes directory")
            notespath = os.path.join(self.__basepath, "notes")
            for name in os.listdir(notespath):
                legacy_dir = os.path.join(notespath, name)
                if os.path.isdir(legacy_dir):
                    desired_dir = os.path.join(self.__basepath, name)
                    try:
                        if not os.path.isdir(desired_dir):
                            os.rename(legacy_dir, desired_dir)
                        else:
                            shutil.copytree(legacy_dir, desired_dir, dirs_exist_ok=True)
                            shutil.rmtree(legacy_dir)
                        print(f"info: successfully migrated {name}")
                    except OSError as ex:
                        print(f"error: failed to migrate {name}: {ex}")
            try:
                os.rmdir(notespath)
                print("info: notes directory removed")
            except OSError:
                print("info: keep notes directory, since it isn't empty")
        if self.__version < 2:
            print("info: migrate note.md to README.md")
            for name in os.listdir(self.__basepath):
                legacy_file = os.path.join(self.__basepath, name, "note.md")
                if os.path.isfile(legacy_file):
                    desired_file = self.__note_filename(name)
                    try:
                        os.rename(legacy_file, desired_file)
                        print(f"info: successfully migrated {name}")
                    except OSError as ex:
                        print(f"error: failed to migrate {name}: {ex}")

    def __find_screenshot_command(self):
        return "spectacle -rbn -o \"{filename}\"" if which("spectacle") is not None \
            else "gnome-screenshot -a -f \"{filename}\""

    def __set_defaults(self):
        self.__version = 0
        self.__basepath_template = DEFAULT_BASE_PATH
        self.__geometry = DEFAULT_GEOMETRY
        self.__font_size = DEFAULT_FONT_SIZE
        self.__screenshot_command = self.__find_screenshot_command()
        self.__theme=DEFAULT_THEME

    def __save_config_file(self):
        config = yaml.dump({
            "persistence_version": PERSISTENCE_VERSION,
            "base_path": self.__basepath_template,
            "geometry": self.__geometry,
            "font_size": self.__font_size,
            "screenshot_command": self.__screenshot_command,
            "theme": self.__theme
        })
        filename = os.path.join(Path.home(), self.__config_file)
        with open(filename, "wb") as config_file:
            config_file.write(config.encode('utf-8'))

    def __load_config_file(self):
        filename = os.path.join(Path.home(), self.__config_file)
        if not os.path.isfile(filename):
            self.__save_config_file()
        with open(filename, 'rb') as config_file:
            config = yaml.load(config_file, yaml.SafeLoader)
        self.__version=config.get('persistence_version', 0)
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
        return os.path.join(self.note_path(name), "README.md")

    def __note_tags_filename(self, name):
        return os.path.join(self.note_path(name), "tags.txt")

    def geometry(self, geometry=None):
        """
        Returns and optionally sets the geometry
        of the application window.

        :param geometry: Optional geometry of application window (Default: None).
        :type  geometry: str | None

        :return: Configured geometry of the application window.
        :rtype: str
        """
        if geometry:
            # pylint: disable-next=attribute-defined-outside-init
            self.__geometry = geometry
            self.__save_config_file()
        return self.__geometry

    def font_size(self):
        """Returns the font size of the application.

        :return: Font size of the application.
        :rtype: int
        """
        return self.__font_size

    def theme(self):
        """Return the theme of the application.

        :return: Theme of the application.
        :rtype: str
        """
        return self.__theme

    def note_path(self, name):
        """Return the directory of a given note.

        :param name: Name of the note.
        :type  name: str

        :return: Path of directory that conatins the nore.
        :rtype: str
        """
        return os.path.join(self.__basepath, quote(name))

    def list_notes(self):
        """Returns a list of all notes.

        :return: List of all notes.
        :rtype: list[str]
        """
        notes = []
        for name in os.listdir(self.__basepath):
            display_name = urllib.parse.unquote(name)
            notefile = self.__note_filename(display_name)
            if os.path.isfile(notefile):
                notes.append(display_name)
        return notes

    def read_note(self, name):
        """Returns the contents of a note.

        Non-existing notes will be created.

        :param name: Name of the note.
        :type  name: str

        :return: Contents of the note.
        :rtype: str
        """
        filename = self.__note_filename(name)
        if not os.path.isfile(filename):
            self.write_note(name, "")
        with open(filename, "rb") as note_file:
            data = note_file.read().decode("utf-8")
        return data

    def write_note(self, name, text):
        """Writes the contents of a note to note file.

        :param name: Name of the note.
        :type  name: str
        :param text: Contents of the note.
        :type  text: str
        """
        self.__mkdir(self.note_path(name))
        filename = self.__note_filename(name)
        with open(filename, "wb") as note_file:
            note_file.write(text.encode("utf-8"))

    def rename_note(self, oldname, newname):
        """Renames a note in the filesystem.

        :param oldname: Old name of the note.
        :type  oldname: str
        :param newname: New name of the note.
        :type  newname: str
        """
        old_path = self.note_path(oldname)
        new_path = self.note_path(newname)
        os.rename(old_path, new_path)

    def remove_note(self, name):
        """Removes a note (including all related files).

        :param name: Name of the note.
        :type  name: str
        """
        note_path = self.note_path(name)
        if os.path.isdir(note_path):
            shutil.rmtree(note_path)

    def read_tags(self, name):
        """Reads all tags associated with a note.

        :param name: Name of the note.
        :type  name: str

        :return: List of tags.
        :rtype: str[]
        """
        filename = self.__note_tags_filename(name)
        if not os.path.isfile(filename):
            return []
        with open(filename, "r", encoding='UTF-8') as tags_file:
            lines = tags_file.readlines()
        return [line.strip() for line in lines]

    def write_tags(self, name, tags):
        """Writes all tags associated with a note.

        :param name: Name of the note.
        :type  name: str
        :param tags: Name of the note.
        :type  tags: str[]
        """
        filename = self.__note_tags_filename(name)
        with open(filename, "w", encoding='UTF-8') as tags_file:
            tags_file.writelines(tag + '\n' for tag in tags)

    def list_tags(self):
        """Returns a list of all tag."""
        tags = []
        for name in self.list_notes():
            tags.extend(self.read_tags(name))
        tags = list(set(tags))
        tags.sort()
        return tags

    def screenshot(self, name):
        """Takes a screenshot and returns it's filename.

        :param name: Name of the note the screenshot is assigned to.
        :type  name: str

        :return: Filename of the screenshot.
        :rtype: str
        """
        filename = "screenshot_" + str(uuid.uuid4()) + ".png"
        full_filename = os.path.join(self.note_path(name), filename)
        if platform.system() != "Windows":
            status = os.system(self.__screenshot_command.format(filename=full_filename))
            exit_code = waitstatus_to_exitcode(status)
        else:
            screenshot = ImageGrab.grab()
            screenshot.save(full_filename)
            exit_code = 0
        return filename if 0 == exit_code else None

    def css(self):
        """Returns the CSS of the webview.

        :return: Returns the style sheet of the webview.
        :rtype: str
        """
        return self.__css

#-------------------------------------------
# Model
#-------------------------------------------

class Note:
    """Contains all business logic of a note.

    :param parent: Note collection that owns the note.
    :type  parent: NoteCollection

    :param persistence: Persitence Provider of the note.
    :type  persistence: Persistence

    :param name: Name of the note.
    :type  name: str

    :param isvalid: Optional flag to mark the note valid (Default: True).
    :type  isvalue: bool
    """

    def __init__(self, parent, persistence, name, isvalid=True):
        self.__parent = parent
        self.__persistence = persistence
        self.__name = name
        self.__contents = self.__persistence.read_note(self.__name) if isvalid else ""
        self.__tags = self.__persistence.read_tags(self.__name) if isvalid else []
        self.isvalid = isvalid


    def __repr__(self):
        return self.__name

    def name(self, value=None):
        """Reads or sets the name of a note.

        :param value: Optional new name of the note (Default: None).
        :type  value: str | None

        :return: Name of the note.
        :rtype: str
        """
        if self.isvalid and value is not None and value != self.__name:
            self.__persistence.rename_note(self.__name, value)
            self.__name = value
            self.__parent.note_changed()
        return self.__name

    def contents(self, value=None):
        """Reads or writes the contents of a note.

        :param value: Optional new contents of the note (Default: None).
        :type  value: str | None

        :return: Contents of the note.
        :rtype: str
        """
        if self.isvalid and value is not None:
            self.__persistence.write_note(self.__name, value)
            self.__contents = value
        return self.__contents

    def tags(self, value=None):
        """Reads or writes tags of a note.

        :param value: Optional new list of tags (Default: None).
        :type  value: str[] | None

        :return: Tags of the note
        :rtype: str[]
        """
        if self.isvalid and value is not None:
            self.__persistence.write_tags(self.__name, value)
            self.__tags = value
            self.__parent.note_changed()
        return self.__tags

    def __matches_filter(self, note_filter):
        result = False
        if self.isvalid:
            if note_filter.lower() in self.__name.lower():
                result = True
            elif note_filter.lower() in self.__contents.lower():
                result = True
        return result

    def __matches_tags(self, tags):
        if len(tags) == 0:
            return True
        note_tags = self.tags()
        for tag in tags:
            if tag in note_tags:
                return True
        return False

    def matches(self, note_filter, tags):
        """"Returns True, when the notes name or content matches the filter.

        :param note_filter: Filter to check the note against.
        :type  note_filter: str
        :param tags: Tags to check the note against.
        :type  tags: str[]

        :return: True, if the note matches the filter.
        :rtype: bool
        """
        return self.__matches_filter(note_filter) and self.__matches_tags(tags)

    def delete(self):
        """Deletes the note and all related files."""
        self.isvalid = False
        self.__persistence.remove_note(self.__name)
        self.__parent.note_changed()

    def screenshot(self):
        """Takes a screenshot and returns the filename.

        :return: Filename of the screenshot on success, None otherwise.
        :rtype: str | None
        """
        return self.__persistence.screenshot(self.__name) if self.isvalid else None

    def base_path(self):
        """Returns the directory of the note.

        :return: Base path of the note.
        :rtype: str
        """
        return self.__persistence.note_path(self.__name)

    def css(self):
        """Returns the CSS for the note.
        All notes share the same CSS yet, but this may change in future.

        :return: Style sheet of the note.
        :rtype: str
        """
        return self.__persistence.css()

class NoteCollection:
    """Business logic of a collection of notes.

    :param persistence: Persistence provider of the notes.
    :type  persistence: Persistence
    """

    def __init__(self, persistence):
        self.__persistence = persistence
        self.notes = {}
        note_names = self.__persistence.list_notes()
        for name in note_names:
            note = Note(self, self.__persistence, name)
            self.notes[name] = note
        self.on_changed = lambda : None
        self.on_selection_changed = lambda : None
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

    def query(self, note_filter, tags):
        """Returns an ordered list of all notes that matches the filter.

        :param note_filter: filter to match the notes
        :type  note_filter: str

        :param tags: tags to match the notes
        :type  tags: str[]

        :return: Ordered list toall notes that matches the filter.
        :rtype: list[Note]
        """
        notes = []
        for note in self.notes.values():
            if note.matches(note_filter, tags):
                notes.append(note)
        notes.sort(key=lambda note: note.name())
        return notes

    def add_new(self):
        """Adds a new note to the collection."""
        name = self._generate_name()
        note = Note(self, self.__persistence, name)
        self.notes[name] = note
        self.select(name)
        self.on_changed()

    def note_changed(self):
        """Is called by notes only to inform about changes."""
        self._rebuild_index()
        self.on_changed()

    def selected_note(self):
        """Returns the currently selected note.

        :return: Currently selected note.
        :rtype: Note
        """
        return self._selected_note

    def select(self, note_name):
        """Selects a note.

        :param note_name: Name of the note to select.
        :type  note_name: str
        """
        self._selected_note = self.notes[note_name] \
            if note_name is not None and note_name in self.notes else self.invalid_note
        self.on_selection_changed()

    def tags(self):
        """Returns a list of all tags."""
        return self.__persistence.list_tags()

#-------------------------------------------
# Widgets
#-------------------------------------------

# pylint: disable-next=too-many-instance-attributes,too-few-public-methods
class Icons:
    """Namespace for icons.

    Note that master is actually not used, but it makes sure a
    tkinter interstance was created when Icons are instanciated.

    :param master: tkinter container.
    :type  master: tk.Widget
    :param font_size: Font size of default icons.
    :type  font_size: int
    """
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
        self.browse = self.__draw_text("\ueedb")
        self.delete = self.__draw_text("\ueebb")
        self.tag = self.__draw_text("\uef5a")

    def __draw_text(self, value, color='black'):
        left, top, right, bottom = self.font.getbbox(value)
        box = (right - left, bottom - top)
        image = Image.new(mode="RGBA", size=box)
        draw = ImageDraw.Draw(im=image)
        draw.text(xy=(0,0), text=value, fill=color, font=self.font, anchor="lt")
        return ImageTk.PhotoImage(image=image)

def float_layout_apply(frame):
    """
    Applys the float layout to a frame widget.

    :param frame: frame widget
    :type  frame: tk.Widget
    """
    frame.bind("<Configure>", float_layout_update)
    frame.pack(side=tk.TOP, fill=tk.X, expand=False)

def float_layout_update(event):
    """
    Updates the layout of a widget.
    This function is called internally by frame layout.

    :param event: resize event
    :param type: tk.Event
    """
    frame = event.widget
    frame_width = frame.winfo_width()
    pos_x = 0
    pos_y = 0
    y_incr = 0
    for widget in frame.winfo_children():
        width  = widget.winfo_reqwidth()
        height = widget.winfo_reqheight()
        y_incr = max(y_incr, height)
        if pos_x > 0 and pos_x + width > frame_width:
            pos_x = 0
            pos_y += y_incr
            y_incr = height
        widget.place(x=pos_x, y=pos_y, width=width, height=height)
        pos_x += width
    frame["height"] = pos_y + y_incr
    frame.pack(side=tk.TOP, fill=tk.X, expand=False)

# pylint: disable-next=too-many-ancestors
class TagButton(ttk.Button):
    """Sticky button used to enable and disable tag filter"""

    def __init__(self, parent, text, command):
        super().__init__(parent, text=text, command=self.__update_state)
        self.__active = False
        self.__tag = text
        self.__command = command

    def __update_state(self):
        self.__active = not self.__active
        state = "pressed" if self.__active else "!pressed"
        self.state([state])
        self.__command()

    def is_active(self):
        """Returns true if the tag filter is active."""
        return self.__active

    def get_tag(self):
        """Returns the name of the tag."""
        return self.__tag

# pylint: disable-next=too-many-instance-attributes,too-many-ancestors
class FilterableListbox(ttk.Frame):
    """Widget to display a filterable list of notes.

    :param master: Control owning this widget.
    :type  master: tk.Widget
    :param model: Note collection that is displayed by the list.
    :type  model: NoteCollection
    :param icons: Icon collection that is used to render some buttons.
    :type  icons: Icons
    """

    def __init__(self, master, model, icons):
        ttk.Frame.__init__(self, master)
        self.model = model
        self.pack()
        self.__create_widgets(icons)
        self.model.on_changed = self.update

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

        self.tagbox = ttk.Frame(self)
        float_layout_apply(self.tagbox)

        self.listbox = tk.Listbox(self)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar=ttk.Scrollbar(self)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand= self.scrollbar.set)
        self.listbox.bind('<<ListboxSelect>>', self.onselect)
        self.scrollbar.config(command=self.listbox.yview)
        self.update()

    def __get_active_tags(self):
        tags = []
        for widget in self.tagbox.winfo_children():
            if widget.is_active():
                tags.append(widget.get_tag())
        return tags

    def __update_tags(self):
        tags = self.model.tags()
        changed = False
        for widget in self.tagbox.winfo_children():
            tag = widget.get_tag()
            if tag in tags:
                tags.remove(tag)
            else:
                widget.destroy()
                changed = True
        for tag in tags:
            TagButton(self.tagbox, tag, self.update)
            changed=True
        if changed:
            self.tagbox.event_generate("<Configure>", when="tail")


    def update(self):
        """Updates the displayed list of notes."""
        note_filter = self.filter.get()
        tags = self.__get_active_tags()
        self.listbox.delete(0, tk.END)
        items = self.model.query(note_filter, tags)
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
        self.__update_tags()

    def onselect(self, event):
        """Callback when a note is selected. Used internally only.

        :param event: Event triggered the callback.
        :type  event: tk.Event
        """
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            result = self.listbox.get(index)
            self.model.select(result)

# pylint: disable-next=too-many-ancestors
class TabControl(ttk.Frame):
    """Replacement for ttk.Notepad

    ttk.Notepad crashed on Windows in combination with
    tkinterweb and tk.Text (see https://github.com/Andereoo/TkinterWeb/issues/19).

    :param master: Control owning the TabControl.
    :type  master: tk.Widget
    """
    def __init__(self, master):
        """Creates a new instance of TabControl."""
        ttk.Frame.__init__(self, master)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.tab_frame = ttk.Frame(self)
        self.tab_frame.grid(column=0, row=0, sticky=tk.EW)
        self.tab_buttons = []
        self.tab_widgets = []
        self.selected_index = -1
        self.selected_widget = None


    def add(self, widget, name):
        """Adds a tab.

        :param widget: Widget containing the contents of the tab.
        :type  widget: tk.Widget
        :param name: Name of the tab.
        :type  name: str
        """
        index = len(self.tab_widgets)
        button = ttk.Button(self.tab_frame, text=name, command=lambda : self.select(index))
        button.grid(column=index, row=0, stick=tk.E)
        self.tab_buttons.append(button)
        self.tab_widgets.append(widget)

        if index == 0:
            self.select(index)

    def select(self, index=None):
        """Selects a tab and returns the selected widget.

        :param index: Optional index of the tab to select (Default: None)
        :type  index: int | None

        :return: Selected widget.
        :rtype: tk.Widget
        """
        length = len(self.tab_widgets)
        if index is not None and 0 <= index < length:
            if self.selected_widget is not None:
                self.selected_widget.grid_forget()
            self.selected_index = index
            self.selected_widget = self.tab_widgets[index]
            self.selected_widget.grid(column=0, row=1, sticky=tk.NSEW)
            for i in range(0, length):
                state = "!pressed" if i != index else "pressed"
                self.tab_buttons[i].state([state])
            self.event_generate("<<TabControlTabChanged>>", when="tail")

        return self.selected_widget

    def index(self, widget):
        """Returns the index of a widget.

        :param widget: Widget to find.
        :type  widget: tk.Widget

        :return: Index of the widget or -1 if widget is not contained.
        :rtype: int
        """
        for i, cur_widget in enumerate(self.tab_widgets):
            if widget == cur_widget:
                return i
        return -1

# pylint: disable-next=too-many-ancestors,too-many-instance-attributes
class NoteFrame(ttk.Frame):
    """Widget to view and edit a single note.

    :param master: Container owning the note frame.
    :type  master: tk.Widget
    :param model: Note collection providing the contents of the note frame.
    :type  model: NoteCollection
    :param icons: Icon collection used to render some frame buttons.
    :type  icons: Icons
    """

    def __init__(self, master, model, icons):
        ttk.Frame.__init__(self, master)
        self.note = None
        self.model = model
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.__create_widgets(icons)
        model.on_selection_changed = self.update
        first_note = list(self.model.notes.keys())[0] if len(self.model.notes) > 0 else None
        self.model.select(first_note)

    def __create_widgets(self, icons):
        self.notebook = TabControl(self)
        self.notebook.grid(column=0, row=0, sticky=tk.NSEW)

        self.frame = HtmlFrame(self.notebook, messages_enabled=False)
        self.frame.on_link_click(self.link_clicked)
        self.frame.load_html("")
        self.notebook.add(self.frame, 'View')

        editframe = tk.Frame(self.notebook)
        commandframe = ttk.Frame(editframe)
        deletebutton = ttk.Button(commandframe, image=icons.delete, command = self.delete)
        deletebutton.pack(side=tk.RIGHT)
        ToolTip(deletebutton, msg="delete this note (Ctrl+D)", delay=1.0)
        updatebutton = ttk.Button(commandframe, image=icons.save, command = self.save)
        updatebutton.pack(side=tk.RIGHT)
        ToolTip(updatebutton, msg="sync changes (Ctrl+S)", delay=1.0)
        browsebutton = ttk.Button(commandframe, image=icons.browse, \
            command = self.browse_attachments)
        browsebutton.pack(side=tk.RIGHT)
        ToolTip(browsebutton, msg="browse attachments (Ctrl+B)", delay=1.0)
        screenshotbutton = ttk.Button(commandframe, image=icons.screenshot, \
            command = self.screenshot)
        screenshotbutton.pack(side=tk.RIGHT, padx=5)
        ToolTip(screenshotbutton, msg="take screenshot (Ctrl+P)", delay=1.0)
        self.namevar = tk.StringVar()
        nameedit = tk.Entry(commandframe, textvariable=self.namevar)
        nameedit.pack(fill=tk.BOTH, expand=True)
        ToolTip(nameedit, msg="change title", delay=1.0)

        commandframe.pack(fill=tk.X, side=tk.TOP)

        tagsframe = ttk.Frame(editframe)
        taglabel = ttk.Label(tagsframe, image=icons.tag)
        taglabel.pack(side=tk.LEFT)
        self.tagsvar = tk.StringVar()
        tagsedit = tk.Entry(tagsframe, textvariable=self.tagsvar)
        tagsedit.pack(fill=tk.BOTH, expand=True)
        tagsframe.pack(fill=tk.X, side=tk.TOP)

        self.text = scrolledtext.ScrolledText(editframe)
        self.text.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(editframe, 'Edit')
        self.activateable_widgets = [ updatebutton, deletebutton, \
            screenshotbutton, nameedit, self.text]
        self.enable(False)

        self.notebook.bind("<<TabControlTabChanged>>", self.tab_changed)

    def browse_attachments(self):
        """Opens a note's attachments in file explorer."""
        if self.note is not None:
            path = self.note.base_path()
            if platform.system() == "Windows":
                # pylint: disable-next=no-member
                os.startfile(path)
            else:
                os.system(f"xdg-open '{path}'")

    def enable(self, value=True):
        """Enables or disables all activatable sub-widgets.

        :param value: True to enable the control (Default: True).
        :type  value: bool
        """
        for widget in self.activateable_widgets:
            widget.configure(state="normal" if value is True else "disabled")

    def __update_view(self):
        """Updates the view of a note."""
        contents = self.text.get(1.0, tk.END)
        html = cmarkgfm.github_flavored_markdown_to_html(contents,
        (cmarkgfmOptions.CMARK_OPT_HARDBREAKS))
        self.frame.load_html(html, base_url=f"file://{self.note.base_path()}/")
        self.frame.add_css(self.note.css())

    def update(self):
        """Update the selected note (e.g. a new note is selected)."""
        self.save()
        self.note = self.model.selected_note()
        if self.note.isvalid:
            self.enable(True)
            contents = self.note.contents()
            self.text.delete(1.0, tk.END)
            self.text.insert(tk.END, contents)
            self.namevar.set(self.note.name())
            self.tagsvar.set(' '.join(self.note.tags()))
            self.__update_view()
        else:
            self.frame.load_html("")
            self.namevar.set("")
            self.tagsvar.set("")
            self.text.delete(1.0, tk.END)
            self.enable(False)

    def save(self):
        """Saves the name and contents of a note."""
        if self.note is not None and self.note.isvalid:
            contents = self.text.get(1.0, tk.END)
            self.note.contents(contents)
            self.note.name(self.namevar.get())
            self.note.tags(self.tagsvar.get().split())
            self.__update_view()

    def delete(self):
        """Asks, if the current note should be deleted and deletes it."""
        confirmed = tk.messagebox.askyesno(title=APP_NAME, \
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
            tk.messagebox.showerror(title=APP_NAME, \
                message="Failed to create screenshot.\nCheck that gnome-screenshot is installed.")

    def link_clicked(self, url):
        """Opens a link in the default web-browser.

        :paran url: Url to open.
        :type url: str
        """
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
    """Main class that runs the app.

    :param model: Model of the application.
    :type model: AppModel
    """
    def __init__(self, persistence = Persistence()):
        self.__persistence = persistence
        notes = NoteCollection(persistence)
        self.root = ThemedTk(theme=persistence.theme(), className=APP_NAME)
        self.icons = Icons(self.root, persistence.font_size())
        self.root.title(APP_NAME)
        self.root.tk.call('wm','iconphoto', self.root._w, self.icons.app)
        self.root.geometry(persistence.geometry())

        self.split_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.split_pane.pack(fill=tk.BOTH, expand=True)

        self.listbox = FilterableListbox(self.split_pane, notes, self.icons)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.split_pane.add(self.listbox)

        self.noteframe = NoteFrame(self.split_pane, notes, self.icons)
        self.noteframe.pack(fill=tk.BOTH, expand=True)
        self.split_pane.add(self.noteframe)

        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<Control-n>", lambda e: notes.add_new())
        self.root.bind("<Control-s>", lambda e: self.noteframe.save())
        self.root.bind("<Control-b>", lambda e: self.noteframe.browse_attachments())
        self.root.bind("<Control-p>", lambda e: self.noteframe.screenshot())
        self.root.bind("<Control-e>", self.noteframe.change_tab)
        self.root.bind("<Control-f>", lambda e: self.listbox.entry.focus_set())
        self.root.bind("<Control-d>", lambda e: self.noteframe.delete())

    def onclose(self):
        """Saves the current note and closes the app."""
        try:
            self.noteframe.save()
            self.__persistence.geometry(self.root.winfo_geometry())
        # pylint: disable-next=bare-except
        except:
            print("error: failed to save note")
        self.root.destroy()

    def run(self):
        """Runs the app."""
        self.root.protocol("WM_DELETE_WINDOW", self.onclose)
        self.root.mainloop()

ICONFONT = (
    "AAEAAAANAIAAAwBQRkZUTZ6Rw5kAAA0UAAAAHE9TLzJEjmFkAAABWAAAAGBj"
    "bWFwvxDAHQAAAdgAAAF6Y3Z0IAAhAnkAAANUAAAABGdhc3D//wADAAANDAAA"
    "AAhnbHlmsREe7gAAA3AAAAckaGVhZCOA3MsAAADcAAAANmhoZWEHJQOVAAAB"
    "FAAAACRobXR4DWwBDgAAAbgAAAAebG9jYQfSCZIAAANYAAAAGG1heHAAVACO"
    "AAABOAAAACBuYW1lXzIqgwAACpQAAAIHcG9zdMH7dLEAAAycAAAAbwABAAAA"
    "AQAAKuf+yl8PPPUACwPoAAAAAOBFzJUAAAAA4EXMlQAh/6gDtQMUAAAACAAC"
    "AAAAAAAAAAEAAAMU/6gAWgPoAAAAAAO1AAEAAAAAAAAAAAAAAAAAAAAEAAEA"
    "AAALAF0ABwAAAAAAAgAAAAEAAQAAAEAALgAAAAAABAPoAZAABQAAAooCvAAA"
    "AIwCigK8AAAB4AAxAQIAAAIABQkAAAAAAAAAAAAAEAAAAAAAAAAAAAAAUGZF"
    "ZACA7rvv9gMg/zgAWgMUAFgAAAABAAAAAAAAAAAAAAAgAAED6AAhAAAAAAPo"
    "AAAD6AA+AIsANAA/ADQArgBHADwAAAAAAAMAAAADAAAAHAABAAAAAAB0AAMA"
    "AQAAABwABABYAAAAEgAQAAMAAu677s/u2+9a73/vtu/C7/b//wAA7rvuz+7b"
    "71rvf++278Lv9v//EU0RNxEuELAQhhBOEEEQEQABAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAABBgAAAQAAAAAAAAABAgAAAAIAAAAAAAAAAAAAAAAAAAABAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACEC"
    "eQAAACoAKgAqAG4A7AGEAeoCagLWA0wDkgACACEAAAEqApoAAwAHAC6xAQAv"
    "PLIHBADtMrEGBdw8sgMCAO0yALEDAC88sgUEAO0ysgcGAfw8sgECAO0yMxEh"
    "ESczESMhAQnox8cCmv1mIQJYAAABAD7/qQOqAxQAKQAAASYnIREnJiIHBgcR"
    "IQcGBxUGFRQXFh8BIREXHgEzMjc2PwERITY3NjU2A6cBBf6pLBocHA4g/qkB"
    "BQECAgEFAQFXBRsZGh0ODBoIAVcFAQIBAYYWGAFXBwICAQb+qQUbDAMXDBAc"
    "DRsF/qgBBQIBAQUBAVgYEw0aFAAABgCL/6gDWgMUABEAJgAyAD4ASwBYAAAB"
    "IxEUBiMhFRQWMyEyNjURNCYDMjY1ETQmIyEVFh0BFAYrAREUFjMTITIWFAYj"
    "ISImNDYXITIWFAYjISImNDYHNDY7ATIWFAYrASImAzM+AT0BNCYiDwEGFgMq"
    "GSwg/i4dFAIGFBwceRQcHBT+pgEoHJodFGMBUgoNDQr+rgkNDQkBUgoNDQr+"
    "rgkNDQ0NCakKDQ0KqQkNaYURFwwPCJgKCgKw/YwfLRcUHR0UAqcUHf1bHBQC"
    "pxQdEAIEhBwo/gYUHAHCDRQNDhIOfA0TDQ0SDosJDg4SDg0BlAEXEYQJDAaZ"
    "ChkABwA0//kDqgLNABUAIgAnADkARgBPAFwAAAEmJyYnJgcGBw4BFxYXFhcW"
    "Njc2NzYFBi4CPgIeAg4BNwYHBTcBJicHBgcGBxUWFxY3Njc2NSYHJicmJyY3"
    "NjcOARYXNyImPgEyHgEGFw4BBzY0JxYXFh8BFgKcEDY1S01QVD49NhAQNjVM"
    "TaM+PBsb/u47bU0WJ1h0bkwWJ1fVHBsBATj+RzhOCQwHXC4WG09gTicBEbwO"
    "ESIXAwMiNhUPDxUKBwkBCQ0JAQqLDzAbIiElHAcMBQMBy1E+PBscDxA2NZpT"
    "UD48GhwfNjVMTb4LJ1h2bEwWJ1d0bk0zKievUQF4LgEBAQERUAQnEz0aFUcB"
    "BB9cBAcPHQQDKwwNLS0NRAoNCQkOCQ0VHgUXSBYIFwYNBgIAAAQAPwAHA6oC"
    "tQAbACsAOABFAAABIzU0JiMhIgYdASMiBhURFBYzITI3PgE1ETQmJTQ2OwEy"
    "Fh0BFAYrASImNRMiLgE0PgEyHgEUDgEDIg4BFB4BMj4BNC4BAzN8HBT+2hQc"
    "fzFCQjECgg4HLDVD/hUXEKIQFxcQohAXdjZcNTdcblw1N101JD8lJD9IPyUk"
    "PgI3RBgiIhhEQjH+tzJCAgdALQFENEIuEBcXEAgQFxcQ/fk3XW1cNTdcbV01"
    "AVAkPUk/JiU/ST4kAAAAAAIANP+9A7UC/gAqAFUAAAEiBh0BFBYzFhcWFxYX"
    "FgcGIi8BJgYVFxQWMzI3MjYvASY0NzY3NicmJyYFNjIfARY2PQE0JisBIgYX"
    "FhceAQcGBwYXFhcWFx4BNzI2NTQ3NCYjJicmAf0EBQYEU0U/LCgOJ3gDCANL"
    "AwQBBgSYTQQCA0cDAmoNDVY7XFj+jwMIA0sDBAYE5QQCAy8ZAgEDSxwaEQ8w"
    "Kj47hTwEBgEGBOpIPQL+BQRTBAYEKCM7Nz+siAMDSgMCBOMEBgEEAkgCCQOC"
    "hYuLXzIwoQMDSwIBBOMEBQQDLxgDCANSZ11hXEk/LywtAwYFNBoEBxbPswAA"
    "AAAFAK7/qAM6AxQACQAZACkAOQBNAAAXHgEzITI2NxMhBTQ2OwEyFhURFAYr"
    "ASImNQM0NjsBMhYVERQGKwEiJjUDNDY7ATIWFREUBisBIiY1ASM1NCYrASIG"
    "HQEjIgYdASE1NCb7ARkSAZsRGgEd/dIBdAsHHQcLCwcdBwt9CwcdBwoKBx0H"
    "C30LBxwHCwsHHAcLAci+BQTHBAa9CxECjBAtEhkZEgJsmgcKCgf+nQcKCgcB"
    "YwcKCgf+nQcKCgcBYwcKCgf+nQcKCgcCpCQEBgYEJBALV1cLEAABAEf/qAOY"
    "AxQASgAAASIHAQ4BIyInLgE2NwE2MhcWBwYHAQYjIiY1NDcBIzY0JiMiByMB"
    "DgEVFBcWMzI2NwE+ASYnLgEiBgcBDgEWFx4BMjY3ATc2NTQmA3YMC/5wGkQl"
    "TDYjGRkjAYIoaCgmAwIm/ssWHxsfFgELAQgUDgsKAf73FxQiJDgdNRQBNCcb"
    "GCUcSFBIHP5+MSIiMSNdZF0kAZAFBBQBvQn+bxocNiNfXyMBgyYmKCwvJv7L"
    "Fh0THhYBCgoaFAj+9xcvHzMgIRYVATQnXl4mHB4eHP59MIKCMSMnJyMBkgYI"
    "CQ4UAAIAPP/FA6wC9wAdACYAAAEmJyUuAQ8BBgcGBwYHBh8BFhcWFxYzFjc2"
    "NxM2JiUOAS4BPgEeAQOWW7b+7wsWDSVvOBwDEgoDFWR0OrZcDBAKCQUI8AsG"
    "/XIPMCgHHjIoBgFXRIfLCAIFETEYDR6USRwPSlUriEQJAQcECwFDERy1FAYe"
    "MSgGHjIAAAAAAAAOAK4AAQAAAAAAAAAYADIAAQAAAAAAAQAJAF8AAQAAAAAA"
    "AgAHAHkAAQAAAAAAAwAlAM0AAQAAAAAABAAJAQcAAQAAAAAABQAQATMAAQAA"
    "AAAABgAGAVIAAwABBAkAAAAwAAAAAwABBAkAAQASAEsAAwABBAkAAgAOAGkA"
    "AwABBAkAAwBKAIEAAwABBAkABAASAPMAAwABBAkABQAgAREAAwABBAkABgAM"
    "AUQAQwBvAHAAeQByAGkAZwBoAHQAIAAoAGMAKQAgADIAMAAyADMALAAgAHUA"
    "cwBlAHIAAENvcHlyaWdodCAoYykgMjAyMywgdXNlcgAAVQBuAHQAaQB0AGwA"
    "ZQBkADEAAFVudGl0bGVkMQAAUgBlAGcAdQBsAGEAcgAAUmVndWxhcgAARgBv"
    "AG4AdABGAG8AcgBnAGUAIAAyAC4AMAAgADoAIABVAG4AdABpAHQAbABlAGQA"
    "MQAgADoAIAAyADYALQAzAC0AMgAwADIAMwAARm9udEZvcmdlIDIuMCA6IFVu"
    "dGl0bGVkMSA6IDI2LTMtMjAyMwAAVQBuAHQAaQB0AGwAZQBkADEAAFVudGl0"
    "bGVkMQAAVgBlAHIAcwBpAG8AbgAgADAAMAAxAC4AMAAwADAAIAAAVmVyc2lv"
    "biAwMDEuMDAwIAAAbgBvAHQAZQBwAHkAAG5vdGVweQAAAAIAAAAAAAD/tQAy"
    "AAAAAQAAAAAAAAAAAAAAAAAAAAAACwAAAAEAAgECAQMBBAEFAQYBBwEIAQkG"
    "cGx1cy0yBnBhcGVycwRsb29rBmNhbWVyYQ1zcGlubmVyLWFsdC0zA2JpbgRj"
    "bGlwBWxhYmVsAAAAAAH//wACAAAAAQAAAADeBipuAAAAAOBFzJUAAAAA4EXM"
    "lQ==")

def main():
    """Entry point."""
    app = App()
    app.run()

if __name__ == "__main__":
    main()
