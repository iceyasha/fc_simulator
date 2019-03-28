from typing import List
import json
from utils import (
    log,
    bytes_to_int,
    sign,
    FlagByte,
)
from config import (
    order_size,
    order_code,
)
import copy
import fc_ppu
import fc_gamepad
import os


def log_to_json():
    f = open('nestest初始化完成.log')
    r = []
    for line in f:
        words = line.split()
        PC = int(words[1], base=16)
        op = words[2]
        address = int(words[4], base=16)
        A = int(words[5].split(':')[1], base=16)
        X = int(words[6].split(':')[1], base=16)
        Y = int(words[7].split(':')[1], base=16)
        S = int(words[8].split(':')[1], base=16)
        P = int(words[9].split(':')[1] + words[10], base=2)
        d = {
            'PC': PC,
            'op': op,
            'address': address,
            'A': A,
            'X': X,
            'Y': Y,
            'S': S,
            'P': P,
        }
        r.append(d)
    s = json.dumps(r)
    f.close()
    with open('nestest初始化完成.json', 'w') as f:
        f.write(s)


class Checker:
    def __init__(self, mode='ppu'):
        if mode == 'cpu':
            log_path = 'nestest_log.json'
        elif mode == 'ppu':
            log_path = 'nestest初始化完成.json'
        log('Checker mode:', mode)
        with open(log_path) as f:
            j = f.read()
        self.logs = json.loads(j)
        self.line = 0

    def check(self, cpu_info: dict):
        record = self.logs[self.line]
        # if info:
        #     print('now line========>', self.line)
        #     print(cpu_info)
        #     print(record)
        assert record == cpu_info, (record, cpu_info)
        self.next_line()

    def next_line(self):
        self.line += 1


