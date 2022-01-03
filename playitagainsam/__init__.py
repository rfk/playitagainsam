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

    $ pias play <input-file>

This will start a simulated playback of the original shell.  Press any keys
to type, and hit "enter" when you reach the end of a line.


Extra Features
--------------

Playitagainsam has some extra features that distinguish it from similar
solutions.


Multiple Terminals
~~~~~~~~~~~~~~~~~~

It's possible to record activity in several terminals simultaneously as part
of a single session, which can be useful for e.g. demonstrating a server
process in one terminal and a client process in another.  Join a new terminal
to an existing recording session like this::

    $ pias --join record <output-file>


Choice of Manual or Automated Typing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While the default playback mode assumes interactive typing, it is also possible
to have pias type automatically for you.  You can have it enter individual
commands but wait for you to manually trigger each newline like this::

    $ pias play <input-file> --auto-type

Or you can have it automatically type all input like this::

    $ pias play <input-file> --auto-type --auto-waypoint

These options both accept an integer millisecond value which will control the
speed of the automated typing.


Canned Replay or Live Replay?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The default playback mode outputs back the 'canned' output text from the
original terminal session(s), without any side effects.  However, the side 
effects might be desirable during the presentation. 

For instance, when demoing a REST API, the presenter might want to show the 
effects of the API calls on a service using a browser.  Or the demoed code 
could drive some other non-console output, like a visualisation or a game. 

The --live-replay option connects the prerecorded input to a live shell for
actual live output and side effects:

    $ pias play <input-file> --live-replay

This option is composable with the previous ones:

    $ pias play <input-file> --live-replay --auto-type --auto-waypoint

Live replay also works two or more joined terminal sessions.


JavaScript Player
~~~~~~~~~~~~~~~~~

There is a javascript-based player that can be used to embed a recorded session
into a HTML document.  This is useful for websites or HTML-based presentations.
The code is here:

    https://github.com/rfk/playitagainsam-js/

And an example presentation using this code is at:

    https://github.com/rfk/talk-webapitesting/


Gotchas
-------

Getting this all running just right can be tricky business!  Here's some thing
that you should be aware of:

  * All terminals should be using utf8 encoding, or you'll see strange output
    and probably some outright errors.

  * All terminals in a session should be the same size.  This restriction
    may go away in the future.

  * The live-replay option has its own particularities:

    * Sessions created with the --append switch won't continue after the first
      recording session ends.

    * Sometimes keypresses "bounce", and double characters get inserted.

    * Some live-replay output sequences lasting longer than the corresponding
      output in the recording session can get buffered waiting for the next 
      user action.

