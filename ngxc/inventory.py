# -*- coding: utf-8 -*-

import collections
import sys
import itertools
from typing import Dict, List, Any, Set, Generator, Tuple, Optional, Union

from .base import _BaseObject, OrderedSet
from .buildunit import State, Scope, Stage, BuildEnv, Env
from .environment import Environment
from .package import PackageUpdatable, TPkg
from .utils import dict_to_tupleobjarray, classproperty, catch
from .yaml import YamlMap, YamlKey, YamlKeyType
from .command import Command, CommandError
from .map import MergedMap, MergeMapType

class DependencyResolver(object):
    """ update requires attribute to tranform name to corrosponding module / library object """
    __slots__ = ()  # no direct instantiation, so allow immutable subclasses

    @classmethod
    def __deep_resolve(cls, nodelist: Dict[str, TPkg], node: TPkg,
                       resolved: Set[str], unresolved: List[str]) -> None:
        # https://www.electricmonk.nl/log/2008/08/07/dependency-resolving-algorithm/
        """ this will also remove duplicates in the dependency graph """
        if node is None:
            return
        unresolved.append(node.name)
        for req in node.requires:
            if req not in resolved:
                if req in unresolved:
                    raise Exception('Circular reference detected: %s -> %s' % (node.name, req))
                cls.__deep_resolve(nodelist, nodelist.get(req), resolved, unresolved)
        resolved.add(node.name)
        unresolved.remove(node.name)

    @classmethod
    def resolve(cls, _dict: Dict[str, TPkg]) -> List[TPkg]:
        def __func(pkg):
            resolved = OrderedSet()
            cls.__deep_resolve(_dict, pkg, resolved, [])
            try:
                assert pkg.name not in pkg._raw_requires, 'Self-referenced [%s] is illegal' % pkg.name
                pkg.requires = OrderedSet(map(lambda x: _dict[x], pkg._raw_requires))
            except KeyError as e:
                print('Undefined [%s] dependencies in [%s]' % (e, pkg.name))
                sys.exit()
            if pkg.status == State.ACTIVE:
                # print(pkg.name)
                # print(pkg._raw_requires)
                inactive_dep = list(map(lambda x: x.name, itertools.filterfalse(lambda x: x.status == State.ACTIVE, pkg.requires)))
                #inactive_dep = [l.name for l in pkg.requires if l.status != State.ACTIVE]
                assert not inactive_dep, 'An active library/module [%s] should depends on active library/module: %s' % (pkg.name, inactive_dep)
            return _dict
        return list(itertools.takewhile(__func, _dict.values()))


