#!/usr/bin/env python3
# Requirements.txt support

import sys

sys.path.append("lib")

from ops.framework import StoredState

import os
import subprocess
import sys

REQUIREMENTS_TXT = "{}/requirements.txt".format(os.environ["JUJU_CHARM_DIR"])


def install_requirements():
    if os.path.exists(REQUIREMENTS_TXT):
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_TXT],
            # Eat stdout so it's not returned in an action's stdout
            # TODO: redirect to a file handle and log to juju log
#            stdout=subprocess.DEVNULL,
        )


# Use StoredState to make sure we're run exactly once automatically
state = StoredState()
installed = getattr(state, "requirements_txt_installed", None)
if not installed:
    install_requirements()
    state.requirements_txt_installed = True

