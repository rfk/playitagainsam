#  Copyright (c) 2012, Ryan Kelly.
#  All rights reserved; available under the terms of the MIT License.
"""

playitagainsam.player: replay interactive terminal sessions
===========================================================

"""

import os
import sys
import time
import socket

from playitagainsam.util import no_echo, get_fd, forkexec
from playitagainsam.coordinator import SocketCoordinator, proxy_to_coordinator


class Player(SocketCoordinator):

    def __init__(self, events, terminal, sock_path):
        self.events = list(events)
        self.terminal = terminal
        super(Player, self).__init__(sock_path)
        self.terminals = {}
        self.view_fds = {}

    def run(self):
        event_stream = self._iter_events()
        try:
            while True:
                event = event_stream.next()
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
        except StopIteration:
            pass

    def cleanup(self):
        for term in self.terminals:
            view_sock, = self.terminals[term]
            view_sock.close()
        super(Player, self).cleanup()

    def _iter_events(self):
        for event in self.events:
            if event["act"] == "ECHO":
                for c in  event["data"]:
                    yield { "act": "READ", "term": event["term"], "data": c }
                    yield { "act": "WRITE", "term": event["term"], "data": c }
            elif event["act"] == "READ":
                for c in  event["data"]:
                    yield { "act": "READ", "term": event["term"], "data": c }
            else:
                yield event

    def _do_open_terminal(self, term):
        ready = self.wait_for_data([self.sock], 0.1)
        if self.sock not in ready:
            # XXX TODO: wait for a keypress from some existing terminal
            # to trigger the appearance of the terminal.
            join_cmd = list(sys.argv)
            join_cmd.insert(1, "--join")
            forkexec(self.terminal, "-x", *join_cmd)
        view_sock, _ = self.sock.accept()
        self.terminals[term] = (view_sock,)

    def _do_close_terminal(self, term):
        view_sock, = self.terminals[term]
        c = view_sock.recv(1)
        while c not in ("\n", "\r"):
            c = view_sock.recv(1)
        view_sock.close()

    def _do_read(self, term, wanted):
        view_sock = self.terminals[term][0]
        c = view_sock.recv(1)
        if wanted in ("\n", "\r"):
            while c not in ("\n", "\r"):
                c = view_sock.recv(1)

    def _do_write(self, term, data):
        view_sock = self.terminals[term][0]
        view_sock.sendall(data)


def proxy_to_player(sock_path, **kwds):
    return proxy_to_coordinator(sock_path, **kwds)
