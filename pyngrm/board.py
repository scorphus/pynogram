# -*- coding: utf-8 -*

from __future__ import unicode_literals, print_function

import logging
import os
import sys

from six import string_types, integer_types, text_type

from pyngrm.utils import pad_list

_log_name = __name__
if _log_name == '__main__':  # pragma: no cover
    _log_name = os.path.basename(__file__)

log = logging.getLogger(_log_name)


class CellState(object):
    NOT_SET = None
    THUMBNAIL = 'T'
    UNSURE = 'U'
    BOX = 'B'
    SPACE = 'S'


class Renderer(object):
    def __init__(self, board=None):
        self.board = board

        self.cells = None
        self.board_width, self.board_height = None, None

        self.init()

    def init(self, board=None):
        board = board or self.board
        if board:
            log.info("Init '%s' renderer with board '%s'",
                     self.__class__.__name__, board)
            self.board = board
            self.board_width, self.board_height = board.full_size
        return board

    def render(self):
        raise NotImplementedError()

    def draw_thumbnail_area(self):
        return self

    def draw_clues(self, horizontal=None):
        if horizontal is None:
            self.draw_clues(True)
            self.draw_clues(False)
        elif horizontal is True:
            self.draw_horizontal_clues()
        else:
            self.draw_vertical_clues()
        return self

    def draw_grid(self):
        return self

    def draw_horizontal_clues(self):
        return self

    def draw_vertical_clues(self):
        return self


class BaseBoard(object):
    def __init__(self, rows, columns, renderer=Renderer):
        self.rows = self._normalize(rows)
        self.columns = self._normalize(columns)

        self.renderer = renderer
        if isinstance(self.renderer, type):
            self.renderer = self.renderer(self)
        elif isinstance(self.renderer, Renderer):
            self.renderer.init(self)
        else:
            raise TypeError('Bad renderer: %s' % renderer)

        self.cells = [[CellState.UNSURE] * self.width for _ in range(self.height)]
        self.validate()

    @classmethod
    def _normalize(cls, rows):
        res = []
        for r in rows:
            if not r:  # None, 0, '', [], ()
                r = ()
            elif isinstance(r, (tuple, list)):
                r = tuple(r)
            elif isinstance(r, integer_types):
                r = (r,)
            elif isinstance(r, string_types):
                r = tuple(map(int, r.split(' ')))
            else:
                raise ValueError('Bad row: %s' % r)
            res.append(r)
        return tuple(res)

    @property
    def width(self):
        return len(self.columns)

    @property
    def height(self):
        return len(self.rows)

    def validate(self):
        self.validate_headers(self.rows, self.width)
        self.validate_headers(self.columns, self.height)

        boxes_in_rows = sum(sum(block) for block in self.rows)
        boxes_in_columns = sum(sum(block) for block in self.columns)
        if boxes_in_rows != boxes_in_columns:
            raise ValueError('Number of boxes differs: {} (rows) and {} (columns)'.format(
                boxes_in_rows, boxes_in_columns))

    @classmethod
    def validate_headers(cls, rows, max_size):
        for row in rows:
            need_cells = sum(row)
            if row:
                # also need at least one space between every two blocks
                need_cells += len(row) - 1

            log.debug('Row: %s; Need: %s; Available: %s.',
                      row, need_cells, max_size)
            if need_cells > max_size:
                raise ValueError('Cannot allocate row {} in just {} cells'.format(
                    list(row), max_size))

    @property
    def full_size(self):
        return (
            self.headers_width + self.width,
            self.headers_height + self.height)

    def draw(self):
        self.renderer.draw_thumbnail_area() \
            .draw_clues() \
            .draw_grid() \
            .render()

    @property
    def headers_height(self):
        return max(map(len, self.columns))

    @property
    def headers_width(self):
        return max(map(len, self.rows))

    def __repr__(self):
        return '{}({}x{})'.format(self.__class__.__name__, self.height, self.width)


class StreamRenderer(Renderer):
    def __init__(self, board=None, stream=sys.stdout):
        super(StreamRenderer, self).__init__(board)
        self.stream = stream

    def init(self, board=None):
        if super(StreamRenderer, self).init(board):
            log.info('init cells: %sx%s', self.board_width, self.board_height)
            self.cells = [[self.cell_icon(CellState.NOT_SET)] * self.board_width
                          for _ in range(self.board_height)]

    def render(self):
        for row in self.cells:
            print(' '.join(self.cell_icon(cell) for cell in row), file=self.stream)

    def draw_thumbnail_area(self):
        for i in range(self.board.headers_height):
            for j in range(self.board.headers_width):
                self.cells[i][j] = CellState.THUMBNAIL
        return super(StreamRenderer, self).draw_thumbnail_area()

    def draw_horizontal_clues(self):
        for i, row in enumerate(self.board.rows):
            rend_i = i + self.board.headers_height
            # row = list(row)
            if not row:
                row = [0]
            rend_row = pad_list(row, self.board.headers_width, CellState.NOT_SET)
            self.cells[rend_i][:self.board.headers_width] = rend_row

        return super(StreamRenderer, self).draw_horizontal_clues()

    def draw_vertical_clues(self):
        for j, col in enumerate(self.board.columns):
            rend_j = j + self.board.headers_width
            if not col:
                col = [0]
            rend_row = pad_list(col, self.board.headers_height, CellState.NOT_SET)
            # self.cells[:self.board._headers_width][rend_j] = map(text_type, rend_row)
            for rend_i, cell in enumerate(rend_row):
                self.cells[rend_i][rend_j] = cell

        return super(StreamRenderer, self).draw_vertical_clues()

    def draw_grid(self):
        for i, row in enumerate(self.board.cells):
            rend_i = i + self.board.headers_height
            for j, cell in enumerate(row):
                rend_j = j + self.board.headers_width
                self.cells[rend_i][rend_j] = cell

        return super(StreamRenderer, self).draw_grid()

    ICONS = {
        CellState.NOT_SET: ' ',
        CellState.THUMBNAIL: 't',
        CellState.UNSURE: '_',
        CellState.BOX: 'X',
        CellState.SPACE: '.',
    }

    @classmethod
    def cell_icon(cls, state):
        try:
            return cls.ICONS[state]
        except KeyError:
            if isinstance(state, integer_types):
                return text_type(state)
            raise


class ConsoleBoard(BaseBoard):
    def __init__(self, rows, columns, renderer=StreamRenderer):
        super(ConsoleBoard, self).__init__(
            rows, columns, renderer=renderer)


class GameBoard(BaseBoard):
    pass
    # def init_screen(self):
    #     # http://programarcadegames.com/index.php?chapter=introduction_to_graphics
    #     import pygame
    #     pygame.init()
    #     size = (700, 500)
    #     pygame.display.set_mode(size)
    #     pygame.display.set_caption('The Great Game')
