#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aes_ctr_host.py - Công cụ phía laptop cho hệ thống DE2 (mic -> AES-128-CTR -> UART -> PC)

Chức năng:
  keygen    : tạo khóa AES-128 ngẫu nhiên, lưu vào file
  newiv     : tạo IV mới (nonce 96-bit ngẫu nhiên + counter 32-bit = 0), ghi vào sessions.jsonl
  session   : cấu hình FPGA (STOP, SET_IV, [SET_KEY], SET_SRC, START) -> nhận frame -> giải mã
              realtime -> ghi WAV + lưu raw capture. Có thống kê mất frame / lỗi CRC.
  decrypt   : giải mã offline từ file capture (.bin) hoặc file ciphertext thô (--raw)
  simulate  : mô phỏng FPGA bằng phần mềm (golden model) -> sinh file capture để test script
  analyze   : phân tích WAV (peak, RMS, tần số trội) để kiểm tra bằng mắt/tai
  budget    : tính băng thông UART có đủ cho tốc độ lấy mẫu hay không
  sessions  : liệt kê các IV đã dùng        ports : liệt kê cổng COM
  selftest  : tự kiểm tra (CRC, vector NIST, round-trip, mất frame, lỗi CRC)

------------------------------------------------------------------------------
GIAO THỨC UART (hai chiều dùng chung một dạng frame)
------------------------------------------------------------------------------
  | 0xA5 0x5A | TYPE (1) | LEN (1) | PAYLOAD (LEN byte) | CRC16 (2, big-endian) |
  CRC16-CCITT-FALSE (poly 0x1021, init 0xFFFF, không reflect) tính trên TYPE|LEN|PAYLOAD.
  (kiểm tra: CRC16("123456789") = 0x29B1)

  FPGA -> PC
    0x01 DATA : PAYLOAD = SID(1) | CTR32(4, BE) | CIPHERTEXT (n*16 byte, n = 1..15)
                SID   = byte đầu của IV (IV[127:120]) -> PC nhận biết dữ liệu cũ/phiên khác
                CTR32 = 32 bit thấp của counter block ứng với block ĐẦU TIÊN trong payload
                => PC giải mã đúng kể cả khi mất frame (CTR truy cập ngẫu nhiên được).
    0x80 ACK  : PAYLOAD = TYPE_được_ack(1) | STATUS(1)   (0 = OK)
  PC -> FPGA
    0x10 SET_IV  : 16 byte IV (counter block ban đầu, MSB trước)
    0x11 SET_KEY : 16 byte key (chỉ dùng khi demo/lab)
    0x12 START   : không payload      0x13 STOP : không payload
    0x14 SET_SRC : 1 byte, 0 = micro, 1 = ramp test (sample k = k & 0xFFFF)

  Một block 128-bit gửi MSB trước. Sample xếp theo thứ tự thời gian, sample cũ nhất ở
  bit cao nhất (dịch trái vào thanh ghi 128-bit) => mặc định big-endian (--endian big).
  Với stereo: L, R xen kẽ.

  YÊU CẦU PHÍA FPGA: sau reset KHÔNG được tự phát dữ liệu; chỉ phát sau khi nhận SET_IV +
  START. Nếu FPGA khởi động lại mà dùng lại IV cũ -> trùng keystream (mất an toàn của CTR).
