# -*- coding: utf-8 -*-

import collections
import enum
from abc import ABCMeta
from copy import copy, deepcopy
from typing import Any, Dict, no_type_check


class MergeDirection(enum.IntEnum):
    Before = 1
    After = 2

class Singleton(type):
    _instances = {}  # type: Dict[type, type]

    def __call__(cls, *args: Any, **kwargs: Any) -> type:
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        # else:
            # cls._instances[cls].__init__(*args, **kwargs)
        return cls._instances[cls]

class _BaseObject(object):

    def __repr__(self) -> str:
        d = {}
        try:
            d.update(self.__dict__)
        except AttributeError as e:
            pass
        # try:
        #     d.update({attr: getattr(self, attr) for attr in self.__slots__})
        # except AttributeError:
        #     pass
        return str(d)
    # http://stackoverflow.com/questions/1500718/what-is-the-right-way-to-override-the-copy-deepcopy-operations-on-an-object-in-p/24621200#24621200

    @no_type_check
    def __copy__(self):
        cls = self.__class__
        result = cls.__new__(cls)
        result.__dict__.update(self.__dict__)
        return result

    @no_type_check
    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))
        return result

    def copy(self) -> Any:
        return copy(self)

    def deepcopy(self) -> Any:
        return deepcopy(self)


class _CustomMap(collections.MutableMapping, metaclass=ABCMeta):

    def __init__(self, *args: dict, **kwargs: Any) -> None:
        # hack: update will skip those none-valued keys, use fromkeys to initialize a empty dict first
        self.__dict__ = dict.fromkeys(list(*args))
        self.__dict__.update(*args, **kwargs)

    @no_type_check
    def __setitem__(self, key, value):
        self.__dict__[key] = value

    @no_type_check
    def __getitem__(self, key):
        return self.__dict__[key]

    @no_type_check
    def __delitem__(self, key):
        del self.__dict__[key]

    @no_type_check
    def __iter__(self):
        return iter(self.__dict__)

    @no_type_check
    def __len__(self):
        return len(self.__dict__)
    # The final two methods aren't required, but nice for demo purposes:

    @no_type_check
    def __str__(self):
        '''returns simple dict representation of the mapping'''
        return str(self.__dict__)

    @no_type_check
    def __repr__(self):
        return super().__repr__()

#http://code.activestate.com/recipes/576694/
class OrderedSet(collections.MutableSet):

    def __init__(self, iterable=None) -> None:
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add_notempty(self, key):
        if key:
            self.add(key)

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:
            key, _prev, _next = self.map.pop(key)
            _prev[2] = _next
            _next[1] = _prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, **kwargs):
        kwargs.setdefault('last', True)
        last = kwargs['last']
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
    #if not self:
        return '%s()' % (self.__class__.__name__)
    #return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)
