import sys
import os
import zlib
import math
import argparse
from collections import Counter

SIGNATURE = b"ZMH1"
MAX_FILE_SIZE = 100 * 1024 * 1024

def build_huffman_codes(freqs):
    if not freqs:
        return {}
    if len(freqs) == 1:
        return {next(iter(freqs)): "0"}

    nodes = [[count, [b], {b: ""}] for b, count in freqs.items()]

    while len(nodes) > 1:
        nodes.sort(key=lambda x: (x[0], len(x[1]), x[1]))
        left = nodes.pop(0)
        right = nodes.pop(0)

        new_codes = {}
        for b, code in left[2].items():
            new_codes[b] = "0" + code
        for b, code in right[2].items():
            new_codes[b] = "1" + code

        parent = [left[0] + right[0], sorted(left[1] + right[1]), new_codes]
        nodes.append(parent)

    return nodes[0][2]


def build_header_bytes(crc, orig_len, freqs):
    freq_items = [f"{b}:{c}" for b, c in sorted(freqs.items())]
    header_str = f"{crc}\n{orig_len}\n{','.join(freq_items)}\n"
    return SIGNATURE + b"\n" + header_str.encode("utf-8")
def compress(in_path, out_path):
    try:
        with open(in_path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        print(f"Ошибочка! входной файл не найден: {in_path}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Ошибочка! непредвиденный сбой: {e}", file=sys.stderr)
        sys.exit(2)
    orig_len = len(data)
    crc = zlib.crc32(data) & 0xFFFFFFFF

    if orig_len == 0:
        header = build_header_bytes(crc, 0, {})
        try:
            with open(out_path, "wb") as f:
                f.write(header)
        except Exception as e:
            print(f"Ошибочка! непредвиденный сбой: {e}", file=sys.stderr)
            sys.exit(2)
        return
    freqs = Counter(data)
    codes = build_huffman_codes(freqs)
    bit_str = "".join(codes[b] for b in data)
    pad = (8 - len(bit_str) % 8) % 8
    bit_str += "0" * pad
    payload = bytearray(int(bit_str[i:i+8], 2) for i in range(0, len(bit_str), 8))
    header = build_header_bytes(crc, orig_len, freqs)
    try:
        with open(out_path, "wb") as f:
            f.write(header)
            f.write(payload)
    except Exception as e:
        print(f"Ошибочка! непредвиденный сбой: {e}", file=sys.stderr)
        sys.exit(2)
def decompress(in_path, out_path):
    if not os.path.exists(in_path):
        print(f"Ошибочка! входной файл не найден: {in_path}", file=sys.stderr)
        sys.exit(2)
    if os.path.getsize(in_path) < len(SIGNATURE):
        print(f"Ошибочка! файл обрезан: {in_path}", file=sys.stderr)
        sys.exit(2)
    try:
        with open(in_path, "rb") as f:
            sig_line = f.readline().strip()
            if sig_line != SIGNATURE:
                print(f"Ошибочка! некорректная сигнатура формата: {sig_line!r}", file=sys.stderr)
                sys.exit(3)
            line_crc = f.readline()
            line_len = f.readline()
            line_freq = f.readline()
            if not line_crc or not line_len or not line_freq:
                print(f"Ошибочка! файл обрезан внутри заголовка: {in_path}", file=sys.stderr)
                sys.exit(2)
            crc_expected = int(line_crc.strip())
            orig_len = int(line_len.strip())
            freq_str = line_freq.strip().decode("utf-8")
            payload = f.read()
    except ValueError as e:
        print(f"Ошибочка! поврежден заголовок файла: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Ошибочка! непредвиденный сбой: {e}", file=sys.stderr)
        sys.exit(2)
    if orig_len > MAX_FILE_SIZE:
        print(f"Ошибочка! поврежден заголовок: заявленный размер {orig_len} превышает лимит {MAX_FILE_SIZE}", file=sys.stderr)
        sys.exit(2)
    if orig_len == 0:
        if crc_expected != 0:
            print("Ошибочка! нарушение целостности данных пустого файла", file=sys.stderr)
            sys.exit(4)
        try:
            with open(out_path, "wb") as f:
                pass
        except Exception as e:
            print(f"Ошибочка! непредвиденный сбой: {e}", file=sys.stderr)
            sys.exit(2)
        return
    freqs = {}
    for item in freq_str.split(","):
        if not item:
            continue
        parts = item.split(":")
        if len(parts) != 2:
            print("Ошибочка! повреждена структура таблицы частот", file=sys.stderr)
            sys.exit(2)
        try:
            b_val = int(parts[0])
            c_val = int(parts[1])
        except ValueError:
            print("Ошибочка! нечисловые данные в таблице частот", file=sys.stderr)
            sys.exit(2)

        if not (0 <= b_val <= 255) or c_val <= 0:
            print("Ошибочка! недопустимые значения в таблице частот", file=sys.stderr)
            sys.exit(2)
        freqs[b_val] = c_val
    if not freqs:
        print("Ошибочка! пустая таблица частот для непустого файла", file=sys.stderr)
        sys.exit(2)

    if sum(freqs.values()) != orig_len:
        print(f"Ошибочка! повреждена таблица частот: сумма частот {sum(freqs.values())} не равна длине данных {orig_len}", file=sys.stderr)
        sys.exit(2)
    codes = build_huffman_codes(freqs)
    rev_codes = {c: b for b, c in codes.items()}

    recovered = bytearray()
    if len(freqs) == 1:
        recovered = bytearray([next(iter(freqs))] * orig_len)
    else:
        bit_str = "".join(f"{byte:08b}" for byte in payload)
        cur = ""
        for bit in bit_str:
            cur += bit
            if cur in rev_codes:
                recovered.append(rev_codes[cur])
                cur = ""
                if len(recovered) == orig_len:
                    break
    if len(recovered) != orig_len:
        print(f"Ошибочка! файл обрезан в потоке данных (восстановлено {len(recovered)} из {orig_len})", file=sys.stderr)
        sys.exit(2)
    crc_actual = zlib.crc32(recovered) & 0xFFFFFFFF
    if crc_actual != crc_expected:
        print(f"Ошибочка! нарушение целостности данных: ожидался CRC {crc_expected}, получен {crc_actual}", file=sys.stderr)
        sys.exit(4)

    try:
        with open(out_path, "wb") as f:
            f.write(recovered)
    except Exception as e:
        print(f"Ошибочка! непредвиденный сбой: {e}", file=sys.stderr)
        sys.exit(2)

def print_stats(path):
    if not os.path.exists(path):
        print(f"Ошибочка! файл не найден: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception as e:
        print(f"Ошибочка! непредвиденный сбой: {e}", file=sys.stderr)
        sys.exit(2)
    orig_len = len(data)
    if orig_len == 0:
        hdr_empty_len = len(build_header_bytes(0, 0, {}))
        print("Файл:", path)
        print("Эмпирическая энтропия H (бит/символ):", 0.0)
        print("Средняя длина кодового слова l_avg (бит/символ):", 0.0)
        print("Размер заголовка (байт):", hdr_empty_len)
        print("Размер сжатых данных (байт):", 0)
        print("Фактический коэффициент сжатия (байт/байт): не определен (файл пуст)")
        return
    freqs = Counter(data)
    codes = build_huffman_codes(freqs)
    H = -sum((c / orig_len) * math.log2(c / orig_len) for c in freqs.values())
    avg_l = sum((c / orig_len) * len(codes[b]) for b, c in freqs.items())
    tmp_file = path + ".tmp.zmh"
    try:
        compress(path, tmp_file)
        sz = os.path.getsize(tmp_file)
        header_sz = len(build_header_bytes(zlib.crc32(data) & 0xFFFFFFFF, orig_len, freqs))
        payload_sz = sz - header_sz
        cr = sz / orig_len
    finally:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
    print("Файл:", path)
    print("Эмпирическая энтропия H (бит/символ):", H)
    print("Средняя длина кодового слова l_avg (бит/символ):", avg_l)
    print("Размер заголовка (байт):", header_sz)
    print("Размер сжатых данных (байт):", payload_sz)
    print("Фактический коэффициент сжатия (байт/байт):", cr)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", action="store_true")
    parser.add_argument("file", nargs="?", default=None)
    parser.add_argument("-c", "--compress", action="store_true")
    parser.add_argument("-d", "--decompress", action="store_true")
    parser.add_argument("-o", "--output")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    if args.variant:
        print("Вариант: s=5, k=3, M=4, L=3, d=3, q=3, eps=1e-4")
        return

    if not args.file:
        print("Ошибочка! укажите входной файл (либо флаг --variant)", file=sys.stderr)
        sys.exit(1)

    if args.stats:
        print_stats(args.file)
    elif args.compress:
        out = args.output if args.output else args.file + ".zmh"
        compress(args.file, out)
        print("Сжато в", out)
    elif args.decompress:
        if args.output:
            out = args.output
        else:
            if args.file.endswith(".zmh"):
                out = args.file[:-4] + ".decompressed"
            else:
                out = args.file + ".decompressed"
        decompress(args.file, out)
        print("Восстановлено в", out)
    else:
        print("Ошибочка! укажите действие: --compress, --decompress или --stats", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()