from __future__ import annotations
import pygame as pg
import random
from time import time
import serial


def color_for_rect(i):
    hsva = (256/9*i, 255, 255, 0)
    color = pg.color.Color(0, 0, 0)
    color.hsva = hsva
    return color.r, color.g, color.b


def draw_rect_with_color(screen, i, color=None):
    if color is None:
        color = color_for_rect(i)
    left = 200
    top = 200
    size = 50
    pad = 5
    pg.draw.rect(screen, color, pg.Rect(left + size * (i % 3), top + size * (i // 3), size - pad, size - pad))
    

class Root:
    def __init__(self):
        pg.init()
        self.screen = pg.display.set_mode((1280, 720))
        self.clock = pg.time.Clock()
        self.running = True
        self.active_scene: Scene = None
        self.ser1 = serial.Serial("COM3")
        self.ser2 = serial.Serial("COM5")

    def mainloop(self):
        while self.running:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.running = False
                self.active_scene.check_for_event()
                self.screen.fill("black")
                pg.display.flip()
                dt = self.clock.tick(60) / 1000
        pg.quit()
        self.clock.get_time()

    def set_new_scene(self, scene: Scene):
        self.active_scene = scene


class Scene:
    def draw_on_screen(self, screen):
        return screen
    
    def check_for_event(self):
        pass


class SequenceScene(Scene):
    def __init__(self, root, sequence=None):
        self.root: Root = root
        self.sequence = sequence
        if self.sequence is None:
            self.sequence = []


class PresentScene(SequenceScene):
    wait = 1

    def __init__(self, root, sequence=None):
        super().__init__(root, sequence)
        self.sequence.append(random.randint(0, 8))
        self.start_time = time()

    def check_for_event(self):
        if time() - self.wait * len(self.sequence):
            self.root.set_new_scene(EchoScene(self.root, self.sequence))

    def draw_on_screen(self, screen):
        would_take_time = 0
        for element in self.sequence:
            would_take_time += self.wait
            if time() - would_take_time < self.start_time:
                break
        return draw_rect_with_color(screen, element)
    

class EchoScene(SequenceScene):
    def __init__(self, root, sequence=None):
        super().__init__(root, sequence)
        self.ser1 = self.root.ser1
        self.ser2 = self.root.ser2
        self.ser1.read_all()
        self.ser2.read_all()

    def check_for_event(self):
        if self.ser1.
