# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractproperty, abstractmethod
import collections
import enum
import os
import sys
import shutil
import logging
import itertools
from typing import Tuple, List, Generator, Optional, Dict, Union

from .base import _BaseObject, OrderedSet, MergeDirection
from .map import MergedMap, MergeMapType
from .command import Command, Patch
from .utils import is_flag, isempty
from .yaml import YamlMap, YamlKey, YamlKeyType
from .environment import Environment
from .err import ErrMsg


class Scope(enum.Enum):
    LOCAL = 'local'
    GLOBAL = 'global'


class State(enum.Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'


class Stage(enum.IntEnum):
    Patch = 1 << 0
    PreBuild = 1 << 1
    BuildScript = 1 << 2
    PostBuild = 1 << 3
    All = Patch | PreBuild | BuildScript | PostBuild


class BuildEnv_Mode(enum.IntEnum):
    UPDATE = 1 << 0
    MERGE = 1 << 1


class BuildEnv(_BaseObject):
    def __init__(self, env: Union[Dict[str, str], MergedMap]=None) -> None:
        self.__curr_env = MergedMap()
        if env is not None:
            self.__curr_env.merge(env, merge=MergeMapType.AsString)
        # print(self.__curr_env)
    @property
    def curr_env(self) -> MergedMap:
        return self.__curr_env

    def update(self, value: Union[Dict[str, str], MergedMap], mode: BuildEnv_Mode=BuildEnv_Mode.UPDATE) -> None:
        if mode == BuildEnv_Mode.UPDATE:
            self.__curr_env.update(value)
        else:
            self.__curr_env.merge(value, merge=MergeMapType.AsString, mdir=MergeDirection.Before)


    # @classproperty
    # def merge(cls, other: BuildEnv):

class Env(_BaseObject):
    def __init__(self, val: collections.MutableMapping) -> None:
        self.__val = val

    def parse(self, cwd: str, env: Union[Dict[str, str], MergedMap]=None) -> Dict[str, str]:
        # NOTE: commands in any stage should be executed in shell, user will do
        # anything like in shell mode, e.g. variable expansion
        return {k:Command('echo %s' % v.strip(), cwd=cwd, shell=True)._run(timeout=5, env=env, stdout=False, log=True).strip() for k, v in self.__val.items()}
        #return {k:Command('sh -c %s' % repr(v.strip()))._runtimeout=5, env=env, stdout=False, log=False).strip() for k, v in self.__val.items()}

class BuildUnit(_BaseObject, metaclass=ABCMeta):

    def is_stage(self, stage: int) -> bool:
        return is_flag(int(stage), self._stage)
    #__slots__ = ('patches', 'pre_run', 'pre_environment', 'post_run', 'post_environemnt', 'configure', 'make')

    def __castTo(self, item: Union[str, dict, YamlMap, collections.MutableMapping]) -> Optional[Union[Command, Env]]:
        if isinstance(item, str):
            # force running command in a shell mode, for evaluating user commands
            #tmp =
            # modify make command, to be run in parallel
            # if tmp.executable.endswith('make'):
            #     mt = ['-j', Environment.num_of_processors] if self.threads_enabled else []
            #     tmp = Command([tmp.executable, *mt, tmp.args])
            return Command(item.strip(), cwd=self.cwd, shell=True)
        elif isinstance(item, (dict, YamlMap, collections.MutableMapping)):
            return Env(item)
        return None

    def __init__(self, node: YamlMap, stage: int=Stage.All) -> None:
        self._compiled = False
        self._build_env = BuildEnv()

        # print(node.name)
        # print(node.branch)
        self.__setup_node = node.get('setup', default=YamlMap(), key=YamlKey.Optional, keytype=YamlKeyType.Map)
        # print(type(node))
        # print('----')
        self.threads_enabled = self.__setup_node.get('threads-enabled', default=True, key=YamlKey.Optional, keytype=YamlKeyType.Boolean)
        self._stage = stage             # type: int
        #self._scripts = self.__getparam(self.__setup_node)
        self._scripts = None
        export_node = node.get('export', default=[], key=YamlKey.Optional, keytype=YamlKeyType.Sequence)
        self._export_env = list(map(self.__castTo, export_node))

    def __getparam(self, node: YamlMap, stage: int=Stage.All) -> Dict[Stage, List[Union[Command, Env]]]:
        #print(self.cwd)
        scripts = collections.OrderedDict([
            (Stage.Patch, []),
            (Stage.PreBuild, []),
            (Stage.BuildScript, []),
            (Stage.PostBuild, [])
        ])

        if is_flag(Stage.Patch, stage):
            _patches = OrderedSet()
            for p in node.get('patches', default=[], key=YamlKey.Optional, keytype=YamlKeyType.Sequence):
                for pf, v in p.items():
                    patchfile = '%s/%s' % (Environment.source.patch_path, pf)
                    assert os.path.exists(patchfile), ErrMsg.FileNotFound.format(patchfile)
                    _patches.add(Patch(patchfile, opts=v, cwd=self.cwd))
            scripts[Stage.Patch] = list(_patches)
            #scripts[Stage.Patch].append(None)

        if is_flag(Stage.PreBuild, stage):
            tmp = node.get('before-script', default=[], key=YamlKey.Optional, keytype=YamlKeyType.Sequence)
            scripts[Stage.PreBuild] = list(map(self.__castTo, tmp))
            # scripts[Stage.PreBuild].append(None)

        if is_flag(Stage.BuildScript, stage):
            tmp = node.get('script', default=[], key=YamlKey.Optional, keytype=YamlKeyType.Sequence)
            scripts[Stage.BuildScript] = list(map(self.__castTo, tmp))
            # scripts[Stage.BuildScript].append(None)

        if is_flag(Stage.PostBuild, stage):
            tmp = node.get('after-script', default=[], key=YamlKey.Optional, keytype=YamlKeyType.Sequence)
            scripts[Stage.PostBuild] = list(map(self.__castTo, tmp))
            # scripts[Stage.PostBuild].append(None)
        #print(scripts[Stage.BuildScript] )
        return scripts

    def merge(self, node: YamlMap, stage: int=Stage.All, mdir: MergeDirection=MergeDirection.After) -> 'BuildUnit':
        if node is None:
            return self
        _scripts = self.__getparam(node, stage)
        self._stage |= stage
        if mdir == MergeDirection.After:
            self._scripts = {s:[*v, *_scripts[s]] for s, v in self.scripts.items()}
        else:
            self._scripts = {s:[*_scripts[s], *v] for s, v in self.scripts.items()}
            #sys.exit()
            # !!!!
            #itertools.takewhile(lambda x: [*_scripts[x[0]], *x[1]] ,self._script.items())

        return self

    def on_stage_enter(self, stage: Stage)-> Generator[Union[Optional[Command], Optional[Env]], None, None]:
        yield from []

    def on_stage(self, stage: Stage, item: Union[Optional[Command], Optional[Env]]) -> Union[Optional[Command], Optional[Env]]:
        pass

    def on_stage_exit(self, stage: Stage) -> Generator[Union[Optional[Command], Optional[Env]], None, None]:
        yield from []

    def __make(self, args: List[str]) -> Command:
        mt = ['-j', Environment.num_of_processors] if self.threads_enabled else []
        return Command(['make', *mt, args], cwd=self.cwd)

    def __gen_commands(self) -> Generator[Tuple[Stage, Union[Optional[Command], Optional[Env]]], None, None]:
        def __on_stage(stage: Stage, item: Union[Optional[Command], Optional[Env]]) -> Union[Optional[Command], Optional[Env]]:
            newitem = self.on_stage(stage, item)
            return item if newitem is None else newitem
        for stage, items in self.scripts.items():
            # print(self.on_stage_enter(stage))
            # print(__on_stage_enter )
            # sys.exit()
            parsed = map(lambda x: __on_stage(stage, x), items)
            for item in itertools.chain(self.on_stage_enter(stage), parsed, self.on_stage_exit(stage)):
            #for item in itertools.chain(parsed):
                if isinstance(item, Command) and item.executable.endswith('make'):
                    item = self.__make(item.args)
                yield (stage, item)
            #
            # __hook = self.stage_enter(stage)
            # if __hook is not None:
            #     for captured in __hook:
            #         yield (stage, captured)
            # for item in items:
            #     if item is None:
            #         # end of stage
            #         __hook = self.stage_exit(stage)
            #         if __hook is not None:
            #             for captured in __hook:
            #                 yield (stage, captured)
            #     else:
            #         __hook = self.on_stage(stage, item)
            #         if __hook is not None:
            #             for captured in __hook:
            #                 if isinstance(captured, Command) and captured.executable.endswith('make'):
            #                     item = self.make(captured.args)
            #                 yield (stage, captured)
            #         if isinstance(item, Command) and item.executable.endswith('make'):
            #             item = self.make(item.args)
            #     yield (stage, item)

    @abstractproperty
    def sourcedir(self) -> str:
        pass

    def _pre_run(self) -> None:
        pass

    def _post_run(self) -> None:
        pass

    def _run(self, env: Union[Dict[str, str], MergedMap]=None) -> None:
        logging.debug("\033[1;31m--------- %s [%s] ---------\033[0m" % (self.name, self._compiled))

        if self._compiled:
            return

        self._pre_run()

        cwd = self.cwd
        if not isempty(self.sourcedir):
            src = '%s/%s/' % (self.sourcedir, self.name)
            if os.path.exists(src) and src != cwd and not os.path.exists(cwd):
                Command(['rsync', '-avH', '--delete', '--quiet', src, cwd])._run()

        # in seq: 1. os env; 2. global environment; 3. self pre-environment; 4. local func env arguments
        self._build_env.update(os.environ.copy(), mode=BuildEnv_Mode.MERGE)
        self._build_env.update(Environment.global_env, mode=BuildEnv_Mode.MERGE)
        if env is not None:
            self._build_env.update(env, mode=BuildEnv_Mode.MERGE)
        #use_env.merge(self._pre_environment, merge=MergeMapType.AsString)
        #use_env.merge(Environment.global_env, merge=MergeMapType.AsString)

        #use_env.merge(os.environ.copy(), merge=MergeMapType.AsString)

        def sticky_env() -> None:
            self._build_env.update({'PREFIX': Environment.working.prefix})

        def func(stage :Stage, item :Union[Command, Env]) -> None:
            use_env = self._build_env.curr_env
            # Each command is run in a clean isolated environment, and
            # their enviroment is only updated by explicitly user-defined env
            if isinstance(item, Command):
                if stage == Stage.BuildScript:
                    #logging.debug('> Current Directory: %s' % os.path.abspath(cwd))
                    #logging.debug('Command [shell=%s, dry_run=%s]: %s' % (c.shell, self.dry_run, str(c)))
                    if use_env is not None:
                        logging.debug('> CFLAGS: %s' % use_env.get('CFLAGS'))
                        logging.debug('> LDFLAGS: %s' % use_env.get('LDFLAGS'))
                item._run(env=use_env, dry_run=Environment._dry_run)
            elif type(item) is Env:
                val = item.parse(cwd=cwd, env=use_env)
                logging.debug('> Update Current Unit Env by: %s' % val)
                self._build_env.update(val, mode=BuildEnv_Mode.MERGE)

            sticky_env()

        for stage, item in itertools.filterfalse(lambda x: x[1] is None, self.__gen_commands()):
            if stage == Stage.BuildScript:
                print(item.cwd)
            sticky_env()
            logging.debug('"\033[1;34m [%s] \033[0m" PREFIX: %s' % (stage, self._build_env.curr_env.get('PREFIX')))
            func(stage, item)

        for env in self._export_env:
            val = env.parse(cwd=cwd, env=self._build_env.curr_env)
            self._build_env.update(val)
            Environment.global_env.update(val)

        self._compiled = True

        self._post_run()

    @property
    def scripts(self) -> Dict[Stage, List[Union[Command, Env]]]:
        if self._scripts is None and self.__setup_node is not None:
            self._scripts = self.__getparam(self.__setup_node)
        return self._scripts

    @property
    def is_compiled(self) -> bool:
        return self._compiled

    @property
    def cwd(self) -> str:
        return '%s/%s' % (Environment.buildroot, self.build_name)

    @abstractproperty
    def name(self) -> str:
        pass

    @abstractproperty
    def build_name(self) -> str:
        pass
