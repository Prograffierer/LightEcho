from socket import timeout
from time import sleep
import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt
from multiprocessing import Process, Queue, Event
from threading import Event as TEvent
import json

# img = cv.imread("test_img.png")

class CamThread(Process):
    def __init__(self, idx, queue: Queue, stop_event: TEvent):
        super().__init__()
        self.setting_fname = f"settings/settings{idx}.json"
        self.idx = idx
        self.queue = queue
        self.stop_event = stop_event

    def load_settings(self):
        with open(self.setting_fname) as f:
            self.settings = json.load(f)
        # self.settings["intervals"] = np.array(self.settings["intervals"])

    def save_settings(self):
        # stngs = 
        # self.settings["intervals"] = np.array(self.settings["intervals"])
        with open(self.setting_fname, "w") as f:
            json.dump(self.settings, f)

    def reload_img(self):
        _, self.img = self.cap.read()

    def process_img(self):
        """intervals is a (9, 2) array:
        [[start_field0, end_field0], [...], ...] (start / end has to be in the right order)"""
        # img = cv.cvtColor(self.img, cv.COLOR_BGR2GRAY)
        img = self.img[..., 0].copy()

        intervals = self.settings["intervals"]

        _, thresh = cv.threshold(img, 254, 255, cv.THRESH_BINARY)
        # cv.imshow(f"thresh {self.idx}", thresh)

        thresh[:self.settings["top"]] = 0
        thresh[self.settings["bottom"]:] = 0

        kernel = np.ones((10, 15))
        thresh = cv.morphologyEx(thresh, cv.MORPH_CLOSE, kernel)
        self.thresh = thresh

        light = np.any(thresh, axis=0)

        percentage_light = np.zeros((9,))

        for i, interval in enumerate(intervals):
            part = light[interval[0]:interval[1]]
            percentage_light[i] = np.sum(part) / part.size

        self.percentage_light = percentage_light

    def action(self):
        return np.sum((self.percentage_light - self.last_perc_light)**2)

    # def too_much_action(self):
    #     return self.action() >= 0.2
    
    def possible_fields(self):
        return self.percentage_light <= 0.5 * (self.action() <= 0.2)
    
    def mouse_callback(self, event, x, y, flags, param):
        if event == cv.EVENT_LBUTTONDOWN:
            if self.config_mode == -1:
                self.settings["top"] = y
                self.save_settings()
            for i in range(9):
                if self.config_mode == i:
                    self.settings["intervals"][i][0] = x
                    self.save_settings()
        elif event == cv.EVENT_RBUTTONDOWN:
            if self.config_mode == -1:
                self.settings["bottom"] = y
                self.save_settings()
            for i in range(9):
                if self.config_mode == i:
                    self.settings["intervals"][i][1] = x
                    self.save_settings()
    
    def run(self):
        self.config_mode = None
        self.cap = cv.VideoCapture(self.idx)
        self.percentage_light = np.zeros((9,))
        cv.namedWindow(f"Raw img {self.idx}")
        cv.setMouseCallback(f"Raw img {self.idx}", self.mouse_callback)
        self.load_settings()
        self.reload_img()
        try:
            while not self.stop_event.is_set():
                self.last_perc_light = self.percentage_light.copy()
                self.reload_img()
                img = self.img.copy()
                if self.config_mode == -1:
                    img = cv.line(img, (0, self.settings["top"]), (1920, self.settings["top"]), (0, 0, 255), 1)
                    img = cv.line(img, (0, self.settings["bottom"]), (1920, self.settings["bottom"]), (0, 0, 255), 1)
                for i, intv in enumerate(self.settings["intervals"]):
                    if self.config_mode == i:
                        img = cv.line(img, (intv[0], 0), (intv[0], 1080), (0, 0, 255), 1)
                        img = cv.line(img, (intv[1], 0), (intv[1], 1080), (0, 0, 255), 1)
                cv.imshow(f"Raw img {self.idx}", img)
                self.process_img()
                cv.imshow(f"Thresh {self.idx}", self.thresh)
                self.queue.put((self.percentage_light, self.possible_fields(), self.action()), timeout=2)
                key = cv.waitKey(50)
                if key == 27:
                    self.stop_event.set()
                for i in range(9):
                    if key == ord(str(i)):
                        self.config_mode = i
                if key == ord("m"):
                    self.config_mode = -1
        finally:
            self.stop_event.set()
            self.cap.release()
            print(f"Process {self.idx} closed")

def darkest_field(*queues):
    # perc_light1 = process_img(img1, intervals1, 1)
    # perc_light2 = process_img(img2, intervals2, 2)

    # ax1.clear()
    # ax2.clear()
    # ax1.bar(np.arange(9), perc_light1, color=[])
    # ax2.bar(np.arange(9), perc_light2)
    perc_light = []
    possible = []
    for ax, queue in zip((ax1, ax2), queues):
        while queue.full():
            queue.get()
            sleep(0.01)
        pl, pssbl, action = queue.get(timeout=5)
        perc_light.append(pl)
        possible.append(pssbl)
        ax.clear()
        ax.bar(np.arange(9), pl, color=["orange" if p else "blue" for p in pssbl])

    overall_intensity = perc_light[0] + perc_light[1]
    overall_possible = possible[0] * possible[1]

    if not np.any(overall_possible):
        return None
    
    overall_intensity[~overall_possible] = 2

    # if np.sum(overall_intensity <= 1.3) > 1:
    #     return None

    idx = np.argmin(overall_intensity)

    # if perc_light1[idx] <= 0.6 and perc_light2[idx] <= 0.6:
    #     return idx

    return idx

def observe(callback=print):
    # cap1 = cv.VideoCapture(0)
    # cap2 = cap1

    # with np.load("settings/intervals.npz") as data:
    #     intervals1 = data["interv1"]
    #     intervals2 = data["interv2"]
    stop_event = Event()

    q0 = Queue(maxsize=2)
    p0 = CamThread(0, q0, stop_event)
    p0.start()

    q1 = Queue(maxsize=2)
    p1 = CamThread(1, q1, stop_event)
    p1.start()

    last_df = 0
    last_sent_df = 0
    try:
        while not stop_event.is_set():
            df = darkest_field(q0, q1)
            if last_df == df and last_sent_df != df:
                last_sent_df = df
                callback(df)
            last_df = df
            plt.pause(0.05)
    finally:
        stop_event.set()
        p0.join()
        p1.join()
        print("Finished")

if __name__ == "__main__":
    plt.ion()
    fig, (ax1, ax2) = plt.subplots(2, sharex=True)
    ax1.set_ylim(0, 1)
    ax2.set_ylim(0, 1)
    ax1.set_xlim(-1, 9)
    ax2.set_xlim(-1, 9)
    ax1.autoscale(False)
    ax2.autoscale(False)

    # intervals = np.array([
    #     [i*71, (i+1)*71] for i in range(9)
    # ])

    # np.savez("settings/intervals.npz", interv1=intervals, interv2=intervals)

    # cv.imshow("Raw image", img)

    # perc_light = process_img(img, intervals)

    # plt.bar(np.arange(9), perc_light)


    # # cv.imwrite("test_img.png", img)

    # cv.waitKey()

    # cv.destroyAllWindows()

    # plt.show()

    observe()