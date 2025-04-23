from __future__ import annotations
import pygame as pg
import random
from time import time, sleep
import logging
import itertools as it
from config import *
import psutil
import os
import traceback

try:
    import laptop
    TESTMODE = True
except ModuleNotFoundError:
    TESTMODE = False

if TESTMODE:
    import vserial as serial
    print("""
********************************************************************************
          ACHTUNG!!! Das Programm laeuft aktuell im Testmodus! Das sollte auf dem Raspberry nicht passieren.
          Falls du nicht genau weißt, dass du den Testmodus moechtest, willst du ihn nicht!
******************************************************************************** 
          """)
    sleep(1)
else:
    import serial


left = 200
top = 100
size = 300
pad = 5
frame_color = (50, 50, 50)
bg_color = "black"

# forbidden combos of fields
FORBIDDEN = [{0, 8}, {2, 6}]

# maximum uptime till shutdown (in s)
UPTIME = (6*60 - 5) * 60

# time after last interaction till the current game is stopped
STANDBY_TIMEOUT = 15

bg_standby = pg.image.load(IM_FOLDER + "BG_Standby.png")
bg_standby = pg.transform.scale(bg_standby, (1920, 1080))

bg_game = pg.image.load(IM_FOLDER + "BG_Game.png")
bg_game = pg.transform.scale(bg_game, (1920, 1080))


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


def draw_game_bg(screen: pg.Surface, font: pg.font.Font, cur_score, highscore, draw_field=True):
    screen.blit(bg_game, (0, 0))
    if draw_field:
        for i in range(9):
            pg.draw.rect(screen, frame_color, rect_for_idx(i, pad=False), 2)
    text = font.render(str(cur_score), True, "white", bg_color)
    textRect = text.get_rect()
    textRect.center = (1440, 260)
    screen.blit(text, textRect)
    text = font.render(str(max(cur_score, highscore)), True, "white", bg_color)
    textRect = text.get_rect()
    textRect.center = (1440, 580)
    screen.blit(text, textRect)


def draw_text(screen: pg.Surface, msg: str, font: pg.font.Font):
    lines = msg.split("\n")
    y = 300
    for line in lines:
        text = font.render(line, True, "white", bg_color)
        textRect = text.get_rect()
        textRect.centerx = 600
        textRect.top = y
        y += textRect.height
        screen.blit(text, textRect)


def draw_rect_with_color(screen, i, color=None):
    if color is None:
        color = color_for_rect(i)
    pg.draw.rect(screen, color, rect_for_idx(i))


def get_uptime():
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
    except FileNotFoundError:
        if not TESTMODE:
            raise
        uptime_seconds = 0

    return uptime_seconds


class ParallelInstanceRunning(RuntimeError):
    pass


