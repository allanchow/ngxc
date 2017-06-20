# -*- coding: utf-8 -*-

import collections
import enum
from typing import Any, Union, Tuple, Dict

from .base import _CustomMap, OrderedSet, MergeDirection


class MergeMapType(enum.IntEnum):
    AsString = 1
    AsMap = 2


class MergedMap(_CustomMap):

    def __merge(self, key: str, value: Any, merge: MergeMapType, mdir: MergeDirection=MergeDirection.After) -> None:
        ''' The merged value appends at the end '''
        if value:
            rtn_val = value
            if key in self:
                rtn_val = self[key]
                if merge == MergeMapType.AsMap:
                    if isinstance(rtn_val, OrderedSet):
                        rtn_val = rtn_val | value if mdir == MergeDirection.After else value | rtn_val
                    else:
                        rtn_val = OrderedSet([rtn_val, value] if mdir == MergeDirection.After else [value, rtn_val])
                else:
                    rtn_val = '%s %s' % (rtn_val, value)
            self[key] = rtn_val
    # def merge(self, *args:Union[Any, Dict[str,Any], MergedMap], **kwds:Any) -> None:

    def merge(self, *args: Union[Tuple[str, Any], Dict[str, Any], 'MergedMap'], **kwargs: Any) -> None:
        if not args:
            raise TypeError("descriptor 'merge' of 'MutableMapping' object "
                            "needs an argument")
        mt = kwargs.pop('merge', MergeMapType.AsMap)
        if len(args) > 1:
            raise TypeError('merge expected at most 1 arguments, got %d' %
                            len(args))
        if args is not None:
            other = args[0]
            if isinstance(other, collections.Mapping):
                for key in other:
                    self.__merge(key, other[key], mt)
            # elif hasattr(other, "keys"):
            #     for key in other.keys():
            #         self.__merge(key, other[key], mt)
            else:
                for key, value in other:
                    self.__merge(key, value, mt)

        for key, value in kwargs.items():
            self.__merge(key, value, mt)
