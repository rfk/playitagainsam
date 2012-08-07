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

    { act: "OPEN", term: <uuid> }
    { act: "READ", term: <uuid>, data: <data> }
    { act: "WRITE", term: <uuid>, data: <data> }
    { act: "ECHO", term: <uuid>, data: <data> }
    { act: "PAUSE", duration: <duration> }
    { act: "CLOSE", term: <uuid> }

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
import json
import argparse
import threading

import playitagainsam.util
import playitagainsam.recorder


def main(argv):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand")
    # The "record" command.
    parser_record = subparsers.add_parser("record")
    parser_record.add_argument("datafile")
    parser_record.add_argument("--shell",
                               default=os.environ.get("SHELL", "/bin/sh"))
    parser_record.add_argument("--join")
    # The "replay" command.
    parser_replay = subparsers.add_parser("replay")
    parser_replay.add_argument("datafile")
    parser_replay.add_argument("--term")

    args = parser.parse_args(argv[1:])

    if args.subcommand == "record":
        if args.join is None:
            events = playitagainsam.util.EventLog()
            recorder = playitagainsam.recorder.Recorder(events)
            t = threading.Thread(target=recorder.run)
            t.setDaemon(True)
            t.start()
            addr = ("localhost", 12345)
        else:
            addr = args.join.split(":")
            addr = (addr[0], int(addr[1]))
        playitagainsam.recorder.spawn_in_recorder(addr, args.shell)
        if args.join is None:
            t.join()
            with open(args.datafile, "w") as datafile:
                data = {"events": events.events}
                output = json.dumps(data, indent=2, sort_keys=True)
                datafile.write(output)
    elif args.subcommand == "replay":
        raise NotImplementedError
