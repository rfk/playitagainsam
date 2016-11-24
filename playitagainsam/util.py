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
import fcntl
import array

try:
    import psutil
except ImportError:
    psutil = None

try:
    from subprocess import MAXFD
except ImportError:
    # On Python 3 this is no longer there
    # This is how it was done
    try:
        MAXFD = os.sysconf("SC_OPEN_MAX")
    except:
        MAXFD = 256



class _UNSPECIFIED(object):
    """A unique object for unspecified arguments.

    We use this as the default value of arguments that might profitably take
    an explicit value of None.
    """
    pass


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


def forkexec(argv, env=None):
    """Fork a child process."""
    child_pid = os.fork()
    if child_pid == 0:
        os.closerange(3, MAXFD)
        environ = os.environ.copy()
        if env is not None:
            environ.update(env)
        os.execve(argv[0], argv, environ)
    return child_pid


def forkexec_pty(argv, env=None, size=None):
    """Fork a child process attached to a pty."""
    child_pid, child_fd = pty.fork()
    if child_pid == 0:
        os.closerange(3, MAXFD)
        environ = os.environ.copy()
        if env is not None:
            environ.update(env)
        os.execve(argv[0], argv, environ)
    if size is None:
        try:
            size = get_terminal_size(1)
        except Exception:
            size = (80, 24)
    set_terminal_size(child_fd, size)
    return child_pid, child_fd


def find_executable(filename, environ=None):
    """Find an executable by searching the user's $PATH."""
    if environ is None:
        environ = os.environ
    path = environ.get("PATH", "/usr/local/bin:/usr/bin:/bin").split(":")
    for dirpath in path:
        dirpath = os.path.abspath(dirpath.strip())
        filepath = os.path.normpath(os.path.join(dirpath, filename))
        if os.path.exists(filepath):
            return filepath
    return None


_ANCESTOR_PROCESSES = []


def get_ancestor_processes():
    """Get a list of the executables of all ancestor processes."""
    if not _ANCESTOR_PROCESSES and psutil is not None:
        proc = psutil.Process(os.getpid())
        while proc.parent() is not None:
            try:
                _ANCESTOR_PROCESSES.append(proc.parent().exe())
                proc = proc.parent()
            except psutil.Error:
                break
    return _ANCESTOR_PROCESSES


def get_default_shell(environ=None, fallback=_UNSPECIFIED):
    """Get the user's default shell program."""
    if environ is None:
        environ = os.environ
    # If the option is specified in the environment, respect it.
    if "PIAS_OPT_SHELL" in environ:
        return environ["PIAS_OPT_SHELL"]
    # Find all candiate shell programs.
    shells = []
    for filename in (environ.get("SHELL"), "bash", "sh"):
        if filename is not None:
            filepath = find_executable(filename, environ)
            if filepath is not None:
                shells.append(filepath)
    # If one of them is an ancestor process, use that.
    for ancestor in get_ancestor_processes():
        if ancestor in shells:
            return ancestor
    # Otherwise use the first option that we found.
    for shell in shells:
        return shell
    # Use an explicit fallback option if given.
    if fallback is not _UNSPECIFIED:
        return fallback
    raise ValueError("Could not find a shell")


def get_default_terminal(environ=None, fallback=_UNSPECIFIED):
    """Get the user's default terminal program."""
    if environ is None:
        environ = os.environ
    # If the option is specified in the environment, respect it.
    if "PIAS_OPT_TERMINAL" in environ:
        return environ["PIAS_OPT_TERMINAL"]
    # Find all candiate terminal programs.
    terminals = []
    colorterm = environ.get("COLORTERM")
    for filename in (colorterm, "gnome-terminal", "konsole", "xterm"):
        if filename is not None:
            filepath = find_executable(filename, environ)
            if filepath is not None:
                terminals.append(filepath)
    # If one of them is an ancestor process, use that.
    for ancestor in get_ancestor_processes():
        if ancestor in terminals:
            return ancestor
    # Otherwise use the first option that we found.
    for term in terminals:
        return term
    # Use an explicit fallback option if given.
    if fallback is not _UNSPECIFIED:
        return fallback
    raise ValueError("Could not find a terminal")


def get_pias_script(environ=None):
    """Get the path to the playitagainsam command-line script."""
    if os.path.basename(sys.argv[0]) == "pias":
        return sys.argv[0]
    filepath = find_executable("pias", environ)
    if filepath is not None:
        return filepath
    filepath = os.path.join(os.path.dirname(__file__), "__main__.py")
    # XXX TODO: check if executable
    if os.path.exists(filepath):
        return filepath
    raise RuntimeError("Could not locate the pias script.")


def get_terminal_size(fd):
    """Get the (width, height) size tuple for the given pty fd."""
    sizebuf = array.array('h', [0, 0])
    fcntl.ioctl(fd, termios.TIOCGWINSZ, sizebuf, True)
    return tuple(reversed(sizebuf))


def set_terminal_size(fd, size):
    """Set the (width, height) size tuple for the given pty fd."""
    sizebuf = array.array('h', reversed(size))
    fcntl.ioctl(fd, termios.TIOCSWINSZ, sizebuf)
