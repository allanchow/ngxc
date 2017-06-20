#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import inspect
import collections
import enum
import functools
import logging
import os
import platform
import re
import shutil
import signal
import subprocess
#import shlex
import sys
import tarfile
import threading
import time
import urllib.parse
import urllib.request
from abc import ABCMeta, abstractmethod, abstractproperty
from contextlib import contextmanager
from copy import copy, deepcopy
from timeit import default_timer as timer  # type: ignore
from typing import (Any, Callable, Dict, Generator, Iterator, List, NamedTuple,
                    Optional, Sequence, Tuple, Type, TypeVar, Union, cast,
                    no_type_check)

import git  # type: ignore
import progressbar  # type: ignore
from memory_profiler import profile  # type: ignore
from ruamel import yaml  # type: ignore

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
#print = functools.partial(print, flush=True)

#__all__ = ['utils', 'git', 'base', 'map', 'yaml']
__all__ = [name for name, obj in locals().items()
           if not (name.startswith('_') or inspect.ismodule(obj))]
