import socket
import keyboard as kb
import numpy as np
import pygame as pg

s = socket.socket()
s.bind(("", 8888))
s.listen(1)
c, addr = s.accept()

print(f"Connected to {addr}")

for i in range(9):
    kb.add_hotkey(f"{(7-3*(i // 3)+(i % 3))}", c.send, args=(bytes((i,)),))
kb.add_hotkey("space", c.send, args=(bytes((9,)),))

pg.mixer.init()

field_sounds = [pg.mixer.Sound(f"sounds/{i}.wav") for i in range(9)]
win_sound = pg.mixer.Sound("sounds/win.wav")
lost_sound = pg.mixer.Sound("sounds/lost.mp3")

try:
    while True:
        msg = c.recv(1)
        if len(msg) == 0:
            break
        if msg[0] < 9:
            msg = msg[0]
            field_sounds[msg].play()
        elif msg[0] == 9:
            win_sound.play()
        elif msg[0] == 10:
            lost_sound.play()
        else:
            msg = msg.decode()
        # print("Correct:", msg)
    print("Host closed connection")
finally:
    print("Ended")
    c.close()
