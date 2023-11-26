#!/usr/bin/env python3

"""Unit test for note.Persistence."""

# Copyright (c) 2022 Falk Werner
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import tempfile
from shutil import rmtree
import os
import pytest
import yaml

from note import Persistence

class FileSystem:
    """Filesystem helper."""

    def __init__(self):
        self.root_dir = tempfile.mkdtemp(prefix="notepy-test-")

    def __del__(self):
        rmtree(self.root_dir)

    def mkdir(self, directory):
        """Creates a directory."""
        full_path = os.path.join(self.root_dir, directory)
        os.mkdir(full_path)

    def write_file(self, filename, contents):
        """Writes a text file and returns it's full qualified path."""
        full_path = os.path.join(self.root_dir, filename)
        with open(full_path, "wb") as text_file:
            text_file.write(contents.encode('utf-8'))
        return full_path

    def read_file(self, filename):
        """Returns the contents of a text file."""
        full_path = os.path.join(self.root_dir, filename)
        with open(full_path, "rb") as text_file:
            contents = text_file.read().decode('utf-8')
        return contents

    def exists(self, filename):
        """Returns true if the file exists."""
        full_path = os.path.join(self.root_dir, filename)
        return os.path.exists(full_path)

    def is_file(self, filename):
        """Returns true, if filename is a file."""
        full_path = os.path.join(self.root_dir, filename)
        return os.path.isfile(full_path)

    def is_dir(self, filename):
        """Returns true, if filename is a directory."""
        full_path = os.path.join(self.root_dir, filename)
        return os.path.isdir(full_path)

    # pylint: disable-next=too-many-arguments
    def write_configfile(self,
        filename=".notepy.yml",
        persistence_version=2,
        base_path="base",
        geometry="800x600",
        font_size=20,
        screenshot_command="true",
        theme="arc"):
        """Writes a note.py config file."""

        config = yaml.dump({
            "persistence_version": persistence_version,
            "base_path": os.path.join(self.root_dir, base_path),
            "geometry": geometry,
            "font_size": font_size,
            "screenshot_command": screenshot_command,
            "theme": theme
        })
        return self.write_file(filename, config)

fs: FileSystem = None

@pytest.fixture(autouse=True)
def manage_filesystem():
    """Manages a temporary file system for each test.

    A fresh file system is created before test.
    The file system is cleaned up after each test.    
    """

    # pylint: disable-next=global-statement
    global fs
    fs = FileSystem()
    yield
    fs = None

def check_note(persistence, title, contents, note_tags):
    """Checks if a note is present with correct contents and tags."""

    assert title in persistence.list_notes()
    tags = persistence.list_tags()
    for tag in note_tags:
        assert tag in tags

    assert persistence.read_note(title) == contents
    tags = persistence.list_tags()
    assert len(tags) == len(note_tags)
    for tag in note_tags:
        assert tag in tags


def test_empty_notes():
    """Test basic directory structure on empty notes.
    
    When notes directory does not exist, the basic directory 
    structure should be created.

    ```
    root               : filesystem root
    +-- .notepy.yml    : notepy config file
    +-- base           : base
        +-- style.css  : style
        +-- notes      : notes directory (empty)
    ```
    """

    config_file = fs.write_configfile(geometry="320x240",
            font_size=42, theme="my-theme")
    persistence = Persistence(config_file)

    # check root directory
    items = os.listdir(fs.root_dir)
    assert len(items) == 2
    assert fs.is_file(".notepy.yml")
    assert fs.is_dir("base")

    # check notes directory
    notes_path = os.path.join(fs.root_dir, "base")
    items = os.listdir(notes_path)
    assert len(items) == 2
    assert fs.is_file(os.path.join("base","style.css"))
    assert fs.is_dir(os.path.join("base","notes"))

    # check notes/notes directory
    notes_path = os.path.join(fs.root_dir, "base", "notes")
    items = os.listdir(notes_path)
    assert len(items) == 0

    # check persistence
    assert len(persistence.list_notes()) == 0
    assert len(persistence.list_tags()) == 0
    assert persistence.read_note("non-existent") == ""
    assert len(persistence.read_tags("non-existent")) == 0
    assert persistence.note_path("non-existent") == os.path.join(notes_path, "non-existent")
    assert persistence.geometry() == "320x240"
    assert persistence.font_size() == 42
    assert persistence.theme() == "my-theme"
    assert persistence.css() != ""


