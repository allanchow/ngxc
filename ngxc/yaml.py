# -*- coding: utf-8 -*-

import collections
import enum
from typing import no_type_check, Any, List, Tuple, TypeVar, NamedTuple

from ruamel.yaml import scalarstring

from .base import _CustomMap
from .utils import is_flag

TMap = TypeVar('TMap', 'YamlMap', dict)

class YamlKey(enum.IntEnum):
    Required = 1 << 0
    Optional = 1 << 1


class YamlKeyType(enum.IntEnum):
    Sequence = 1 << 0
    Map = 1 << 1
    Boolean = 1 << 2
    String = 1 << 3
    Auto = Sequence | Map | Boolean | String


class YamlSeq(collections.MutableSequence):

    def __init__(self, _list: List=[]) -> None:
        self.__list__ = _list

    @no_type_check
    def __getitem__(self, index):
        val = self.__list__[index]
        if isinstance(val, dict):
            return YamlMap(val)
        if isinstance(val, list):
            return YamlSeq(val)
        return val

    @no_type_check
    def __setitem__(self, index, value):
        return NotImplemented
        #self.__list__[index] = value

    @no_type_check
    def __delitem__(self, index):
        return NotImplemented
        #del self.__list__[index]

    @no_type_check
    def __len__(self):
        return len(self.__list__)

    @no_type_check
    def insert(self, index, value):
        self.__list__.insert(index, value)

_vm = collections.namedtuple('_vm', ['flag', 'vt', 'cls'])

def _valmap() -> List[_vm]:
    return [
        _vm(flag=YamlKeyType.Map, vt=dict, cls=YamlMap),
        _vm(flag=YamlKeyType.Sequence, vt=list, cls=YamlSeq),
        _vm(flag=YamlKeyType.Boolean, vt=bool, cls=bool),
        _vm(flag=YamlKeyType.String, vt=scalarstring.DoubleQuotedScalarString, cls=scalarstring.DoubleQuotedScalarString),
        _vm(flag=YamlKeyType.String, vt=scalarstring.SingleQuotedScalarString, cls=scalarstring.SingleQuotedScalarString),
        _vm(flag=YamlKeyType.String, vt=str, cls=str),
    ]

class YamlMap(_CustomMap):

    @no_type_check
    def __setitem__(self, key, value):
        return NotImplemented

    @no_type_check
    def __delitem__(self, key):
        return NotImplemented

    @no_type_check
    def __repr__(self):
        '''echoes class, id, & reproducible representation in the REPL'''
        return '{}, YamlMap({})'.format(super().__repr__(), self.__dict__)

    @no_type_check
    def __getitem__(self, key):
        return self.get(key, default=None, key=YamlKey.Required, keytype=YamlKeyType.Auto)

    def exists(self, yaml_key: str) -> bool:
        return yaml_key in self.__dict__

    def get(self, yaml_key: str, **kwargs) -> Any:
        kwargs.setdefault('default', None)
        kwargs.setdefault('key', YamlKey.Required)
        kwargs.setdefault('keytype', YamlKeyType.Auto)

        required = (kwargs['key'] == YamlKey.Required)
        if required:
            assert self.exists(yaml_key), 'Missing required key: %s in %s' % (yaml_key, self.__dict__)
        # has keys but no val, get will return None
        # but this should return default in this situation
        defval = kwargs['default']
        val = self.__dict__.get(yaml_key)
        # val = self.__dict__.get(yaml_key, defval)
        if val is None:
            assert not required, 'Empty value in key: %s in %s' % (yaml_key, self.__dict__)
            return defval
        else:
        # if(yaml_key == 'branch' and val==2.0):
        #     a = self.__a(val, kwargs['keytype'])
        #     print(kwargs['keytype'])
        #     print(type(a))
        #     print(type(str(a)))
            return self.__wrap(val, kwargs['keytype'])

    def __wrap(self, val: Any, keytype: YamlKeyType=YamlKeyType.Auto) -> Any:
        types = [k for k in _valmap() if is_flag(k.flag, keytype)]

        for k in types:
            if isinstance(val, k.vt):
                # print('%s, %s, %s' % (val,type(val), k.vt))
                if k.vt == scalarstring.SingleQuotedScalarString:
                    return "'" + str(val) + "'"
                if k.vt == scalarstring.DoubleQuotedScalarString:
                    return  '"' + str(val) + '"'
                return (k.cls(val) if k.cls else val)

        if keytype != YamlKeyType.Auto:
            assert False, 'Please conform to the scheme: %s' % keytype
        # Reach here if keytype is auto and not match to our transform types
        return val
    # def __wrap(self, val: Any, keytype: YamlKeyType=YamlKeyType.Auto) -> Any:
    #     at = [k for k in _valmap() if is_flag(k.flag, keytype)]
    #     f = [k.flag for k in at]
    #     for k in at:
    #         if isinstance(val, k.vt):
    #             return k.cls(val) if k.cls else val
    #         assert k.flag in f, '%s: %s' % (k.msg, val)
    #     # Reach here if keytype is auto and not match to our transform types
    #     return val
