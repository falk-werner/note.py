#!/usr/bin/env python3

# Copyright (c) 2022 Falk Werner
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from note import waitstatus_to_exitcode
import os

def test_affirmative_exitcode():
    status = os.system('true')
    exit_code = waitstatus_to_exitcode(status)
    assert exit_code == 0

def test_non_affirmative_exitcode():
    status = os.system('false')
    exit_code = waitstatus_to_exitcode(status)
    assert exit_code != 0
