# -*- coding: utf-8 -*-

import collections
import logging
import os
import subprocess
import sys
import signal
from typing import Union, List, Optional, Tuple, Any

from ngxc.base import _BaseObject

class Command(_BaseObject):

    def __init__(self,
                 commandline: Union[str, List[str]],
                 rescue_commandline: Optional[Union[str, List[str]]]=None,
                 cwd: Optional[str]='.',
                 shell: Optional[bool]=None) -> None:
        ''' shell is None: => determined by commandline
                commandline (list) => shell (false), __cmd (list)
                commandline (str)  => shell (true), __cmd (str)
            shell is True: => shell be fixed
                commandline (list) => shell (false), __cmd (list)
                commandline (str) => shell (true), __cmd (str)
            shell is False: => shell be fixed
                commandline (list) => shell (false), __cmd (list)
                commandline (str) => shell (true), __cmd (str)
           rescue_commandline should be as the same type as commandline '''
        self.__cmd = commandline
        self.__value = self.__cmd
        is_list = isinstance(commandline, list)
        if shell is None:
            shell = not is_list
        if shell and is_list:
            self.__cmd = ' '.join(commandline)
            self.__value = commandline
        elif isinstance(commandline, str):
            self.__value = commandline.strip().split()
        else:
            # cut out any empty elements if self.__cmd is an array
            self.__cmd = list(filter(lambda x: x, self.__cmd))
        self.__shell = shell
        self.__executable = self.__value[0]
        self.__args = ' '.join(self.__value[1:])

        self.rescue_cmd = None
        if rescue_commandline:
            assert isinstance(rescue_commandline, shell and str or list), 'Rescue commandline should be in %s' % (shell and 'str' or 'list')
            self.rescue_cmd = rescue_commandline if is_list else rescue_commandline.strip().split()

        self.__cwd = cwd or '.'


    @property
    def cwd(self) -> str:
        return self.__cwd

    @property
    def shell(self) -> bool:
        return self.__shell

    @property
    def executable(self) -> str:
        return self.__executable

    @property
    def args(self) -> str:
        return self.__args

    @property
    def value(self) -> Tuple[str, str]:
        return (self.__executable, self.__args)

    def __str__(self) -> str:
        return '%s %s' % (self.__executable, self.__args)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Command):
            return False
        return str(self) == str(other)

    def __hash__(self):
        return hash(self.__executable) ^ hash(self.__args)


    def _run(self, stdout: bool=True, timeout: Optional[int]=None,
             env: Union[dict, collections.Mapping]=None, log: bool=True, dry_run :bool=False) -> Any:

        cwd = self.__cwd
        if dry_run or log:
            logging.debug('Command [shell=%s, dry_run=%s, pwd=%s]: "\033[1;92m%s\033[0m"' % (self.__shell, dry_run, cwd, str(self)))

        if not dry_run:
            #subprocess.check_call(self.value, shell=shell, env=env, cwd=cwd, executable='/bin/bash')
            shell = self.__shell
            fcmd = self.__cmd
            rcmd = self.rescue_cmd
            if rcmd:
                shell = True
                rcmd = ' '.join(rcmd) if isinstance(rcmd, list) else rcmd
                fcmd = '(%s; if [ $? -ne 0 ]; then %s; fi)' % (str(self), rcmd)
            __exec = '/bin/sh' if shell else None
            __exec_fn = os.setpgrp if shell else None       # or os.setsid
            __stdout = None if stdout else subprocess.PIPE
            sys.stdout.flush()
            sys.stderr.flush()

            with subprocess.Popen(fcmd, shell=shell, env=env, cwd=cwd, executable=__exec,
                                  stdout=__stdout, stderr=subprocess.STDOUT,
                                  universal_newlines=True, preexec_fn=__exec_fn) as process:
                try:
                    out, err = process.communicate(timeout=timeout)
                except (subprocess.TimeoutExpired, KeyboardInterrupt):
                    # signalling SIGKILL to any child processes even those running ins shell
                    if __exec_fn is not None:
                        # Send the signal to all the process groups
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.kill()
                    process.wait()
                    raise
                except:
                    process.kill()
                    process.wait()
                    raise
                retcode = process.poll()
                if retcode != 0:
                    #raise subprocess.CalledProcessError(retcode, str(self), output=out, stderr=err)
                    raise CommandError(str(self), retcode, out, err)
                if not stdout:
                    return out
        return


class CommandError(Exception):
    def __init__(self, cmd: str=None, retcode: int=None, output: str=None, stderr: str=None) -> None:
        if cmd is not None:
            super().__init__(cmd)
        self.retcode = retcode
        self.output = output
        self.stderr = stderr

class Patch(Command):

    def __init__(self, patchfile: str, opts: str, cwd: str) -> None:
        self.patchfile = patchfile
        super().__init__('patch -sNt -r - %s < %s' % (opts, patchfile), cwd=cwd, shell=True)