"""

__ver_major__ = 0
__ver_minor__ = 6
__ver_patch__ = 0
__ver_sub__ = ""
__ver_tuple__ = (__ver_major__, __ver_minor__, __ver_patch__, __ver_sub__)

__version__ = "%d.%d.%d%s" % __ver_tuple__


import os
import sys
import argparse

from playitagainsam.recorder import Recorder, join_recorder
from playitagainsam.player import Player, join_player
from playitagainsam.eventlog import EventLog
from playitagainsam import util


def main(argv, env=None):
    if env is None:
        env = os.environ

    # Some default values for our options are taken from the environment.
    # This allows the player to spawn copies of itself without having to
    # pass command-line options, which can be awkward or impossible depending
    # on the terminal program in use.
    argv = list(argv)
    if len(argv) == 1 and "PIAS_OPT_COMMAND" in env:
        argv.append(env["PIAS_OPT_COMMAND"])

    default_datafile = env.get("PIAS_OPT_DATAFILE")

    parser = argparse.ArgumentParser()
    parser.add_argument("--join", action="store_true",
                        help="join an existing record/replay session",
                        default=env.get("PIAS_OPT_JOIN", False))
    parser.add_argument("--shell",
                        help="the shell to execute when recording or live-replaying",
                        default=util.get_default_shell(fallback=None))
    subparsers = parser.add_subparsers(dest="subcommand", title="subcommands")

    # The "record" command.
    parser_record = subparsers.add_parser("record")
    parser_record.add_argument("datafile",
                               nargs="?" if default_datafile else 1,
                               default=[default_datafile])
    datafile_opts = parser_record.add_mutually_exclusive_group()
    datafile_opts.add_argument("--append", action="store_true",
                               help="append to an existing session file",
                               default=False)
    datafile_opts.add_argument("-f", "--overwrite", action="store_true",
                               help="overwrite an existing session file",
                               default=False)

    # The "play" command.
    parser_play = subparsers.add_parser("play")
    parser_play.add_argument("datafile",
                             nargs="?" if default_datafile else 1,
                             default=[default_datafile])
    parser_play.add_argument("--terminal",
                             help="the terminal program to execute",
                             default=util.get_default_terminal(fallback=None))
    parser_play.add_argument("--auto-type", type=int, nargs="?", const=100,
                             help="automatically type at this speed in ms",
                             default=False)
    parser_play.add_argument("--auto-waypoint", type=int, nargs="?", const=600,
                             help="auto type newlines at this speed in ms",
                             default=False)
    parser_play.add_argument("--live-replay", action="store_true",
                             help="recorded input is passed to a live session, and recorded output is ignored",
                             default=False)

    # The "replay" alias for the "play" command.
    # Python2.7 argparse doesn't seem to have proper support for aliases.
    subparsers.add_parser("replay", parents=(parser_play,),
                          conflict_handler="resolve")

    # Parse the arguments and do some addition sanity-checking.
    args = parser.parse_args(argv[1:])
    if not args.subcommand:
        parser.error("too few arguments")

    args.datafile = args.datafile[0]
    sock_path = args.datafile + ".pias-session.sock"

    def err(msg, *args):
        if args:
            msg = msg % args
        sys.stderr.write(msg + '\n')

    if os.path.exists(sock_path) and not args.join:
        err("Error: a recording session is already in progress.")
        err("You can:")
        err(" * use --join to join the session as a new terminal.")
        err(" * remove the file %r to clean up a dead session.", sock_path)
        return 1

    if not os.path.exists(sock_path) and args.join:
        err("Error: no recording session is currently in progress.")
        err("Execute without --join to begin a new session.")
        return 1

    if args.subcommand == "record" and os.path.exists(args.datafile):
        if not args.join and not args.append and not args.overwrite:
            err("Error: the recording data file already exists.")
            err("You can:")
            err(" * use --append to add data to an existing recording.")
            err(" * use --overwrite to overwrite an existing recording.")
            err(" * manually remove the file %r.", args.datafile)
            return 1

    if args.subcommand == "record" and not os.path.exists(args.datafile):
        if not args.join and args.append:
            err("Error: the recording data file does not exist.")
            err("Execute without --append to begin a new recording.")
            return 1

    # Now we can dispatch to the appropriate command.

    recorder = player = eventlog = None

    try:
        if args.subcommand == "record":
            if not args.join:
                eventlog = EventLog(args.datafile, "a" if args.append else "w", args.shell)
                recorder = Recorder(sock_path, eventlog, args.shell)
                recorder.start()
            join_recorder(sock_path)

        elif args.subcommand in ("play", "replay"):
            if not args.join:
                eventlog = EventLog(args.datafile, "r", args.shell, live_replay=args.live_replay)
                shell = args.shell or eventlog.shell 
                player = Player(sock_path, eventlog, args.terminal, 
                                args.auto_type, args.auto_waypoint, 
                                args.live_replay, args.shell)
                player.start()
            join_player(sock_path)

        else:
            raise RuntimeError("Unknown command %r" % (args.subcommand,))

    finally:
        if eventlog is not None:
            eventlog.close()
        if recorder is not None:
            recorder.wait()
        if player is not None:
            player.wait()
        if os.path.exists(sock_path) and not args.join:
            os.unlink(sock_path)
