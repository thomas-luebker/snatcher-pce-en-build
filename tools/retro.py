#!/usr/bin/env python3
"""Headless libretro frontend: run a PC Engine CD image with scripted input, save screenshots.

  retro.py CUE --frames 3000 --press "start@300-310,a@600-605" --shots 290,620,3000 [--every 300]
           [--core emu/mednafen_pce_libretro.dylib] [--out work/shots] [--state-out f] [--state-in f]

Buttons: up down left right a(=I) b(=II) select start(=RUN).
The System Card is taken from ~/.mednafen/firmware/syscard3.pce.
"""
import argparse
import ctypes as C
import os
import struct
import zlib

BUTTONS = {"b": 0, "select": 2, "start": 3, "up": 4, "down": 5, "left": 6, "right": 7, "a": 8}
ENV_GET_CAN_DUPE, ENV_GET_SYSTEM_DIRECTORY, ENV_SET_PIXEL_FORMAT = 3, 9, 10
ENV_GET_VARIABLE, ENV_GET_VARIABLE_UPDATE, ENV_GET_LOG_INTERFACE, ENV_GET_SAVE_DIRECTORY = 15, 17, 27, 31


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


def write_png(path, w, h, rgb):
    raw = b"".join(b"\0" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


class Emu:
    def __init__(self, core, sysdir):
        self.lib = C.CDLL(core)
        self.fmt, self.frame, self.pressed = 0, None, set()
        self.sysdir = C.c_char_p(sysdir.encode())
        ENV = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
        VID = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
        AUD = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
        AUDB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
        POLL = C.CFUNCTYPE(None)
        INP = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
        # printf-style and variadic in C; only the fixed arguments are read here (the core crashes without a logger)
        self._log = C.CFUNCTYPE(None, C.c_int, C.c_char_p)(lambda level, fmt: None)
        self._cbs = [ENV(self._env), VID(self._video), AUD(lambda l, r: None), AUDB(lambda d, n: n),
                     POLL(lambda: None), INP(self._input)]
        L = self.lib
        L.retro_set_environment(self._cbs[0])
        L.retro_set_video_refresh(self._cbs[1])
        L.retro_set_audio_sample(self._cbs[2])
        L.retro_set_audio_sample_batch(self._cbs[3])
        L.retro_set_input_poll(self._cbs[4])
        L.retro_set_input_state(self._cbs[5])
        L.retro_init()
        L.retro_load_game.argtypes = [C.POINTER(GameInfo)]
        L.retro_load_game.restype = C.c_bool
        L.retro_serialize_size.restype = C.c_size_t
        L.retro_serialize.argtypes = [C.c_void_p, C.c_size_t]
        L.retro_serialize.restype = C.c_bool
        L.retro_unserialize.argtypes = [C.c_void_p, C.c_size_t]
        L.retro_unserialize.restype = C.c_bool

    def _env(self, cmd, data):
        cmd &= 0xFFFF
        if cmd == ENV_GET_CAN_DUPE:
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        if cmd in (ENV_GET_SYSTEM_DIRECTORY, ENV_GET_SAVE_DIRECTORY):
            C.cast(data, C.POINTER(C.c_char_p))[0] = self.sysdir
            return True
        if cmd == ENV_SET_PIXEL_FORMAT:
            self.fmt = C.cast(data, C.POINTER(C.c_int))[0]
            return True
        if cmd == ENV_GET_LOG_INTERFACE:
            C.cast(data, C.POINTER(C.c_void_p))[0] = C.cast(self._log, C.c_void_p).value
            return True
        if cmd == ENV_GET_VARIABLE_UPDATE:
            C.cast(data, C.POINTER(C.c_bool))[0] = False
            return True
        return False

    def _video(self, data, w, h, pitch):
        if data:
            self.frame = (C.string_at(data, pitch * h), w, h, pitch)

    def _input(self, port, device, index, ident):
        return 1 if port == 0 and device == 1 and ident in self.pressed else 0

    def load(self, path):
        info = GameInfo(path.encode(), None, 0, None)
        if not self.lib.retro_load_game(C.byref(info)):
            raise SystemExit("core refused the image (BIOS missing?)")
        self.lib.retro_set_controller_port_device(0, 1)          # plug a joypad in, or input is ignored

    def run(self, pressed=()):
        self.pressed = set(pressed)
        self.lib.retro_run()

    def screenshot(self, path):
        buf, w, h, pitch = self.frame
        rgb = bytearray(w * h * 3)
        for y in range(h):
            row = buf[y * pitch:y * pitch + pitch]
            if self.fmt == 1:                                   # XRGB8888
                px = row[:w * 4]
                rgb[y * w * 3:(y + 1) * w * 3] = bytes(b for i in range(0, w * 4, 4) for b in (px[i + 2], px[i + 1], px[i]))
            else:                                               # RGB565
                vals = struct.unpack(f"<{w}H", row[:w * 2])
                rgb[y * w * 3:(y + 1) * w * 3] = bytes(c for v in vals for c in
                                                       (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31))
        write_png(path, w, h, bytes(rgb))

    def save_state(self, path):
        n = self.lib.retro_serialize_size()
        buf = C.create_string_buffer(n)
        if self.lib.retro_serialize(buf, n):
            open(path, "wb").write(buf.raw)

    def load_state(self, path):
        data = open(path, "rb").read()
        buf = C.create_string_buffer(data, len(data))
        return self.lib.retro_unserialize(buf, len(data))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cue")
    ap.add_argument("--core", default=os.path.join(os.path.dirname(__file__), "..", "emu", "mednafen_pce_libretro.dylib"))
    ap.add_argument("--frames", type=int, default=1800)
    ap.add_argument("--press", default="")
    ap.add_argument("--shots", default="")
    ap.add_argument("--every", type=int, default=0)
    ap.add_argument("--out", default="work/shots")
    ap.add_argument("--state-in")
    ap.add_argument("--state-out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    script = []
    for item in filter(None, a.press.split(",")):
        name, span = item.split("@")
        lo, _, hi = span.partition("-")
        script.append((BUTTONS[name], int(lo), int(hi or lo) ))
    shots = {int(x) for x in a.shots.split(",") if x}
    emu = Emu(os.path.abspath(a.core), os.path.expanduser("~/.mednafen/firmware"))
    emu.load(os.path.abspath(a.cue))
    if a.state_in:
        emu.run()
        print("state loaded:", emu.load_state(a.state_in))
    for f in range(1, a.frames + 1):
        emu.run([b for b, lo, hi in script if lo <= f <= hi])
        if f in shots or (a.every and f % a.every == 0):
            emu.screenshot(os.path.join(a.out, f"f{f:06d}.png"))
    if a.state_out:
        emu.save_state(a.state_out)
    print(f"ran {a.frames} frames, screenshots in {a.out}")


if __name__ == "__main__":
    main()
