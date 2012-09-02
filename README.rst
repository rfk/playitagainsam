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

