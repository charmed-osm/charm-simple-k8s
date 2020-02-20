#!/usr/bin/env python3
# Requirements.txt support

import sys

sys.path.append("lib")

from ops.framework import StoredState

import os
import subprocess
import sys
from remote_pdb import RemotePdb

REQUIREMENTS_TXT = "{}/requirements.txt".format(os.environ["JUJU_CHARM_DIR"])


def install_requirements():
    if os.path.exists(REQUIREMENTS_TXT):

        # First, make sure python3 and python3-pip are installed
        if not os.path.exists("/usr/bin/python3") or not os.path.exists("/usr/bin/pip3"):
            # Update the apt cache
            subprocess.check_call(["apt-get", "update"])
            # Install the Python3 package
            subprocess.check_call(
                ["apt-get", "install", "-y", "python3", "python3-pip", "python3-paramiko"],
                # Eat stdout so it's not returned in an action's stdout
                # TODO: redirect to a file handle and log to juju log
                # stdout=subprocess.DEVNULL,
            )

        # Lastly, install the python requirements
        cmd = [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_TXT]
        # stdout = subprocess.check_output(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    
        stdout, stderr = p.communicate()

        print(stdout)
        print(stderr)
        #     subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_TXT],
        #     # Eat stdout so it's not returned in an action's stdout
        #     # TODO: redirect to a file handle and log to juju log
        #     # stdout=subprocess.DEVNULL,
        # )


# Use StoredState to make sure we're run exactly once automatically
# RemotePdb('127.0.0.1', 4444).set_trace()

state = StoredState()

installed = getattr(state, "requirements_txt_installed", None)
if not installed:
    install_requirements()
    state.requirements_txt_installed = True

