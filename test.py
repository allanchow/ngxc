#!/usr/bin/env python3
import os

top = '/build/BUILDROOT/vm/lib/lua'
for root, dirs, files in os.walk(top, topdown=True):
  print(root)
  print(dirs)
  print(files)
