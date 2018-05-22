# -*- coding: utf-8 -*-
"""
Defines various renderers for the game of nonogram
"""

from __future__ import unicode_literals, print_function

import curses
import locale
import logging
import time

from six import string_types
from six.moves import queue

from pynogram.renderer import BaseAsciiRenderer

_LOG_NAME = __name__
LOG = logging.getLogger(_LOG_NAME)

# need for unicode support on PY2 (however pypy2 does not work)
# https://docs.python.org/2/library/curses.html
locale.setlocale(locale.LC_ALL, '')


class StringsPager(object):
    """
    Draws the strings on a curses window.
    The strings are come from the queue and draws on subsequent lines one after another.
    When the specified line (`restart_on`) appears in the queue,
    the drawing restarts from the very beginning.
    Also vertical scrolling is supported.

    Best suitable for fixed-size but constantly changed set of lines (like the gaming board).

    Inspired by https://gist.github.com/claymcleod/b670285f334acd56ad1c
    """

    def __init__(self, window, source_queue, restart_on='\n'):
        self.window = window
        self.source_queue = source_queue
        self.restart_on = restart_on

        self.lines = dict()
        self.row_index = 0

        # the index from which to start drawing (for long pages)
        self.vertical_offset = 0

    @property
    def window_size(self):
        """The (height, width) pair of active window"""
        return self.window.getmaxyx()

    @property
    def window_height(self):
        """The height of active window"""
        return self.window_size[0]

    @property
    def window_width(self):
        """The width of active window"""
        return self.window_size[1]

    def scroll_down(self):
        """Scroll the page down"""

        # we should not hide more than a third of the lines
        # if some spaces are presented below
        allow_to_hide = len(self.lines) / 3

        # we should be able to see the lower edge anyway
        max_offset = max(len(self.lines) - self.window_height, allow_to_hide)

        if self.vertical_offset < max_offset:
            self.vertical_offset += 1
            self.redraw()

    def scroll_up(self):
        """Scroll the page up"""

        # do not allow empty lines at the top
        if self.vertical_offset > 0:
            self.vertical_offset -= 1
            self.redraw()

    @property
    def current_draw_position(self):
        """The y-coordinate to draw next line on"""
        return self.row_index - self.vertical_offset

    def put_line(self, line, y_position=None, x_offset=0):
        """
        Draws the line on the current position
        (if it is within visible area)
        """

        if y_position is None:
            y_position = self.current_draw_position

        height, width = self.window_size
        # only draw if will be visible on a screen
        if 0 <= y_position <= height - 1:
            # to fit in the screen
            line = line[:width - 1]

            if isinstance(line, string_types):
                line = line.encode('UTF-8')

            self.window.addstr(y_position, x_offset, line)

    def move_cursor(self, y_position, x_position):
        if ((0 <= y_position <= self.window_height - 1) and (
                0 <= x_position <= self.window_width - 1)):
            self.window.move(y_position, x_position)

    def line_feed(self, x_cursor_position=0):
        """
        Shift the cursor (and the next line position) one line lower
        """
        self.row_index += 1
        self.move_cursor(self.current_draw_position, x_cursor_position)

    def redraw(self):
        """
        Redraw the whole screen from cached lines
        """
        save_index = self.row_index

        self.row_index = 0
        self.window.clear()
        for _, line in sorted(self.lines.items()):
            self.put_line(line)
            self.line_feed()

        self.row_index = save_index

    def update(self):
        """
        Read from the queue and update the screen if needed
        Return whether the screen was actually updated.
        """

        try:
            line = self.source_queue.get_nowait()
        except queue.Empty:
            return False

        if line == self.restart_on:
            self.window.refresh()
            self.row_index = 0
            return False

        redraw = False
        old_line = self.lines.get(line)
        if old_line != line:
            self.lines[self.row_index] = line
            redraw = True

        if redraw:
            self.put_line(line)

        self.line_feed()
        return redraw

    @classmethod
    def draw(cls, window, source_queue, restart_on='\n'):
        """
        The entry point for a curses.wrapper to start the pager.

        `curses.wrapper(StringsPager.draw, queue)`
        """
        # clear and refresh the screen for a blank canvas
        window.clear()
        window.refresh()
        window.nodelay(True)
        curses.curs_set(False)

        # start colors in curses
        # curses.start_color()
        # curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)

        _self = cls(window, source_queue, restart_on=restart_on)

        # k is the last character pressed
        k = 0
        while k != ord('q'):
            if k == curses.KEY_DOWN:
                _self.scroll_down()
            elif k == curses.KEY_UP:
                _self.scroll_up()

            _self.update()
            # Refresh the screen
            # window.refresh()

            # Wait for next input
            k = window.getch()


class CursesRenderer(BaseAsciiRenderer):
    """
    Hack for renderers to be able to put their strings in queue
    instead of printing them out into stream
    """

    def _print(self, *args):
        for arg in args:
            self.stream.put(arg)

    def render(self):
        # clear the screen before next board
        self._print('\n')
        super(CursesRenderer, self).render()
        # allow the drawing thread to do its job
        time.sleep(0)
