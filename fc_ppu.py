from utils import (
    log,
    bytes_to_int,
    draw,
    FlagByte,
)
import json
import copy

class PPU:
    def __init__(self):
        self.registers = {
            'PPUCTRL': FlagByte(0b00000000),
            'PPUMASK': 0,
            'PPUSTATUS': FlagByte(0b10100000),
            'OAMADDR': 0,
            'OAMDATA': 0,
            'PPUSCROLL': 0,
            'PPUADDR': 0,
            'PPUDATA': 0,
            'OAMDMA': 0,
            'v':0,
            't':0,
            'e':0,
            'w':0,
        }
        self.PPUADDR_write = 'high'
        self.space = PpuSpace()
        self.pixels = [0] * 256 * 240
        self.OAM = [0] * 256

    # 快速存档
    def dumps(self):
        c_registers = copy.copy(self.registers)
        for key, value in c_registers.items():
            if isinstance(value, FlagByte):
                c_registers[key] = value.flag
        d = {
            'registers': c_registers,
        }
        allow_attr = ['PPUADDR_write']
        for attr_name in allow_attr:
            d[attr_name] = getattr(self, attr_name)
        j = json.dumps(d)
        with open('save/ppu_save.json', 'w') as f:
            f.write(j)
        self.space.dumps()

    # 快速读档
    def loads(self):
        with open('save/ppu_save.json') as f:
            data = f.read()
        d = json.loads(data)
        for name, value in d.items():
            setattr(self, name, value)

        registers = d['registers']
        for name in registers.keys():
            if name in ['PPUCTRL', 'PPUSTATUS']:
                value = FlagByte(registers[name])
            else:
                value = registers[name]
            self.registers[name] = value
        self.space.loads()

    def PPUADDR_add(self):
        flag = self.registers['PPUCTRL'][2]
        if flag == 1:
            self.registers['PPUADDR'] += 32
        else:
            self.registers['PPUADDR'] += 1

    def get_PPUADDR(self):
        r = self.registers['PPUADDR']
        return r

    def set_PPUADDR(self, value):
        if self.PPUADDR_write == 'high':
            low = self.registers['PPUADDR'] % 256
            new = value * 256 | low
            self.PPUADDR_write = 'low'
        elif self.PPUADDR_write == 'low':
            high = self.registers['PPUADDR'] // 256
            new = high * 256 | value
            self.PPUADDR_write = 'high'
        else:
            raise Exception('set_PPUADDR error')
        self.registers['PPUADDR'] = new

    def get_PPUDATA(self):
        index = self.registers['PPUADDR']
        if 0x3f00 <= index <= 0x3fff:
            r = self.space[index]
        else:
            r = self.space.buffer
        self.space.buffer = self.space[index]
        self.PPUADDR_add()
        return r

    def set_PPUDATA(self, value):
        index = self.registers['PPUADDR']
        self.space[index] = value
        self.PPUADDR_add()

    def get_OAMADDR(self):
        r = self.registers['OAMADDR']
        return r

    def set_OAMADDR(self, value):
        if self.PPUADDR_write == 'high':
            low = self.registers['OAMADDR'] % 256
            new = value * 256 + low
            self.PPUADDR_write = 'low'
        elif self.PPUADDR_write == 'low':
            # 设置低位
            high = self.registers['OAMADDR'] // 256
            new = high * 256 + value
            self.PPUADDR_write = 'high'
        else:
            raise Exception('set_OAMADDR error')
        self.registers['OAMADDR'] = new

    def get_OAMDATA(self):
        index = self.registers['OAMADDR']
        if 0x3FFF0 >= index >= 0x3F00:
            r = self.space[index]
        else:
            # 不然走缓冲区
            # print('缓冲')
            # print('index', index)
            r = self.space.buffer[index]
            self.space.buffer[index] = self.space[index]
        self.registers['OAMADDR'] += 1
        return r

    def set_OAMDATA(self, value):
        index = self.registers['OAMADDR']
        self.space[index] = value
        self.registers['OAMADDR'] += 1

    def get_PPUCTRL(self):
        r = self.registers['PPUCTRL'].flag
        return r

    def set_PPUCTRL(self, value):
        self.registers['PPUCTRL'].flag = value

    def set_PPUCTRL_flag(self, index, value):
        self.registers['PPUCTRL'][index] = value

    def get_PPUSTATUS(self):
        r = self.registers['PPUSTATUS'].flag
        self.registers['PPUSTATUS'][7] = 0
        return r

    def set_PPUSTATUS(self, value):
        self.registers['PPUSTATUS'].flag = value

    def set_PPUSTATUS_flag(self, index, value):
        self.registers['PPUSTATUS'][index] = value

    def draw(self):
        self.update_tabel()
        self.draw_pixels()
        self.draw_sprites()

    def update_tabel(self):
        name_tabel_start = 0x2000
        attribute_table_start = name_tabel_start + 32 * 30
        self.name_tabel_start = name_tabel_start
        self.attribute_table_start = attribute_table_start
        self.name_tabel = self.space[name_tabel_start:attribute_table_start]
        self.attribute_table = self.space[attribute_table_start:attribute_table_start + 64]

    def draw_pixels(self):
        # 2x30=960 block
        # 64 字节被瓜分成 8x8，也就是把背景分成 8x8 的区域：
        # 属性表自然是描述属性的
        # 描述背景(32x32 block)所使用的调色板
        # 每个属性表字节对应32x32 像素，也就是4x4个图块
        # 每2位对应6x16 像素( 2x2 图块)。

        # 之前的按block画的版本
        for block_no in range(960):
            self.draw_block(block_no)
        #
        #
        # pixels = self.pixels
        # flag = self.registers['PPUCTRL'][4]
        # if flag == 0:
        #     pattern_base = 0
        # elif flag == 1:
        #     pattern_base = 0x1000
        #
        # name_tabel_start = 0x2000
        # attribute_table_start = name_tabel_start + 32 * 30
        # self.name_tabel_start = name_tabel_start
        # self.attribute_table_start = attribute_table_start
        # self.name_tabel = self.space[name_tabel_start:attribute_table_start]
        # self.attribute_table = self.space[attribute_table_start:attribute_table_start + 64]
        # for y in range(240):
        #     for x in range(256):
        #         aid = (x >> 5) + (y >> 5) * 8
        #         attr = self.space[attribute_table_start + aid]
        #         aoffset = ((x & 0x10) >> 3) | ((y & 0x10) >> 2)
        #         high_two = (attr & (3 << aoffset)) >> aoffset
        #
        #         p_id = (x >> 3) + (y >> 3) * 32
        #         pattern_index = self.name_tabel[p_id]
        #         start = pattern_index * 16 + pattern_base
        #         nowp0 = self.space[start:start + 8]
        #         nowp1 = self.space[start + 8:start + 16]
        #         offset = y & 0x7
        #         p0 = nowp0[offset]
        #         p1 = nowp1[offset]
        #         shift = x % 8
        #         mask = 0b10000000 >> shift
        #         low_two = (0b00000001 if (p0 & mask) != 0 else 0) | (0b00000010 if (p1 & mask) != 0 else 0)
        #
        #         color_4 = (high_two << 2) | low_two
        #         if low_two == 0b00:
        #             color_4 = 0
        #         # 0x3F00 背景颜色起始位置
        #         color_index = 0x3F00 + color_4
        #         color_code = self.space[color_index]
        #         p_index = y * 256 + x
        #         pixels[p_index] = color_code

    # block版本
    def draw_block(self, block_no):
        # 如果PPUCTRL 4位位0，从图样表 0取。如果为1，从图样表 1取。
        flag = self.registers['PPUCTRL'][4]
        if flag == 0:
            pattern_base = 0
        elif flag == 1:
            pattern_base = 0x1000
        pixels = self.pixels
        block_w = 8
        block_h = 8
        block_per_line = 32

        pattern_index = self.name_tabel[block_no]
        start = pattern_index * 16 + pattern_base
        stop = start + 16
        pattern = self.space[start:stop]
        pattern_block = self.pattern_block(pattern)

        block_base_index = (block_no // block_per_line) * block_h * 256 + (block_no % block_per_line) * block_w
        for block_index, pixel_low_two in enumerate(pattern_block):
            pixel_index = block_base_index + (block_index // block_w) * 256 + (block_index % block_w)
            y = pixel_index // 256
            x = pixel_index % 256

            aid = (x >> 5) + (y >> 5) * 8
            attr = self.space[self.attribute_table_start + aid]
            aoffset = ((x & 0x10) >> 3) | ((y & 0x10) >> 2)
            high_two = (attr & (3 << aoffset)) >> aoffset
            color_4 = (high_two << 2) | pixel_low_two
            if pixel_low_two == 0b00:
                color_4 = 0
            # 0x3F00 颜色起始位置
            color_index = 0x3F00 + color_4
            color = self.space[color_index]
            pixels[pixel_index] = color

    # 过去版本
    def pattern_block(self, pattern):
        """
        每个图样16字节，对应8x8像素的图块。
        先按前后8字节分开。
        前8个字节，8x8 一共64bit，每个bit对应像素2位的低位。
        后8个字节，8x8 一共64bit，每个bit对应像素2位的高位。
        """
        low_8 = pattern[:8]
        high_8 = pattern[8:]
        block = [0] * 8 * 8
        for y in range(8):
            low_byte = low_8[y]
            high_byte = high_8[y]
            for x in range(8):
                low_bit = (low_byte >> (7 - x)) & 1
                high_bit = (high_byte >> (7 - x)) & 1
                low_two = (high_bit << 1) + low_bit
                offset = y * 8 + x
                block[offset] = low_two
        return block

    def draw_sprites(self):
        # 最多64个精灵
        OAM = self.OAM
        flag = self.registers['PPUCTRL'][3]
        if flag == 0:
            pattern_base = 0
        elif flag == 1:
            pattern_base = 0x1000
        block_w = 8
        pixels = self.pixels
        OAM_len = len(OAM)
        # 倒序。因为OAM是在前的精灵图像优先级高。但实际画图我们是反着来。
        for i in range(4, OAM_len, 4):
            end = OAM_len - i
            sprite_bytes = OAM[end - 4: end]
            sprite_y = sprite_bytes[0] + 1
            sprite_x = sprite_bytes[3]

            pattern_index = sprite_bytes[1]
            flag = sprite_bytes[2]
            color_high_two = flag & 0b11
            # screen_behind = (flag >> 5) & 1
            # if screen_behind == 1:
            #     continue

            # 每个pattern（图样）16字节 图样表0
            flip_horizontal = (flag >> 6) & 1
            # TODO 垂直翻转 一条扫描线最多渲染8个精灵 8x16
            # flip_vertical = (flag >> 7) & 1
            start = pattern_index * 16 + pattern_base
            stop = start + 16

            pattern = self.space[start:stop]
            pattern_block = self.pattern_block(pattern)
            for block_index, pixel_low_two in enumerate(pattern_block):
                if flip_horizontal == 1:
                    pixel_x = (7 - block_index % block_w) + sprite_x
                else:
                    pixel_x = block_index % block_w + sprite_x
                pixel_y = block_index // block_w + sprite_y
                if pixel_x > 255 or pixel_y > 239:
                    continue
                pixel_index = pixel_y * 256 + pixel_x

                color_4 = (color_high_two << 2) + pixel_low_two
                # 0x3F10 精灵颜色起始位置
                color_index = 0x3F10 + color_4
                color = self.space[color_index]
                pixels[pixel_index] = color


class PpuSpace:
    def __init__(self, size=16):
        self.space = [0] * size * 1024
        self.buffer = 0

    def check_mirror(self, index):
        # 如果Slice跨过了镜像怎么办？
        if isinstance(index, int):
            if 0x3EFF >= index >= 0x3000:
                index -= 4096
            elif 0x3FFF >= index >= 0x3F20:
                index -= 32
            if index == 0x3F10:
                index = 0x3F00
            if index == 0x3F14:
                index = 0x3F04
            if index == 0x3F18:
                index = 0x3F08
            if index == 0x3F1C:
                index = 0x3F0C
        elif isinstance(index, slice):
            start = index.start
            stop = index.stop
            if 0x3EFF >= start >= 0x3000:
                start -= 4096
            elif 0x3FFF >= start >= 0x3F20:
                start -= 32
            elif 0x3EFF >= stop > 0x3000:
                stop -=  4096
            elif 0x3FFF >= stop > 0x3F20:
                stop -= 32
            index = slice(start, stop, 1)
        return index

    def __getitem__(self, index):
        space = self.space
        i = self.check_mirror(index)
        if isinstance(i, int):
            r = space[i]
        elif isinstance(i, slice):
            r = space[i.start:i.stop]
        else:
            raise IndexError("index error")
        return r

    def __setitem__(self, index, value):
        space = self.space
        i = self.check_mirror(index)
        if isinstance(i, int):
            space[i] = value
        elif isinstance(i, slice):
            start = i.start
            stop = i.stop
            space[start:stop] = value
        else:
            raise IndexError("index error")

    def dumps(self):
        d = {}
        allow_attr = ['buffer', 'space']
        for attr_name in allow_attr:
            d[attr_name] = getattr(self, attr_name)
        j = json.dumps(d)
        with open('save/ppu_space_save.json', 'w') as f:
            f.write(j)

    def loads(self):
        with open('save/ppu_space_save.json') as f:
            data = f.read()
        d = json.loads(data)
        for name, value in d.items():
            setattr(self, name, value)
