# -*- coding: utf-8 -*-

import sys
import os

from ruamel.yaml import YAML

from .environment import Environment
from .inventory import Inventory
from .yaml import YamlMap
from .base import OrderedSet

class YamlConfig(object):

    def __init__(self, yamlfile: str) -> None:
        #try:
        yml = YAML(pure = True)
        yml.preserve_quotes = True
        with open(yamlfile, 'r') as configfile:
            # IMPORTANT: ruamel.yaml.RoundTripLoader will preserve yaml aliases, that not suit our application
            #yaml_root = ruamel.yaml.load(configfile, ruamel.yaml.RoundTripLoader)
            yaml_root = yml.load(configfile)

            yamldoc = []
            for inc in OrderedSet(yaml_root.get("includes", [])):
                with open('%s/%s' % (os.path.dirname(yamlfile), inc), 'r') as f:
                    yamldoc.extend([line for line in f])
            yaml_root = yml.load(''.join(yamldoc))
            del yamldoc
            #    yaml_root.update(ruamel.yaml.load(open('%s/%s' % (os.path.dirname(yamlfile), inc), 'r')))
            #print(ruamel.yaml.dump(yaml_root, Dumper=ruamel.yaml.RoundTripDumper), end='')
            #print(ruamel.yaml.dump(yaml_root), end='')
            #sys.exit()
            #ruamel.yaml.dump(yaml_root, sys.stdout, allow_unicode=True)
            assert not yaml_root is None, 'YAML <%s> load error' % yamlfile
            # print(type(yaml_root))
            # #yml.dump(yaml_root, sys.stdout)
            # print(type(yaml_root['inventory']['library-lua'][0]['apt']['git']))
            # print(type(yaml_root.get('inventory').get('library-lua')[0].get('apt').get('git')))
            # exit(0)
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
