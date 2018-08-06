# -*- coding: utf-8 -*-
"""
Enables general-purpose cache
"""

from __future__ import unicode_literals, print_function

import logging
import os
from collections import defaultdict
from functools import partial, wraps
from time import time

from six import iteritems

_LOG_NAME = __name__
if _LOG_NAME == '__main__':  # pragma: no cover
    _LOG_NAME = os.path.basename(__file__)

LOG = logging.getLogger(_LOG_NAME)


class Cache(object):
    """
    Presents the simple dictionary
    with size limit and hit counter.
    """

    def __init__(self, max_size=10 ** 5, increase=False, do_not_increase_after=10 ** 6):
        """
        :param max_size: maximum number of items that the cache can store
        :param increase: whether to increase the size dynamically when reached the max.
        If you specify the True, the size will simply doubled. If you specify a number,
        the size will be multiplied by that amount.
        :param do_not_increase_after: prevent the cache from growing
        at certain number of items
        """
        self._storage = dict()
        self.init_size = max_size
        self.max_size = max_size
        self.hits = 0
        self.total_queries = 0

        if increase is True:
            increase = 2
        self.increase = increase
        self.do_not_increase_after = do_not_increase_after

    def __len__(self):
        return len(self._storage)

    def _clear(self):
        self._storage.clear()

    def save(self, name, value, **kwargs):
        """Write the value to cache."""

        if len(self) >= self.max_size:
            LOG.warning('Maximum size for cache reached (%s).', self.max_size)

            self._clear()
            self._increase_size()

        self._save(name, value, **kwargs)

    # noinspection PyUnusedLocal
    def _save(self, name, value, **kwargs):
        self._storage[name] = value

    def get(self, name):
        """Get the value from a cache"""

        self.total_queries += 1
        value = self._get(name)

        if value is None:
            return None

        self.hits += 1
        return value

    def _get(self, name):
        return self._storage.get(name)

    def _increase_size(self):
        if self.max_size >= self.do_not_increase_after:
            return

        if self.increase and self.increase > 1:
            new_max = self.max_size * self.increase
            self.max_size = min(new_max, self.do_not_increase_after)
        else:
            LOG.info('Bad increase multiplier: %s', self.increase)

    def delete(self, name):
        """Just drop the value from a cache"""
        return bool(self._storage.pop(name, False))

    @property
    def hit_rate(self):
        """How much queries successfully reached the cache"""
        if not self.total_queries:
            return 0

        return float(self.hits) / self.total_queries


# noinspection SpellCheckingInspection
# https://english.stackexchange.com/a/312087
class ExpirableCache(Cache):
    """
    The cache with limited support for expiration.
    """

    # TODO: make thread to expire objects

    def _save(self, name, value, **kwargs):
        """Optionally you can specify an expiration timeout"""
        _time = kwargs.get('time')
        self._storage[name] = (time(), _time, value)

    def _get(self, name):
        item = self._storage.get(name)

        if item is None:
            return None

        start, _time, value = item
        # expires
        if _time is not None and time() - start > _time:
            self.delete(name)

        return value


class Memoized(object):  # pragma: no cover
    """
    Decorator to cache function results
    """

    def __init__(self, func):
        self.func = func
        self._cache = {}

    def __call__(self, *args, **kwargs):
        key = tuple(args)
        if kwargs:
            key += tuple(iteritems(kwargs))

        try:
            return self._cache[key]
        except KeyError:
            res = self.func(*args, **kwargs)
            self._cache[key] = res
            return res
        except TypeError:
            # non cachable, better to not cache than to blow up entirely
            return self.func(*args, **kwargs)

    def __get__(self, obj, objtype):
        """To support instance methods."""
        return partial(self.__call__, obj)


def memoized_instance(func):
    """
    Decorator to cache function results.
    Can be safely applied to the instance methods.
    """

    func_name = func.__name__

    @wraps(func)
    def wrapper(*args, **kwargs):
        _self = args[0]
        _args = args[1:]

        try:
            cache = _self._memoized[func_name]
        except AttributeError:
            cache = defaultdict(dict)
            _self._memoized = cache

        key = tuple(_args)
        if kwargs:
            key += tuple(iteritems(kwargs))

        try:
            return cache[key]
        except KeyError:
            res = func(*args, **kwargs)
            cache[key] = res
            return res

    return wrapper