class Root:
    def __init__(self):
        c = 0
        c2 = 0
        for name in map(lambda pc: pc.name(), psutil.process_iter(attrs=["name"])):
            if "python3" in name:
                c += 1
            if "py" in name:
                c2 += 1
        if c >= 2 and not TESTMODE:
            self.running = False
            raise ParallelInstanceRunning(f"{c-1} parallel instance(s) found")
        elif c == 0:
            print(f"No process with 'python3' but {c2} with 'py' found")

        self.day = 0
        while os.path.exists(FOLDER + f"highscore{self.day:03d}"):
            self.day += 1

        f_idx = 0
        while os.path.exists(FOLDER + f"log{f_idx:03d}.txt"):
            f_idx += 1
        logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s", level=logging.INFO, filename=FOLDER + f"log{f_idx:03d}.txt", datefmt="%Y-%m-%d %H:%M:%S")
        logging.getLogger().addHandler(logging.StreamHandler())
        logging.info(f"--- Day {self.day} ---")
        self.ser1 = serial.Serial(SER1, timeout=2)
        self.ser2 = serial.Serial(SER2, timeout=2)
        sleep(2)
        # set threshold to 10
        self.send_to_ser(12)
        self.send_to_ser(10)
        pg.init()
        if not TESTMODE:
            self.screen = pg.display.set_mode((0, 0), pg.FULLSCREEN)
        else:
            self.screen = pg.display.set_mode((1920, 1080))
        self.clock = pg.time.Clock()
        self.running = True
        self.active_scene: Scene = None
        self.set_new_scene(WaitForNewGameScene(self))
        self.numfont = pg.font.Font(FONT, 140)
        self.msgfont = pg.font.Font(FONT, 80)
        self.steps = 0
        if get_uptime() > UPTIME:
            self.running = False
            return
        try:
            with open(FOLDER + "highscore.txt") as f:
                val = int(f.read())
            self.daily_highscore = val
        except FileNotFoundError:
            self.daily_highscore = 0
        
    @property
    def daily_highscore(self):
        return self._daily_highscore
    
    @daily_highscore.setter
    def daily_highscore(self, value):
        self._daily_highscore = value
        with open(FOLDER + "highscore.txt", "w") as f:
            f.write(str(self._daily_highscore))

    def mainloop(self):
        while self.running:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.running = False
                elif event.type == pg.MOUSEBUTTONDOWN:
                    print(event.pos)
            if self.steps % 100 == 0:
                self.check_uptime()
            self.active_scene.check_for_event()
            self.screen.fill(bg_color)
            self.active_scene.draw_on_screen(self.screen)
            pg.display.flip()
            self.steps += 1
            sleep(1 / 60)
        pg.quit()

    def set_new_scene(self, scene: Scene):
        self.active_scene = scene
        print(f"Started scene {scene.__class__.__name__}")
        self.ser1.read_all()
        self.ser2.read_all()

    def send_to_ser(self, msg: int):
        for ser in (self.ser1, self.ser2):
            ser.write(bytes((msg,)))

    def check_uptime(self):
        if get_uptime() > UPTIME:
            self.running = False


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
            while new == self.sequence[-1] or {new, self.sequence[-1]} in FORBIDDEN:
                new = random.randint(0, 8)
        else:
            new = random.randint(0, 8)
        self.sequence.append(new)
        seq_str = " ".join(map(str, self.sequence))
        logging.info(f"Sequence is {seq_str}")
        self.start_time = time()
        self._last_field = 11

    def check_for_event(self):
        if time() - self.start_time > self.wait * len(self.sequence):
            self.root.set_new_scene(EchoScene(self.root, self.sequence))
        f = self.cur_field()
        if f != self._last_field and f is not None:
            self.root.send_to_ser(f)
            self._last_field = f
    
    def cur_field(self):
        would_take_time = 0
        for element in self.sequence:
            would_take_time += self.wait * min(1, max(0, 1-(len(self.sequence) - 10)/30))
            if time() - would_take_time < self.start_time:
                return element
        return self.sequence[-1]

    def draw_on_screen(self, screen):
        field = self.cur_field()
        draw_game_bg(screen, self.root.numfont, len(self.sequence) - 1, self.root.daily_highscore)
        draw_rect_with_color(screen, field)


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
            if time() - self.last_event_time > STANDBY_TIMEOUT:
                logging.info("Standby")
                score = len(self.sequence) - 1
                if self.root.daily_highscore < score:
                    self.root.daily_highscore = score
                    logging.info(f"New highscore {self.root.daily_highscore}")
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
                    logging.info(f"Answer was {max_idx} with value {max_val}")
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
        draw_game_bg(screen, self.root.numfont, len(self.sequence) - 1, self.root.daily_highscore)
        if self.last_field is not None:
            draw_rect_with_color(screen, self.last_field)


