from __future__ import annotations
import pygame as pg
import random
from time import time, sleep
import serial
import logging
import itertools as it
from config import *


left = 500
top = 200
size = 200
pad = 5
frame_color = (50, 50, 50)
bg_color = "black"


def color_for_rect(i):
    hsva = (100 / 9 * i, 100, 100, 100)
    color = pg.color.Color(0, 0, 0)
    color.hsva = hsva
    return color.r, color.g, color.b


def rect_for_idx(i, pad=True):
    if pad:
        return pg.Rect(
            left + size * (i % 3), top + size * (i // 3), size - pad, size - pad
        )
    else:
        return pg.Rect(left + size * (i % 3), top + size * (i // 3), size, size)


def draw_field_bg(screen):
    for i in range(9):
        pg.draw.rect(screen, frame_color, rect_for_idx(i, pad=False), 2)


def draw_rect_with_color(screen, i, color=None):
    if color is None:
        color = color_for_rect(i)
    pg.draw.rect(screen, color, rect_for_idx(i))


class Root:
    def __init__(self):
        # if they are already blocked, an error is raised immediately and the script ends without opening a pygame window
        self.ser1 = serial.Serial(SER1)
        self.ser2 = serial.Serial(SER2)
        pg.init()
        self.screen = pg.display.set_mode((0, 0), pg.FULLSCREEN)
        self.clock = pg.time.Clock()
        self.running = True
        self.active_scene: Scene = None
        self.set_new_scene(WaitForNewGameScene(self))
        self.textfont = pg.font.Font("ARIBLK.TTF", 100)
        self.daily_highscore = 0
        
    @property
    def daily_highscore(self):
        return self._daily_highscore
    
    @daily_highscore.setter
    def daily_highscore(self, value):
        self._daily_highscore = value
        # TODO: save this value and load it at startup

    def mainloop(self):
        while self.running:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.running = False
            self.active_scene.check_for_event()
            self.screen.fill(bg_color)
            self.active_scene.draw_on_screen(self.screen)
            pg.display.flip()
            sleep(1 / 60)
        pg.quit()
        self.clock.get_time()

    def set_new_scene(self, scene: Scene):
        self.active_scene = scene
        print(f"Started scene {scene.__class__.__name__}")
        self.ser1.read_all()
        self.ser2.read_all()

    def send_to_ser(self, msg: int):
        for ser in (self.ser1, self.ser2):
            ser.write(bytes((msg,)))


class Scene:
    def __init__(self, root):
        self.root: Root = root

    def draw_on_screen(self, screen):
        return screen

    def check_for_event(self):
        pass


class SequenceScene(Scene):
    def __init__(self, root, sequence=None):
        super().__init__(root)
        self.sequence = sequence
        if self.sequence is None:
            self.sequence = []


class PresentScene(SequenceScene):
    wait = 1

    def __init__(self, root, sequence=None):
        super().__init__(root, sequence)
        if len(self.sequence) > 0:
            new = self.sequence[-1]
            while new == self.sequence[-1]:
                new = random.randint(0, 8)
        else:
            new = random.randint(0, 8)
        self.sequence.append(new)
        self.start_time = time()

    def check_for_event(self):
        if time() - self.start_time > self.wait * len(self.sequence):
            self.root.set_new_scene(EchoScene(self.root, self.sequence))

    def draw_on_screen(self, screen):
        would_take_time = 0
        for element in self.sequence:
            would_take_time += self.wait * min(1, max(0, 1-(len(self.sequence) - 10)/30))
            if time() - would_take_time < self.start_time:
                break
        draw_rect_with_color(screen, element)
        draw_field_bg(screen)


class EchoScene(SequenceScene):
    def __init__(self, root: Root, sequence=None):
        super().__init__(root, sequence)
        self.ser1 = self.root.ser1
        self.ser2 = self.root.ser2
        self.send_to_ser = self.root.send_to_ser
        self.ser1.read_all()
        self.ser2.read_all()
        self.send_to_ser(11)
        self.last_field: int = None
        self.remaining_sequence = self.sequence.copy()
        self.last_error = ""
        self.error_count = 0
        self.last_event_time = time()

    def check_for_event(self):
        try:
            if time() - self.last_event_time > 20:
                self.root.set_new_scene(WaitForNewGameScene(self.root))
                return
            if self.ser1.in_waiting > 0 or self.ser2.in_waiting > 0:
                pg.time.delay(100)
                s1 = s2 = "00000"
                s1 = self.ser1.read_all()
                s2 = self.ser2.read_all()
                s = max(s1, s2, key=lambda s: self.decode(s)[1])
                max_idx = self.decode(s)[0]
                max_val = self.decode(s)[1]
                assert max_val > 0
                self.last_event_time = time()
                if self.last_field == max_idx:
                    logging.warning(
                        f"Field {max_idx} was reported twice, the second time with value {max_val}"
                    )
                    self.send_to_ser(self.last_field)
                else:
                    self.last_field = max_idx
                    if not self.remaining_sequence.pop(0) == max_idx:
                        self.send_to_ser(10)
                        self.root.set_new_scene(
                            MistakeScene(self.root, len(self.sequence)-1)
                        )
                        return
                    if len(self.remaining_sequence):
                        self.send_to_ser(self.last_field)
                    else:
                        self.send_to_ser(9)
                        self.root.set_new_scene(SuccessScene(root, self.sequence))
        except Exception as e:
            # here, everything can happen, from errors in the serial communication to parsing errors
            logging.error(e)
            if self.last_error == str(e):
                self.error_count += 1
                # if we have an error too often, that's probably a real problem, so we should restart the complete setup
                if self.error_count >= 10:
                    raise
            else:
                self.last_error = str(e)
                self.error_count = 1
            self.send_to_ser(11)

    @staticmethod
    def decode(msg: bytes):
        if len(msg) == 0:
            return 0, 0
        field = int(msg[-2])
        value = int(msg[-1])
        return field, value

    def draw_on_screen(self, screen):
        draw_field_bg(screen)
        if self.last_field is not None:
            draw_rect_with_color(screen, self.last_field)


class MistakeScene(Scene):
    stay_on_screen = 5

    def __init__(self, root: Root, score: int):
        self.start_time = time()
        self.root = root
        self.score = score
        if self.root.daily_highscore < score:
            self.root.daily_highscore = score

    def check_for_event(self):
        if time() - self.start_time > self.stay_on_screen:
            self.root.set_new_scene(WaitForNewGameScene(self.root))

    def draw_on_screen(self, screen: pg.Surface):
        text = self.root.textfont.render(f"{self.score} hast du geschafft!", True, "white", bg_color)
        textRect = text.get_rect()
        textRect.center = (1920//2, 300)
        screen.blit(text, textRect)


class SuccessScene(Scene):
    stay_on_screen = 2

    def __init__(self, root, seq):
        super().__init__(root)
        self.start_time = time()
        self.seq = seq

    def check_for_event(self):
        if time() - self.start_time > self.stay_on_screen:
            # self.root.send_to_ser(11)
            self.root.set_new_scene(PresentScene(self.root, sequence=self.seq))

    def draw_on_screen(self, screen: pg.Surface):
        text = self.root.textfont.render(f"Alles richtig!", True, "white", bg_color)
        textRect = text.get_rect()
        textRect.center = (400, 300)
        screen.blit(text, textRect)


class WaitForNewGameScene(Scene):
    def __init__(self, root):
        super().__init__(root)
        self.root.ser1.reset_input_buffer()
        self.root.ser1.reset_input_buffer()

    def check_for_event(self):
        s1, s2 = self.root.ser1, self.root.ser2
        for s in (s1, s2):
            if s.in_waiting > 0:
                self.root.set_new_scene(PresentScene(self.root))

    def draw_on_screen(self, screen):
        # TODO: Bild einfügen als Standbild für Warten
        text = self.root.textfont.render(f"Highscore: {self.root.daily_highscore}", True, "white", bg_color)
        textRect = text.get_rect()
        textRect.center = (800, 300)
        screen.blit(text, textRect)


if __name__ == "__main__":
    root = Root()
    root.mainloop()