class Inventory(_BaseObject):

    modules = {}       # type: Dict[str, Any]
    libraries = {}     # type: Dict[str, Any]
    _allitems = []     # type: List[TPkg]
    __initialized = False

    class Library(PackageUpdatable):
        def pkgconfig_libs(self) -> str:
            ''' inventory library name will be used to search library in pkg-config '''
            assert self.is_compiled, '[%s] not yet compiled' % self.name
            #rtn = Command('%s %s --libs-only-l %s' % (Environment.pkgconfig, , '--static' if self.static else ''))._run
            try:
                rtn = Command([Environment.pkgconfig, self.name, '--libs-only-l', '--static' if self.static else ''])._run(
                    stdout=False,
                    env={
                        'PKG_CONFIG_PATH': '%s/pkgconfig' % Environment.working.lib_path,
                    },
                    timeout=15,
                    dry_run=Environment._dry_run
                )
            except CommandError:
                rtn = ''
            return rtn.strip() if rtn else ''

        def __init__(self, node: YamlMap) -> None:
            super().__init__(node)
            # scope = node.get('scope', default=Scope.LOCAL, key=YamlKey.Optional, keytype=YamlKeyType.String)
            # with catch(AttributeError, default=Scope.LOCAL) as __scope:
            #     __scope = Scope(scope)
            # self.scope = __scope
            self.scope = Scope(node.get('scope', default=Scope.LOCAL, key=YamlKey.Optional, keytype=YamlKeyType.String))
            self.static = True
            self.__conf_opts = {
                'prefix': Environment.working.prefix
                #        'includedir'  : Environment.working.inc_path,
                #        'libdir'      : Environment.working.lib_path,
                #                    'bindir'      : '%s/bin'       % Environment.working.prefix,
                #                    'datadir'     : '%s/share'     % Environment.working.prefix,
                #                    'mandir'      : '%s/share/man' % Environment.working.prefix,
                #                    'sysconfdir'  : '%s/etc'       % Environment.working.prefix,
                #                    'sharedlibdir': '%s/share'     % Environment.working.prefix,
            }

        @property
        def sourcedir(self) -> str:
            return Environment.source.lib_path

        def _pre_run(self) -> None:
            self._build_env = BuildEnv(dict(CFLAGS='-fPIC'))

        def _post_run(self) -> None:
            if self.scope == Scope.GLOBAL and not Environment._dry_run:
                Environment.global_env.merge(dict(LDFLAGS=self.pkgconfig_libs()), merge=MergeMapType.AsString)

        def on_stage(self, stage: Stage, item: Union[Optional[Command], Optional[Env]]) -> Union[Optional[Command], Optional[Env]]:
            # if s == Stage.BuildScript and c and (c.cmd.endswith('configure') or c.cmd.endswith('autogen.sh')):
            if not (
                    stage == Stage.BuildScript and
                    isinstance(item, Command) and
                    any([bool(item.executable.endswith(cmd)) for cmd in ['configure', 'autogen.sh']])
                ):
                return None

            #c = Command([c.cmd, *['--%s=%s' % (k, v) for k, v in conf_opts.items()], c.args])
            conf_opts_cmd = list(map(lambda x: '--%s' % x[0] if isinstance(x[1], bool) and x[1] else '--%s=%s' % (x[0], x[1]), self.__conf_opts.items()))
            if self.static:
                cmd = Command([item.executable, *conf_opts_cmd + ['--enable-static'], item.args],
                              cwd=item.cwd, shell=False, rescue_commandline=[item.executable, *conf_opts_cmd, item.args])
            else:
                cmd = Command([item.executable, *conf_opts_cmd, item.args], cwd=item.cwd, shell=item.shell)
            return cmd

    class Module(PackageUpdatable):
        def __init__(self, node: YamlMap) -> None:
            super().__init__(node, Stage.Patch | Stage.PreBuild | Stage.PostBuild)
            self.dynamic = node.get('dynamic', default=True, key=YamlKey.Optional, YamlKeyType=YamlKeyType.Boolean)

        @property
        def sourcedir(self) -> str:
            return Environment.source.modules_path


    class LuaLibrary(PackageUpdatable):

        def __init__(self, node: YamlMap) -> None:
            super().__init__(node)
            #super().__init__(node, Stage.Patch | Stage.PreBuild | Stage.PostBuild)
            # Add basic dependencies
            self._raw_requires |= OrderedSet(['luajit', 'lua-nginx-module'])

        @property
        def sourcedir(self) -> str:
            return Environment.source.lib_path

        # def on_stage_exit(self, stage: Stage) -> Generator[Union[Optional[Command], Optional[Env]], None, None]:
        #     if stage == Stage.BuildScript:
        #         yield Command(['make', 'install'])

    #@classmethod
    # def load(cls, node:YamlMap) -> None

    @classproperty
    def lib_active(cls) -> Dict[str, 'Inventory.Library']:
        return collections.OrderedDict([(_, l) for _, l in cls.libraries.items() if l.status == State.ACTIVE])

    @classproperty
    def lualib_active(cls) -> Dict[str, 'Inventory.LuaLibrary']:
        return collections.OrderedDict([(_, l) for _, l in cls.lua_libraries.items() if l.status == State.ACTIVE])

    @classproperty
    def mod_active(cls) -> Dict[str, 'Inventory.Module']:
        return collections.OrderedDict([(_, m) for _, m in cls.modules.items() if m.status == State.ACTIVE])

    @classmethod
    def load(cls, node: YamlMap) -> None:
        if cls.__initialized:
            return
        lib = collections.OrderedDict()         # type: Dict[str, TPkg]
        lualib = collections.OrderedDict()      # type: Dict[str, TPkg]
        mod = collections.OrderedDict()         # type: Dict[str, TPkg]
        _ = node.get('library', key=YamlKey.Optional)
        if _:
            lib = collections.OrderedDict(dict_to_tupleobjarray(Inventory.Library, _))
        _ = node.get('library-lua', key=YamlKey.Optional)
        if _:
            lualib = collections.OrderedDict(dict_to_tupleobjarray(Inventory.LuaLibrary, _))
        _ = node.get('modules', key=YamlKey.Optional)
        if _:
            mod = collections.OrderedDict(dict_to_tupleobjarray(Inventory.Module, _))
        intersect = list(set(lib) & set(lualib) & set(mod))
        assert not intersect, 'Duplicate package in inventory: %s' % intersect

        cls.libraries = lib
        cls.lua_libraries = lualib
        cls.modules = mod
        cls.__initialized = True

        cls._allitems = DependencyResolver.resolve({**cls.lib_active, **cls.lualib_active, **cls.mod_active})

    @classproperty
    def is_initialized(cls) -> bool:
        return cls.__initialized