class MistakeScene(Scene):
    stay_on_screen = 5

    def __init__(self, root: Root, score: int):
        self.start_time = time()
        self.root = root
        self.score = score
        logging.info(f"Mistake. Score was {self.score}")
        if score <= 3:
            msgs = [
                "Schade, das war\ndas falsche Feld :(",
                "Leider falsch...",
                "Nicht ganz richtig..."
            ]
        elif score <= 6:
            msgs = [
                f"Nach {score} richtigen Feldern\nein kleiner Fehler...\nSehr stark!",
                f"{score} Felder - super!",
                f"Du hast {score} Felder\nrichtig - Respekt :)"
            ]
        if self.root.daily_highscore < score:
            self.root.daily_highscore = score
            logging.info(f"New highscore {self.root.daily_highscore}")
            msgs = ["Du hast den\nHighscore gebrochen!!!\nHerzlichen Glückwunsch!"]
        self.msg = random.choice(msgs)

    def check_for_event(self):
        if time() - self.start_time > self.stay_on_screen:
            self.root.set_new_scene(WaitForNewGameScene(self.root))

    def draw_on_screen(self, screen: pg.Surface):
        draw_game_bg(screen, self.root.numfont, self.score, self.root.daily_highscore, draw_field=False)
        draw_text(screen, self.msg, self.root.msgfont)


class SuccessScene(Scene):
    stay_on_screen = 2

    def __init__(self, root, seq):
        super().__init__(root)
        self.start_time = time()
        self.seq = seq
        score = len(self.seq)
        msgs = [
            "Super!",
            "Gut gemacht!",
            "Sehr gut!",
        ]
        if score > 3:
            msgs.extend([
                "Glückwunsch, alles richtig!",
                "Schon wieder richtig!",
                "Alles perfekt :)",
            ])
        if score > 6:
            msgs.extend([
                "Wow, du hast ein\ngutes Gedächtnis ;)",
                "Richtig stark!",
                "Immer noch alles richtig!",
            ])
        self.msg = random.choice(msgs)

    def check_for_event(self):
        if time() - self.start_time > self.stay_on_screen:
            # self.root.send_to_ser(11)
            self.root.set_new_scene(PresentScene(self.root, sequence=self.seq))

    def draw_on_screen(self, screen: pg.Surface):
        score = len(self.seq)
        draw_game_bg(screen, self.root.numfont, score, self.root.daily_highscore, draw_field=False)
        draw_text(screen, self.msg, self.root.msgfont)


class WaitForNewGameScene(Scene):
    def __init__(self, root):
        super().__init__(root)
        self.root.ser1.reset_input_buffer()
        self.root.ser1.reset_input_buffer()
        self.root.send_to_ser(16)
        logging.info("Config check")
        logging.info("From ser1:")
        logging.info(self.root.ser1.readline().decode()[:-1])
        logging.info(self.root.ser1.readline().decode()[:-1])
        logging.info(self.root.ser1.readline().decode()[:-1])
        logging.info("From ser2:")
        logging.info(self.root.ser2.readline().decode()[:-1])
        logging.info(self.root.ser2.readline().decode()[:-1])
        logging.info(self.root.ser2.readline().decode()[:-1])
        self.start_time = time()
        self.blinks = 0

    def check_for_event(self):
        s1, s2 = self.root.ser1, self.root.ser2
        for s in (s1, s2):
            if s.in_waiting > 0:
                logging.info(f"Started game with {s.read()[0]} and val {s.read()[0]}")
                self.root.set_new_scene(PresentScene(self.root))
        if time() - self.start_time >= 2 * self.blinks:
            self.root.send_to_ser(random.randint(0, 8))
            self.blinks += 1

    def draw_on_screen(self, screen: pg.Surface):
        screen.blit(bg_standby, (0, 0))
        text = self.root.numfont.render(str(self.root.daily_highscore), True, "white", bg_color)
        textRect = text.get_rect()
        textRect.center = (920, 970)
        screen.blit(text, textRect)


if __name__ == "__main__":
    root = Root()
    try:
        root.mainloop()
    except Exception as e:
        logging.error(str(e))
        for l in traceback.format_exception(e):
            logging.info(l[:-1])
        raise
