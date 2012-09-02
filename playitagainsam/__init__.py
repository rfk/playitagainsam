#  Copyright (c) 2012, Ryan Kelly.
#  All rights reserved; available under the terms of the MIT License.
"""

playitagainsam:  record and replay interactive terminal sessions
================================================================

Playitagainsam is a tool and a corresponding file format for recording
and replaying interactive terminal sessions.  It takes inspiration from
the unix commands "script" and "ttyrec" and the python tool "playerpiano".

Useful features include:

    * ability to replay with fake typing for enhanced "interactivity"
    * ability to replay synchronized output in multiple terminals

It's early days, still kinda buggy and easy to crash.  But I hope this will
be resolved in short order!


Basic Usage
-----------

Run the software using either the included "pias" script, or using the
python module-running syntax of "python -m playitagainsam".

Record a session like this::

    $ pias record <output-file>

This will drop you into a shell and record all the input and output that
occurs during the session.  Once you exit the shell, all activity will be
written into the output file as a JSON document.

Replay a recorded session like this::

    $ pias replay <input-file>

This will start a simulated playback of the original shell.  Press any keys
to type, and hit "enter" when you reach the end of a line.


Extra Features
--------------

It's possible to record activity in several terminals simultaneously as part
of a single session, which can be useful for e.g. demonstrating a server
process in one terminal and a client process in another.  Join a new terminal
to an existing recording session like this::

    $ pias --join record <output-file>

"""

__ver_major__ = 0
__ver_minor__ = 1
__ver_patch__ = 0
__ver_sub__ = ""
__ver_tuple__ = (__ver_major__, __ver_minor__, __ver_patch__, __ver_sub__)

__version__ = "%d.%d.%d%s" % __ver_tuple__


import os
import argparse

from playitagainsam.recorder import Recorder, join_recorder
from playitagainsam.player import Player, join_player
from playitagainsam.eventlog import EventLog
from playitagainsam import util


def main(argv, env=None):
    if env is None:
        env = os.environ

    argv = list(argv)
    if len(argv) == 1 and "PIAS_OPT_COMMAND" in env:
        argv.append(env["PIAS_OPT_COMMAND"])

    default_datafile = env.get("PIAS_OPT_DATAFILE")

    parser = argparse.ArgumentParser()
    parser.add_argument("--join", action="store_true",
                        help="join an existing record/replay session",
                        default=env.get("PIAS_OPT_JOIN", False))
    subparsers = parser.add_subparsers(dest="subcommand", title="subcommands")

    # The "record" command.
    parser_record = subparsers.add_parser("record")
    parser_record.add_argument("datafile",
                               nargs="?" if default_datafile else 1,
                               default=[default_datafile])
    parser_record.add_argument("--shell",
                               help="the shell to execute",
                               default=util.get_default_shell())

    # The "replay" command.
    parser_replay = subparsers.add_parser("replay")
    parser_replay.add_argument("datafile",
                               nargs="?" if default_datafile else 1,
                               default=[default_datafile])
    parser_replay.add_argument("--terminal",
                               help="the terminal program to execute",
                               default=util.get_default_terminal())

    args = parser.parse_args(argv[1:])

    args.datafile = args.datafile[0]
    sock_path = args.datafile + ".sock"
    if os.path.exists(sock_path) and not args.join:
        raise RuntimeError("session already in progress")

    recorder = player = eventlog = None

    try:
        if args.subcommand == "record":
            if not args.join:
                eventlog = EventLog(args.datafile, "w")
                recorder = Recorder(sock_path, eventlog, args.shell)
                recorder.start()
            join_recorder(sock_path)

        elif args.subcommand == "replay":
            if not args.join:
                eventlog = EventLog(args.datafile, "r")
                player = Player(sock_path, eventlog, args.terminal)
                player.start()
            join_player(sock_path)

    finally:
        if eventlog is not None:
            eventlog.close()
        if recorder is not None:
            recorder.wait()
        if player is not None:
            player.wait()
        if os.path.exists(sock_path) and not args.join:
            os.unlink(sock_path)
