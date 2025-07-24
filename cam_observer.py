import socket
import keyboard as kb
import numpy as np
import pygame as pg
from video_analysis import Observer

def callback(field):
    if field is not None:
        print(f"Signal on field {field}")
        c.send(bytes((field,)))
        print("Signal sent")
    try:
        msg = c.recv(1)
        print("Received sth")
        if len(msg) == 0:
            raise ConnectionAbortedError("Message with length 0 received")
        if msg[0] < 9:
            msg = msg[0]
            field_sounds[msg].play()
        elif msg[0] == 9:
            win_sound.play()
        elif msg[0] == 10:
            lost_sound.play()
        elif msg[0] == 37:
            observer.reset()
            print("Observer reset")
        else:
            msg = msg.decode()
    except BlockingIOError:
        pass


if __name__ == "__main__":
    observer = Observer()

    s = socket.socket()
    s.bind(("", 8888))
    s.listen(1)
    c, addr = s.accept()
    c.setblocking(False)

    print(f"Connected to {addr}")

    for i in range(9):
        kb.add_hotkey(f"{(7-3*(i // 3)+(i % 3))}", c.send, args=(bytes((i,)),))
    kb.add_hotkey("space", c.send, args=(bytes((9,)),))
    kb.add_hotkey("t", observer.toggle)

    pg.mixer.init()

    field_sounds = [pg.mixer.Sound(f"sounds/{i}.mp3") for i in range(9)]
    win_sound = pg.mixer.Sound("sounds/win.mp3")
    lost_sound = pg.mixer.Sound("sounds/lost.mp3")


    try:
        observer.observe(callback)
        print("Host closed connection")
    finally:
        print("Ended")
        c.close()
