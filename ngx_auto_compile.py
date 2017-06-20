#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import sys
from typing import Tuple

from ruamel import yaml
import git
#from memory_profiler import profile

from ngxc.yamlconfig import YamlConfig
from ngxc.nginx import Nginx

"""
nginx build script
"""

__author__ = 'Gnought'
__copyright__ = 'Copyright 2017'
__credits__ = ''
__license__ = 'GPL'
__version__ = '2.0'
__maintainer = 'Gnought'
__email__ = 'gnought.yeung@allbrightnet.com'
__status__ = 'Developement'
__date__ = 'Jan 24, 2017'

# the sed note in OSX: http://blog.csdn.net/cuiaamay/article/details/49495885
# https://google.github.io/styleguide/pyguide.html
# http://stackoverflow.com/questions/1523427/what-is-the-common-header-format-of-python-files


#@profile
def main(dry_run :bool=False) -> None:
    __script_path = os.path.dirname(os.path.realpath(__file__))
    #yc = YamlConfig('%s/c.yml' % __script_path)

    yc = YamlConfig('%s/config/main.yml' % __script_path)
    ngx = Nginx(yc)
    #ngx.reset_buildroot = False
    ngx.run(dry_run)
    # print(Environment.global_env)
    # cmd = './configure --help | grep "\-\-with\-"'

    #out, error  = subprocess.Popen(cmd, shell=True, cwd='/build/BUILDROOT/nginx-1.10.3', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True).communicate()
    #p = subprocess.Popen(cmd, shell=True, cwd='/build/BUILDROOT/nginx-1.10.3', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
    #lines = out.decode().split('\\n')

    # lines = [ l.lstrip() for l in out.decode().split('\n') if l.lstrip().startswith('--with-debug')]
    #lines = [ l for l in out.decode().split('\n') if '--with-debug'.split('=')[0] in l]
    # print(lines)
#    print(lines)
#    for line in p.stdout:
#        line = line.lstrip().decode()
#        #if line.startswith('--with'):
#        print(line)
#        print(line.startswith('--with-debug'))
    #ret = str(out).split('\\n')
    # print(len(ret))
    # rr = [ l for l in ret ]

    # for i in ret:
    #    print(i)

    # print(ngx.libraries['libatomic'])
#    print(b.inventory.libraries['jemalloc'].requires)

if __name__ == '__main__':

    def ver_fmt(_ver: Tuple) -> str:
        return '.'.join(map(str, _ver[:3]))
    ver = sys.version_info
    assert ver[:2] >= (3, 5), 'Python minium version required: >= 3.5'
    logging.info('Python Version: %s' % ver_fmt(ver))
    ver = git.Git().version_info
    assert ver[:2] >= (2, 5), 'Git minium version required: >= 2.5'
    logging.info('Git Version: %s' % ver_fmt(ver))
    ver = yaml.version_info
    assert ver >= (0, 15), 'ruamel.yaml minium version required: >= 0.15'
    # TODO: requires libtool
    # TODO: check pkg-config if exist, >0.9.0
    package_force_update = '-f' in sys.argv

    main(dry_run=('-d' in sys.argv))

# TODO: Dynamic TLS size
# https://blog.cloudflare.com/optimizing-tls-over-tcp-to-reduce-latency/
