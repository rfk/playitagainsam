#  Copyright (c) 2012, Ryan Kelly.
#  All rights reserved; available under the terms of the MIT License.
"""

playitagainsam.recorder:  record interactive terminal sessions
==============================================================

This module provides the ability to record interactive terminal sessions.

"""

import os
import time
import uuid
import queue
import thread

import six

from playitagainsam.util import forkexec_pty, get_default_shell
from playitagainsam.util import get_terminal_size, set_terminal_size
from playitagainsam.coordinator import SocketCoordinator, proxy_to_coordinator


class Recorder(SocketCoordinator):
    """Object for recording activity in a session."""

    def __init__(self, sock_path, eventlog, resize_event, shell=None):
        super(Recorder, self).__init__(sock_path)
        self.eventlog = eventlog
        self.shell = shell or get_default_shell()
        self.terminals = {}
        self.view_fds = {}
        self.proc_fds = {}
        self.resize_event = resize_event

    def run(self):
        # Loop waiting for the first terminal to be opened.
        while not self.terminals:
            ready = self.wait_for_data([self.sock])
            if self.sock in ready:
                client_sock, _ = self.sock.accept()
                self._handle_open_terminal(client_sock)
        # Startup the resize_event_thread to resize terminals.
        thread.start_new_thread(self._resize_event_thread, tuple())
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

    def _utf8_length_first_byte(self, byte):
        # https://en.wikipedia.org/wiki/UTF-8#Description
        byte_int = ord(byte)
        if byte_int & 0b11111100 == 0b11111100:
            return 6
        elif byte_int & 0b11111000 == 0b11111000:
            return 5
        elif byte_int & 0b11110000 == 0b11110000:
            return 4
        elif byte_int & 0b11100000 == 0b11100000:
            return 3
        elif byte_int & 0b11000000 == 0b11000000:
            return 2
        elif byte_int & 0b10000000 == 0b10000000:
            # 0b10 in the significant bits is a flag for continuation bytes. We
            # should not see this on a utf8 character start. This is not good.
            raise OSError
        else:
            return 1

    def _get_utf8_character(self, view_fd):
        partial_input = [self._read_one_byte(view_fd)]
        for _ in xrange(self._utf8_length_first_byte(partial_input[0]) - 1):
            partial_input.append(self._read_one_byte(view_fd))
        return "".join(partial_input)

    def _handle_input(self, view_fd):
        try:
            c = self._get_utf8_character(view_fd)
        except OSError:
            pass
        else:
            term = self.view_fds[view_fd]
            proc_fd = self.terminals[term][1]
            # Log it to the eventlog.
            self.eventlog.write_event({
                "act": "READ",
                "term": term,
                "data": c,
            })
            # Forward it to the corresponding terminal process.
            os.write(proc_fd, c)

    def _handle_output(self):
        ready = self.wait_for_data(self.proc_fds, 0.01)
        # Process output from each ready process in turn.
        for proc_fd in ready:
            term = self.proc_fds[proc_fd]
            view_fd = self.terminals[term][0].fileno()
            # Loop through one character at a time, consuming as
            # much output from the process as is available.
            # We buffer it and write it to the eventlog as a single event,
            # because multiple bytes might be part of a single utf8 char.
            proc_output = []
            proc_ready = [proc_fd]
            character_count = 0
            while proc_ready and character_count < 4096:
                # Loop until we have no new data or we have >= 4096 characters
                # processed.
                try:
                    c = self._get_utf8_character(proc_fd)
                    character_count += 1
                except OSError:
                    if proc_output:
                        self.eventlog.write_event({
                            "act": "WRITE",
                            "term": term,
                            "data": six.b("").join(proc_output),
                        })
                    self._handle_close_terminal(term)
                    break
                else:
                    # Buffer it for writing, and forward it
                    # to the corresponding terminal view.
                    proc_output.append(c)
                    os.write(view_fd, c)
                    proc_ready = self.wait_for_data([proc_fd], 0)
            else:
                self.eventlog.write_event({
                    "act": "WRITE",
                    "term": term,
                    "data": six.b("").join(proc_output),
                })

    def _resize_event_thread(self):
        # Check if we have a resize event.
        for _ in iter(self.resize_event.get, None):
            size = get_terminal_size(1)
            for term in self.terminals:
                _unused_1, proc_fd, _unused_2 = self.terminals[term]
                set_terminal_size(proc_fd, size)

    def _read_one_byte(self, fd):
        """Read a single byte, or raise OSError on failure."""
        c = os.read(fd, 1)
        if not c:
            raise OSError
        return c

    def _handle_open_terminal(self, client_sock):
        # Fork a new shell behind a pty.
        proc_pid, proc_fd = forkexec_pty([self.shell])
        # Assign a new id for the terminal.
        # As a special case, the first terminal created when appending to
        # an existing session will re-use the last-known terminal uuid.
        term = None
        if not self.terminals and self.eventlog.events:
            last_event = self.eventlog.events[-1]
            if last_event["act"] == "CLOSE":
                term = last_event.get("term")
        if term is None:
            term = uuid.uuid4().hex
        self.terminals[term] = client_sock, proc_fd, proc_pid
        self.view_fds[client_sock.fileno()] = term
        self.proc_fds[proc_fd] = term
        # Append it to the eventlog.
        # XXX TODO: this assumes all terminals are the same size as mine.
        self.eventlog.write_event({
            "act": "OPEN",
            "term": term,
            "size": get_terminal_size(1)
        })

    def _handle_close_terminal(self, term):
        self.eventlog.write_event({
            "act": "CLOSE",
            "term": term,
        })
        client_sock, proc_fd, proc_pid = self.terminals.pop(term)
        del self.view_fds[client_sock.fileno()]
        del self.proc_fds[proc_fd]
        client_sock.close()
        os.close(proc_fd)

    def _handle_pause(self, duration):
        self.eventlog.write_event({
            "act": "PAUSE",
            "duration": duration,
        })


def join_recorder(sock_path, **kwds):
    return proxy_to_coordinator(sock_path, **kwds)
