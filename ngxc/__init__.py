# -*- coding: utf-8 -*-
# pragma pylint: disable=C0413,W0622,W0401

import inspect
import logging
import functools

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
print = functools.partial(print, flush=True)

# from ngxc.err import *
# from ngxc.utils import *
# from ngxc.base import *
# from ngxc.map import *
# from ngxc.yaml import *
# from ngxc.command import *
# from ngxc.gitw import *
# from ngxc.environment import *
# from ngxc.buildunit import *
# from ngxc.package import *
# from ngxc.inventory import *
# from ngxc.yamlconfig import *
# from ngxc.nginx import *


__all__ = [name for name, obj in locals().items()
           if not (name.startswith('_') or inspect.ismodule(obj))]
