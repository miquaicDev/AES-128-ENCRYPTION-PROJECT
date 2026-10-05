import serial
import struct
import numpy as np
import sounddevice as sd
from Crypto.Cipher import AES

# Cấu hình âm thanh & truyền thông
SERIAL_PORT = 'COM3'        # Đổi thành cổng COM thực tế
BAUD_RATE = 921600          # Cần baudrate cao cho audio PCM
SAMPLE_RATE = 16000         # 16 kHz, 16-bit Mono (phù hợp với mic thoại)
CHANNELS = 1

# Pre-shared Key 128-bit (Khớp với hardcode trong Verilog)
AES_KEY = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")

# Định dạng gói tin giả định từ FPGA:
# [SYNC_BYTE (0xAA)] [12-byte NONCE] [128-byte CIPHERTEXT (8 blocks AES)]
SYNC_BYTE = b'\xAA'
NONCE_LEN = 12
BLOCK_CHUNK = 128  # 128 bytes = 8 blocks AES-128 = 64 samples âm thanh (16-bit)

def audio_playback_stream():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    
    # Mở output stream âm thanh
    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16'
    )
    stream.start()

    print("[*] Đang chờ đồng bộ dữ liệu từ FPGA...")

    try:
        while True:
            # 1. Tìm Sync Byte mở đầu session
            b = ser.read(1)
            if b != SYNC_BYTE:
                continue

            # 2. Đọc Nonce của phiên
            nonce = ser.read(NONCE_LEN)
            if len(nonce) < NONCE_LEN:
                continue

            print(f"[+] Đồng bộ thành công. Nonce: {nonce.hex()}")

            # 3. Khởi tạo AES-CTR Decryptor
            # initial_value=1 tương ứng với Counter 32-bit bắt đầu từ 1
            cipher = AES.new(AES_KEY, AES.MODE_CTR, nonce=nonce, initial_value=1)

            # 4. Vòng lặp giải mã stream dữ liệu
            while True:
                ciphertext = ser.read(BLOCK_CHUNK)
                if len(ciphertext) < BLOCK_CHUNK:
                    break

                # AES CTR decrypt (chính là encrypt counter rồi XOR với ciphertext)
                plaintext_pcm = cipher.decrypt(ciphertext)

                # Chuyển raw bytes thành mảng PCM 16-bit
                audio_samples = np.frombuffer(plaintext_pcm, dtype=np.int16)

                # Đưa ra loa laptop
                stream.write(audio_samples)

    except KeyboardInterrupt:
        print("\n[*] Dừng chương trình.")
    finally:
        stream.stop()
        stream.close()
        ser.close()

if __name__ == "__main__":
    audio_playback_stream()