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