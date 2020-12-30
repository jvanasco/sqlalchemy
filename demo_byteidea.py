import dis
import time
import timeit
import sys



def normal(a):
    if isinstance(a, str):
        return True
    elif isinstance(a, int):
        return False
    return None


def improved(a, isinstance=isinstance, str=str, int=int):
    if isinstance(a, str):
        return True
    elif isinstance(a, int):
        return False
    return None


def factory(isinstance=isinstance, str=str, int=int):
    def _(a):
        if isinstance(a, str):
            return True
        elif isinstance(a, int):
            return False
        return None
    return _

factorized = factory()


print(normal("a"), normal(1), normal(None))
print(improved("a"), improved(1), improved(None))
print(factorized("a"), factorized(1), factorized(None))

number = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
print(timeit.timeit("normal(1)", setup="from __main__ import normal", number=number))
print(timeit.timeit("improved(1)", setup="from __main__ import improved", number=number))
print(timeit.timeit("factorized(1)", setup="from __main__ import factorized", number=number))

print ("=====")
print("normal")
print dis.dis(normal)
print ("-----")
print("improved")
print dis.dis(improved)
print ("-----")
print("factorized")
print dis.dis(factorized)


