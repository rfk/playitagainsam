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


class Replayer(object):

    def __init__(self, events):
        self.events = list(events)
        self._ping_pipe_r, self._ping_pipe_w = os.pipe()
        self.running = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("localhost", 12345))
        self.sock.listen(1)
        self.terminals = {}
        self.view_fds = {}

    def __del__(self):
        self._cleanup_pipes()

    def _cleanup_pipes(self, os=os):
        if getattr(self, "_ping_pipe_r", None) is not None:
            os.close(self._ping_pipe_r)
            self._ping_pipe_r = None
        if getattr(self, "_ping_pipe_w", None) is not None:
            os.close(self._ping_pipe_w)
            self._ping_pipe_w = None

    def stop(self):
        self.running = False
        os.write(self._ping_pipe_w, "X")

    def run(self):
        self.running = True
        event_stream = self._iter_events()
        try:
            while self.running:
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
        for term in self.terminals:
            self._do_close_terminal(term)

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
        child_pid = forkexec("/usr/bin/gnome-terminal", "-x", "/bin/bash", "-c", sys.executable + " -c \"from playitagainsam.recorder import proxy_to_recorder_addr; proxy_to_recorder_addr(('localhost', 12345))\" ; sleep 10")
        view_sock, _ = self.sock.accept()
        self.terminals[term] = (view_sock, child_pid)

    def _do_close_terminal(self, term):
        view_sock, client_pid = self.terminals[term]
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
