#!/usr/bin/env python3

# Copyright (c) 2022 Falk Werner
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
import pytest

@pytest.mark.skipif(os.name=='nt', reason="Don't run on windows")
def test_affirmative_exitcode():
    status = os.system('true')
    exit_code = os.waitstatus_to_exitcode(status)
    assert exit_code == 0

@pytest.mark.skipif(os.name=='nt', reason="Don't run on windows")
def test_non_affirmative_exitcode():
    status = os.system('false')
    exit_code = os.waitstatus_to_exitcode(status)
    assert exit_code != 0
