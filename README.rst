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

Run the software using either the included "pias" script, or using the
python module-running syntax of "python -m playitagainsam".

Record a session:

    $ pias record <output-file>

Join an existing recording as a new terminal:

    $ pias --join record <output-file>

Replay a recorded session:

    $ pias replay <input-file>
