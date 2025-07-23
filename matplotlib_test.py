import matplotlib.pyplot as plt
import numpy as np
from time import perf_counter, sleep

def fun(x, slope):
    y = x*slope - 50
    return (y > 0) * y

x = np.linspace(0, 100, 200)

plt.ion()

l, = plt.plot(x, fun(x, 0))
# plt.bar()

start = perf_counter()

while True:
    plt.cla()
    plt.bar(x, fun(x, (perf_counter() - start) / 5), color=["red" if e else "blue" for e in x < 50])
    # l.set_ydata(fun(x, (perf_counter() - start) / 5))
    plt.pause(0.01)
    sleep(0.5)