def test_read_existing():
    """Checks reading existing notes.

    ```
    root                      : filesystem root
    +-- .notepy.yml           : notepy config file
    +-- base                  : base
        +-- style.css         : style
        +-- notes             : notes directory
            +-- simple        : simple note directory
            |   +-- README.md : simple note contents
            +-- tagged        : tagged note directory
            |   +-- README.md : tagged note contents
            |   +-- tags.txt  : tagged note tags
            +-- complex       : complex note directory
                +-- README.md : complex note contents
                +-- tags.txt  : complex note tags
                +-- pic.png   : complex note attachment
    ```
    """

    config_file = fs.write_configfile(persistence_version=1)
    fs.mkdir("base")
    fs.mkdir(os.path.join("base","notes"))

    custom_style = "custom_ style"
    fs.write_file(os.path.join("base", "style.css"), custom_style)

    simple_note_path = os.path.join("base","notes","simple")
    fs.mkdir(simple_note_path)
    simple_note_contents = "# Simple Note"
    fs.write_file(os.path.join(simple_note_path, "README.md"), simple_note_contents)

    tagged_note_path = os.path.join("base","notes","tagged")
    fs.mkdir(tagged_note_path)
    tagged_note_contents = "# Tagged Note"
    fs.write_file(os.path.join(tagged_note_path, "README.md"), tagged_note_contents)
    fs.write_file(os.path.join(tagged_note_path, "tags.txt"), "info")

    complex_note_path = os.path.join("base","notes","complex")
    fs.mkdir(complex_note_path)
    complex_note_contents = "# Complex Note"
    fs.write_file(os.path.join(complex_note_path, "README.md"), complex_note_contents)
    fs.write_file(os.path.join(complex_note_path, "tags.txt"), "info\ncomplex")
    fs.write_file(os.path.join(complex_note_path, "pic.png"), "some attachment")

    persistence = Persistence(config_file)

    # check custom css
    assert persistence.css() == custom_style

    # check notes
    notes = persistence.list_notes()
    assert len(notes) == 3
    assert "simple" in notes
    assert "tagged" in notes
    assert "complex" in notes

    # check overall tags
    tags = persistence.list_tags()
    assert len(tags) == 2
    assert "info" in tags
    assert "complex" in tags

    # check simple note
    assert persistence.read_note("simple") == simple_note_contents
    assert len(persistence.read_tags("simple")) == 0

    # check tagged note
    assert persistence.read_note("tagged") == tagged_note_contents
    tags = persistence.read_tags("tagged")
    assert len(tags) == 1
    assert "info" in tags

    # check comple note
    assert persistence.read_note("complex") == complex_note_contents
    tags = persistence.read_tags("complex")
    assert len(tags) == 2
    assert "info" in tags
    assert "complex" in tags


def test_write_geometry():
    """Checks if geometry is written to config file."""

    initial_geometry = "320x240"
    config_file = fs.write_configfile(geometry=initial_geometry)
    persistence = Persistence(config_file)
    assert persistence.geometry() == initial_geometry

    new_geometry = "640x480"
    assert persistence.geometry(new_geometry) == new_geometry

    new_persistence = Persistence(config_file)
    assert new_geometry == new_persistence.geometry()


def test_create_note():
    """Checks if a new note can be created."""

    config_file = fs.write_configfile()
    persistence = Persistence(config_file)
    title = "new_note"
    contents = "# New Note\n\nThis is a new note."
    persistence.write_note(title, contents)
    persistence.write_tags(title, ["new", "note"])

    check_note(persistence, title, contents, ["new", "note"])

    # Check also against fresh persistence to make
    # sure everything is written to file system.
    check_note(Persistence(config_file), title, contents, ["new", "note"])


def test_create_note_special_char():
    """Checks if a new note can be created with some special characters."""

    config_file = fs.write_configfile()
    persistence = Persistence(config_file)
    title = "new_note /!<>:\ \\ | ?*%"
    contents = "# New Note\n\nThis is a new note."
    persistence.write_note(title, contents)
    persistence.write_tags(title, ["new", "note"])

    check_note(persistence, title, contents, ["new", "note"])

    # Check also against fresh persistence to make
    # sure everything is written to file system.
    check_note(Persistence(config_file), title, contents, ["new", "note"])


