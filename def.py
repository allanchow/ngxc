#/usr/bin/python3
import itertools

class Session:
  def __init__(self):
    self.a = 1


class Ngx:
  def __init__(self, sess):
    self.session = sess

def hhh():
  yield 2

def ddd():
  for i in [1,2,3]:
    v = hhh()
    if v is not None:
      for h in v:
        yield h
    yield i


for a in ddd():
  print(a)