------------------------------------------------------------------------------
"""
import argparse
import array
import json
import math
import os
import random
import sys
import tempfile
import time
import wave
from datetime import datetime

# --------------------------------------------------------------------------
# AES-128 (ECB encrypt) : dùng pycryptodome nếu có, nếu không dùng bản thuần Python
# --------------------------------------------------------------------------
try:
    from Crypto.Cipher import AES as _CAES
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False


def _build_sbox():
    sbox = [0] * 256
    p = q = 1
    while True:
        p = (p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)) & 0xFF
        q = (q ^ (q << 1)) & 0xFF
        q = (q ^ (q << 2)) & 0xFF
        q = (q ^ (q << 4)) & 0xFF
        if q & 0x80:
            q ^= 0x09

        def rotl(x, s):
            return ((x << s) | (x >> (8 - s))) & 0xFF
        x = q ^ rotl(q, 1) ^ rotl(q, 2) ^ rotl(q, 3) ^ rotl(q, 4)
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox


_SBOX = _build_sbox()
_M2 = [(((x << 1) ^ 0x1B) & 0xFF) if x & 0x80 else (x << 1) for x in range(256)]
_M3 = [_M2[x] ^ x for x in range(256)]
_SR = [(i + 4 * (i % 4)) % 16 for i in range(16)]


class _PyAES:
    """AES-128 encrypt-only, thuần Python (chậm, chỉ là fallback)."""

    def __init__(self, key):
        w = [list(key[4 * i:4 * i + 4]) for i in range(4)]
        rc = 1
        for i in range(4, 44):
            t = w[i - 1][:]
            if i % 4 == 0:
                t = [_SBOX[x] for x in t[1:] + t[:1]]
                t[0] ^= rc
                rc = _M2[rc]
            w.append([w[i - 4][j] ^ t[j] for j in range(4)])
        self.rk = [sum(w[4 * r:4 * r + 4], []) for r in range(11)]

    def _blk(self, b):
        rk = self.rk
        s = [b[i] ^ rk[0][i] for i in range(16)]
        for r in range(1, 10):
            s = [_SBOX[s[_SR[i]]] for i in range(16)]
            t = [0] * 16
            for c in range(0, 16, 4):
                a0, a1, a2, a3 = s[c:c + 4]
                t[c] = _M2[a0] ^ _M3[a1] ^ a2 ^ a3
                t[c + 1] = a0 ^ _M2[a1] ^ _M3[a2] ^ a3
                t[c + 2] = a0 ^ a1 ^ _M2[a2] ^ _M3[a3]
                t[c + 3] = _M3[a0] ^ a1 ^ a2 ^ _M2[a3]
            k = rk[r]
            s = [t[i] ^ k[i] for i in range(16)]
        return bytes(_SBOX[s[_SR[i]]] ^ rk[10][i] for i in range(16))

    def encrypt(self, data):
        out = bytearray()
        for i in range(0, len(data), 16):
            out += self._blk(data[i:i + 16])
        return bytes(out)


def make_ecb(key):
    if HAVE_CRYPTO:
        return _CAES.new(key, _CAES.MODE_ECB)
    return _PyAES(key)


# --------------------------------------------------------------------------
# CRC16 + framing
# --------------------------------------------------------------------------
SYNC = b"\xA5\x5A"
T_DATA, T_SET_IV, T_SET_KEY, T_START, T_STOP, T_SET_SRC, T_ACK = \
    0x01, 0x10, 0x11, 0x12, 0x13, 0x14, 0x80
MASK128 = (1 << 128) - 1
MASK32 = 0xFFFFFFFF


def _crc_table():
    t = []
    for i in range(256):
        c = i << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
        t.append(c)
    return t


_CRC = _crc_table()


def crc16(data, crc=0xFFFF):
    for b in data:
        crc = ((crc << 8) & 0xFFFF) ^ _CRC[(crc >> 8) ^ b]
    return crc


def build_frame(ftype, payload=b""):
    body = bytes([ftype, len(payload)]) + payload
    return SYNC + body + crc16(body).to_bytes(2, "big")


class FrameParser:
    def __init__(self):
        self.buf = bytearray()
        self.crc_errors = 0
        self.junk_bytes = 0
        self.frames = 0

    def feed(self, data):
        buf = self.buf
        buf += data
        out = []
        while True:
            i = buf.find(SYNC)
            if i < 0:
                keep = 1 if buf and buf[-1] == SYNC[0] else 0
                self.junk_bytes += len(buf) - keep
                del buf[:len(buf) - keep]
                break
            if i > 0:
                self.junk_bytes += i
                del buf[:i]
            if len(buf) < 4:
                break
            total = 4 + buf[3] + 2
            if len(buf) < total:
                break
            body = bytes(buf[2:total - 2])
            if crc16(body) == int.from_bytes(buf[total - 2:total], "big"):
                out.append((body[0], body[2:]))
                self.frames += 1
                del buf[:total]
            else:
                self.crc_errors += 1
                del buf[:1]
        return out

    def finish(self):
        """Hết dữ liệu: bỏ frame dang dở ở đầu buffer và quét lại phần còn lại."""
        out = []
        while self.buf:
            del self.buf[:1]
            out += self.feed(b"")
        return out


# --------------------------------------------------------------------------
# AES-CTR
# --------------------------------------------------------------------------
def xor_bytes(a, b):
    return (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).to_bytes(len(a), "big")


class CtrEngine:
    """keystream(block n) = AES_K(IV + n), IV là số 128-bit, cộng modulo 2^128."""

    def __init__(self, key, iv_bytes):
        self.ecb = make_ecb(key)
        self.iv = int.from_bytes(iv_bytes, "big")
        self.iv_low = self.iv & MASK32

    def block_index(self, ctr32):
        return (ctr32 - self.iv_low) & MASK32

    def ctr32_of(self, n):
        return (self.iv_low + n) & MASK32

    def crypt(self, n, data):
        nblk = len(data) // 16
        blocks = b"".join(((self.iv + n + i) & MASK128).to_bytes(16, "big")
                          for i in range(nblk))
        return xor_bytes(data, self.ecb.encrypt(blocks))


# --------------------------------------------------------------------------
# Key / IV / session log
# --------------------------------------------------------------------------
def load_key(a):
    if a.key:
        k = bytes.fromhex(a.key)
    elif os.path.exists(a.key_file):
        k = bytes.fromhex(open(a.key_file).read().strip())
    else:
        sys.exit("Không có khóa: dùng --key HEX hoặc chạy 'keygen' trước (%s)" % a.key_file)
    if len(k) != 16:
        sys.exit("Khóa phải đúng 16 byte (32 ký tự hex)")
    return k


def load_sessions(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def make_iv(log_path, label=""):
    """IV = nonce 12 byte ngẫu nhiên (không trùng phiên cũ) || counter 32-bit = 0."""
    sessions = load_sessions(log_path)
    used = {s["iv"][:24] for s in sessions}
    last_sid = sessions[-1]["sid"] if sessions else None
    while True:
        nonce = os.urandom(12)
        if nonce.hex() not in used and nonce[0] != last_sid:
            break
    iv = nonce + bytes(4)
    entry = {"session": len(sessions) + 1, "time": datetime.now().isoformat(timespec="seconds"),
             "iv": iv.hex(), "sid": iv[0], "label": label}
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return iv, entry


def resolve_iv(a):
    if a.iv:
        iv = bytes.fromhex(a.iv)
    elif a.session:
        ss = load_sessions(a.log)
        if not ss:
            sys.exit("Chưa có phiên nào trong %s" % a.log)
        if a.session == "latest":
            s = ss[-1]
        else:
            m = [x for x in ss if x["session"] == int(a.session)]
            if not m:
                sys.exit("Không thấy phiên %s" % a.session)
            s = m[0]
        iv = bytes.fromhex(s["iv"])
    else:
        sys.exit("Cần --iv HEX hoặc --session N|latest")
    if len(iv) != 16:
        sys.exit("IV phải đúng 16 byte")
    return iv


# --------------------------------------------------------------------------
# Audio helpers
# --------------------------------------------------------------------------
class AudioFmt:
    def __init__(self, a):
        self.rate, self.channels, self.width, self.endian = a.rate, a.channels, a.width, a.endian
        if self.width not in (2, 4) or self.channels not in (1, 2):
            sys.exit("Chỉ hỗ trợ width 2|4 byte và 1|2 kênh (để 128-bit chia hết)")
        self.tcs = {2: "h", 4: "i"}[self.width]
        self.tcu = {2: "H", 4: "I"}[self.width]
        assert array.array(self.tcs).itemsize == self.width


def swap_endian(data, width):
    out = bytearray(len(data))
    for i in range(width):
        out[i::width] = data[width - 1 - i::width]
    return bytes(out)


def to_le_arr(tc, le):
    a = array.array(tc)
    a.frombytes(le)
    if sys.byteorder == "big":
        a.byteswap()
    return a


def dbfs(rms, width):
    full = float(1 << (8 * width - 1))
    return -999.0 if rms <= 0 else 20 * math.log10(rms / full)


# --------------------------------------------------------------------------
# Giải mã luồng frame -> WAV
# --------------------------------------------------------------------------
class Decryptor:
    def __init__(self, engine, sid, fmt, wav_path=None, expect=None):
        self.e, self.sid, self.f, self.expect = engine, sid, fmt, expect
        self.wav = None
        if wav_path:
            self.wav = wave.open(wav_path, "wb")
            self.wav.setnchannels(fmt.channels)
            self.wav.setsampwidth(fmt.width)
            self.wav.setframerate(fmt.rate)
        self.next_n = 0
        self.frames = self.blocks = self.lost = 0
        self.wrong_sid = self.bad_len = self.backwards = 0
        self.ramp_bad = self.ramp_checked = 0
        self.max_fill = max(1, fmt.rate * fmt.width * fmt.channels * 10 // 16)
        self.tot_sumsq = 0
        self.tot_n = 0
        self.tot_peak = 0
        self.win_sumsq = self.win_n = self.win_peak = 0

    # -- một frame DATA
    def on_data(self, p):
        if len(p) < 21 or (len(p) - 5) % 16:
            self.bad_len += 1
            return
        if p[0] != self.sid:
            self.wrong_sid += 1
            return
        n = self.e.block_index(int.from_bytes(p[1:5], "big"))
        ct = p[5:]
        d = (n - self.next_n) & MASK32
        if d >= 1 << 31:
            d -= 1 << 32
        if d < 0:
            self.backwards += 1      # counter đi lùi: trùng/đảo thứ tự hoặc FPGA reset
            return
        if d > 0:
            self.lost += d
            if self.wav and d <= self.max_fill:
                self.wav.writeframesraw(bytes(16 * d))   # chèn im lặng giữ đúng thời gian
        self.decrypt_blocks(n, ct)
        self.frames += 1
        self.next_n = (n + len(ct) // 16) & MASK32

    def decrypt_blocks(self, n, ct):
        pt = self.e.crypt(n, ct)
        le = pt if self.f.endian == "little" else swap_endian(pt, self.f.width)
        if self.wav:
            self.wav.writeframesraw(le)
        a = to_le_arr(self.f.tcs, le)
        sq = sum(x * x for x in a)
        pk = max(max(a), -min(a))
        self.tot_sumsq += sq
        self.tot_n += len(a)
        self.tot_peak = max(self.tot_peak, pk)
        self.win_sumsq += sq
        self.win_n += len(a)
        self.win_peak = max(self.win_peak, pk)
        if self.expect == "ramp":
            u = to_le_arr(self.f.tcu, le)
            s0 = n * 16 // self.f.width
            mask = (1 << (8 * self.f.width)) - 1
            self.ramp_bad += sum(1 for i, x in enumerate(u) if x != ((s0 + i) & mask))
            self.ramp_checked += len(u)
        self.blocks += len(ct) // 16

    def window_level(self):
        rms = math.sqrt(self.win_sumsq / self.win_n) if self.win_n else 0
        s = "RMS %6.1f dBFS  peak %6.1f dBFS" % (dbfs(rms, self.f.width), dbfs(self.win_peak, self.f.width))
        self.win_sumsq = self.win_n = self.win_peak = 0
        return s

    def close(self):
        if self.wav:
            self.wav.close()
            self.wav = None

    def summary(self, parser, elapsed, wav_path):
        tot = self.blocks + self.lost
        print("\n===== KẾT QUẢ =====")
        print("Thời gian           : %.1f s" % elapsed)
        print("Frame hợp lệ        : %d  (%d block = %d byte)" % (self.frames, self.blocks, self.blocks * 16))
        print("Lỗi CRC             : %d    byte rác bỏ qua: %d" % (parser.crc_errors, parser.junk_bytes))
        print("Block bị mất        : %d / %d (%.2f%%)" % (self.lost, tot, 100.0 * self.lost / tot if tot else 0))
        print("Sai SID / sai độ dài: %d / %d" % (self.wrong_sid, self.bad_len))
        if self.backwards:
            print("!! CẢNH BÁO: %d frame có counter đi LÙI. FPGA có thể đã reset và dùng lại IV"
                  " -> nguy cơ trùng keystream. Hãy tạo IV mới." % self.backwards)
        if self.tot_n:
            rms = math.sqrt(self.tot_sumsq / self.tot_n)
            print("Mức tín hiệu        : RMS %.1f dBFS, peak %.1f dBFS"
                  % (dbfs(rms, self.f.width), dbfs(self.tot_peak, self.f.width)))
        if self.expect == "ramp":
            if self.ramp_checked and self.ramp_bad == 0:
                print("Kiểm tra RAMP       : OK - %d sample giải mã khớp 100%% (key/IV/FPGA đúng)"
                      % self.ramp_checked)
            else:
                print("Kiểm tra RAMP       : FAIL - %d/%d sample sai (sai key/IV, sai endian, hoặc FPGA lỗi)"
                      % (self.ramp_bad, self.ramp_checked))
        if wav_path:
            print("WAV                 : %s" % wav_path)


# --------------------------------------------------------------------------
# Link: serial hoặc file
# --------------------------------------------------------------------------
class Link:
    def __init__(self):
        self.raw = None
        self.is_file = False

    def read_chunk(self):
        d = self._read()
        if d and self.raw:
            self.raw.write(d)
        return d

    def close(self):
        if self.raw:
            self.raw.close()


class SerialLink(Link):
    def __init__(self, port, baud):
        super().__init__()
        try:
            import serial
        except ImportError:
            sys.exit("Thiếu pyserial: pip install pyserial")
        self.ser = serial.Serial(port, baud, timeout=0.1)

    def _read(self):
        return self.ser.read(max(1, self.ser.in_waiting))

    def write(self, b):
        self.ser.write(b)
        self.ser.flush()

    def flush_input(self):
        self.ser.reset_input_buffer()

    def close(self):
        super().close()
        self.ser.close()


class FileLink(Link):
    def __init__(self, path):
        super().__init__()
        self.f = open(path, "rb")
        self.is_file = True

    def _read(self):
        d = self.f.read(4096)
        return d if d else None

    def write(self, b):
        pass

    def flush_input(self):
        pass

    def close(self):
        super().close()
        self.f.close()


def open_link(spec, baud):
    return FileLink(spec[5:]) if spec.startswith("file:") else SerialLink(spec, baud)


def wait_ack(link, parser, orig_type, pending, timeout=1.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = link.read_chunk()
        if d is None:
            return None
        status = None
        for t, p in (parser.feed(d) if d else []):
            if status is None and t == T_ACK and len(p) >= 2 and p[0] == orig_type:
                status = p[1]
            else:
                pending.append((t, p))   # giữ lại mọi frame khác (vd. DATA đầu tiên)
        if status is not None:
            return status
    return None


def send_cmd(link, parser, ftype, payload, pending, name, retries=3):
    for _ in range(retries):
        link.write(build_frame(ftype, payload))
        st = wait_ack(link, parser, ftype, pending)
        if st == 0:
            print("  %-8s -> ACK OK" % name)
            return True
        if st is not None:
            print("  %-8s -> FPGA báo lỗi, status=%d" % (name, st))
    print("  %-8s -> không có ACK" % name)
    return False


def receive_loop(link, parser, dec, pending, duration=None, quiet=False):
    t0 = last = time.time()
    last_blocks = 0

    def handle(items):
        for t, p in items:
            if t == T_DATA:
                dec.on_data(p)
    handle(pending)
    try:
        while True:
            now = time.time()
            if duration and now - t0 >= duration:
                break
            d = link.read_chunk()
            if d is None:
                handle(parser.finish())
                break
            if d:
                handle(parser.feed(d))
            now = time.time()
            if not quiet and not link.is_file and now - last >= 1.0:
                rate = (dec.blocks - last_blocks) * 16 / (now - last) / 1024.0
                sys.stderr.write("\r[%5.0fs] frames %d  lost %d  crc_err %d  %.1f KB/s  %s   "
                                 % (now - t0, dec.frames, dec.lost, parser.crc_errors, rate,
                                    dec.window_level()))
                sys.stderr.flush()
                last, last_blocks = now, dec.blocks
    except KeyboardInterrupt:
        pass
    return time.time() - t0


# --------------------------------------------------------------------------
# Mô phỏng FPGA (golden model)
# --------------------------------------------------------------------------
def make_plain(kind, nbytes, fmt, freq=1000.0, wav_path=None):
    """Trả về plaintext (đã ở endian của đường truyền) dài đúng nbytes (hoặc ngắn hơn với wav)."""
    nwords = nbytes // fmt.width
    mask = (1 << (8 * fmt.width)) - 1
    full = (1 << (8 * fmt.width - 1)) - 1
    if kind == "ramp":
        arr = array.array(fmt.tcu, (w & mask for w in range(nwords)))
    elif kind == "tone":
        arr = array.array(fmt.tcs, (int(0.5 * full * math.sin(2 * math.pi * freq * (w // fmt.channels) / fmt.rate))
                                    for w in range(nwords)))
    elif kind == "wav":
        with wave.open(wav_path, "rb") as w:
            if (w.getsampwidth(), w.getnchannels()) != (fmt.width, fmt.channels):
                sys.exit("WAV không khớp --width/--channels")
            le = w.readframes(w.getnframes())[:nbytes]
        return le if fmt.endian == "little" else swap_endian(le + bytes(-len(le) % fmt.width), fmt.width)[:len(le)]
    else:
        sys.exit("source không hợp lệ")
    if sys.byteorder == "big":
        arr.byteswap()
    le = arr.tobytes()
    return le if fmt.endian == "little" else swap_endian(le, fmt.width)


def simulate_capture(engine, sid, plain, bpf, drop=0.0, corrupt=0.0, rng=None):
    rng = rng or random.Random()
    fsz = 16 * bpf
    if len(plain) % fsz:
        plain += bytes(fsz - len(plain) % fsz)
    out = bytearray()
    n = 0
    for off in range(0, len(plain), fsz):
        ct = engine.crypt(n, plain[off:off + fsz])
        fr = bytearray(build_frame(T_DATA, bytes([sid]) + engine.ctr32_of(n).to_bytes(4, "big") + ct))
        n += bpf
        if rng.random() < drop:
            continue
        if rng.random() < corrupt:
            fr[rng.randrange(2, len(fr))] ^= 1 << rng.randrange(8)
        out += fr
    return bytes(out)


# --------------------------------------------------------------------------
# Các lệnh
# --------------------------------------------------------------------------
def verilog_lit(b):
    return "128'h" + b.hex()


def cmd_keygen(a):
    if os.path.exists(a.key_file) and not a.force:
        sys.exit("%s đã tồn tại (dùng --force để ghi đè)" % a.key_file)
    key = os.urandom(16)
    fd = os.open(a.key_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key.hex() + "\n")
    print("Đã tạo khóa -> %s" % a.key_file)
    if a.show:
        print("KEY = %s" % verilog_lit(key))


def cmd_newiv(a):
    iv, e = make_iv(a.log, a.label)
    print("Phiên #%d   SID = 0x%02X" % (e["session"], e["sid"]))
    print("IV (hex)    : %s" % iv.hex())
    print("IV (Verilog): %s" % verilog_lit(iv))
    print("(đã ghi vào %s - IV này coi như đã dùng, không bao giờ dùng lại)" % a.log)


def cmd_sessions(a):
    for s in load_sessions(a.log):
        print("#%-3d %s  sid=0x%02X  iv=%s  %s" % (s["session"], s["time"], s["sid"], s["iv"], s.get("label", "")))


def cmd_ports(a):
    try:
        from serial.tools import list_ports
    except ImportError:
        sys.exit("Thiếu pyserial: pip install pyserial")
    for p in list_ports.comports():
        print("%-12s %s" % (p.device, p.description))


def cmd_budget(a):
    fmt = AudioFmt(a)
    pay = fmt.rate * fmt.width * fmt.channels
    fsz = 11 + 16 * a.bpf
    line = pay / (16.0 * a.bpf) * fsz
    need = line * 10
    print("Dữ liệu audio     : %.1f KB/s" % (pay / 1024.0))
    print("Kích thước frame  : %d byte (overhead %.1f%%)" % (fsz, 100.0 * (fsz - 16 * a.bpf) / fsz))
    print("Cần tối thiểu     : %.0f baud (8N1)   Đang dùng: %d baud" % (need, a.baud))
    ok = need <= a.baud * 0.95
    print("Kết luận          : %s" % ("ĐỦ băng thông" if ok else "KHÔNG ĐỦ -> giảm sample rate / tăng baud / dùng mono"))
    mx = a.baud * 0.95 / 10.0 / fsz * 16 * a.bpf / (fmt.width * fmt.channels)
    print("Sample rate tối đa: ~%.0f Hz với baud này" % mx)
    if a.baud <= 115200:
        print("Lưu ý: RS-232 (MAX232) trên DE2 chỉ ổn tới ~115200-250000 baud; muốn >= 1 Mbaud hãy dùng "
              "mạch USB-UART (FTDI/CP2102) nối vào GPIO.")


def cmd_session(a):
    key = load_key(a)
    fmt = AudioFmt(a)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    wav_path = a.out or "recv_%s.wav" % stamp
    raw_path = a.raw_out or "recv_%s.bin" % stamp
    link = open_link(a.port, a.baud)
    link.raw = open(raw_path, "wb")
    parser, pending = FrameParser(), []
    if a.no_config:
        iv = resolve_iv(a)
    else:
        if link.is_file:
            sys.exit("Không cấu hình được khi đọc từ file, dùng --no-config hoặc lệnh 'decrypt'")
        iv, e = make_iv(a.log, a.label)
        print("Phiên #%d  SID=0x%02X  IV=%s" % (e["session"], e["sid"], iv.hex()))
        link.write(build_frame(T_STOP))
        time.sleep(0.3)
        link.flush_input()
        steps = []
        if a.send_key:
            steps.append((T_SET_KEY, key, "SET_KEY"))
        steps += [(T_SET_IV, iv, "SET_IV"),
                  (T_SET_SRC, bytes([1 if a.source == "ramp" else 0]), "SET_SRC"),
                  (T_START, b"", "START")]
        for t, p, name in steps:
            if not send_cmd(link, parser, t, p, pending, name):
                link.close()
                sys.exit("Cấu hình FPGA thất bại")
    expect = "ramp" if a.source == "ramp" else a.expect
    dec = Decryptor(CtrEngine(key, iv), iv[0], fmt, wav_path, expect)
    print("Đang nhận... (Ctrl-C để dừng)  WAV -> %s   RAW -> %s" % (wav_path, raw_path))
    el = receive_loop(link, parser, dec, pending, a.duration)
    if not link.is_file and not a.no_config:
        try:
            link.write(build_frame(T_STOP))
        except Exception:
            pass
    dec.close()
    link.close()
    dec.summary(parser, el, wav_path)


def cmd_decrypt(a):
    key = load_key(a)
    fmt = AudioFmt(a)
    iv = resolve_iv(a)
    out = a.out or os.path.splitext(a.capture)[0] + ".wav"
    dec = Decryptor(CtrEngine(key, iv), iv[0], fmt, out, a.expect)
    parser = FrameParser()
    t0 = time.time()
    if a.raw:
        data = open(a.capture, "rb").read()
        data = data[:len(data) // 16 * 16]
        dec.decrypt_blocks(0, data)
    else:
        link = FileLink(a.capture)
        receive_loop(link, parser, dec, [], quiet=True)
        link.close()
    dec.close()
    dec.summary(parser, time.time() - t0, out)


def cmd_simulate(a):
    key = load_key(a)
    fmt = AudioFmt(a)
    if a.iv or a.session:
        iv = resolve_iv(a)
    else:
        iv, e = make_iv(a.log, "simulate")
        print("Phiên #%d  SID=0x%02X  IV=%s" % (e["session"], e["sid"], iv.hex()))
    nbytes = int(a.seconds * fmt.rate) * fmt.width * fmt.channels
    plain = make_plain(a.source, nbytes, fmt, a.freq, a.wav)
    cap = simulate_capture(CtrEngine(key, iv), iv[0], plain, a.bpf, a.drop, a.corrupt,
                           random.Random(a.seed))
    with open(a.out, "wb") as f:
        f.write(cap)
    print("Đã ghi %d byte capture -> %s" % (len(cap), a.out))
    print("Giải mã thử: python3 %s decrypt %s --session latest%s" %
          (os.path.basename(sys.argv[0]), a.out, " --expect ramp" if a.source == "ramp" else ""))


def cmd_analyze(a):
    with wave.open(a.wav, "rb") as w:
        ch, wd, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    tcs = {2: "h", 4: "i"}.get(wd)
    if not tcs:
        sys.exit("Chỉ phân tích WAV 16/32-bit")
    arr = to_le_arr(tcs, raw)
    ch0 = arr[0::ch]
    mean = sum(ch0) / len(ch0)
    rms = math.sqrt(sum(x * x for x in ch0) / len(ch0))
    peak = max(max(ch0), -min(ch0))
    zeros = sum(1 for i in range(0, len(ch0) - 15, 16) if not any(ch0[i:i + 16]))
    print("Kênh %d, %d Hz, %d-bit, %.2f s" % (ch, rate, wd * 8, n / float(rate)))
    print("DC offset : %.1f   RMS: %.1f dBFS   peak: %.1f dBFS" % (mean, dbfs(rms, wd), dbfs(peak, wd)))
    print("Đoạn im lặng tuyệt đối (nghi mất frame): %.2f%%" % (100.0 * zeros * 16 / len(ch0)))
    try:
        import numpy as np
        x = np.array(ch0, dtype=np.float64)
        x *= np.hanning(len(x))
        sp = np.abs(np.fft.rfft(x))
        sp[0] = 0
        print("Tần số trội: %.1f Hz" % (np.argmax(sp) * rate / float(len(x))))
    except ImportError:
        print("(cài numpy để xem tần số trội)")


def cmd_selftest(a):
    ok = True

    def check(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print("[%s] %s" % ("PASS" if cond else "FAIL", name))
    print("AES backend:", "pycryptodome" if HAVE_CRYPTO else "Python thuần (fallback)")
    check("CRC16-CCITT('123456789') == 0x29B1", crc16(b"123456789") == 0x29B1)
    fips = make_ecb(bytes(range(16))).encrypt(bytes.fromhex("00112233445566778899aabbccddeeff"))
    check("AES-128 FIPS-197", fips.hex() == "69c4e0d86a7b0430d8cdb78070b4c55a")
    key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
    iv = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff")
    pt = bytes.fromhex("6bc1bee22e409f96e93d7e117393172a" "ae2d8a571e03ac9c9eb76fac45af8e51"
                       "30c81c46a35ce411e5fbc1191a0a52ef" "f69f2445df4f9b17ad2b417be66c3710")
    ct = bytes.fromhex("874d6191b620e3261bef6864990db6ce" "9806f66b7970fdff8617187bb9fffdff"
                       "5ae4df3edbd5d35e5b4f09020db03eab" "1e031dda2fbe03d1792170a0f3009cee")
    eng = CtrEngine(key, iv)
    check("NIST SP800-38A F.5.1 (4 block)", eng.crypt(0, pt) == ct)
    check("Truy cập ngẫu nhiên block #2", eng.crypt(2, pt[32:48]) == ct[32:48])
    fr = build_frame(T_DATA, b"\x01" * 21)
    p = FrameParser()
    got = p.feed(b"\x00\xA5" + fr[:7]) + p.feed(fr[7:] + b"\xFF" + fr)
    check("Parser: ghép frame, bỏ rác", len(got) == 2)

    class NS:
        pass
    n = NS()
    n.rate, n.channels, n.width, n.endian = 48000, 1, 2, "big"
    fmt = AudioFmt(n)
    k2, iv2 = os.urandom(16), os.urandom(12) + bytes(4)
    plain = make_plain("ramp", 48000 * 2 * 1, fmt)
    tmp = tempfile.mkdtemp()
    for name, drop, cor in (("sạch", 0.0, 0.0), ("mất 5% frame + lỗi 3% bit", 0.05, 0.03)):
        cap = simulate_capture(CtrEngine(k2, iv2), iv2[0], plain, 8, drop, cor, random.Random(1))
        path = os.path.join(tmp, "c.bin")
        open(path, "wb").write(cap)
        dec = Decryptor(CtrEngine(k2, iv2), iv2[0], fmt, os.path.join(tmp, "o.wav"), "ramp")
        pr = FrameParser()
        link = FileLink(path)
        receive_loop(link, pr, dec, [], quiet=True)
        dec.close()
        extra = (dec.lost > 0 and pr.crc_errors > 0) if drop else (dec.lost == 0 and pr.crc_errors == 0)
        check("Round-trip ramp, %s (lost=%d, crc=%d, sai=%d)" % (name, dec.lost, pr.crc_errors, dec.ramp_bad),
              dec.ramp_checked > 0 and dec.ramp_bad == 0 and extra)
    # sai key phải bị phát hiện
    dec = Decryptor(CtrEngine(os.urandom(16), iv2), iv2[0], fmt, None, "ramp")
    link = FileLink(path)
    receive_loop(link, FrameParser(), dec, [], quiet=True)
    check("Sai key bị phát hiện bởi kiểm tra ramp", dec.ramp_bad > 0)
    print("\nTẤT CẢ ĐỀU PASS" if ok else "\nCÓ LỖI")
    sys.exit(0 if ok else 1)


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="AES-CTR host tool cho DE2", formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def key_args(p):
        p.add_argument("--key", help="khóa HEX 32 ký tự")
        p.add_argument("--key-file", default="aes.key")
        p.add_argument("--log", default="sessions.jsonl")

    def audio_args(p):
        p.add_argument("--rate", type=int, default=48000)
        p.add_argument("--channels", type=int, default=1)
        p.add_argument("--width", type=int, default=2, help="byte/sample: 2 (16-bit) hoặc 4 (32-bit)")
        p.add_argument("--endian", choices=["big", "little"], default="big", help="thứ tự byte của sample trong block")

    def iv_args(p):
        p.add_argument("--iv", help="IV HEX 32 ký tự")
        p.add_argument("--session", help="số phiên hoặc 'latest' (lấy IV từ sessions.jsonl)")

    p = sub.add_parser("keygen"); p.add_argument("--key-file", default="aes.key")
    p.add_argument("--force", action="store_true"); p.add_argument("--show", action="store_true")
    p.set_defaults(f=cmd_keygen)

    p = sub.add_parser("newiv"); p.add_argument("--log", default="sessions.jsonl")
    p.add_argument("--label", default=""); p.set_defaults(f=cmd_newiv)

    p = sub.add_parser("sessions"); p.add_argument("--log", default="sessions.jsonl")
    p.set_defaults(f=cmd_sessions)

    p = sub.add_parser("ports"); p.set_defaults(f=cmd_ports)

    p = sub.add_parser("budget"); audio_args(p)
    p.add_argument("--baud", type=int, default=2000000)
    p.add_argument("--bpf", type=int, default=8, help="số block 16 byte mỗi frame (1..15)")
    p.set_defaults(f=cmd_budget)

    p = sub.add_parser("session"); key_args(p); audio_args(p); iv_args(p)
    p.add_argument("--port", required=True, help="COMx, /dev/ttyUSBx hoặc file:capture.bin")
    p.add_argument("--baud", type=int, default=2000000)
    p.add_argument("--out"); p.add_argument("--raw-out"); p.add_argument("--duration", type=float)
    p.add_argument("--source", choices=["mic", "ramp"], default="mic")
    p.add_argument("--expect", choices=["ramp"])
    p.add_argument("--send-key", action="store_true", help="gửi cả key tới FPGA (chỉ để demo)")
    p.add_argument("--no-config", action="store_true", help="không cấu hình FPGA, chỉ nghe (cần --iv/--session)")
    p.add_argument("--label", default="")
    p.set_defaults(f=cmd_session)

    p = sub.add_parser("decrypt"); key_args(p); audio_args(p); iv_args(p)
    p.add_argument("capture"); p.add_argument("--out"); p.add_argument("--expect", choices=["ramp"])
    p.add_argument("--raw", action="store_true", help="file là ciphertext thô, bắt đầu từ block 0, không có frame")
    p.set_defaults(f=cmd_decrypt)

    p = sub.add_parser("simulate"); key_args(p); audio_args(p); iv_args(p)
    p.add_argument("--out", default="sim_capture.bin")
    p.add_argument("--source", choices=["tone", "ramp", "wav"], default="tone")
    p.add_argument("--seconds", type=float, default=3.0); p.add_argument("--freq", type=float, default=1000.0)
    p.add_argument("--wav"); p.add_argument("--bpf", type=int, default=8)
    p.add_argument("--drop", type=float, default=0.0); p.add_argument("--corrupt", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=None)
    p.set_defaults(f=cmd_simulate)

    p = sub.add_parser("analyze"); p.add_argument("wav"); p.set_defaults(f=cmd_analyze)
    p = sub.add_parser("selftest"); p.set_defaults(f=cmd_selftest)

    a = ap.parse_args()
    if getattr(a, "bpf", 8) not in range(1, 16):
        sys.exit("--bpf phải trong 1..15")
    a.f(a)


if __name__ == "__main__":
    main()
