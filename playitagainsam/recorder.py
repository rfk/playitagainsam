#  Copyright (c) 2012, Ryan Kelly.
#  All rights reserved; available under the terms of the MIT License.
"""

playitagainsam.recorder:  record interactive terminal sessions
==============================================================

This module provides the ability to record interactive terminal sessions.

"""

import os
import sys
import time
import select
import socket
import json
import uuid

from playitagainsam.util import forkexec_pty, get_fd, no_echo
from playitagainsam.coordinator import SocketCoordinator, proxy_to_coordinator


class Recorder(SocketCoordinator):
    """Object for recording activity in a session."""

    def __init__(self, eventlog, sock_path):
        self.eventlog = eventlog
        super(Recorder, self).__init__(sock_path)
        self.terminals = {}
        self.view_fds = {}
        self.proc_fds = {}

    def run(self):
        # Loop waiting for the first terminal to be opened.
        while not self.terminals:
            ready = self.wait_for_data([self.sock])
            if self.sock in ready:
                client_sock, _ = self.sock.accept()
                self._handle_open_terminal(client_sock)
        # Loop waiting for activity to occur, or all terminals to close.
        while self.terminals:
            # Time how long it takes, in case we need to trigger output
            # via a pause in the event stream.
            t1 = time.time()
            fds = [self.sock] + list(self.view_fds) + list(self.proc_fds)
            ready = self.wait_for_data(fds)
            t2 = time.time()
            if not ready:
                continue
            # Find some trigger for any output that becomes available.
            # It might be a keypress, or the creation of a new terminal.
            # Or it might just be the passage of time.
            for view_fd in self.view_fds:
                if view_fd in ready:
                    self._handle_input(view_fd)
                    break
            else:
                if self.sock in ready:
                    client_sock, _ = self.sock.accept()
                    self._handle_open_terminal(client_sock)
                else:
                    self._handle_pause(t2 - t1)
            # Now process any output that has been triggered.
            # This will loop and consume as much output as is available.
            self._handle_output()

    def cleanup(self):
        for term in self.terminals:
            client_sock, proc_fd, proc_pid = self.terminals[term]
            client_sock.close()
            os.close(proc_fd)
        super(Recorder, self).cleanup()

    def _handle_input(self, view_fd):
        try:
            c = os.read(view_fd, 1)
        except OSError:
            pass
        else:
            if c:
                term = self.view_fds[view_fd]
                proc_fd = self.terminals[term][1]
                # Log it to the eventlog.
                self.eventlog.append({
                    "act": "READ",
                    "term": term,
                    "data": c,
                })
                # Forward it to the corresponding terminal process.
                os.write(proc_fd, c)

    def _handle_output(self):
        ready = self.wait_for_data(self.proc_fds)
        # Process output from each ready process in turn.
        for proc_fd in ready:
            term = self.proc_fds[proc_fd]
            view_fd = self.terminals[term][0].fileno()
            # Loop through one character at a time, consuming as
            # much output from the process as is available.
            proc_ready = [proc_fd]
            while proc_ready:
                try:
                    c = os.read(proc_fd, 1)
                    if not c:
                        raise OSError
                except OSError:
                    self._handle_close_terminal(term)
                    proc_ready = []
                else:
                    # Log it to the eventlog.
                    self.eventlog.append({
                        "act": "WRITE",
                        "term": term,
                        "data": c,
                    })
                    # Forward it to the corresponding terminal view.
                    os.write(view_fd, c)
                    proc_ready = self.wait_for_data([proc_fd], 0)

    def _handle_open_terminal(self, client_sock):
        # Read the program to start, in form "SIZE JSON-DATA\n"
        size = 0
        c = client_sock.recv(1)
        while c != " ":
            size = (size * 10) + int(c)
            c = client_sock.recv(1)
        data = client_sock.recv(size)
        while len(data) < size + 1:
            more_data = client_sock.recv(size + 1 - len(data))
            if not more_data:
                raise ValueError("client sent incomplete data")
            data += more_data
        shell = json.loads(data.strip())
        # Fork the requested process behind a pty.
        if isinstance(shell, basestring):
            shell = [shell]
        proc_pid, proc_fd = forkexec_pty(*shell)
        # Assign a new id for the terminal
        term = uuid.uuid4().hex
        self.terminals[term] = client_sock, proc_fd, proc_pid
        self.view_fds[client_sock.fileno()] = term
        self.proc_fds[proc_fd] = term
        # Append it to the eventlog.
        self.eventlog.append({
            "act": "OPEN",
            "term": term,
        })

    def _handle_close_terminal(self, term):
        self.eventlog.append({
            "act": "CLOSE",
            "term": term,
        })
        client_sock, proc_fd, proc_pid = self.terminals.pop(term)
        del self.view_fds[client_sock.fileno()]
        del self.proc_fds[proc_fd]
        client_sock.close()
        os.close(proc_fd)

    def _handle_pause(self, duration):
        self.eventlog.append({
            "act": "PAUSE",
            "duration": duration,
        })


def spawn_in_recorder(sock_path, shell, **kwds):
    data = json.dumps(shell)
    header = "%d %s\n" % (len(data), data)
    return proxy_to_coordinator(sock_path, header, **kwds)
