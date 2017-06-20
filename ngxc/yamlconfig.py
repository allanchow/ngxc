# -*- coding: utf-8 -*-

import sys
import os

import ruamel.yaml

from .environment import Environment
from .inventory import Inventory
from .yaml import YamlMap
from .base import OrderedSet

class YamlConfig(object):

    def __init__(self, yamlfile: str) -> None:
        #try:
        with open(yamlfile, 'r') as configfile:
            # IMPORTANT: ruamel.yaml.RoundTripLoader will preserve yaml aliases, that not suit our application
            #yaml_root = ruamel.yaml.load(configfile, ruamel.yaml.RoundTripLoader)
            yaml_root = ruamel.yaml.safe_load(configfile)
            yaml = []
            for inc in OrderedSet(yaml_root.get("includes", [])):
                with open('%s/%s' % (os.path.dirname(yamlfile), inc), 'r') as f:
                    yaml.extend([line for line in f])
            yaml_root = ruamel.yaml.safe_load(''.join(yaml))
            del yaml
            #    yaml_root.update(ruamel.yaml.load(open('%s/%s' % (os.path.dirname(yamlfile), inc), 'r')))
            #print(ruamel.yaml.dump(yaml_root, Dumper=ruamel.yaml.RoundTripDumper), end='')
            #print(ruamel.yaml.dump(yaml_root), end='')
            #sys.exit()
            #ruamel.yaml.dump(yaml_root, sys.stdout, allow_unicode=True)
            assert not yaml_root is None, 'YAML <%s> load error' % yamlfile
            # print(type(yaml_root))
            __y = YamlMap(yaml_root)
            del yaml_root
        #except IOError as e:
        #    print('ERROR: Unable to open file %s!' % yamlfile)
        #    sys.exit(1)
        self.env = __y.get('environment')
        self.inv = __y.get('inventory')
        self.nginx = __y.get('nginx')
        del __y
        Environment.load(self.env)
        Inventory.load(self.inv)

    # @property
    # def documentroot(self) -> YamlMap: return self.__y