class Cpu:
    def __init__(self):
        self.space = CpuSpace()
        self.ppu = self.space.ppu
        p = FlagByte(0b00100100)
        self.registers = {
            'A': 0,
            'X': 0,
            'Y': 0,
            'PC': 0,
            'S': 0xFD,
            'P': p,
        }
        self.orders = order_code()
        self.sizes = order_size()
        self.IRQ_AD = 0xFFFE
        self.NMI_AD = 0xFFFA
        self._cur_value = None
        self.info = False
        self.checker = Checker(mode='cpu')

    # 快速存档
    def dumps(self):
        c_registers = copy.copy(self.registers)
        for key, value in c_registers.items():
            if isinstance(value, FlagByte):
                c_registers[key] = value.flag
        d = {
            'registers': c_registers,
        }
        c_registers = copy.copy(self.registers)
        for key, value in c_registers.items():
            if isinstance(value, FlagByte):
                c_registers[key] = value.flag
        d = {
            'registers': c_registers,
        }
        allow_attr = []
        for attr_name in allow_attr:
            d[attr_name] = getattr(self, attr_name)
        j = json.dumps(d)
        with open('save/cpu_save.json', 'w') as f:
            f.write(j)
        self.space.dumps()

    # 快速读档
    def loads(self):
        with open('save/cpu_save.json') as f:
            data = f.read()
        d = json.loads(data)
        for name, value in d.items():
            setattr(self, name, value)

        registers = d['registers']
        for name in registers.keys():
            if name in ['P']:
                value = FlagByte(registers[name])
            else:
                value = registers[name]
            self.registers[name] = value
        self.space.loads()

    def run(self):
        log('=====loop_5000====')
        self.loop_5000()

    def loop_logs(self):
        self.registers['PC'] = 0xC000
        for i in range(len(self.checker.logs)):
            self.debug_run_order()

    def loop_5000(self):
        for i in range(5000):
            self.run_order()

    def loop_10000(self):
        for i in range(10000):
            self.run_order()

    def loop_20000(self):
        for i in range(20000):
            self.run_order()

    def debug_run_order(self):
        self._cur_value = None
        self.parse_order()
        self.eval_ad()
        cpu_info = {
            'PC': self.PC,
            'op': self.cur_order,
            'address': self.cur_ad,
            'A': self.A,
            'X': self.X,
            'Y': self.Y,
            'P': self.registers['P'].flag,
            'S': self.S,
        }
        self.checker.check(cpu_info)
        # log('[info]PC', ff(self.PC), self.cur_order, self.ad_type,  ff(self.cur_ad), 'A:', ff(self.A), 'X:', ff(self.X), 'Y:', ff(self.Y), 'S:', ff(self.S))
        self.add_pc()
        self.execute()

    def run_order(self):
        self._cur_value = None
        self.parse_order()
        self.eval_ad()
        if self.info:
            log('cur_order', self.cur_order)
            log('ad_type', self.ad_type)
            size = self.sizes[self.ad_type]
            log('ad_args', self.space[self.PC + 1: self.PC + size])
            log('cur_ad', self.cur_ad)
        self.add_pc()
        self.execute()

    def load_prg_rom(self, data_prgrom: bytes):
        # 暂时实现16kb
        self.space[0x8000:0xC000] = data_prgrom[:16384]
        self.space[0xC000:] = data_prgrom[-16384:]
        # 加载PC
        start_index = bytes_to_int(self.space[0xFFFC:0xFFFC + 2])
        self.PC = start_index
        self.space[0x2002] = 0b10100000

    def load_chr_rom(self, data_chrrom: bytes):
        self.space.ppu.space[0x0000:0x1FFF] = data_chrrom

    @property
    def cur_value(self):
        if self._cur_value is None:
            self._cur_value = self.space[self.cur_ad]
        value = self._cur_value
        return value

    @property
    def PC(self):
        return self.registers['PC']

    @PC.setter
    def PC(self, value: int):
        self.registers['PC'] = value % 65536

    @property
    def X(self):
        return self.registers['X']

    @X.setter
    def X(self, value: int):
        self.registers['X'] = value % 256

    @property
    def Y(self):
        return self.registers['Y']

    @Y.setter
    def Y(self, value: int):
        self.registers['Y'] = value % 256

    @property
    def A(self):
        return self.registers['A']

    @A.setter
    def A(self, value: int):
        self.registers['A'] = value % 256

    @property
    def S(self):
        return self.registers['S']

    @S.setter
    def S(self, value: int):
        self.registers['S'] = value % 256

    def add_pc(self):
        order = self.space[self.PC]
        _, ad_type = self.orders[order]
        size = self.sizes[ad_type]
        self.PC += size

    def parse_order(self):
        order = self.space[self.PC]
        order_name, ad_type = self.orders[order]
        self.ad_type = ad_type
        self.cur_order = order_name

    def eval_ad(self):
        ad_type = self.ad_type
        size = self.sizes[ad_type]
        ad_args = self.space[self.PC + 1: self.PC + size]
        if ad_type == 'ABS':
            # 绝对地址
            cur_ad = bytes_to_int(ad_args)
        elif ad_type == 'IMM':
            # 直接赋值  cur_ad供log用
            cur_ad = bytes_to_int(ad_args)
            self._cur_value = cur_ad
        elif ad_type == 'ZPG':
            # 零页地址
            cur_ad = bytes_to_int(ad_args)
        elif ad_type == 'IMP':
            # 内部定义，不需要外部值
            cur_ad = -1
        elif ad_type == 'REL':
            # 间接地址 需要正负号 考虑地址溢出
            offset = bytes_to_int(ad_args, signed=True)
            size = self.sizes[self.ad_type]
            ad = self.PC + size + offset & 0xffff
            cur_ad = ad
            # value = self.space[cur_ad]
        elif ad_type == 'ABX':
            # 考虑地址溢出
            y = self.X
            base_ad = bytes_to_int(ad_args)
            cur_ad = (base_ad + y) & 0xffff
            # value = self.space[cur_ad]
        elif ad_type == 'ABY':
            # 考虑 地址溢出
            y = self.Y
            base_ad = bytes_to_int(ad_args)
            cur_ad = (base_ad + y) % 65536
            # value = self.space[cur_ad]
        elif ad_type == 'ZPX':
            # 考虑零页溢出
            offset = bytes_to_int(ad_args)
            cur_ad = (self.X + offset) % 256
            # value = self.space[cur_ad]
        elif ad_type == 'ZPY':
            # 考虑零页溢出
            offset = bytes_to_int(ad_args)
            cur_ad = (self.Y + offset) % 256
        elif ad_type == 'INX':
            # 间接系列，存在bug. order ($xxFF)无法正常工作.
            base_ad = (ad_args[0] + self.X) & 0xff
            low = (base_ad) & 0xff
            high = (base_ad + 1) & 0xff
            real_ad = [self.space[low], self.space[high]]
            cur_ad = bytes_to_int(real_ad)
        elif ad_type == 'INY':
            # 间接系列，存在bug. order ($xxFF)无法正常工作.
            base_ad = ad_args[0]
            if base_ad % 256 == 255:
                real_ad = [self.space[base_ad], self.space[base_ad - 255]]
            else:
                real_ad = self.space[base_ad: base_ad + 2]
            cur_ad = (bytes_to_int(real_ad) + self.Y) % 65536
            # value = self.space[cur_ad]
        elif ad_type == 'IND':
            # 间接系列，存在bug. order ($xxFF)无法正常工作.
            base_ad = bytes_to_int(ad_args)
            if base_ad % 256 == 255:
                real_ad = [self.space[base_ad], self.space[base_ad - 255]]
            else:
                real_ad = self.space[base_ad: base_ad + 2]
            cur_ad = bytes_to_int(real_ad)
        else:
            print('未实现的寻址', ad_type)
            raise Exception('未实现的寻址', ad_type)
        self.cur_ad = cur_ad

    def execute(self):
        order_func = getattr(self, self.cur_order)
        order_func()

    def JMP(self):
        self.PC = self.cur_ad

    def LDX(self):
        self.X = self.cur_value
        self.check_z_flag(self.X)
        self.check_n_flag(self.X)

    def LDA(self):
        self.A = self.cur_value
        self.check_z_flag(self.A)
        self.check_n_flag(self.A)

    def STX(self):
        self.space[self.cur_ad] = self.X

    def STA(self):
        # if (self.X) == 0x20:
        #     log('right stx', self.X, self.cur_ad)
        self.space[self.cur_ad] = self.A

    def STY(self):
        self.space[self.cur_ad] = self.Y

    def JSR(self):
        value = self.PC - 1
        self.stack_push(value, size=2)
        self.PC = self.cur_ad

    def NOP(self):
        pass

    def SEC(self):
        self.registers['P'][0] = 1

    def SEC(self):
        self.registers['P'][0] = 1

    def BCS(self):
        carry_flag = self.registers['P'][6]
        if carry_flag:
            self.PC = self.cur_value

    def BCS(self):
        # Branch if Carry Set
        carry_flag = self.registers['P'][0]
        if carry_flag is 1:
            self.PC = self.cur_ad

    def BCC(self):
        # Branch if Carry clear
        carry_flag = self.registers['P'][0]
        if carry_flag is 0:
            self.PC = self.cur_ad

    def CLC(self):
        self.registers['P'][0] = 0

    def BEQ(self):
        # Branch if Zero Set
        zero_flag = self.registers['P'][1]
        if zero_flag is 1:
            self.PC = self.cur_ad

    def BNE(self):
        # Branch if Zero Clear
        zero_flag = self.registers['P'][1]
        if zero_flag == 0:
            self.PC = self.cur_ad

    def BIT(self):
        value = self.cur_value
        a = self.A
        r = a & value
        self.check_z_flag(r)
        m_flag = FlagByte(value)
        self.registers['P'][7] = m_flag[7]
        self.registers['P'][6] = m_flag[6]

    def BVS(self):
        # Branch if V Set
        v_flag = self.registers['P'][6]
        if v_flag is 1:
            self.PC = self.cur_ad

    def BVC(self):
        # Branch if V clear
        v_flag = self.registers['P'][6]
        if v_flag is 0:
            self.PC = self.cur_ad

    def BPL(self):
        # Branch if V n_flag is clear
        n_flag = self.registers['P'][7]
        if n_flag is 0:
            self.PC = self.cur_ad

    def RTS(self):
        # 直接存+1后地址不好么
        value = self.stack_pop(size=2)
        self.PC = value + 1

    def SEI(self):
        # 设置P中的Interrupt Disable为1
        self.registers['P'][2] = 1

    def SED(self):
        # 设置P中的Set Decimal Flag为1
        self.registers['P'][3] = 1

    def PHP(self):
        # 复制一份P，并依据指令修改后推入stack
        p = copy.copy(self.registers['P'])
        p[4] = 1
        p[5] = 1
        self.stack_push(p.flag)

    def PLA(self):
        # 从stack pull 1字节
        value = self.stack_pop()
        self.check_z_flag(value)
        self.check_n_flag(value)
        self.A = value

    def AND(self):
        # 'And' memory with A
        r = self.A & self.cur_value
        self.check_z_flag(r)
        self.check_n_flag(r)
        self.A = r

    def CMP(self):
        # 'And' memory with A, then A = memory_value
        r = self.A - self.cur_value
        if r >= 0:
            self.registers['P'][0] = 1
        else:
            self.registers['P'][0] = 0
        self.check_z_flag(r)
        self.check_n_flag(r)

    def CLD(self):
        # 清除P中的d flag
        self.registers['P'][3] = 0

    def PHA(self):
        # 从A装的值 push stack
        value = self.A
        self.stack_push(value)

    def PLP(self):
        # 从stack pop 8位 装载至p
        # warnning 4/5位保持原样
        value = self.stack_pop()
        new_p = FlagByte(value)
        old_p = self.registers['P']
        new_p[4] = old_p[4]
        new_p[5] = old_p[5]
        self.registers['P'] = new_p

    def BMI(self):
        # 如果n_flag为1，跳转
        n_flag = self.registers['P'][7]
        if n_flag == 1:
            self.PC = self.cur_ad

    def ORA(self):
        # 'Or' memory with A
        r = self.A | self.cur_value
        self.check_z_flag(r)
        self.check_n_flag(r)
        self.A = r

    def CLV(self):
        # 清除P中的V_flag
        self.registers['P'][6] = 0

    def EOR(self):
        r = self.A ^ self.cur_value
        self.check_z_flag(r)
        self.check_n_flag(r)
        self.A = r

    def ADC(self):
        """
        emm 看婉仪的吧
        """
        # r = A + M + c_flay
        result = self.A + self.cur_value + self.registers['P'][0]
        signed_a = sign(self.A)
        signed_value = sign(self.cur_value)
        signed_result = signed_a + signed_value + self.registers['P'][0]
        if result > 255:
            self.registers['P'][0] = 1
        else:
            self.registers['P'][0] = 0
        if signed_result < -127 or signed_result > 128:
            self.registers['P'][6] = 1
        else:
            self.registers['P'][6] = 0

        set_value = result % 256
        self.check_z_flag(set_value)
        self.check_n_flag(set_value)
        self.A = set_value

    def LDY(self):
        # set Y from memory
        value = self.cur_value
        self.check_z_flag(value)
        self.check_n_flag(value)
        self.Y = value

    def LDX(self):
        # set Y from memory
        value = self.cur_value
        self.check_z_flag(value)
        self.check_n_flag(value)
        self.X = value

    def CPY(self):
        r = self.Y - self.cur_value
        if r >= 0:
            self.registers['P'][0] = 1
        else:
            self.registers['P'][0] = 0
        self.check_z_flag(r)
        self.check_n_flag(r)

    def CPX(self):
        r = self.X - self.cur_value
        if r >= 0:
            self.registers['P'][0] = 1
        else:
            self.registers['P'][0] = 0
        self.check_z_flag(r)
        self.check_n_flag(r)

    def SBC(self):
        #  A = A - M - (1-C)
        # 从累加器减去存储器和进位标志C,结果送累加器A.
        result = self.A - self.cur_value - (1 - self.registers['P'][0])
        signed_a = sign(self.A)
        signed_value = sign(self.cur_value)
        signed_result = signed_a - signed_value - (1 - self.registers['P'][0])
        # signed_result = signed_a - signed_value - self.registers['P'][0]
        if result < 0 or result > 255:
            self.registers['P'][0] = 0
        else:
            self.registers['P'][0] = 1
        if signed_result < -127 or signed_result > 128:
            self.registers['P'][6] = 1
        else:
            self.registers['P'][6] = 0
        set_value = result % 256
        self.check_z_flag(set_value)
        self.check_n_flag(set_value)
        self.A = set_value

    def INY(self):
        self.Y += 1
        self.check_z_flag(self.Y)
        self.check_n_flag(self.Y)

    def INX(self):
        self.X += 1
        self.check_z_flag(self.X)
        self.check_n_flag(self.X)

    def INC(self):
        # Increment Memory
        # 头疼的溢出问题
        value = (self.space[self.cur_ad] + 1) % 256
        self.check_z_flag(value)
        self.check_n_flag(value)
        self.space[self.cur_ad] = value

    def DEY(self):
        self.Y -= 1
        self.check_z_flag(self.Y)
        self.check_n_flag(self.Y)

    def DEX(self):
        self.X -= 1
        self.check_z_flag(self.X)
        self.check_n_flag(self.X)

    def DEC(self):
        # Increment Memory
        # 头疼的溢出问题
        value = (self.space[self.cur_ad] - 1) % 256
        self.check_z_flag(value)
        self.check_n_flag(value)
        self.space[self.cur_ad] = value

    def TAY(self):
        self.Y = self.A
        self.check_z_flag(self.Y)
        self.check_n_flag(self.Y)

    def TAX(self):
        self.X = self.A
        self.check_z_flag(self.X)
        self.check_n_flag(self.X)

    def TYA(self):
        self.A = self.Y
        self.check_z_flag(self.A)
        self.check_n_flag(self.A)

    def TXA(self):
        self.A = self.X
        self.check_z_flag(self.A)
        self.check_n_flag(self.A)

    def TSX(self):
        self.X = self.S
        self.check_z_flag(self.X)
        self.check_n_flag(self.X)

    def TXS(self):
        # 不影响p
        self.S = self.X

    def RTI(self):
        # 从栈中先提取8位p， z
        p = self.stack_pop()
        new_p = FlagByte(p)
        old_p = self.registers['P']
        new_p[4] = old_p[4]
        new_p[5] = old_p[5]
        self.registers['P'] = new_p
        pc = self.stack_pop(size=2)
        self.PC = pc

    def LSR(self):
        # A 或内存的值，右移一位。原bit_0 放置到c_flag
        if self.ad_type == "IMP":
            bit_0 = self.A & 1
            value = self.A >> 1
            self.A = value
        else:
            bit_0 = self.cur_value & 1
            value = self.cur_value >> 1
            self.space[self.cur_ad] = value
        self.registers['P'][0] = bit_0
        self.check_z_flag(value)
        self.check_n_flag(value)

    def ASL(self):
        # A 或内存的值，左移一位。原bit_7 放置到c_flag
        if self.ad_type == "IMP":
            bit_7 = (self.A >> 7) & 1
            value = (self.A << 1) % 256
            self.A = value
        else:
            bit_7 = (self.cur_value >> 7) & 1
            value = (self.cur_value << 1) % 256
            self.space[self.cur_ad] = value
        self.registers['P'][0] = bit_7
        self.check_z_flag(value)
        self.check_n_flag(value)

    def ROR(self):
        # 右移动1位， 原C位站bit_7，原bit_0站c位
        c = self.registers['P'][0]
        if self.ad_type == "IMP":
            bit_0 = self.A & 1
            value = (self.A >> 1) % 128 + (c << 7)
            self.A = value
        else:
            bit_0 = self.cur_value & 1
            value = (self.cur_value >> 1) % 128 + (c << 7)
            self.space[self.cur_ad] = value
        self.registers['P'][0] = bit_0
        self.check_z_flag(value)
        self.check_n_flag(value)

    def ROL(self):
        # 左移动1位， c_flag站bit_0， 原bit_7去c_flag
        c = self.registers['P'][0]
        if self.ad_type == "IMP":
            bit_7 = (self.A >> 7) & 1
            value = (self.A << 1) % 256 + c
            self.A = value
        else:
            bit_7 = (self.cur_value >> 7) & 1
            value = (self.cur_value << 1) % 256 + c
            self.space[self.cur_ad] = value
        self.registers['P'][0] = bit_7
        self.check_z_flag(value)
        self.check_n_flag(value)

    def LAX(self):
        self.A = self.cur_value
        self.X = self.A
        self.check_z_flag(self.A)
        self.check_n_flag(self.A)

    def SAX(self):
        self.space[self.cur_ad] = self.A & self.X

    def DCP(self):
        # Decrement memory then Compare with A
        # DEC + CMP
        self.space[self.cur_ad] = (self.space[self.cur_ad] - 1) % 256
        c = self.A - self.space[self.cur_ad]
        if c >= 0:
            self.registers['P'][0] = 1
        else:
            self.registers['P'][0] = 0
        self.check_z_flag(c)
        self.check_n_flag(c)

    def ISB(self):
        # Increment memory then Subtract with Carry
        #  INC + SBC
        self.space[self.cur_ad] = (self.space[self.cur_ad] + 1) % 256

        result = self.A - self.space[self.cur_ad] - (1 - self.registers['P'][0])
        signed_a = sign(self.A)
        signed_value = sign(self.space[self.cur_ad])
        signed_result = signed_a - signed_value - (1 - self.registers['P'][0])
        if result < 0 or result > 255:
            self.registers['P'][0] = 0
        else:
            self.registers['P'][0] = 1
        if signed_result < -127 or signed_result > 128:
            self.registers['P'][6] = 1
        else:
            self.registers['P'][6] = 0
        set_value = result % 256
        self.check_z_flag(set_value)
        self.check_n_flag(set_value)
        self.A = set_value

    def SLO(self):
        # Shift Left then 'Or' -
        #    ASL + ORA
        # 由于要和累加器计算, 所以没有单字节指令SLO A, 没有IMP
        bit_7 = (self.cur_value >> 7) & 1
        value = (self.cur_value << 1) % 256
        self.space[self.cur_ad] = value
        self.registers['P'][0] = bit_7

        r = self.A | value
        self.check_z_flag(r)
        self.check_n_flag(r)
        self.A = r

    def RLA(self):
        # Rotate Left then 'And'
        # ROL + AND
        # 同样用到了A， 也没有IMP的情况
        c = self.registers['P'][0]
        bit_7 = (self.cur_value >> 7) & 1
        value = (self.cur_value << 1) % 256 + c
        self.space[self.cur_ad] = value
        self.registers['P'][0] = bit_7

        r = self.A & value
        self.check_z_flag(r)
        self.check_n_flag(r)
        self.A = r

    def SRE(self):
        # Shift Right then "Exclusive-Or"
        # LSR + EOR
        # 同样用到了A， 也没有IMP的情况
        bit_0 = self.cur_value & 1
        value = self.cur_value >> 1
        self.space[self.cur_ad] = value
        self.registers['P'][0] = bit_0

        r = self.A ^ value
        self.check_z_flag(r)
        self.check_n_flag(r)
        self.A = r

    def RRA(self):
        # Rotate Right then Add with Carry
        # ROR + ADC
        # 同样用到了A， 也没有IMP的情况
        c = self.registers['P'][0]
        bit_0 = self.cur_value & 1
        value = (self.cur_value >> 1) % 128 + (c << 7)
        self.space[self.cur_ad] = value
        self.registers['P'][0] = bit_0

        result = self.A + value + self.registers['P'][0]
        signed_a = sign(self.A)
        signed_value = sign(value)
        signed_result = signed_a + signed_value + self.registers['P'][0]
        if result > 255:
            self.registers['P'][0] = 1
        else:
            self.registers['P'][0] = 0
        if signed_result < -127 or signed_result > 128:
            self.registers['P'][6] = 1
        else:
            self.registers['P'][6] = 0
        set_value = result % 256
        self.check_z_flag(set_value)
        self.check_n_flag(set_value)
        self.A = set_value

    def NMI(self):
        # 即要等到这次 NMI 执行结束之后，才能引起下一次 NMI
        # self.space[0x2000][7] = 0
        # 这个不是汇编指令，但暂时也放在这里。
        self.stack_push(self.PC, size=2)
        P = copy.copy(self.registers['P'])
        P[4] = 0
        p = P.flag
        self.stack_push(p)
        pc_bytes = self.space[self.NMI_AD: self.NMI_AD + 2]
        pc = bytes_to_int(pc_bytes)
        self.PC = pc

    # def BRK(self):
    #     # 没有log测试
    #     # 强行PC + 1 指令要求
    #     self.PC += 1
    #     pc_h = self.PC // 256
    #     pc_l = self.PC % 256
    #     p = self.registers['P'].flag
    #     self.stack_push(pc_h)
    #     self.stack_push(pc_l)
    #     self.stack_push(p)
    #     low = self.space[self.IRQ_AD]
    #     high = self.space[self.IRQ_AD+1]
    #     self.PC = high * 256 + low

    def check_z_flag(self, value):
        if value == 0:
            self.registers['P'][1] = 1
        else:
            self.registers['P'][1] = 0

    def check_n_flag(self, value):
        a7 = FlagByte(value)[7]
        if a7 == 1:
            self.registers['P'][7] = 1
        else:
            self.registers['P'][7] = 0

    def stack_push(self, value, size=1):
        # S其实是个偏移量，栈空间存从第一页开始
        s = self.S + 256
        if size == 1:
            self.space[s] = value
        elif size == 2:
            bs = value.to_bytes(2, byteorder='little')
            self.space[s - 1] = bs[0]
            self.space[s] = bs[1]
        self.S -= size

    def stack_pop(self, size=1):
        # S其实是个偏移量，栈空间存从第一页开始
        s = self.S + 256
        if size == 1:
            value = self.space[s + 1]
        if size == 2:
            bs = self.space[s + 1:s + 3]
            value = bytes_to_int(bs)
        self.S += size
        return value

    def check_NMI(self):
        PPUCTRL = self.space[0x2000]
        if PPUCTRL >> 7 == 1:
            log('NMI')
            self.NMI()


