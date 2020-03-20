import schedula as sh

dsp = sh.Dispatcher()


def func(a, b):
    return a + b, sh.NONE


print(dsp.add_data('a', 1, 3))
print(dsp.add_func(func, inputs=['a', 'b'], outputs=['c', 'd']))
print(list(dsp({'b': 1}).items()))
