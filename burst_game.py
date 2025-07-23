import pygame as pg
import numpy as np
import random
from scipy.spatial import distance_matrix
from copy import deepcopy
import cv2 as cv

class Game:
    def __init__(self):
        self.spawn_velocity = 160
        pg.init()
        self.screen = pg.display.set_mode((1920, 1080))
        self.w, self.h = pg.display.get_window_size()
        # print(w, h)
        self.centers = np.array([[self.w / 2, self.h / 2], [600, 400]]) # shape (N, 2)
        self.vel = np.array([[150., 150.], [0, 0]]) # shape (N, 2)
        self.radius = 80
        self.last_overlap = np.zeros((self.vel.shape[0], self.vel.shape[0]), dtype=bool)
        self.last_ud_collide = np.zeros((self.vel.shape[0],), dtype=bool)
        self.last_lr_collide = np.zeros((self.vel.shape[0],), dtype=bool)
        self.running = True
        self.clock = pg.time.Clock()
        self.add_counter = 0
        self.bubble = pg.image.load("bubble.png")
        self.bubble = pg.transform.scale(self.bubble, (2*self.radius, 2*self.radius))
        self.pop_sound = pg.mixer.Sound("pop2.wav")
        self.min_ball_count = 0
        self.last_ball_delete_center = np.array([0, 0])
        self.T = np.identity(3)

    def draw(self):
        for i in range(len(self.centers)):
            # print(self.centers[i])
            # pg.draw.circle(self.screen, pg.color.Color(255, 255, 0), self.centers[i], self.radius, width=0)
            self.screen.blit(self.bubble, (self.centers[i] - self.radius))

    def add_ball(self):
        """Check if circle should be added and adds it at the right place if necessary"""
        # print("Ball check")
        img = np.zeros((self.w, self.h), dtype=np.uint8)
        img[*np.astype(self.centers.T, int)] = 255
        img[[0, -1]] = 255
        img[:, [0, -1]] = 255
        img[*np.astype(self.last_ball_delete_center, int)] = 255
        img = cv.distanceTransform(~img, cv.DIST_L2, cv.DIST_MASK_PRECISE)
        # cv.imshow("dist", img)
        max_dist = np.max(img)
        if max_dist > self.radius * 4:
            coord_maxes = np.nonzero(img == max_dist)
            coord_max = np.array([coord_maxes[i][0] for i in range(2)])
            self.centers = np.append(self.centers, [coord_max], 0)
            initial_angle = random.random() * 2 * np.pi
            self.vel = np.append(self.vel, [[self.spawn_velocity * np.cos(initial_angle), self.spawn_velocity * np.sin(initial_angle)]], 0)
            last_overlap = np.zeros((self.vel.shape[0], self.vel.shape[0]), dtype=bool)
            last_overlap[:-1, :-1] = self.last_overlap
            self.last_overlap = last_overlap
            self.last_lr_collide = np.append(self.last_lr_collide, [False])
            self.last_ud_collide = np.append(self.last_ud_collide, [False])
            # print("Ball added")

    def delete_balls_at_points(self, points: np.array):
        """points is a (n, 2) array of points.
        If a ball intersects with one of them, it is deleted."""
        dists = distance_matrix(self.centers, points)
        dists = np.max(dists, axis=1)
        delete = dists <= self.radius
        self.delete_balls(delete)

    def process_lidar_data(self, points: np.array):
        """points is a (n, 2) array of points
        representing cartesian coordinates in real world.
        They don't have to be filtered for points inside the window.
        """
        

    def delete_balls(self, delete, pop=True):
        """delete is a numpy array of shape (N,) and dtype bool"""
        if np.any(delete):
            self.last_ball_delete_center = self.centers[np.nonzero(delete)[0][0]]
            self.centers = np.delete(self.centers, delete, axis=0)
            self.vel = np.delete(self.vel, delete, axis=0)
            self.last_overlap = np.delete(self.last_overlap, delete, axis=0)
            self.last_overlap = np.delete(self.last_overlap, delete, axis=1)
            self.last_lr_collide = np.delete(self.last_lr_collide, delete)
            self.last_ud_collide = np.delete(self.last_ud_collide, delete)
            if pop:
                self.pop_sound.play()
            if len(self.centers) < self.min_ball_count:
                print(len(self.centers))
                self.min_ball_count = len(self.centers)

    def check_for_left_balls(self):
        delete = np.any((
            (self.centers < -self.radius) |
            (self.centers > [self.w + self.radius, self.h + self.radius])
        ), axis=1)
        self.delete_balls(delete, pop=False)

    def reset_min_ball_count(self):
        self.min_ball_count = len(self.centers)
    
    def step(self, dt):
        self.centers += self.vel * dt

        dists = distance_matrix(self.centers, self.centers)

        overlap = dists <= 2 * self.radius
        self.last_overlap, overlap = np.copy(overlap), overlap & (~self.last_overlap)
        crossing = np.nonzero(overlap)
        for i, j in zip(*crossing):
            if i < j:
                c1 = self.centers[i]
                c2 = self.centers[j]
                direction_of_collision = (c2 - c1) / np.linalg.norm(c2 - c1)
                perpend = direction_of_collision[::-1] * np.array([1, -1])
                vs = self.vel[[i, j, 0]]
                v_coll = np.cross(vs, perpend)
                v_tang = np.cross(vs, direction_of_collision)
                v_coll = v_coll[[1, 0, 2]]
                v_end = v_tang[:, None] * perpend - v_coll[:, None] * direction_of_collision
                self.vel[[i, j]] = v_end[[0, 1]]

        glitched = dists <= 2 * self.radius - 5
        glitch_idxs = np.nonzero(glitched)
        for i,j in zip(*glitch_idxs):
            if i < j:
                c1 = self.centers[i]
                c2 = self.centers[j]
                absvel1 = np.hypot(*self.vel[i])
                absvel2 = np.hypot(*self.vel[j])
                direction = (c2 - c1) / np.hypot(*(c2 - c1))
                self.vel[[i, j]] = [-absvel1 * direction, absvel2 * direction]
                # print("Glitch")

        # up / down collision
        collides = (self.centers[:, 1] <= self.radius) | (self.centers[:, 1] >= self.h - self.radius)
        self.last_ud_collide, collides = np.copy(collides), collides & (~self.last_ud_collide)
        self.vel[collides, 1] *= -1

        # left / right collision
        collides = (self.centers[:, 0] <= self.radius) | (self.centers[:, 0] >= self.w - self.radius)
        self.last_lr_collide, collides = np.copy(collides), collides & (~self.last_lr_collide)
        self.vel[collides, 0] *= -1

    def mainloop(self):
        dt = 0
        while self.running:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.running = False
                elif event.type == pg.MOUSEMOTION and pg.mouse.get_pressed()[0]:
                    self.delete_balls_at_points(np.array([[*event.pos]]))
                elif event.type == pg.KEYDOWN and event.key == pg.K_c:
                    self.reset_min_ball_count()
            # content = ""
            self.screen.fill("white")
            self.check_for_left_balls()
            if self.add_counter * 300 < pg.time.get_ticks():
                self.add_ball()
                self.add_counter += 1
            self.step(dt)
            self.draw()
            pg.display.flip()
            dt = self.clock.tick(60) / 1000
        pg.quit()


if __name__ == "__main__":
    game = Game()
    game.mainloop()