class CpuSpace:
    def __init__(self, size=64):
        self.space = [0] * size * 1024
        self.ppu = fc_ppu.PPU()
        self.gamepad = fc_gamepad.Gamepad()

    def __getitem__(self, index):
        space = self.space
        ppu = self.ppu
        gamepad = self.gamepad
        if isinstance(index, int):
            if index == 0x2000:
                # 返回 FlagByte
                r = ppu.get_PPUCTRL()
            elif index == 0x2002:
                r = ppu.get_PPUSTATUS()
            elif index in [0x2005, 0x2006]:
                raise IndexError("index not allow get.only set")
            elif index == 0x2007:
                r = ppu.get_PPUDATA()
            elif index == 0x4016:
                r = gamepad.cpu_load()
            else:
                r = space[index]
        elif isinstance(index, slice):
            start = index.start
            stop = index.stop
            r = space[start:stop]
        else:
            raise IndexError("index error")
        return r

    def __setitem__(self, index, value):
        space = self.space
        ppu = self.ppu
        if isinstance(index, int):
            if index == 0x2000:
                # 此处只改变值。位操作，需要另外实现。
                ppu.set_PPUCTRL(value)
            elif index == 0x2002:
                ppu.set_PPUSTATUS(value)
            elif index == 0x2006:
                ppu.set_PPUADDR(value)
            elif index == 0x2007:
                ppu.set_PPUDATA(value)
            elif index == 0x4014:
                # 涉及cpu空间，不方便封在ppu里
                ppu.registers['OAMDMA'] = value
                copy_data = space[value * 0x100 : (value+1) * 0x100]
                self.ppu.OAM = copy_data
            elif index == 0x4016:
                # CPU不会修改手柄的按键状态
                pass
            else:
                space[index] = value
        elif isinstance(index, slice):
            start = index.start
            stop = index.stop
            space[start:stop] = value
        else:
            raise IndexError("index error")

    def dumps(self):
        d = {}
        allow_attr = ['space']
        for attr_name in allow_attr:
            d[attr_name] = getattr(self, attr_name)
        j = json.dumps(d)
        with open('save/cpu_space_save.json', 'w') as f:
            f.write(j)

    def loads(self):
        with open('save/cpu_space_save.json') as f:
            data = f.read()
        d = json.loads(data)
        for name, value in d.items():
            setattr(self, name, value)


