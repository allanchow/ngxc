# -*- coding: utf-8 -*-

import collections
import os
import sys
import logging
from contextlib import contextmanager
import shutil
import tarfile
import urllib.parse
import urllib.request
from timeit import default_timer as timer  # type: ignore
from typing import Any, Iterator, List, Optional, Callable, no_type_check, Tuple


@contextmanager
def catch(*exceptions: Exception, **kwargs: Any) -> Iterator[Any]:
    try:
        yield kwargs.get('default', None)
    except Exception as e:
        if exceptions is not None:
            return
        raise e


def ensure(directory: str) -> bool:
    ret = os.path.exists(directory)
    if not ret:
        logging.debug('not exists: %s' % directory)
        os.makedirs(directory)
    return ret

def isempty(s: str) -> bool:
    return s is None or s == '' or s.isspace()

def basename(path: str) -> str:
    return path.strip('/').strip('\\').split('/')[-1].split('\\')[-1]


def untar(filename: str, dest_path: str='.', clean: bool=True) -> str:
    def rchop(s: str, endings: List[str]) -> str:
        for e in endings:
            l = len(e)
            if s[-l:] == e:
                return s[:-l]
        return s
    #pkg_name = rchop(rchop(basename(filename), '.gz'), '.tar')
    f = basename(filename)
    pkg_name = rchop(f, ['.bz2', '.xz', '.tar.gz', '.tar', '.gz'])
    assert pkg_name != f, 'Unsupport file extensions. Can''t untar file: %s' % f
    assert tarfile.is_tarfile(filename), 'It seems it is not a tar file: %s' % f
    dest = '%s/%s' % (dest_path, pkg_name)
    if clean and os.path.exists(dest):
        shutil.rmtree(dest)
    logging.debug('untar: %s' % filename)
    tarfile.open(filename, 'r').extractall(path=dest_path)
    return pkg_name


def download(url: str, cwd: str='.', filename: Optional[str]=None) -> str:
    def getFileName(url: str, openUrl: Any) -> str:
        if 'Content-Disposition' in openUrl.info():
            # If the response has Content-Disposition, try to get filename from it
            cd = dict(map(
                lambda x: x.strip().split('=') if '=' in x else (x.strip(), ''),
                openUrl.info()['Content-Disposition'].split(';')))
            if 'filename' in cd:
                filename = cd['filename'].strip("\"'")
                if filename:
                    return filename
        # if no filename was found above, parse it out of the final URL.
        return os.path.basename(urllib.parse.urlsplit(openUrl.url)[2])

    def exists(cwd: str, filename: str) -> bool:
        return os.path.exists('%s/%s' % (cwd, filename))
    if filename is not None and not isempty(filename) and exists(cwd, filename):
        return filename
    with urllib.request.urlopen(url) as response:
        filename = filename or getFileName(url, response)
        if not exists(cwd, filename):
            logging.debug('Download %s' % url)
            with open('%s/%s' % (cwd, filename), 'wb') as out_file:
                out_file.write(response.read())
    return filename


@contextmanager
def pushd(newDir: str, create: bool=False) -> Iterator[str]:
    previousDir = os.getcwd()
    if create:
        ensure(newDir)
    try:
        os.chdir(newDir)
        yield newDir
#    except (IOError, OSError):
#        logging.error('Can\'t change to %s' % newDir)
#        sys.exit(-1)
    finally:
        os.chdir(previousDir)


@contextmanager
def elapsed_timer() -> Iterator[Callable[[], int]]:
    start = timer()
    elapser = lambda: timer() - start  # type: Callable[[], int]
    yield lambda: elapser()
    end = timer()
    elapser = lambda: end - start


class final(type):

    @no_type_check
    def __init__(cls, name, bases, namespace) -> None:
        super(final, cls).__init__(name, bases, namespace)
        for klass in bases:
            if isinstance(klass, final):
                raise TypeError(str(klass.__name__) + " is final")

# tuple(tuple[int],dict[str,int])

class classproperty(object):

    def __init__(self, getter: Callable) -> None:
        self.getter = getter

    def __get__(self, instance: object, owner: object) -> Any:
        return self.getter(owner)


def dict_to_tupleobjarray(cls: type, obj: List, *args: Any, **kwargs: Any) -> List[Tuple[str, Any]]:
    _set = set([cls(l, *args, **kwargs) for l in obj])
    _list = [k for k, v in collections.Counter([l.name for l in _set if l]).items() if v > 1]
    assert not _list, 'Duplicated items: %s in %s' % (_list, obj)
    _dict = [(l.name, l) for l in _set if l]
    del _set
    del _list
    return _dict


def is_flag(target: int, flags: int) -> bool:
    return (target & flags) == target


def query_yes_no(question :str, default :str="yes") -> bool:
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")
