#  Copyright (c) 2012, Ryan Kelly.
#  All rights reserved; available under the terms of the MIT License.
"""

playitagainsam.eventlog:  event reader/writer for playitagainsam
================================================================

"""

import os
import json

from tempfile import NamedTemporaryFile

import six

from playitagainsam.util import get_default_shell


class EventLog(object):

    def __init__(self, datafile, mode, shell, live_replay=False):
        self.datafile = datafile
        self.mode = mode
        self.live_replay = live_replay
        self.shell = shell
        if mode == "r" or mode == "a":
            with open(self.datafile, "r") as f:
                data = json.loads(f.read())
            self.events = data["events"]
            # for compatibility with older recorded sessions, 
            # we'll get the default shell if none is in the eventlog
            if live_replay:
                self.shell = self.shell or data.get("shell", None) or get_default_shell()
            self._event_stream = None
        else:
            self.events = []
        self.terminals = set()
        for event in self.events:
            try:
                self.terminals.add(event["term"])
            except KeyError:
                pass

    def close(self):
        if self.mode != "r":
            dirnm, basenm = os.path.split(self.datafile)
            tf = NamedTemporaryFile(prefix=basenm, dir=dirnm, delete=False)
            with tf:
                data = {"events": self.events, "shell": self.shell}
                output = json.dumps(data, indent=2, sort_keys=True)
                tf.write(output.encode("utf8"))
                tf.flush()
                os.rename(tf.name, self.datafile)

    def write_event(self, event):
        # Append an event to the event log.
        # Since we'll be writing JSON, we need to ensure serializability.
        if six.PY3 and "data" in event:
            data = event["data"]
            if isinstance(data, six.binary_type):
                event["data"] = data.decode("utf8")
        # We try to do some basic simplifications.
        # Collapse consecutive "PAUSE" events into a single pause.
        if event["act"] == "PAUSE":
            if self.events and self.events[-1]["act"] == "PAUSE":
                self.events[-1]["duration"] += event["duration"]
                return
        # Try to collapse consecutive IO events on the same terminal.
        if event["act"] == "WRITE" and self.events:
            if self.events[-1].get("term") == event["term"]:
                # Collapse consecutive writes into a single chunk.
                if self.events[-1]["act"] == "WRITE":
                    self.events[-1]["data"] += event["data"]
                    return
                # Collapse read/write of same data into an "ECHO".
                if self.events[-1]["act"] == "READ":
                    if self.events[-1]["data"] == event["data"]:
                        self.events[-1]["act"] = "ECHO"
                        # Collapse consecutive "ECHO" events.
                        if len(self.events) > 1:
                            if self.events[-2]["act"] == "ECHO":
                                if self.events[-2]["term"] == event["term"]:
                                    self.events[-2]["data"] += event["data"]
                                    del self.events[-1]
                        return
        # A CLOSE then OPEN of the same terminal is a no-op.
        if event["act"] == "OPEN" and self.events:
            if self.events[-1]["act"] == "CLOSE":
                if self.events[-1]["term"] == event["term"]:
                    del self.events[-1]
                    return
        # Otherwise, just add it to the list.
        self.events.append(event)

    def read_event(self):
        if self._event_stream is None:
            self._event_stream = self._iter_events()
        try:
            return next(self._event_stream)
        except StopIteration:
            return None

    def _iter_events(self):
        for event in self.events:
            if event["act"] == "ECHO":
                for c in event["data"]:
                    yield {"act": "READ", "term": event["term"], "data": c}
                    if not self.live_replay:
                        yield {"act": "WRITE", "term": event["term"], "data": c}
            elif event["act"] == "READ":
                for c in event["data"]:
                    yield {"act": "READ", "term": event["term"], "data": c}
            elif event["act"] == "WRITE":
                if not self.live_replay:
                    yield event
            else:
                yield event
