#  Copyright (c) 2012, Ryan Kelly.
#  All rights reserved; available under the terms of the MIT License.
"""

playitagainsam:  record and replay interactive terminal sessions
================================================================

Playitagainsam is a tool and a corresponding file format for recording
and replating interactive terminal sessions.  It takes inspiration from
the unix commands "script" and "ttyrec" and the python tool "playerpiano".

Useful features include:

    * ability to replay with fake typing
    * ability to replay sessions in multiple terminals

Run the software using either the included "pias" script, or using the
python module-running syntax of "python -m playitagainsam".

Record a session:

    $ pias record

Join an existing recording as a new terminal:

    $ pias record --join addr

Replay a recorded session:

    $ pias replay


Session Log Format
------------------

Sessions are recorded as a JSON file.  The outer JSON object contains metadata
along with an "events" member.  Each event is one of the following types:

    { type: "BEGIN", term: <uuid> }
    { type: "READ", term: <uuid>, data: <data> }
    { type: "WRITE", term: <uuid>, data: <data> }
    { type: "ECHO", term: <uuid>, data: <data> }
    { type: "END", term: <uuid> }

    {
      events: [
      ]
    }

"""

__ver_major__ = 0
__ver_minor__ = 1
__ver_patch__ = 0
__ver_sub__ = ""
__ver_tuple__ = (__ver_major__,__ver_minor__,__ver_patch__,__ver_sub__)
__version__ = "%d.%d.%d%s" % __ver_tuple__


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
    fd = file_or_fd
    if fd is None:
        fd = default
    if hasattr(fd, "fileno"):
        fd = fd.fileno()
    return fd


def record_session(logfile, argv=None, stdin=None, stdout=None):
    # Find the program to execute.  Use the default shell by default.
    if argv is None:
        argv = os.environ.get("SHELL", "/bin/sh")
    if isinstance(argv, basestring):
        argv = [argv]
    # Grab file descriptors for stdin and stdout, we're going to
    # to lots of low-level IO on them.
    stdin_fd = get_fd(stdin, default=sys.stdin)
    stdout_fd = get_fd(stdout, default=sys.stdout)
    # Fork the child with a pty.
    child_pid, child_fd = pty.fork()
    if child_pid == 0:
        os.closerange(3, MAXFD)
        os.execv(argv[0], argv)
    def wait_for_activity():
        ready, _, _ = select.select([child_fd, stdin_fd], [], [])
        return ready
    def read_output():
        output = []
        try:
            ready, _, _ = select.select([child_fd, stdin_fd], [], [])
            while child_fd in ready:
                c = os.read(child_fd, 1)
                if not c:
                    break
                output.append(c)
                os.write(stdout_fd, c)
                ready, _, _ = select.select([child_fd, stdin_fd], [], [], 0)
        finally:
            if output:
                logfile.write("W %s\n" % ("".join(output).encode("string-escape"),))
    def read_keypress():
        c = ""
        ready, _, _ = select.select([child_fd, stdin_fd], [], [])
        if stdin_fd in ready:
            c = os.read(stdin_fd, 1)
            if c:
                logfile.write("R %s\n" % (c.encode("string-escape"),))
                os.write(child_fd, c)
        return c
    # Shuffle data back and forth between our terminal and the pty.
    # Log everything.
    with no_echo(stdin_fd):
        try:
            while True:
                ts1 = time.time()
                ready = wait_for_activity()
                ts2 = time.time()
                if stdin_fd in ready:
                    read_keypress()
                    read_output()
                else:
                    logfile.write("P %.6f\n" % (ts2 - ts1,))
                    read_output()
        except EnvironmentError:
            pass


def replay_session(logfile, stdin=None, stdout=None):
    # Grab file descriptors for stdin and stdout, we're going to
    # to lots of low-level IO on them.
    stdin_fd = get_fd(stdin, default=sys.stdin)
    stdout_fd = get_fd(stdout, default=sys.stdout)
    # Replay the session, controlling timing from keyboard.
    with no_echo(stdin):
        try:
            while True:
                ln = logfile.readline()
                if not ln:
                    break
                act = ln[0]
                data = ln[2:-1].decode("string-escape")
                if act == "P":
                    time.sleep(float(data))
                elif act == "W":
                    os.write(stdout_fd, data)
                elif act == "R":
                    c = os.read(stdin_fd, 1)
                    if data in ("\n", "\r"):
                        while c not in ("\n", "\r"):
                            c = os.read(stdin_fd, 1)
            c = os.read(stdin_fd, 1)
            while c not in ("\n", "\r"):
                c = os.read(stdin_fd, 1)
        except EnvironmentError:
            pass


if __name__ == "__main__":

    parser = optparse.OptionParser()
    parser.add_option("-f", "--logfile", default="session.log",
                      help="file in which to store the session log",)
    parser.add_option("-c", "--command",
                      help="command to execute (by default, your shell)")

    opts, args = parser.parse_args(sys.argv)

    if args[1] == "record":
        with open(opts.logfile, "w") as logfile:
            record_session(logfile, opts.command)
    elif args[1] == "replay":
        with open(opts.logfile, "r") as logfile:
            replay_session(logfile)
    else:
        raise ValueError("unknown command %r" % (args[1],))