def test_modify_existing_note():
    """Checks if a note can be moified."""

    config_file = fs.write_configfile()
    initial_persistence = Persistence(config_file)
    title = "some note"
    old_contents = "old contents"
    initial_persistence.write_note(title, old_contents)
    initial_persistence.write_tags(title, ["old", "note"])

    persistence = Persistence(config_file)
    assert persistence.read_note(title) == old_contents
    new_contents = "new contents"
    persistence.write_note(title, new_contents)
    persistence.write_tags(title, ["new"])
    check_note(persistence, title, new_contents, ["new"])

    # Check also against fresh persistence to make
    # sure everything is written to file system.
    new_persistence = Persistence(config_file)
    check_note(new_persistence, title, new_contents, ["new"])
    assert len(new_persistence.list_tags()) == 1


def test_rename_note():
    """Checks if a note can be renamed."""

    config_file = fs.write_configfile()
    initial_persistence = Persistence(config_file)
    old_title = "old-note"
    contents = "some contents"
    initial_persistence.write_note(old_title, contents)
    initial_persistence.write_tags(old_title, ["some", "note"])

    persistence = Persistence(config_file)
    check_note(persistence, old_title, contents, ["some", "note"])
    new_title = "new-note"
    persistence.rename_note(old_title, new_title)
    check_note(persistence, new_title, contents, ["some", "note"])
    assert len(persistence.list_notes()) == 1

    # Check also against fresh persistence to make
    # sure everything is written to file system.
    new_persistence = Persistence(config_file)
    check_note(new_persistence, new_title, contents, ["some", "note"])
    assert len(new_persistence.list_notes()) == 1


def test_remove_note():
    """Check if a note can be removed."""

    config_file = fs.write_configfile()
    initial_persistence = Persistence(config_file)
    title = "some-note"
    contents = "some contents"
    initial_persistence.write_note(title, contents)
    initial_persistence.write_tags(title, ["some", "note"])

    persistence = Persistence(config_file)
    check_note(persistence, title, contents, ["some", "note"])
    persistence.remove_note(title)
    assert len(persistence.list_notes()) == 0
    assert len(persistence.list_tags()) == 0
    assert len(persistence.read_tags(title)) == 0

    # Check also against fresh persistence to make
    # sure everything is written to file system.
    new_persistence = Persistence(config_file)
    assert len(new_persistence.list_notes()) == 0
    assert len(new_persistence.list_tags()) == 0
    assert len(new_persistence.read_tags(title)) == 0


def test_migrate_from_v1():
    """Checks migration from persistence v1.

    In persistence v1, the contents of a note where stored in
    a file called note.md. This file should be renamed to
    README.md.

    
    V1 filesystem layout:
    ```
    root                     : filesystem root
    +-- .notepy.yml          : notepy config file
    +-- base                 : base
        +-- notes            : notes directory
            +-- old-note     : direcotry of the old note
                +-- note.md  : contents of the old note
    ```

    V2 filesystem layout:
    ```
    root                       : filesystem root
    +-- .notepy.yml            : notepy config file
    +-- base                   : base
        +-- notes              : notes directory
            +-- old-note       : direcotry of the old note
                +-- README.md  : contents of the old note
    ```
    """

    config_file = fs.write_configfile(persistence_version=1)
    fs.mkdir("base")
    fs.mkdir(os.path.join("base","notes"))

    note_path = os.path.join("base","notes","old-note")
    fs.mkdir(note_path)
    contents = "Contents of old note"
    fs.write_file(os.path.join(note_path, "note.md"), contents)

    persistence = Persistence(config_file)
    assert fs.is_dir(note_path)
    assert fs.is_file(os.path.join(note_path, "README.md"))
    assert not fs.exists(os.path.join(note_path, "note.md"))

    notes = persistence.list_notes()
    assert len(notes) == 1
    assert len(persistence.list_tags()) == 0
    assert "old-note" in notes
    assert persistence.read_note("old-note") == contents
    assert len(persistence.read_tags("old-note")) == 0
