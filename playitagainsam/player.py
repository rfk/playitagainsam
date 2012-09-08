#  Copyright (c) 2012, Ryan Kelly.
#  All rights reserved; available under the terms of the MIT License.
"""

playitagainsam.player: replay interactive terminal sessions
===========================================================

"""

import time

import six

from playitagainsam.util import forkexec, get_default_terminal
from playitagainsam.util import get_pias_script
from playitagainsam.coordinator import SocketCoordinator, proxy_to_coordinator

# XXX TODO: set the size of each terminal


class Player(SocketCoordinator):

    waypoint_chars = (six.b("\n"), six.b("\r"))

    def __init__(self, sock_path, eventlog, terminal=None, auto_type=False,
                 auto_waypoint=False):
        super(Player, self).__init__(sock_path)
        self.eventlog = eventlog
        self.terminal = terminal or get_default_terminal()
        if not auto_type:
            self.auto_type = False
        else:
            self.auto_type = auto_type / 1000.0
        if not auto_waypoint:
            self.auto_waypoint = False
        else:
            self.auto_waypoint = auto_waypoint / 1000.0
        self.terminals = {}
        self.view_fds = {}

    def run(self):
        event = self.eventlog.read_event()
        while event is not None:
            if event["act"] == "OPEN":
                self._do_open_terminal(event["term"])
            elif event["act"] == "CLOSE":
                self._do_close_terminal(event["term"])
            elif event["act"] == "PAUSE":
                time.sleep(event["duration"])
            elif event["act"] == "READ":
                self._do_read(event["term"], event["data"])
            elif event["act"] == "WRITE":
                self._do_write(event["term"], event["data"])
            event = self.eventlog.read_event()

    def cleanup(self):
        for term in self.terminals:
            view_sock, = self.terminals[term]
            view_sock.close()
        super(Player, self).cleanup()

    def _do_open_terminal(self, term):
        ready = self.wait_for_data([self.sock], 0.1)
        if self.sock not in ready:
            # XXX TODO: wait for a keypress from some existing terminal
            # to trigger the appearance of the terminal.
            # Specify options via the environment.
            # This allows us to spawn the joiner with no arguments,
            # so it will work with the "-e" option of terminal programs.
            env = {}
            env["PIAS_OPT_JOIN"] = "1"
            env["PIAS_OPT_COMMAND"] = "replay"
            env["PIAS_OPT_DATAFILE"] = self.eventlog.datafile
            env["PIAS_OPT_TERMINAL"] = self.terminal
            forkexec([self.terminal, "-e", get_pias_script()], env)
        view_sock, _ = self.sock.accept()
        self.terminals[term] = (view_sock,)

    def _do_close_terminal(self, term):
        view_sock, = self.terminals[term]
        self._do_read_waypoint(view_sock)
        view_sock.close()

    def _do_read(self, term, wanted):
        if isinstance(wanted, six.text_type):
            wanted = wanted.encode("utf8")
        view_sock = self.terminals[term][0]
        if wanted in self.waypoint_chars:
            self._do_read_waypoint(view_sock)
        else:
            self._do_read_nonwaypoint(view_sock)

    def _do_read_nonwaypoint(self, view_sock):
        # For non-waypoint characters, behaviour depends on auto-typing mode.
        # we can can either wait for the user to type something, or just
        # sleep briefly to simulate the typing.
        if self.auto_type:
            time.sleep(self.auto_type)
        else:
            c = view_sock.recv(1)
            while c in self.waypoint_chars:
                c = view_sock.recv(1)

    def _do_read_waypoint(self, view_sock):
        # For waypoint characters, behaviour depends on auto-waypoint mode.
        # Either we just proceed automatically, or the user must actually
        # type one before we proceed.
        if self.auto_waypoint:
            time.sleep(self.auto_waypoint)
        else:
            c = view_sock.recv(1)
            while c not in self.waypoint_chars:
                c = view_sock.recv(1)

    def _do_write(self, term, data):
        view_sock = self.terminals[term][0]
        if isinstance(data, six.text_type):
            data = data.encode("utf8")
        view_sock.sendall(data)


def join_player(sock_path, **kwds):
    return proxy_to_coordinator(sock_path, **kwds)
