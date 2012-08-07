#  Copyright (c) 2012, Ryan Kelly.
#  All rights reserved; available under the terms of the MIT License.
"""

playitagainsam.util:  utility functions for interacting with terminals
======================================================================

"""

import os
import sys
import tty
import pty
import termios
import select
import optparse
import time

from subprocess import MAXFD


class no_echo(object):
    """Context-manager that blocks echoing of keys typed in tty."""

    def __init__(self, fd=None):
        if fd is None:
            fd = sys.stdin.fileno()
        elif hasattr(fd, "fileno"):
            fd = fd.fileno()
        self.fd = fd

    def __enter__(self):
        self.old_attr = termios.tcgetattr(self.fd)
        new_attr = list(self.old_attr)
        new_attr[3] = new_attr[3] & ~termios.ECHO
        termios.tcsetattr(self.fd, termios.TCSADRAIN, new_attr)
        tty.setraw(sys.stdin)

    def __exit__(self, exc_typ, exc_val, exc_tb):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_attr)


def get_fd(file_or_fd, default=None):
    """Helper function for getting a file descriptor."""
    fd = file_or_fd
    if fd is None:
        fd = default
    if hasattr(fd, "fileno"):
        fd = fd.fileno()
    return fd


def forkexec(*argv):
    """Fork a child process."""
    child_pid = os.fork()
    if child_pid == 0:
        os.closerange(3, MAXFD)
        os.execv(argv[0], argv)
    return child_pid


def forkexec_pty(*argv):
    """Fork a child process attached to a pty."""
    child_pid, child_fd = pty.fork()
    if child_pid == 0:
        os.closerange(3, MAXFD)
        os.execv(argv[0], argv)
    return child_pid, child_fd


class EventLog(object):

    def __init__(self):
        self.events = []

    def append(self, event):
        # Append an event to the event log.
        # We try to do some basic simplifications.
        # Collapse consecutive "PAUSE" events into a single pause.
        if event["act"] == "PAUSE":
            if self.events and self.events[-1]["act"] == "PAUSE":
                self.events[-1]["duration"] += event["duration"]
                return
        # Try to collapse consecutive IO events on the same terminal.
        if event["act"] == "WRITE" and self.events:
            if self.events[-1].get("term") == event["term"]:
                # Collapse consecutive writes into a single chunk.
                if self.events[-1]["act"] == "WRITE":
                    self.events[-1]["data"] += event["data"]
                    return
                # Collapse read/write of same data into an "ECHO".
                if self.events[-1]["act"] == "READ":
                    if self.events[-1]["data"] == event["data"]:
                        self.events[-1]["act"] = "ECHO"
                        # Collapse consecutive "ECHO" events.
                        if len(self.events) > 1:
                            if self.events[-2]["act"] == "ECHO":
                                if self.events[-2]["term"] == event["term"]:
                                    self.events[-2]["data"] += event["data"]
                                    del self.events[-1]
                        return
        # Otherwise, just add it to the list.
        self.events.append(event)
