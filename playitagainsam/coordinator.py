#  Copyright (c) 2012, Ryan Kelly.
#  All rights reserved; available under the terms of the MIT License.
"""

playitagainsam.coordinator:  object for coordinating simulated terminals
========================================================================

This module provides a base class that can be used to coordinate input/output
for one or more simulated terminals.  Each terminal is associated with a
"view" process that handles input and output.

"""

import os
import sys
import select
import socket
import threading

from playitagainsam.util import get_fd, no_echo


class StopCoordinator(Exception):
    """Exception raised to stop execution of the coordinator."""
    pass


class SocketCoordinator(object):
    """Object for coordinating activity between views and data processes."""

    def __init__(self, sock_path):
        self.__running = False
        self.__run_thread = None
        self.__ping_pipe_r, self.__ping_pipe_w = os.pipe()
        self.sock_path = sock_path
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(sock_path)
        self.sock.listen(1)

    def __del__(self):
        self.__cleanup_pipes()

    def __cleanup_pipes(self, os=os):
        if self.__ping_pipe_r is not None:
            os.close(self.__ping_pipe_r)
            self.__ping_pipe_r = None
        if self.__ping_pipe_w is not None:
            os.close(self.__ping_pipe_w)
            self.__ping_pipe_w = None

    def start(self):
        assert self.__run_thread is None
        self.__running = True

        def runit():
            try:
                self.run()
            except StopCoordinator:
                pass
            finally:
                self.cleanup()

        self.__run_thread = threading.Thread(target=runit)
        self.__run_thread.start()

    def stop(self):
        assert self.__run_thread is not None
        self.__running = False
        os.write(self.__ping_pipe_w, "X")

    def wait(self):
        self.__run_thread.join()

    def run(self):
        raise NotImplementedError

    def cleanup(self):
        pass

    def wait_for_data(self, fds, timeout=None):
        fds = [self.__ping_pipe_r] + list(fds)
        try:
            ready, _, _ = select.select(fds, [], fds, timeout)
            if not self.__running:
                raise StopCoordinator
            return ready
        except OSError:
            return []


def proxy_to_coordinator(socket_path, header=None, stdin=None, stdout=None):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(socket_path)
    try:
        stdin_fd = get_fd(stdin, sys.stdin)
        stdout_fd = get_fd(stdout, sys.stdout)
        with no_echo(stdin_fd):
            while True:
                ready, _, _ = select.select([stdin_fd, sock], [], [])
                if stdin_fd in ready:
                    c = os.read(stdin_fd, 1)
                    if c:
                        sock.send(c)
                if sock in ready:
                    try:
                        c = sock.recv(1024)
                    except socket.error as e:
                        break
                    if not c:
                        break
                    os.write(stdout_fd, c)
    finally:
        sock.close()
