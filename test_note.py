#!/usr/bin/env python3

# Copyright (c) 2023 note.py authors
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import note

class FakeNoteCollection:
    def __init__(self):
        pass

    def note_changed(self):
        pass

class FakePersistence:
    def __init__(self):
        pass

    def read_note(self, name):
        return ""

    def write_note(self, name, contents):
        pass

    def read_tags(self, name):
        return []

    def write_tags(self, name, tags):
        pass

    def rename_note(self, old_name, new_name):
        pass

def test_get_name():
    collection = FakeNoteCollection()
    persistence = FakePersistence()
    n = note.Note(collection, persistence, "test")
    assert("test" == n.name())

def test_set_name():
    collection = FakeNoteCollection()
    persistence = FakePersistence()
    n = note.Note(collection, persistence, "test")
    n.name("new name")
    assert("new name" == n.name())

def test_get_contents():
    collection = FakeNoteCollection()
    persistence = FakePersistence()
    n = note.Note(collection, persistence, "test")
    assert("" == n.contents())

def test_set_contents():
    collection = FakeNoteCollection()
    persistence = FakePersistence()
    n = note.Note(collection, persistence, "test")
    n.contents("brummni")
    assert("brummni" == n.contents())

def test_get_tags():
    collection = FakeNoteCollection()
    persistence = FakePersistence()
    n = note.Note(collection, persistence, "test")
    assert([] == n.tags())

def test_set_tags():
    collection = FakeNoteCollection()
    persistence = FakePersistence()
    n = note.Note(collection, persistence, "test")
    n.tags(["foo"])
    assert(["foo"] == n.tags())

def test_matches_name():
    collection = FakeNoteCollection()
    persistence = FakePersistence()
    n = note.Note(collection, persistence, "test")
    assert(n.matches("test", []))
    assert(not n.matches("foo", []))

def test_matches_tag():
    collection = FakeNoteCollection()
    persistence = FakePersistence()
    n = note.Note(collection, persistence, "test")
    n.tags(["foo"])
    assert(n.matches("", ["foo"]))
    assert(not n.matches("", ["bar"]))