def load_nes(name='nestest.nes'):
    path = os.path.join('nes', name)
    with open(path, 'rb') as f:
        b = f.read()
    prg_rom_size = b[4]  # 单位16kb
    chr_rom_size = b[5]  # 单位8kb
    flag6 = b[6]
    flag7 = b[7]
    # 8-15: byte      保留用, 应该为0. 其实有些在用了, 目前不管
    header_size = 16  # 头字段长度8字节
    low_mapper = flag6 >> 4
    high_mapper = flag7 & 0xF0
    mapper = high_mapper | low_mapper
    data_prgrom_end = header_size + prg_rom_size * 16 * 1024
    data_chrrom_end = data_prgrom_end + chr_rom_size * 8 * 1024
    data_prgrom = b[header_size: data_prgrom_end]
    data_chrrom = b[data_prgrom_end: data_chrrom_end]
    d = {
        'prg_rom_size': prg_rom_size,
        'chr_rom_size': chr_rom_size,
        'mapper': mapper,
        'prg_rom': data_prgrom,
        'chr_rom': data_chrrom,
    }
    return d


def main():
    cpu = Cpu()
    nes = load_nes()
    cpu.load_prg_rom(nes['prg_rom'])
    cpu.load_chr_rom(nes['chr_rom'])
    cpu.run()


if __name__ == '__main__':
    main()
    # log_to_json()
