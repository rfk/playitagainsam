#  Copyright (c) 2012, Ryan Kelly.
#  All rights reserved; available under the terms of the MIT License.
"""

playitagainsam.player: replay interactive terminal sessions
===========================================================

"""

import os
import sys
import time

import six

from playitagainsam.util import forkexec, get_default_terminal
from playitagainsam.util import forkexec_pty
from playitagainsam.util import get_pias_script, get_fd
from playitagainsam.coordinator import SocketCoordinator, proxy_to_coordinator

# XXX TODO: set the size of each terminal


class Player(SocketCoordinator):

    waypoint_chars = (six.b("\n"), six.b("\r"))

    def __init__(self, sock_path, eventlog, terminal=None, auto_type=False,
                 auto_waypoint=False, live_replay=False, replay_shell=None):
        super(Player, self).__init__(sock_path)
        self.eventlog = eventlog
        self.terminal = terminal
        self.live_replay = live_replay
        self.replay_shell = replay_shell
        if not auto_type:
            self.auto_type = False
        else:
            self.auto_type = auto_type / 1000.0
        if not auto_waypoint:
            self.auto_waypoint = False
        else:
            self.auto_waypoint = auto_waypoint / 1000.0
        self.terminals = {}
        self.proc_fds = {}
        # Ensure we have a terminal cmd if we know one will be needed.
        if len(eventlog.terminals) > 1:
            if self.terminal is None:
                self.terminal = get_default_terminal()

    def run(self):
        event = self.eventlog.read_event()
        while event is not None:
            action = event["act"]
            term = event.get("term", None)
            data = event.get("data", None)

            # TODO (JC) -- possibly this should not be in the event process loop:
            # it should be event-driven by an asyncore.dispatcher.handle_read();
            # we would also ignore PAUSEs if (live-replay and not auto-type),
            # but for now it works well enough for the patch author's use cases.
            self._maybe_do_live_output(term)

            if action == "OPEN":
                self._do_open_terminal(term)
            elif action == "PAUSE":
                time.sleep(event["duration"])
            elif action == "READ":
                self._do_read(term, data)
            elif action == "WRITE":
                # when in --live-replay mode, eventlog sends no WRITE events,
                # so no need to check here whether we are on --live-replay or not
                self._do_write(term, data)
            if action == "CLOSE":
                self._do_close_terminal(term)

            event = self.eventlog.read_event()

    def cleanup(self):
        for term in self.terminals:
            view_sock, _, = self.terminals[term]
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
            cmd = self.terminal or get_default_terminal()
            forkexec([cmd, "-e", get_pias_script()], env)
        view_sock, _ = self.sock.accept()

        if self.live_replay:
            # this is cribbed from recorder._handle_open_terminal
            # TODO (JC): look into further refactoring common code into an util function
            # Fork a new shell behind a pty.
            _, proc_fd = forkexec_pty([self.replay_shell])
            # often the terminal comes up before the pty has had a chance to send:
            ready = None
            while not ready:
                ready = self.wait_for_data([proc_fd], 0.1)
        else:
            proc_fd = None

        self.terminals[term] = (view_sock, proc_fd)
        self.proc_fds[proc_fd] = term

    def _do_close_terminal(self, term):
        view_sock, proc_fd = self.terminals[term]
        view_sock.close()
        # TODO (JC): would the pty still be open? close it?

    def _do_read(self, term, recorded):
        if isinstance(recorded, six.text_type):
            recorded = recorded.encode("utf8")
        view_sock = self.terminals[term][0]
        if recorded in self.waypoint_chars:
            self._do_read_waypoint(view_sock, term, recorded)
        else:
            self._do_read_nonwaypoint(view_sock, term, recorded)

    def _maybe_live_replay(self, term, c=None):
        if self.live_replay:
            proc_fd = self.terminals[term][1]
            if c:
                os.write(proc_fd, c)

    def _do_read_nonwaypoint(self, view_sock, term, recorded):
        # For non-waypoint characters, behaviour depends on auto-typing mode.
        # we can can either wait for the user to type something, or just
        # sleep briefly to simulate the typing.
        if self.auto_type:
            time.sleep(self.auto_type)
        else:
            c = view_sock.recv(1)
            while c in self.waypoint_chars:
                c = view_sock.recv(1)
        self._maybe_live_replay(term, recorded)

    def _do_read_waypoint(self, view_sock, term, recorded):
        # For waypoint characters, behaviour depends on auto-waypoint mode.
        # Either we just proceed automatically, or the user must actually
        # type one before we proceed.
        if self.auto_waypoint:
            time.sleep(self.auto_waypoint)
        else:
            c = view_sock.recv(1)
            while c not in self.waypoint_chars:
                c = view_sock.recv(1)
        self._maybe_live_replay(term, recorded)

    def _maybe_do_live_output(self, term):
        if self.live_replay:
            # like self._do_open_terminal above, also cribbed from recorder.py
            # TODO (JC): for the same reason, look into refactoring
            ready = self.wait_for_data(self.proc_fds, 0.01)
            # Process output from each ready process in turn.
            for proc_fd in ready:
                term = self.proc_fds[proc_fd]
                view_fd = self.terminals[term][0].fileno()
                # Loop through one character at a time, consuming as
                # much output from the process as is available.
                # We buffer it and write it to the eventlog as a single event,
                # because multiple bytes might be part of a single utf8 char.
                proc_ready = [proc_fd]
                while proc_ready:
                    try:
                        c = self._read_one_byte(proc_fd)
                    except OSError:
                        self._do_close_terminal(term)
                        break
                    else:
                        os.write(view_fd, c)
                        proc_ready = self.wait_for_data([proc_fd], 0)

    ## TODO (JC): No reason for this to be a method. Refactor to utils
    def _read_one_byte(self, fd):
        """Read a single byte, or raise OSError on failure."""
        c = os.read(fd, 1)
        if not c:
            raise OSError
        return c

    def _do_write(self, term, data):
        view_sock = self.terminals[term][0]
        if isinstance(data, six.text_type):
            data = data.encode("utf8")
        view_sock.sendall(data)


def join_player(sock_path, **kwds):
    stdout_fd = get_fd(kwds.get("stdout"), sys.stdout)
    os.write(stdout_fd, b"\x1b[2J\x1b[H")
    return proxy_to_coordinator(sock_path, **kwds)
