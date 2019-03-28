import pygame
from fc_cpu import (
    Cpu,
    load_nes,
    sign,
)
from utils import (
    log,
    bytes_to_int,
)
from config import (
    palette_table,
)

class Fc:
    def __init__(self, scale=1):
        log('=' * 10, 'fc init', '=' * 10)
        self.scale = scale
        self.init()

    def init(self):
        scale = self.scale
        self.width = 256
        self.height = 240
        self.fps = 30
        self.running = True
        self.screen = pygame.display.set_mode((self.width * scale, self.height * scale))
        self.clock = pygame.time.Clock()
        self.color_table = palette_table()

        cpu = Cpu()
        self.cpu = cpu
        self.ppu = cpu.ppu
        # nes = load_nes()
        nes = load_nes('balloon.nes')
        # nes = load_nes('mario.nes')
        # nes = load_nes('color_test.nes')
        cpu.load_prg_rom(nes['prg_rom'])
        cpu.load_chr_rom(nes['chr_rom'])
        self.key_conf = {
            pygame.K_w: 'up',
            pygame.K_s: 'down',
            pygame.K_a: 'left',
            pygame.K_d: 'right',
            pygame.K_j: 'a',
            pygame.K_k: 'b',
            pygame.K_t: 'select',
            pygame.K_y: 'start',
        }

    def loop(self):
        fps = self.fps
        cpu = self.cpu
        clock = self.clock
        while self.running:
            # run for 5000 orders
            cpu.run()
            self.check_gamepad()
            cpu.check_NMI()
            self.draw()
            self.set_vblank_start_flags()
            clock.tick(fps)

    def check_gamepad(self):
        gamepad = self.cpu.space.gamepad
        key_conf = self.key_conf
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in key_conf.keys():
                    key = key_conf[event.key]
                    gamepad.key_on(key)
                # 按键停止
                if event.key == pygame.K_v:
                    log('dumps')
                    self.cpu.dumps()
                    self.ppu.dumps()
                if event.key == pygame.K_b:
                    log('loads')
                    self.cpu.loads()
                    self.ppu.loads()
                if event.key == pygame.K_l:
                    l = self.ppu.space[0x2000:0x2000 + 1024]
                    print(l)

            elif event.type == pygame.KEYUP:
                if event.key in key_conf.keys():
                    key = key_conf[event.key]
                    gamepad.key_off(key)

    def draw(self):
        width = self.width
        color_table = self.color_table
        scale = self.scale
        screen = self.screen

        self.ppu.draw()
        pixels = self.cpu.ppu.pixels
        for index, color_code in enumerate(pixels):
            x = index % width * scale
            y = index // width * scale
            rect_list = [x, y, scale, scale]
            color = color_table[color_code]
            pygame.draw.rect(screen, color, rect_list, 0)
        pygame.display.flip()

    def set_vblank_start_flags(self):
        ppu = self.ppu
        ppu.registers['PPUSTATUS'][7] = 1
        ppu.registers['PPUSTATUS'][6] = not ppu.registers['PPUSTATUS'][6]

def main():
    fc = Fc()
    fc.loop()


if __name__ == '__main__':
    main()
