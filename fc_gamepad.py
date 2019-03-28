from utils import (
    log,
)

class Gamepad:
    def __init__(self):
        self.data = [0] * 8
        self.load_index = 0
        self.key_order = {
            'a': 0,
            'b': 1,
            'select':2,
            'start':3,
            'up':4,
            'down':5,
            'left':6,
            'right':7,
        }

    def cpu_load(self):
        r = self.data[self.load_index]
        self.load_index = (self.load_index + 1) % 8
        return r

    def key_on(self, key):
        index = self.key_order[key]
        self.data[index] = 1
        log(key, 'on')

    def key_off(self, key):
        index = self.key_order[key]
        self.data[index] = 0
        log(key, 'off')