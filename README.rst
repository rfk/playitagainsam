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
