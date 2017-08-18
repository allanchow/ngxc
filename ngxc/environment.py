# -*- coding: utf-8 -*-

import os
import platform
import enum
from typing import Any

import cpuinfo

from .base import _BaseObject, Singleton
from .yaml import YamlMap, YamlKey
from .utils import classproperty, ensure
from .map import MergedMap
from .command import Command

class Optimization_Level(enum.Enum):
    LEVEL_0 = '0'
    LEVEL_1 = '1'
    LEVEL_2 = '2'
    LEVEL_3 = '3'
    LEVEL_FAST = 'fast'


class Environment(_BaseObject, metaclass=Singleton):
    __slots__ = ()  # no direct instantiation, so allow immutable subclasses
    __platform = platform.platform()
    __cpu = None
    __buildroot = None
    __source = None
    __working = None
    __global_env = None
    __initialized = False
    _dry_run = False
    _debug = False

    class CpuCapability(_BaseObject):
        __cpu = cpuinfo.get_cpu_info()

        def __init__(self, node: YamlMap) -> None:
            def_sse4_2 = 'sse4_2' in self.__cpu['flags'] or 'sse4.2' in self.__cpu['flags']
            def_pclmul = 'pclmul' in self.__cpu['flags'] or 'pclmulqdq' in self.__cpu['flags']
            self.__sse4_2 = node.get('sse4_2', default=def_sse4_2, key=YamlKey.Optional)
            self.__pclmul = node.get('pclmul', default=def_pclmul, key=YamlKey.Optional)

        @property
        def is_supported_sse4_2(self) -> bool:
            return self.__sse4_2

        @property
        def is_supported_pclmul(self) -> bool:
            return self.__pclmul

    class Source(_BaseObject):

        def __init__(self, node: YamlMap) -> None:
            self.prefix = node.get('prefix')
            self.lib_path = node.get('lib-path')
            self.modules_path = node.get('module-path')
            self.patch_path = node.get('patch-path')

    class Working(_BaseObject):

        def __init__(self, node: YamlMap) -> None:
            self.prefix = node.get('prefix')
            self.inc_path = node.get('include')
            self.lib_path = node.get('lib-path')
            self.lua_inc_path = node.get('lua-include')
            self.lua_cmodule_path = node.get('lua-cmodule')


    @classmethod
    def __get(cls, val: Any) -> Any:
        assert cls.__initialized, 'Environment is uninitialized'
        return val

    @classmethod
    def load(cls, node: YamlMap) -> None:
        if cls.__initialized:
            return
        cls.__cpu = Environment.CpuCapability(node.get('cpu', default=YamlMap(), key=YamlKey.Optional))
        cls.__buildroot = node.get('buildroot')
        cls.__source = Environment.Source(node.get('source'))
        cls.__working = Environment.Working(node.get('vm'))
        cls.__initialized = True
        cls.__global_env = cls.__get_def_global_environemnt()
        # cls.__global_env = MergedMap()


    @classmethod
    def ensure_io(cls) -> None:
        ensure(cls.buildroot)
        ensure(cls.working.prefix)
        ensure(cls.working.inc_path)
        ensure(cls.working.lib_path)
        ensure(cls.source.prefix)
        ensure(cls.source.lib_path)
        ensure(cls.source.modules_path)
        ensure(cls.source.patch_path)

    @classproperty
    def is_initialized(cls) -> bool:
        return cls.__initialized

    @classmethod
    def __get_pkg_verinfo(cls, pkg: str, env: dict=None) -> int:
        # REVIEW: not support in OSX
        if cls.is_Darwin:
            return 0
        if cls.is_Ubuntu:
            # args="dpkg-query -W -f='${Version}' gcc | sed 's#^[[:digit:]]*:*\([^\-]\+\)\-.*$#\1#g' | sed 's#\.##g'"
            cmd = Command(['dpkg-query', r"-W -f='${Version}' ", pkg,
                           r"| sed 's#^\([[:digit:]]*:\)*\([^\-]\+\)\-.*$#\2#g' | sed 's#\.##g'"], shell=True)
        else:
            cmd = Command(['rpm', '-q', r"--qf '%{VERSION}'",
                           '$(rpm -q %s | /usr/lib/rpm/redhat/rpmsort -r | head -n 1)' % pkg,
                           r"| head -n 1 | sed 's#\.##g'"], shell=True)
        # with catch(subprocess.CalledProcessError, default=0) as _:
        #    _ = int(subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env).communicate()[0])
        _ = cmd._run(stdout=False, env=env, timeout=15).strip()
        assert _, 'Can''t find any version info for %s' % pkg
        return int(_)

    @staticmethod
    def is_ld_gold() -> bool:
        out = Command(['ld', '-v'])._run(stdout=False, timeout=15)
        # try:
        #     out = subprocess._run['ld','-v'], shell=False, check=True, stdout=subprocess.PIPE, timeout=15).stdout
        # except subprocess.CalledProcessError as e:
        #     print(e.output)
        # print(out)
        # sys.exit()
        return 'GNU gold' in str(out)

    @classproperty
    def gcc_version(cls) -> int:
        return cls.__get_pkg_verinfo('gcc')

    @classproperty
    def glibc_version(cls) -> int:
        return cls.__get_pkg_verinfo('libc-bin' if cls.is_Ubuntu else 'glibc')

    @classproperty
    def pkgconfig(cls) -> str:
        return os.environ.get('PKG_CONFIG') or 'pkg-config'

    @classproperty
    def pkgconfig_version(cls) -> int:
        return cls.__get_pkg_verinfo(cls.pkgconfig)

    @classmethod
    def __get_def_global_environemnt(cls, optimi_lvl: Optimization_Level=Optimization_Level.LEVEL_3) -> MergedMap:
        ol = '' if optimi_lvl == Optimization_Level.LEVEL_FAST else '-g%s' % optimi_lvl.value
        gcc_cflags = ['-I%s -Wall -pipe %s -O%s -funroll-loops' % (cls.working.inc_path, ol, optimi_lvl.value)]

        # if static, may break library even dynamic modules
        #gcc_cflags.append('-fvisibility=hidden -Wl,--exclude-libs,ALL')
        # part of O3 options
        gcc_cflags.append('-fexcess-precision=fast -fpredictive-commoning -fgcse-after-reload -fipa-cp-clone')
        gcc_cflags.append('-mtls-dialect=gnu2')

        gcc_cflags.append('-fomit-frame-pointer -ftrapv -fwrapv -fno-wrapv -fdebug-prefix-map=/root=.')
        # harderen
        gcc_cflags.append('-Wformat -Werror=format-security -Wdate-time -Wno-unused-parameter -Wsign-compare')
        gcc_cflags.append('-Wp,-D_FORTIFY_SOURCE=2 -fexceptions -fstack-protector-strong' if cls.gcc_version >= 490 else '-fstack-protector --param=ssp-buffer-size=4')
        # dwarf debug
        if cls._debug:
            gcc_cflags.append('-grecord-gcc-switches')
        # arch
        gcc_cflags.append('-m64')
        if not cls.is_Darwin:
            gcc_cflags.append('-m128bit-long-double -minline-stringops-dynamically')
        # arch tune flags
        gcc_cflags.append('-march=core2 -mcx16 -mmmx -msse -msse2 -mfpmath=sse')
        __cpuflags = [(' -m' if cls.cpu_capability.is_supported_sse4_2 else ' -mno-').join(['', 'sse4.2', 'sse4', 'sse4.1', 'sse3']),
                      '-m%spclmul' % ('' if cls.cpu_capability.is_supported_pclmul else 'no-'), ]
        gcc_cflags.extend(__cpuflags)
        if not cls.is_Darwin:
            gcc_cflags.append('-mno-sse2avx -mno-sse4a -mno-avx2 -mno-aes')
            # gcc_cflags.append('-mno-sse2avx -mno-ssse3 -mno-sse4.1 -mno-sse4 -mno-sse4a -mno-avx2 -mno-aes')
        # NOTE: add -L in CFLAGS for cc compiler to find library location
        gcc_cflags.append('-L%s' % cls.working.lib_path)

        # gcc_ldflags = ['-L%s' % cls.__working.lib_path]
        #gcc_ldflags = ['-L{0} -Wl,-R{0}'.format(cls.working.lib_path)]
        gcc_ldflags = ['-L{0} -Wl,-rpath={0}'.format(cls.working.lib_path)]
        if not cls.is_Darwin:
            gcc_ldflags.append('-Wl,-Bsymbolic-functions -Wl,-z,relro,-z,now')

        gcc_grapite = ''
        gcc_use = ''
        if cls.is_ld_gold():
            # http://yuguangzhang.com/blog/enabling-gcc-graphite-and-lto-on-gentoo/
            gcc_grapite = '-floop-interchange -ftree-loop-distribution -floop-strip-mine -floop-block'
            gcc_use = 'graphite'
            if not Environment.is_Ubuntu:
                # LTO does not work in Ubuntu gcc
                gcc_use = 'graphite %s' % ('lto' if cls.gcc_version >= 482 else '')
                gcc_cflags.append('-flto=%s %s -ftree-vectorize' % (cls.num_of_processors, gcc_grapite))
                gcc_ldflags.append('-fuse-linker-plugin')

        env = {
            'CFLAGS': ' '.join(gcc_cflags),
            'CPPFLAGS': ' '.join(gcc_cflags),
            'LDFLAGS': ' '.join(gcc_ldflags),
            'GRAPHITE': gcc_grapite,
            'USE': gcc_use,
            'BUILDROOT': cls.__buildroot,
            'VM_PREFIX': cls.working.prefix,
            'VM_INCLUDE_PATH': cls.working.inc_path,
            'VM_LIBRARY_PATH': cls.working.lib_path,
            'LD_LIBRARY_PATH': cls.working.lib_path,
            'VM_LUA_INCLUDE_PATH': cls.working.lua_inc_path,
            'VM_LUA_CMODULE_PATH': cls.working.lua_cmodule_path,
            'PKG_CONFIG_PATH': '%s/pkgconfig' % cls.working.lib_path,
            'PATH' : ':%s/bin:' % cls.working.prefix
        }
        # if cls.is_Darwin:
        # env.update({'KERNEL_BITS': 64})
        return MergedMap(env)

    @classproperty
    def cpu_capability(cls) -> 'CpuCapability':
        return cls.__get(cls.__cpu)

    @classproperty
    def global_env(cls) -> MergedMap:
        return cls.__get(cls.__global_env)

    @classproperty
    def buildroot(cls) -> str:
        return cls.__get(cls.__buildroot)

    @classproperty
    def source(cls) -> 'Source':
        return cls.__get(cls.__source)

    @classproperty
    def working(cls) -> 'Working':
        return cls.__get(cls.__working)

    @classproperty
    def is_Ubuntu(cls) -> bool:
        return 'Ubuntu' in cls.__platform

    @classproperty
    def is_Darwin(cls) -> bool:
        return 'Darwin' in cls.__platform

    @classproperty
    def is_tfo(cls) -> bool:
        return int(platform.release().split('-', 1)[0].replace('.', '')) >= 360

    @classproperty
    def num_of_processors(cls) -> str:
        return str(os.cpu_count())
