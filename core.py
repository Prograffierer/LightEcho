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
import numpy as np
from serial_socket import SerialSocket

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


left = 210
top = 50
size = 290
pad = 5
frame_color = (255, 255, 255)
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

bg_game_2 = pg.image.load(IM_FOLDER + "BG_Game_2.png")
bg_game_2 = pg.transform.scale(bg_game_2, (1920, 1080))

bg_game_empty = pg.image.load(IM_FOLDER + "BG_Game_empty.png")
bg_game_empty = pg.transform.scale(bg_game_empty, (1920, 1080))

bg_game_empty_2 = pg.image.load(IM_FOLDER + "BG_Game_empty_2.png")
bg_game_empty_2 = pg.transform.scale(bg_game_empty_2, (1920, 1080))


def color_for_rect(i):
    hsva = (100 / 9 * i, 100, 100, 100)
    color = pg.color.Color(0, 0, 0)
    color.hsva = hsva
    return color.r, color.g, color.b


def rect_for_idx(i, pad=2):
    if pad:
        return pg.Rect(
            left + size * (i % 3) + pad, top + size * (i // 3) + pad, size - 2*pad, size - 2*pad
        )
    else:
        return pg.Rect(left + size * (i % 3), top + size * (i // 3), size, size)


def draw_game_bg(screen: pg.Surface, font: pg.font.Font, cur_score, highscore, draw_field=True, hint=False, dont_jump=True, kl_logo=True):
    if hint:
        screen.blit(bg_game_2, (0, 0))
    else:
        if dont_jump:
            screen.blit(bg_game, (0, 0))
        else:
            if kl_logo:
                screen.blit(bg_game_empty, (0, 0))
            else:
                screen.blit(bg_game_empty_2, (0, 0))
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


def draw_text(screen: pg.Surface, msg: str, font: pg.font.Font, color="white"):
    lines = msg.split("\n")
    y = 300
    for line in lines:
        text = font.render(line, True, color, bg_color)
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
        # uptime_seconds = (time() - laptop.global_start_time) * 60 * 4
        uptime_seconds = 0

    return uptime_seconds


class ParallelInstanceRunning(RuntimeError):
    pass


class Config:
    MIN_FACTOR = 0.2

    def __init__(self, root: Root):
        self.root = root
        self.autopilot = AUTOPILOT
        # try:
        #     self._factors = np.loadtxt(FOLDER + "factors.txt")
        # except FileNotFoundError:
        #     self._factors = np.ones((9,))
        self._factors = np.ones((9,), dtype=float)
        self._factors[DEACTIVATE] = 0
        self._factors[self._factors < self.MIN_FACTOR] = 0
        try:
            self._factors[DEACTIVATE] = 0
        except IndexError:
            pass
        try:
            with open(FOLDER + "threshold.txt") as f:
                val = int(f.read())
            self.threshold = val
        except (FileNotFoundError, ValueError) as e:
            # logging.error("Exception in load of threshold.txt:", str(e))
            self.threshold = 10
        self.send_config()
        self.set_max_vals()

    def send_config(self):
        if not self.autopilot:
            logging.warning("Attempted a send_config() when autopilot was off")
            return
        for i, factor in enumerate(self._factors):
            self.root.send_to_ser(13)
            self.root.send_to_ser(i)
            self.root.send_to_ser(int(255*factor))
        self.root.send_to_ser(12)
        self.root.send_to_ser(self.threshold)

    def store_factors(self):
        np.savetxt(FOLDER + "factors.txt", self._factors, fmt="%.3f")

    def multiply_factor(self, field, coeff):
        if self.autopilot:
            self[field] = self[field] * coeff
        else:
            logging.warning("Attempted a multiply_factor when autopilot was off")

    def reset_to_full_sensitivity(self):
        if self.autopilot:
            for i in range(9):
                if i != DEACTIVATE:
                    self[i] = 0.9

    def set_max_vals(self):
        self._max_vals = self._factors.copy()

    def unexpected_signal(self, correct, false):
        diff = abs(correct // 3 - false // 3) + abs(correct % 3 - false % 3)
        if diff <= 1 and self.autopilot:
            logging.info(f"Autopilot: Shifted {correct} up and {false} down")
            # self[correct] = self[correct] * 1.05
            # self[false] = self[false] * 0.95
            if self.autopilot:
                self._factors[correct] /= 0.92
                self._factors[false] *= 0.92
                self.rescale()
    
    def rescale(self):
        if self.autopilot:
            try:
                mask = (self._max_vals > 0) & (self._factors > 0)
                self._factors *= np.min(self._max_vals[mask] / self._factors[mask])
                self._factors[self._factors < self.MIN_FACTOR] = 0
                self.store_factors()
                self.send_config()
                # if np.sum(self._factors == 0) > 5:
                #     logging.warning(f"{np.sum(self._factors == 0)} field deactivated - turning Autopilot off")
                #     self.autopilot = False
            except AttributeError:
                logging.warning("Attempted a rescaling when no max_vals where set")

    def __getitem__(self, key):
        return self._factors[key]

    def __setitem__(self, key, factor: float):
        if self.autopilot:
            if factor > 1.0:
                factor = 1
            if factor < self.MIN_FACTOR:
                factor = 0
            if key == DEACTIVATE:
                logging.warning(f"Attempted a change of deactivated field {key} to {factor}")
                factor = 0
            logging.info(f"Autopilot: Set factor {key} to {factor}")
            self._factors[key] = factor
            self.root.send_to_ser(13)
            self.root.send_to_ser(key)
            self.root.send_to_ser(int(255*factor))
            self.store_factors()
            if np.sum(self._factors == 0) > 3:
                logging.warning(f"{np.sum(self._factors == 0)} field deactivated - turning Autopilot off")
                self.autopilot = False
        else:
            logging.warning(f"Attempted a change of factor {key} to {factor} when autopilot was off")

    @property
    def threshold(self):
        return self._threshold
    
    @threshold.setter
    def threshold(self, val):
        if self.autopilot:
            self._threshold = int(val)
            logging.info(f"Autopilot: Threshold set to {self._threshold}")
            self.root.send_to_ser(12)
            self.root.send_to_ser(self.threshold)
            with open(FOLDER + "threshold.txt", "w") as f:
                f.write(str(self._threshold))
        else:
            logging.warning(f"Attempted a change of threshold to {val} when autopilot was off")

    @property
    def autopilot(self):
        return self._autopilot
    
    @autopilot.setter
    def autopilot(self, val):
        self._autopilot = bool(val)
        if not self._autopilot:
            self._factors = np.array(FACTORS)
            self._threshold = THRESH
            self.send_config()

    @property
    def deactivated(self):
        deact = set(np.nonzero(self._factors == 0)[0])
        deact.add(DEACTIVATE)
        return deact


class Root:
    min_factor = 0.2

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
        while os.path.exists(FOLDER + f"highscore{self.day:03d}.txt"):
            self.day += 1
        # if self.day == 0:
        #     global UPTIME
        #     UPTIME = (2*60 + 15) * 60

        f_idx = 0
        while os.path.exists(FOLDER + f"log{f_idx:03d}.txt"):
            f_idx += 1
        logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s", level=logging.DEBUG, filename=FOLDER + f"log{f_idx:03d}.txt", datefmt="%Y-%m-%d %H:%M:%S")
        logging.getLogger().addHandler(logging.StreamHandler())
        logging.info(f"--- Day {self.day} ---")
        self.ser1 = serial.Serial(SER1, timeout=2)
        self.ser2 = serial.Serial(SER2, timeout=2)
        self.ser_in = SerialSocket() # TODO
        sleep(2)
        self.config = Config(self)
        self.config.autopilot = False
        for s in [self.ser1, self.ser2]:
            for idx in range(9):
                s.write(bytes((13,)))
                s.write(bytes((idx,)))
                s.write(bytes((0,)))
        pg.init()
        if not TESTMODE:
            self.screen = pg.display.set_mode((0, 0), pg.FULLSCREEN)
        else:
            self.screen = pg.display.set_mode((1920, 1080))
        self.clock = pg.time.Clock()
        self.running = True
        self.active_scene: Scene = None
        self.set_new_scene(WaitForNewGameScene(self))
        # self.set_new_scene(CalibrationScene(self))
        self.last_calibration_time = 0
        self.numfont = pg.font.Font(FONT, 140)
        self.msgfont = pg.font.Font(FONT, 80)
        if not TESTMODE:
            pg.mouse.set_visible(False)
        self.steps = 0
        # if get_uptime() > UPTIME:
        #     self.running = False
        #     return
        try:
            with open(FOLDER + "highscore.txt") as f:
                val = int(f.read())
            self.daily_highscore = val
        except (FileNotFoundError, ValueError):
            self.daily_highscore = 0
        self.error_msg = None
        
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
            content = ""
            if self.steps % 100 == 0:
                self.check_uptime()
                with open(FOLDER + "msg.txt") as f:
                    content = f.read()
                if len(content) > 3:
                    self.error_msg = content
                else:
                    self.error_msg = None
            self.active_scene.check_for_event()
            self.screen.fill(bg_color)
            self.active_scene.draw_on_screen(self.screen)
            if self.error_msg is not None:
                text = self.msgfont.render(self.error_msg, True, "white", bg_color)
                textRect = text.get_rect()
                textRect.center = (1920//2, 1080//2)
                self.screen.blit(text, textRect)
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
        pass
        # if get_uptime() > UPTIME:
        #     self.running = False
        #     logging.info("Controlled shutdown")
        #     with open(FOLDER + f"highscore{self.day:03d}.txt", "w") as f:
        #         f.write(str(self.daily_highscore))
        #     with open(FOLDER + "highscore.txt", "w") as f:
        #         f.write("0")


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
            new = DEACTIVATE
            while new in self.root.config.deactivated:
                new = random.randint(0, 8)
            self.sequence.append(new)
            new = self.sequence[-1]
            while new == self.sequence[-1] or {new, self.sequence[-1]} in FORBIDDEN or new in self.root.config.deactivated or new == self.sequence[0]:
                new = random.randint(0, 8)
            self.sequence.append(new)


class IntroScene(Scene):
    wait = 2

    def __init__(self, root):
        super().__init__(root)
        self.start_time = time()
        
    def check_for_event(self):
        if time() - self.start_time > 3 * self.wait:
            self.root.set_new_scene(PresentScene(self.root))

    def draw_on_screen(self, screen):
        draw_game_bg(screen, self.root.numfont, cur_score=0, highscore=self.root.daily_highscore, draw_field=False, dont_jump=False)
        if time() - self.start_time <= self.wait:
            msg = "Warte, bis wir\ndie komplette Abfolge\nangezeigt haben"
        elif time() - self.start_time <= 2 * self.wait:
            msg = "Laufe sie dann\nauf dem Spielfeld nach"
        else:
            msg = "Warte jedes Mal,\nbis das aktuelle\nFeld aufleuchtet"
        draw_text(screen, msg, self.root.msgfont, color="orange")


class PresentScene(SequenceScene):
    wait = 1

    def __init__(self, root, sequence=None):
        super().__init__(root, sequence)
        if len(self.sequence) > 0:
            new = self.sequence[-1]
            while new == self.sequence[-1] or {new, self.sequence[-1]} in FORBIDDEN or new in self.root.config.deactivated or new == self.sequence[0]:
                new = random.randint(0, 8)
        else:
            new = DEACTIVATE
            while new in self.root.config.deactivated:
                new = random.randint(0, 8)
        self.sequence.append(new)
        seq_str = " ".join(map(str, self.sequence))
        logging.info(f"Sequence is {seq_str}")
        self.start_time = time()
        self._last_field = 11
        self.hint_font = pg.font.Font(FONT, 80)

    def check_for_event(self):
        if time() - self.start_time > self.wait * len(self.sequence):
            self.root.set_new_scene(EchoScene(self.root, self.sequence))
        f = self.cur_field()
        if f != self._last_field and f is not None:
            self.root.send_to_ser(f)
            self.root.ser_in.send(bytes((f,)))
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
        draw_game_bg(screen, self.root.numfont, len(self.sequence) - 1 if len(self.sequence) > 3 else 0, self.root.daily_highscore, dont_jump=False)
        draw_rect_with_color(screen, field)
        pg.draw.rect(screen, "darkorange", pg.Rect(left - 20, top - 20, 3*size + 40, 3*size + 40), 10, border_radius=10)
        text = self.hint_font.render("Gut aufpassen...", True, "orange", bg_color)
        textRect = text.get_rect()
        textRect.center = (650, 1000)
        screen.blit(text, textRect)


class EchoScene(SequenceScene):
    def __init__(self, root: Root, sequence=None):
        super().__init__(root, sequence)
        self.ser1 = self.root.ser1
        self.ser2 = self.root.ser2
        self.ser_in = self.root.ser_in
        self.send_to_ser = self.root.send_to_ser
        self.ser1.read_all()
        self.ser2.read_all()
        self.ser_in.reset()
        self.send_to_ser(11)
        self.last_field: int = None
        self.remaining_sequence = self.sequence.copy()
        self.last_error = ""
        self.error_count = 0
        self.last_event_time = time()
        self.hint_font = pg.font.Font(FONT, 70)
        self.ser_in.send(bytes((self.remaining_sequence[0],)))

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
            if self.ser_in.is_available:
                pg.time.delay(100)
                # s1 = s2 = "00000"
                # s1 = self.ser1.read_all()
                # s2 = self.ser2.read_all()
                # s = max(s1, s2, key=lambda s: self.decode(s)[1])
                max_idx = self.ser_in.get_field()
                # max_idx = self.decode(s)[0]
                # max_val = self.decode(s)[1]
                # assert max_val > 0
                self.last_event_time = time()
                if self.last_field == max_idx:
                    logging.warning(
                        f"Field {max_idx} was reported twice"
                    )
                    self.send_to_ser(self.last_field)
                else:
                    self.last_field = max_idx
                    logging.info(f"Answer was {max_idx}")
                    correct = self.remaining_sequence.pop(0)
                    if not correct == max_idx:
                        self.last_field = correct
                        self.send_to_ser(10)
                        self.root.set_new_scene(
                            MistakeScene(self.root, len(self.sequence)-1 if len(self.sequence) > 3 else 0, self)
                        )
                        if len(self.sequence) > 4 and len(self.remaining_sequence) > 0:
                            self.root.config.unexpected_signal(correct, max_idx)
                        return
                    self.resume()
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

    def resume(self):
        if len(self.remaining_sequence):
            self.send_to_ser(self.last_field)
            # self.ser_in.send(bytes((self.remaining_sequence[0],)))
            self.ser_in.send(bytes((self.last_field,)))
            # print(f"Sent {self.remaining_sequence[-1]}")
        else:
            self.send_to_ser(9)
            self.root.set_new_scene(SuccessScene(root, self.sequence))

    @staticmethod
    def decode(msg: bytes):
        if len(msg) == 0:
            return 0, 0
        field = int(msg[-2])
        value = int(msg[-1])
        return field, value

    def draw_on_screen(self, screen):
        seq_len = len(self.sequence)
        if seq_len == 3:
            seq_len = 1
        stampfen = time() - self.last_event_time > 5
        draw_game_bg(screen, self.root.numfont, seq_len - 1, self.root.daily_highscore, hint=False, dont_jump=not stampfen, kl_logo=not stampfen)
        if self.last_field is not None:
            draw_rect_with_color(screen, self.last_field)
        # if seq_len == 1:
        #     msg = "Betritt das Feld, das gerade angezeigt wurde"
        # elif seq_len == 2:
        #     if len(self.remaining_sequence) == 2:
        #         msg = "Betritt das erste Feld in der Abfolge"
        #     else:
        #         msg = "Sehr gut! Jetzt das zweite Feld"
        if stampfen:
            msg = "Manchmal ist vorsichtiges Stampfen nötig"
        try:
            text = self.hint_font.render(msg, True, "white", bg_color)
            textRect = text.get_rect()
            textRect.center = (1920//2, 1000)
            screen.blit(text, textRect)
        except UnboundLocalError:
            pass
        if len(self.remaining_sequence) == len(self.sequence):
            text = self.root.msgfont.render("Und jetzt du!", True, "white", bg_color)
            textRect = text.get_rect()
            textRect.center = (left + 1.5*size, top + 1.5*size)
            screen.blit(text, textRect)


class MistakeScene(Scene):
    stay_on_screen = 5

    def __init__(self, root: Root, score: int, last_echo_scene: EchoScene):
        self.start_time = time()
        self.root = root
        self.last_echo_scene = last_echo_scene
        self.score = score
        logging.info(f"Mistake. Score was {self.score}")
        if score <= 4:
            msgs = [
                "Schade, das war\ndas falsche Feld :(",
                "Leider falsch...",
                "Nicht ganz richtig..."
            ]
        else:
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
        if self.root.ser_in.was_right():
            self.root.set_new_scene(self.last_echo_scene)
            self.last_echo_scene.resume()

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
        logging.debug("Config check")
        logging.debug("From ser1:")
        logging.debug(self.root.ser1.readline().decode()[:-1])
        logging.debug(self.root.ser1.readline().decode()[:-1])
        logging.debug(self.root.ser1.readline().decode()[:-1])
        logging.debug("From ser2:")
        logging.debug(self.root.ser2.readline().decode()[:-1])
        logging.debug(self.root.ser2.readline().decode()[:-1])
        logging.debug(self.root.ser2.readline().decode()[:-1])
        with open(FOLDER + "msg.txt", "w") as f:
            pass
        self.start_time = time()
        self.blinks = 0

    def check_for_event(self):
        # s1, s2 = self.root.ser1, self.root.ser2
        # for s in (s1, s2):
        s = self.root.ser_in
        if s.is_available > 0:
            logging.info("Game started")
            # logging.info(f"Started game with {s.read()[0]} and val {s.read()[0]}")
            self.root.set_new_scene(IntroScene(self.root))
            return
        # if time() - self.root.last_calibration_time >= 60*60 and self.root.config.autopilot and not TESTMODE:
        #     self.root.set_new_scene(CalibrationScene(root))
        if time() - self.start_time >= 2 * self.blinks:
            self.root.send_to_ser(random.randint(0, 8))
            self.blinks += 1

    def draw_on_screen(self, screen: pg.Surface):
        screen.blit(bg_standby, (0, 0))
        text = self.root.numfont.render(str(self.root.daily_highscore), True, "white", bg_color)
        textRect = text.get_rect()
        textRect.center = (940, 930)
        screen.blit(text, textRect)


class CalibrationScene(Scene):
    bg_calibration = pg.image.load(IM_FOLDER + "BG_Calibration.png")
    bg_calibration = pg.transform.scale(bg_calibration, (1920, 1080))

    TIME = 180

    def __init__(self, root, coeff=0.9, dont_reset=False):
        super().__init__(root)
        if not self.root.config.autopilot:
            self.root.set_new_scene(WaitForNewGameScene(root))
            logging.warning("Attempted starting a calibration when autopilot was off")
            return
        self.start_time = time()
        self.critical_signals = 0 # number of signals received in the last minute of calibration (should be at most 1)
        if not dont_reset:
            self.root.config.reset_to_full_sensitivity()
        else:
            logging.info("No reset to full sensitivity")
        self.coeff = coeff
        self.root.config.threshold = 4
        logging.info(f"Calibration started with coeff {coeff}")

    def draw_on_screen(self, screen: pg.Surface):
        screen.blit(self.bg_calibration, (0, 0))
        rem_time = self.TIME - (time() - self.start_time)
        mins = int(rem_time // 60)
        secs = int(rem_time % 60)
        text = self.root.numfont.render(f"{mins}:{secs:02d}", True, "white", bg_color)
        textRect = text.get_rect()
        textRect.center = (1630, 480)
        screen.blit(text, textRect)

    def check_for_event(self):
        if time() - self.start_time >= 5:
            for ser in self.root.ser1, self.root.ser2:
                if ser.in_waiting > 0:
                    try:
                        field, value = ser.read_all()[-2:]
                        logging.info(f"During calibration: Field {field} with val {value}")
                        self.root.config.multiply_factor(field, self.coeff)
                        # no send_to_ser required as multiply_factor does this already (updates the factors)
                        if time() - self.start_time >= self.TIME - 60:
                            self.critical_signals += 1
                            if self.critical_signals > 2:
                                logging.error(f"Calibration failed, we had {self.critical_signals} signals in the last minute")
                                self.root.set_new_scene(CalibrationScene(self.root, self.coeff * 0.8, dont_reset=True))
                    except ValueError as e:
                        logging.warning(e)
        if time() - self.start_time >= self.TIME:
            self.root.config.threshold = 5
            self.root.last_calibration_time = time()
            self.root.config.set_max_vals()
            self.root.set_new_scene(WaitForNewGameScene(self.root))


if __name__ == "__main__":
    root = Root()
    try:
        root.mainloop()
    except Exception as e:
        logging.error(str(e))
        for l in traceback.format_exception(e):
            logging.info(l[:-1])
        raise
