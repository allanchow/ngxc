# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractmethod
import tarfile
import logging
from typing import Tuple, Generator, Optional, Union, Dict, List, Set, TypeVar, Any
import sys

from .buildunit import BuildUnit, State, Scope, Stage
from .yaml import YamlMap, YamlKey, YamlKeyType
from .utils import catch, download, untar
from .environment import Environment
from .gitw import GitUtil, GitClean
from .command import Command
from .map import MergedMap
from .base import OrderedSet

TPkg = TypeVar('TPkg', bound='Package')

class Package(BuildUnit, metaclass=ABCMeta):

    def __init__(self, node: YamlMap, stage: int=Stage.All) -> None:
        super().__init__(node, stage)

        self._name = node.get('name')

        # with catch(AttributeError, default=State.INACTIVE) as __status:
        #     __status = State(node.get('status', default=State.ACTIVE, key=YamlKey.Optional))
        # self.status = __status
        self.status = State(node.get('status', default=State.INACTIVE, key=YamlKey.Optional))
        self._raw_requires = OrderedSet(node.get('requires', default=[], key=YamlKey.Optional))
        # Resolved dep name from _raw_requires to dep object in Inventory.load
        self.requires = OrderedSet()

    @property
    def name(self) -> str:
        return self._name

    @property
    def build_name(self) -> str:
        return self._name

    def _pre_run(self):
        for dep in self.requires:
            dep._run()


class PackageUpdatable(Package, metaclass=ABCMeta):
    #__slots__ = ('status','repository','branch','tag','last_commit','scope','F')

    def __init__(self, node: YamlMap, stage: int=Stage.All) -> None:
        ''' Precedence: git > url > file '''
        super().__init__(node, stage)
        apt = node.get('apt')
        self.git = apt.get('git', key=YamlKey.Optional, keytype=YamlKeyType.String)
        self.git_submodule = apt.get('git_submodule', default=False, key=YamlKey.Optional, keytype=YamlKeyType.Boolean)
        self.url = apt.get('url', key=YamlKey.Optional, keytype=YamlKeyType.String)
        self.file = apt.get('file', key=YamlKey.Optional, keytype=YamlKeyType.String)
        assert self.git or self.url or self.file, 'Missing source target: %s' % self.name
        self.branch = str(node.get('branch', default='master', key=YamlKey.Optional))
        self.tag = node.get('tag', key=YamlKey.Optional, keytype=YamlKeyType.String)
        self.commit = node.get('commit', key=YamlKey.Optional, keytype=YamlKeyType.String)
        # self._setup      = Setup(node.get('setup', YamlMap(), key=YamlKey.Optional))
        self.__pkg_dirname = ''  # type: str
        self.__updated = False
        self.__gw_var = None    # type: GitClean

    @property
    def __gw(self) -> GitClean:
        if self.__gw_var is None:
            self.__gw_var = GitClean(self.git, '%s/%s' % (self.sourcedir, self.name), branch=self.branch)
        return self.__gw_var

    @property
    def build_name(self) -> str:
        if not self.__pkg_dirname:
            logging.debug('[%s] build_name is undefined. Trigger to its package process' % self.name)
            self.update(force=(not self.__updated))
        return self.__pkg_dirname

    @property
    def is_outdated(self) -> bool:
        if self.git is None:
            return False
        return self.__gw.is_outdated

    def update(self, force: bool=False, tar: bool=False) -> None:
        def from_git() -> str:
            logging.info('%s - %s - %s' % (self.name, self.branch, self.git))
            self.__gw.checkout(commit=self.commit, tag=self.tag, submodule=self.git_submodule)
            committed_date = self.__gw.repo.head.commit.committed_date
            short_sha = self.__gw.repo.head.object.hexsha[:7]
            logging.info('%s - HEAD is now at %s' % (self.__gw.repo.head.reference, short_sha))
            if tar:
                tar_format = '%s-%s-%s' % (self.name, committed_date, short_sha)
                tar_file = '@%s.tar.gz' % tar_format
                with tarfile.open('%s/%s' % (self.sourcedir, tar_file), 'w|gz') as f:
                    logging.info('Tar %s into file %s' % (self.name, tar_file))
                    f.add('.', arcname=tar_format)
                    f.close()
            return '%s-%s-%s' % (self.name, committed_date, short_sha)

        # def from_url() -> str:
        #     f = download(self.url, Environment.source.lib_path)
        #     return untar('%s/%s' % (Environment.source.lib_path, f), clean=True)

        if self.__updated and not force:
            return
        logging.info('Fetching %s' % (self.git or self.url or self.file))

        assert self.sourcedir, 'Empty source dir'
        if self.git:
            _ = from_git()
        else:
            f = download(self.url, self.sourcedir) if self.url else self.file
            _ = untar('%s/%s' % (self.sourcedir, f), dest_path=Environment.buildroot, clean=True)
        self.__pkg_dirname = _

        #lib_abs_path = '%s/%s' % (Environment.source.lib_path, self.name)
        # with pushd(lib_abs_path, create=True):
        #    pkg_dirname = from_git() if self.git else from_url()
        self.__updated = True
        #self.__pkg_dirname = pkg_dirname
