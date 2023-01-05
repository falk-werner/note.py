#!/usr/bin/env python3

# Copyright (c) 2022 note.py authors
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import note

class Handler:
    def __init__(self, callback=None):
        self.call_count = 0
        self.callback = callback
    
    def invoke(self):
        self.call_count += 1
        if self.callback:
            self.callback(self)

def call():
    call_count += 1

def test_fire():
    event = note.ModelEvent()
    handler = Handler()
    event.subscribe(handler.invoke)
    event.fire()
    assert handler.call_count == 1

def test_subscribe_multiple():
    event = note.ModelEvent()
    handler1 = Handler()
    event.subscribe(handler1.invoke)
    handler2 = Handler()
    event.subscribe(handler2.invoke)
    event.fire()
    assert handler1.call_count == 1
    assert handler2.call_count == 1

def test_unsubscribe():
    event = note.ModelEvent()
    handler = Handler()
    event.subscribe(handler.invoke)
    event.unsubscribe(handler.invoke)
    event.fire()
    assert handler.call_count == 0

def test_unsubscribe_in_handler():
    event = note.ModelEvent()
    handler = Handler(lambda h, event=event: event.unsubscribe(h.invoke))
    event.subscribe(handler.invoke)
    event.fire()
    event.fire()
    assert handler.call_count == 1
