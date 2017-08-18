# -*- coding: utf-8 -*-

import collections
import logging
import shutil
import os
import subprocess
import sys
import re
import time
import itertools
import functools
from typing import no_type_check, List, Optional, Union, Dict, Tuple, Generator, Iterator, Set, Any

from .base import _BaseObject, OrderedSet
from .buildunit import Scope, State, Stage, MergeDirection, Env
from .command import Command
from .environment import Environment
from .err import ErrMsg
from .inventory import Inventory
from .package import Package, PackageUpdatable
from .map import MergedMap, MergeMapType
from .yaml import YamlMap, YamlKey
from .yamlconfig import YamlConfig
from .utils import ensure, dict_to_tupleobjarray, download, untar, basename, elapsed_timer, catch, pushd, query_yes_no

class Nginx(PackageUpdatable):

    class Options(_BaseObject):

        def __init__(self, ngx_opts: YamlMap, prefix: str='/usr/local/nginx') -> None:
            assert prefix, 'Prefix is required'
            self.prefix = ngx_opts.get('prefix', default=prefix, key=YamlKey.Optional)
            self.sbin = ngx_opts.get('sbin', key=YamlKey.Optional)
            self.modules_path = ngx_opts.get('modules-path', key=YamlKey.Optional)
            self.conf = ngx_opts.get('conf', key=YamlKey.Optional)
            self.http_log = ngx_opts.get('http-log', key=YamlKey.Optional)
            self.error_log = ngx_opts.get('error-log', key=YamlKey.Optional)
            self.pid = ngx_opts.get('pid', key=YamlKey.Optional)
            self.user = ngx_opts.get('user', key=YamlKey.Optional)
            self.group = ngx_opts.get('group', key=YamlKey.Optional)
            self.force_tfo = ngx_opts.get('force_tfo', default=False, key=YamlKey.Optional)
            self.debug = ngx_opts.get('debug', default=False, key=YamlKey.Optional)

    class Library(Inventory.Library):
        #__slots__ = ['reference', 'status']
        #_inventory = None  # type: Inventory

        @no_type_check
        def __new__(cls, node: YamlMap, ngx: 'Nginx'):
            cls._ref = None
            if node.exists('ref'):
                reference = node.get('ref', key=YamlKey.Optional)
                assert reference, 'Defined but empty ref value in %s' % node
                #cls._ref = cls._inventory.libraries[reference]
                cls._ref = Inventory.libraries.get(reference)
                assert cls._ref is not None, 'Undefined reference [%s] is in Nginx libraries' % reference
               #c = cls._inventory.libraries[reference]
                c = super().__new__(cls)
                # c = Nginx.Library.__base__.__new__(cls)
                # print(c.__dict__)
                # print(c._ref.__dict__)
                #c.__dict__.update(cls._ref.__dict__.copy())
                c.__dict__.update(cls._ref.__dict__)
                # print(type(c))
                #c.__class__ = cls
                return c

        def __init__(self, node: YamlMap, ngx: 'Nginx') -> None:
            # NOTE: merge the existing setup defined in the inventory
            # print(node)
            # print(self._pre_run()
            self.__ngx = ngx
            # Rebuild the following attributes as they are overwritten by __new__
            self._name = node.get('name')
            self.__cwd = self._ref.cwd
            self._scripts = self.scripts.copy()

            node = node.get('setup', default=YamlMap(), key=YamlKey.Optional)

            # NOTE: local before-script actions relative to nginx
            if node:
                stage = Stage.Patch | Stage.PreBuild | Stage.PostBuild
                self.__cwd = '%s/%s' % (Environment.buildroot, ngx.build_name)
                self.merge(node, stage, MergeDirection.Before)
                self.__cwd = self._ref.cwd
                self._ref._scripts = self.scripts

        def _run(self, env: Union[Dict[str, str], MergedMap]=None) -> None:
            self._ref._run(env)

        @property
        def cwd(self) -> str:
            return self.__cwd

        @property
        def is_compiled(self) -> bool:
            return self._ref._compiled

    class UserModule(Inventory.Module):
        pass

    class Module(Package):

        def __init__(self, node: YamlMap, ngx: 'Nginx') -> None:
            super().__init__(node, Stage.Patch | Stage.PreBuild | Stage.PostBuild)
            self.__ngx = ngx
            self.dynamic = node.get('dynamic', default=False, key=YamlKey.Optional)
            self.conf_value = node.get('conf_value', key=YamlKey.Optional)

        @property
        def sourcedir(self) -> str:
            return ""

        @property
        def build_name(self) -> str:
            ''' Nginx.Module is part of nginx, the build_name should be the same as it '''
            return self.__ngx.build_name

    class Helper(object):
        # OptsPair =

        class OptsPair(collections.namedtuple('OptsPair', 'key value')):
            # def __init__(self, pair:List[str]) -> None:
            #     assert isinstance(pair, list)
            #     self.key = pair[0]
            #     self.value = pair[1] if len(pair) > 1 else None

            def __eq__(self, other: object) -> bool:
                if not isinstance(other, Nginx.Helper.OptsPair):
                    return False
                has_value = self.value or []
                other_has_value = other.value or []
                return (self.key == other.key) and set(has_value) == set(other_has_value)

        def __init__(self, ngx: 'Nginx') -> None:
            self._ngx_configure_cmd = 'configure'
            self.__ngx = ngx
            ngx_path = '%s/%s' % (Environment.buildroot, ngx.build_name)
            f = '%s/%s' % (ngx_path, self._ngx_configure_cmd)
            assert os.path.exists(f), 'Configure file not exists: %s' % f
            __cmd = r'./%s --help | grep "\-\-with"' % self._ngx_configure_cmd
            sp = subprocess.Popen(__cmd, shell=True, cwd=ngx_path, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, close_fds=True)
            out, error = sp.communicate()
            assert sp.returncode == 0, 'Command [%s] fails' % __cmd

            __configure_out = [re.findall(r'[^\s\t]+', l.lstrip())[0] for l in out.decode('utf-8').split('\n') if l]

            def nsplit(s: str, sep: str, n: int) -> List[Optional[str]]:
                return (s.split(sep) + [None] * n)[:n]
            # self.__avail_mod_without = [ Nginx.Helper.OptsPair._make(o[len('--without-'):].split('=')) for o in __configure_out if o.startswith('--without-') ]
            # self.__avail_mod_without = [Nginx.Helper.OptsPair._make(
            #     nsplit(o[len('--without-'):], '=', 2)) for o in __configure_out if o.startswith('--without-')]
            # self.__avail_mod_with = [Nginx.Helper.OptsPair._make(
            #     nsplit(o[len('--with-'):], '=', 2)) for o in __configure_out if o.startswith('--with-')]
            # self.__avail_mod_with = []
            __conf = {'with':[], 'without':[]}
            for verb in __conf:
                v = '--%s-' % verb
                _ = [(nsplit(o[len(v):], '=', 2)) for o in __configure_out if o.startswith(v)]
                # same option key may have multiple values, group it in Nginx.Helper.OptsPair(key, [value,...])
                for key, group in itertools.groupby(_, lambda x: x[0]):
                    __conf[verb].append(Nginx.Helper.OptsPair(key, [thing[1] for thing in group]))
            self.__avail_with_opts = __conf['with']
            self.__avail_without_opts = __conf['without']
            del out, __configure_out

        def is_defined_in_opts(self, pkg: Union['Nginx.Module', 'Nginx.Library']) -> bool:
            if pkg is None:
                return False
            return pkg.name in map(lambda x: x.key, itertools.chain(self.__avail_with_opts, self.__avail_without_opts))

        @property
        def ngx_lib_active(self) -> Dict[str, 'Nginx.Library']:
            return collections.OrderedDict([(_, l) for _, l in self.__ngx.libraries.items() if l.status == State.ACTIVE])

        @property
        def ngx_mod_active(self) -> Dict[str, 'Nginx.Module']:
            return collections.OrderedDict([(_, m) for _, m in self.__ngx.modules.items() if m.status == State.ACTIVE])

        @property
        def ngx_mod_inactive(self) -> Dict[str, 'Nginx.Module']:
            return collections.OrderedDict([(_, m) for _, m in self.__ngx.modules.items() if m.status == State.INACTIVE])

        # @property
        # def avail_mod_with_opt(self) -> Iterator['OptsPair']:
        #     return self.__avail_mod_with

        # @property
        # def avail_mod_without_opt(self) -> Iterator['OptsPair']:
        #     return self.__avail_mod_without

        @property
        def _fix_tfo(self) -> str:
            # TCP_FASTOPEN is supported in kerenel >= 3.6, but GLIBC >=2.18 defines
            # the constant. Fix it when using lower version of GLIBC
            return '-DTCP_FASTOPEN=23' if self.__ngx.options.force_tfo or (Environment.is_tfo and Environment.glibc_version < 218) else ''

        @property
        def __build_string(self) -> str:
            build_epoch = str(int(time.time()))
            s = 'Custom Build %s' % build_epoch
            flags = [
                {'TFO': Environment.is_tfo},
                {'SSE4.2': Environment.cpu_capability.is_supported_sse4_2},
                {'PCLMUL': Environment.cpu_capability.is_supported_pclmul},
            ]
            ret = [k for f in flags for k, v in f.items() if v]
            if len(ret) > 0:
                s = '%s [%s]' % (s, ','.join(ret))
            return s

        def __compile_lua(self) -> str:
            # Build lua libraries
            # list all files, => rename => luajit *.lua to o => [final] ar rcus lualib.a *.o
            lua_cmodule_top = Environment.working.lua_cmodule_path
            lua_cmodule_objs = '%s/lua_objs' % Environment.working.lib_path
            ensure(lua_cmodule_objs)
            wholeluaname = 'libluamod.a'
            lua_ld_opts = set()
            lua_libs = [l for l in Inventory.lualib_active.values()]
            for lua in lua_libs:
                lua._run()
                lua_ld_opts.add('-Dil_%s' % lua.name.replace('-', '_'))
            if not Environment._dry_run:
                lua_pkg_sep = '_'
                for root, dirs, files in os.walk(lua_cmodule_top, topdown=True):
                    for f in files:
                        file_full_path = '%s/%s' % (root, f)
                        prefix = root.replace('%s' % lua_cmodule_top, '')
                        if prefix:
                            prefix = '%s%s' % (prefix[1:].replace('/', lua_pkg_sep), lua_pkg_sep)
                        obj_lua_filename = '%s%s' % (prefix, f)
                        #obj_lua_filename = '%s%s%s' % (root.replace('%s/' % lua_cmodule_top, '').replace('/', lua_pkg_sep), lua_pkg_sep, f)
                        if f.endswith('.lua'):
                            obj_lua_fullpath = '%s/%s' % (lua_cmodule_objs, obj_lua_filename)
                            os.rename(file_full_path, obj_lua_fullpath)
                            Command(['bin/luajit',
                                     '-b',
                                     obj_lua_fullpath,
                                     '%s.o' % obj_lua_fullpath[:-4]],
                                    cwd=Environment.working.prefix)._run()
                    #if f.endswith('.so'):
                    #        shutil.copy(file_full_path, lua_cmodule_objs)
                            #lua_ld_opts.append('-Wl,-Bstatic %s -Wl,-Bdynamic' %s)
                Command(['ar', 'rcus', wholeluaname, '%s/*.o' % lua_cmodule_objs], shell=True, cwd=Environment.working.lib_path)._run()
            return '%s -Wl,--whole-archive -l%s -Wl,--no-whole-archive' % (' '.join(lua_ld_opts), wholeluaname[3:][:-2])

        def __get_compile_libs_ldopts(self) -> str:
            # Get related pkg-config library flag, ready for static linking
            library_ld_opts = []
            for l in Inventory.lib_active.values():
                if Environment._dry_run:
                    library_ld_opts.append('-l<%s>' % l.name)
                elif l.is_compiled:
                    libs = l.pkgconfig_libs()
                    logging.debug(libs)
                    if libs:
                        library_ld_opts.extend([o for o in libs.split() if o not in ['-ldl', '-lm']])
            # -ldl -pthread is required if compile openssl in static
            return '-Wl,-Bstatic %s -Wl,-Bdynamic -ldl -pthread' % ' '.join(itertools.filterfalse(lambda x: x.strip() == '-ldl', library_ld_opts)) if library_ld_opts else ''

        def __compile_global(self) -> None:
            # Build global Inventory.library [ACTIVE]
            glo_req_libs = [l for l in Inventory.lib_active.values() if l.scope == Scope.GLOBAL]
            # Build nginx library if referenced Inventory.library [ACTIVE]
            ngx_libs = [Inventory.libraries[nl._ref.name] for nl in self.ngx_lib_active.values()]

            for l in itertools.chain(glo_req_libs, ngx_libs):
                l._run()

        def __compile_mods(self) -> Set[str]:
            # Libraries and modules sometimes should be in order in compiling time
            modlib_usage = itertools.chain.from_iterable(
                ([*map(
                    lambda l: list(set([l.name]) | l._raw_requires),
                    itertools.chain(
                        Inventory.mod_active.values(),
                        Inventory.lib_active.values(),
                        self.ngx_mod_active.values()
                        )
                    )
                 ])
                )
            modlib_usage_freq = collections.Counter(modlib_usage)

            # Build extra modules, their related dependencies will be auto built
            ngx_extra_mods = Inventory.mod_active.values()
            m_compiled = []
            for m in ngx_extra_mods:
                m._run()
                verb = '--add-dynamic-module' if m.dynamic else '--add-module'
                # Try not to use Environment.buildroot, use relative instead
                m_compiled.append((m.name, '%s=../%s' % (verb, m.build_name)))
            m_compiled = sorted(m_compiled, reverse=True, key=(lambda x: modlib_usage_freq.get(x[0], 0)))

            return OrderedSet(map(lambda x: x[1], m_compiled))

        def _compile_all(self) -> Tuple[str, Set[str]]:
            # Compile libraries that flagged as global
            self.__compile_global()
            ld_opts = []
            # Compile Lua modules
            ld_opts.append(self.__compile_lua())
            # Compile Inventory modules
            extra_mod = self.__compile_mods()
            # Retrieve related libraries pkgconfig
            ld_opts.append(self.__get_compile_libs_ldopts())

            return (' '.join(ld_opts), extra_mod)

        def make_configure_cmd(self, ld_opts, extra_mod) -> Command:

            __configure_opts = {
                'build': self.__build_string,
                'prefix': self.__ngx.options.prefix,
                #'sbin-path': self.__options.sbin,
                #'modules-path': self.__options.modules_path,
                #'conf-path': self.__options.conf,
                # NOTE: <error-log-path>/logs/error.log
                #                'error-log-path' : self.__options.error_log,
                #                'http-log-path'  : self.__options.http_log,
                #'pid-path': self.__options.pid,
                #'user': self.__ngx.options.user,
                #'group': self.__ngx.options.group,
                #'with-libatomic' : None,
                #'with-cc-opt': repr('-static -static-libgcc'),
                #'with-cc-opt': '%s' % (repr('-static') if self.static else ''),
                # NOTE: -static causes Nginx not pass integer checking
                # ??  static-libgcc
                'with-cc-opt': '-I%s' % Environment.working.inc_path,
                #
                'with-ld-opt': '-L{0} -Wl,-rpath={0} {1}'.format(Environment.working.lib_path, ld_opts),
                # 'with-ld-opt' : repr('-L%s -Wl,-Bstatic -lz -Wl,-Bdynamic' % Environment.working.lib_path),
                #'with-ld-opt' : repr('-L%s -static' % Environment.working.lib_path),
            }
            # append the end of the buildscript stage
            buildcmd = ['./%s' % self._ngx_configure_cmd]
            for k in __configure_opts:
                buildcmd.append('--%s' % k if __configure_opts[k] is None else '--%s=%s' % (k, __configure_opts[k]))
            buildcmd.extend(list(self.__get_bundled_lib_configure_opts()))
            buildcmd.extend(list(self.__get_bundled_mod_configure_opts()))
            buildcmd.extend(extra_mod)
            #print(buildcmd)
            if self.__ngx.debug:
                key = 'debug'
                assert key in (o.key for o in self.__avail_with_opts), 'No debuggable option'
                buildcmd.append('--with-%s' % key)

            return Command(buildcmd, cwd=self.__ngx.cwd)

        def __get_bundled_lib_configure_opts(self) -> Iterator[str]:
            _opts_active = itertools.filterfalse(lambda x: self.ngx_lib_active.get(x.key) is None, self.__avail_with_opts)
            def func(opt, verb, _set):
                l = _set.get(opt.key)
                if verb == 'with':
                    l._run()
                if None in opt.value:
                    return '--%s-%s' % (verb, opt.key)

            return itertools.filterfalse(lambda y: y is None, map(lambda x: func(x, 'with', self.ngx_lib_active), _opts_active))

        def __get_bundled_mod_configure_opts(self) -> Iterator[str]:
            #ok_opts_active = ((m.name, m.value) for _, m in self.__ngx.modules.items()
            #                  for amw in self.__avail_mod_with if amw.key == m.name and m.status == State.ACTIVE)
            #ok_opts_inactive = ((m.name, m.value) for _, m in self.__ngx.modules.items()
            #                    for amw in self.__avail_mod_without if amw.key == m.name and m.status == State.INACTIVE)
            # print(list(self.__avail_mod_with))
            # sys.exit()
            _opts_active = itertools.filterfalse(lambda x: self.ngx_mod_active.get(x.key) is None, self.__avail_with_opts)
            _opts_inactive = itertools.filterfalse(lambda x: self.ngx_mod_inactive.get(x.key) is None, self.__avail_without_opts)

            def func(opt, verb, _set):
                m = _set.get(opt.key)
                if verb == 'with':
                    m._run()
                if m.dynamic:
                    assert 'dynamic' in opt.value, 'Bundled module [%s] is not a dynamic module' % m.name
                val = 'dynamic' if m.dynamic else m.conf_value
                return '--%s-%s%s' % (verb, opt.key, '' if val is None else '=%s' % val)

            return itertools.chain(
                map(lambda x: func(x, 'with', self.ngx_mod_active), _opts_active),
                map(lambda x: func(x, 'without', self.ngx_mod_inactive), _opts_inactive)
            )
            # return itertools.chain(
            #     #*['--with-%s=%s' % (i, j) if j else '--with-%s' % i for i, j in ok_opts_active],
            #     ['--with-%s%s' % (o.key, self.ngx_mod_active.get(o.key).value is None and '' or '=%s' % self.ngx_mod_active.get(o.key).value) for o in _opts_active],
            #     #*['--without-%s=%s' % (i, j) if j else '--without-%s' % i for i, j in ok_opts_inactive]
            #     #['--without-%s=%s' % (o.key,  self.ok_mod_inactive.get(o.key)) if m.value else '--without-%s' % o.key for o in _opts_inactive]
            #     ['--without-%s%s' % (o.key, self.ngx_mod_inactive.get(o.key).value and '=%s' % self.ngx_mod_inactive.get(o.key).value or '') for o in _opts_inactive],
            # )

    def __prompt_toupdate(self) -> None:
        prompt = False

        #for v in Inventory._allitems:
        for v in itertools.chain(
                Inventory.mod_active.values(),
                Inventory.lib_active.values()
            ):
            if v.is_outdated:
                print('\033[1;92m outdated \033[0m: %s %s' % (v.name, v.git))
                prompt = True
        if prompt:
            ans = query_yes_no('There is/are outdated packages. Go ahead to update?')
            if not ans:
                sys.exit()

    def __init__(self, yamlconfig: YamlConfig) -> None:

        assert isinstance(yamlconfig, YamlConfig), ErrMsg.TypeMisMatch.format(yamlconfig, YamlConfig)
        # Nginx.Library._inventory = yamlconfig.inventory
        ngx = yamlconfig.nginx
        super().__init__(ngx, Stage.Patch | Stage.PreBuild | Stage.PostBuild)

        assert Environment.is_initialized, 'Environment is unitialized'
        assert Inventory.is_initialized, 'Inventory is unitialized'

        self.__prompt_toupdate()
        self.static = True
        self.__reset_buildroot = True
        #self.__reset_buildroot = False

        if self.__reset_buildroot:
        # reset the build root
            logging.debug('Reset the buildroot %s' % Environment.buildroot)
            shutil.rmtree(Environment.buildroot, ignore_errors=True)

        Environment.ensure_io()

        #self.__name = ngx.get('name')
        #self.version = ngx.get('version')
        #assert self.__name or self.verson, 'Missing Nginx name and version'

        self.__build_cmd = None

        #f = '%s-%s.tar.gz' % (self.__name, self.version)
        #f = download('%s%s' % (self.__url, f), Environment.source.prefix, f)
        #self._ngx_name = untar('%s/%s' % (Environment.source.prefix, f), Environment.buildroot)

        self.__options = Nginx.Options(ngx.get('options', default={}, key=YamlKey.Optional))
        self.debug = self.__options.debug or False
        Environment._debug = self.debug

        # This helper will call build_name property for triggering nginx fetching
        self.__helper = Nginx.Helper(self)

        self._libraries = collections.OrderedDict(dict_to_tupleobjarray(
            Nginx.Library, ngx.get('library', default=[], key=YamlKey.Optional), self))

        m = ngx.get('modules', default={}, key=YamlKey.Optional)
        self._modules = collections.OrderedDict(dict_to_tupleobjarray(Nginx.Module, m.get('bundled', default=[]), self))

        for _, item in self._modules.items():
            if item.status == State.INACTIVE:
                continue
            #sys.exit()
            #print(set(item._raw_requires))
            #print(set(Inventory.libraries.keys()))
            assert self.__helper.is_defined_in_opts(item), 'Invalid modules [%s] that is undefined in nginx configure' % item.name
            # print(item.status)
            # print(item.name)
            # print(item._raw_requires)
            # print(set(Inventory.lib_active.keys()))
            # sys.exit()

            assert item._raw_requires <= set(Inventory.lib_active.keys()), 'Out-of-bound active libraries in Nginx bundled modules [%s]' % item.name
            item.requires = map(Inventory.lib_active.get, item._raw_requires)
            #item.requires = [Inventory.libraries[l] for l in item._raw_requires]

        for _, item in self._libraries.items():
            #print(set(item._raw_requires))
            #print(set(Inventory.libraries.keys()))
            assert self.__helper.is_defined_in_opts(item), 'Invalid library [%s] that is undefined in nginx configure' % item.name


        self.__modules_third_party = collections.OrderedDict(dict_to_tupleobjarray(Nginx.UserModule, m.get('third-party', default=[])))

    # @property
    # def name(self) -> str:
    #     return self.__name
    #
    # @property
    # def build_name(self) -> str:
    #     return self._ngx_name

    @property
    def sourcedir(self) -> str:
        return Environment.source.prefix

    def run(self, dry_run: bool=False):
        with elapsed_timer() as elapsed:
            Environment._dry_run = dry_run
            self._run(dict(CFLAGS='%s' % self.__helper._fix_tfo))
        print("all done at %.2f seconds" % elapsed())

    def _pre_run(self) -> None:
        ''' Auto build libraries and extra modules if necessary '''
        ld_opts, extra_mod = self.__helper._compile_all()
        self.__build_cmd = self.__helper.make_configure_cmd(ld_opts, extra_mod)

            # print('-'*20)
            # input("Press the <ENTER> key to continue...")

    # def _gen_commands(self) -> Generator[Tuple[Stage, Optional[Command]], None, None]:
    #
    #     # openssl -> $(pkg-config --libs openssl) -ldl -lz  -> in seq
    #     # or -BWl,-Bstatic -lssl -lcrypto -lz -Wl,-Bdynamic -ldl
    #     # zlib
    #     #./configure --error-log-path=/usr/local/nginx/logs/error.log --sbin-path=/usr/local/nginx/sbin/nginx --build='Custom Build 1487008429 [TFO,SSE4.2,PCLMUL]' --with-cc-opt='-I/build/BUILDROOT/vm/include -L/build/BUILDROOT/vm/lib -Wl,-rpath=/build/BUILDROOT/vm/lib' --modules-path=/usr/local/nginx/modules --conf-path=/usr/local/nginx/conf/nginx.conf --prefix=/usr/local/nginx --pid-path=/var/run/nginx.pid --with-ld-opt=' -Wl,-rpath=/build/BUILDROOT/vm/lib -Wl,-Bstatic -L/build/BUILDROOT/vm/lib -lssl -lcrypto -lz -Wl,-Bdynamic -ldl' --group=nginx --user=nginx --http-log-path=/usr/local/nginx/logs/access.log --with-http_addition_module --with-file-aio --with-pcre-jit --with-http_slice_module --with-http_secure_link_module --with-http_v2_module --with-stream=dynamic --with-stream=dynamic --with-http_realip_module --with-http_sub_module --with-http_ssl_module --with-stream_ssl_module --with-http_gzip_static_module --with-http_stub_status_module --with-http_gunzip_module --with-threads --with-http_mp4_module --without-http_autoindex_module --without-http_memcached_module
    #     #
    #     #  --with-openssl=/build/BUILDROOT/vm/include
    #
    #     _ngx_make_cmd = 'make'
    #     for stage, c in super()._gen_commands():
    #         if stage == Stage.BuildScript and c is None:
    #             yield (stage, self.__build_cmd)
    #             mt = ['-j', Environment.num_of_processors] if self.threads_enabled else []
    #             yield (stage, Command([_ngx_make_cmd, *mt]))
    #         if stage == Stage.PostBuild and c is None:
    #             # append the end of the postbuild stage
    #             f = basename(self.__options.sbin or self.name)
    #             if self.debug:
    #                 yield (stage, Command(['mv', 'objs/%s' %f, 'objs/%s-debug' % f]))
    #             else:
    #                 # strip all result dynamic modules and nginx binary
    #                 yield (stage, Command('strip --preserve-dates --strip-debug objs/*.so || true'))
    #                 yield (stage, Command('strip --preserve-dates --strip-all objs/%s || true' % f))
    #         yield (stage, c)

    def on_stage_exit(self, stage: Stage) -> Generator[Union[Optional[Command], Optional[Env]], None, None]:
        if stage == Stage.BuildScript:
            yield self.__build_cmd
            yield Command(['make'])
        if stage == Stage.PostBuild:
            # append the end of the postbuild stage
            f = basename(self.__options.sbin or self.name)
            if self.debug:
                yield Command(['mv', 'objs/%s' %f, 'objs/%s-debug' % f])
            else:
                # strip all result dynamic modules and nginx binary
                yield Command('strip --preserve-dates --strip-debug objs/*.so || true', cwd=self.cwd)
                yield Command('strip --preserve-dates --strip-all objs/%s || true' % f, cwd=self.cwd)

    @property
    def options(self) -> 'Options':
        return self.__options

    @property
    def libraries(self) -> Dict[str, 'Nginx.Library']:
        return self._libraries

    @property
    def modules(self) -> Dict[str, 'Nginx.Module']:
        return self._modules

    @property
    def modules_third_party(self) -> Dict[str, 'UserModule']:
        return self.__modules_third_party
