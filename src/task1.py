import sys
import json
import argparse
import random
import math
from fractions import Fraction

def to_frac(val):
    if type(val) is bool:
        raise ValueError(f"получено булево значение {val!r}")
    if isinstance(val, int):
        return Fraction(val)
    if isinstance(val, str):
        text = val.strip()
        if "/" in text:
            num, den = text.split("/")
            return Fraction(int(num.strip()), int(den.strip()))
        return Fraction(text)
    raise ValueError(f"вероятность должна быть строкой ('1/3', '0.3'), получен {type(val).__name__}: {val!r}")

def check_dist(dist, place_name):
    if not isinstance(dist, dict) or len(dist) == 0:
        raise ValueError(f"распределение в {place_name} не задано или не является словарем")
    total = Fraction(0)
    for sym, p_val in dist.items():
        p = to_frac(p_val)
        if p < 0:
            raise ValueError(f"отрицательная вероятность у символа '{sym}' в {place_name}")
        total += p
    if total != 1:
        raise ValueError(f"распределение в {place_name} не нормировано: сумма = {total} (ожидалась 1)")

def validate_config(data):
    if not isinstance(data, dict):
        raise ValueError("корневая структура JSON должна быть объектом")
    if "context_models" in data or "default_model" in data:
        if "default_model" not in data:
            raise ValueError("в расширенном формате отсутствует обязательное поле 'default_model'")
        check_dist(data["default_model"], "default_model")

        depth = data.get("memory_depth", 0)
        if type(depth) is not int or depth < 0:
            raise ValueError(f"параметр 'memory_depth' должен быть неотрицательным целым числом, получено: {depth!r}")

        if "context_models" in data:
            if not isinstance(data["context_models"], dict):
                raise ValueError("поле 'context_models' должно быть словарем контекстов")
            for ctx, dist in data["context_models"].items():
                if not isinstance(ctx, str):
                    raise ValueError(f"ключ контекста {ctx!r} должен быть строкой")
                if len(ctx) > depth:
                    raise ValueError(f"длина контекста '{ctx}' ({len(ctx)}) превышает memory_depth ({depth})")
                check_dist(dist, f"контексте '{ctx}'")
        return
    if "source" not in data:
        raise ValueError("отсутствует обязательное поле 'source'")
    if not isinstance(data["source"], list):
        raise ValueError("поле 'source' должно быть списком переключателей, а не строкой")
    if len(data["source"]) == 0:
        raise ValueError("список 'source' не должен быть пустым")

    if "models" not in data or not isinstance(data["models"], dict) or len(data["models"]) == 0:
        raise ValueError("блок 'models' пуст или отсутствует")
    if "switches" not in data or not isinstance(data["switches"], dict) or len(data["switches"]) == 0:
        raise ValueError("блок 'switches' пуст или отсутствует")

    for m_name, dist in data["models"].items():
        check_dist(dist, f"модели '{m_name}'")

    for sw_name, dist in data["switches"].items():
        check_dist(dist, f"переключателе '{sw_name}'")
        for m_name in dist.keys():
            if m_name not in data["models"]:
                raise ValueError(f"в переключателе '{sw_name}' указана неизвестная модель '{m_name}'")

    for sw_name in data["source"]:
        if sw_name not in data["switches"]:
            raise ValueError(f"в списке 'source' указан неизвестный переключатель '{sw_name}'")


def get_symbol_dist(data, step, context=""):
    if "context_models" in data or "default_model" in data:
        depth = data.get("memory_depth", 0)
        ctx = context[-depth:] if depth > 0 else ""
        if "context_models" in data and ctx in data["context_models"]:
            dist = data["context_models"][ctx]
        else:
            dist = data.get("default_model", {})
        return {sym: to_frac(p) for sym, p in dist.items()}

    L = len(data["source"])
    sw_name = data["source"][step % L]
    sw_dist = data["switches"][sw_name]
    res = {}
    for m_name, m_prob in sw_dist.items():
        pm = to_frac(m_prob)
        for sym, s_prob in data["models"][m_name].items():
            ps = to_frac(s_prob)
            res[sym] = res.get(sym, Fraction(0)) + pm * ps
    return res
def sample_symbol(dist, rng):
    items = list(dist.items())
    lcm_val = 1
    for _, p in items:
        lcm_val = math.lcm(lcm_val, p.denominator)
    weights = [p.numerator * (lcm_val // p.denominator) for _, p in items]
    total_w = sum(weights)
    rnd = rng.randrange(total_w)
    acc = 0
    for idx, w in enumerate(weights):
        acc += w
        if rnd < acc:
            return items[idx][0]
    return items[-1][0]
def prob_of_sequence(data, seq, start_step=0):
    prob = Fraction(1)
    for i, sym in enumerate(seq):
        dist = get_symbol_dist(data, start_step + i)
        prob *= dist.get(sym, Fraction(0))
        if prob == 0:
            break
    return prob
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", action="store_true")
    parser.add_argument("--file", type=str)
    parser.add_argument("--mode", type=int, choices=[1, 2])
    parser.add_argument("-N", type=int, default=None)
    parser.add_argument("--seq", type=str)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--table", action="store_true")
    args = parser.parse_args()
    if args.variant:
        print("Вариант: s=5, k=3, M=4, L=3, d=3, q=3, eps=1e-4")
        return
    if not args.file or not args.mode:
        print("Ошибочка! укажите параметры --file и --mode (либо флаг --variant)", file=sys.stderr)
        sys.exit(1)
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        validate_config(data)
    except FileNotFoundError:
        print(f"Ошибочка! входной файл не найден: {args.file}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"Ошибочка! некорректный JSON в файле {args.file}: {e}", file=sys.stderr)
        sys.exit(2)
    except ValueError as e:
        print(f"Ошибочка! некорректное описание источника: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Ошибочка! непредвиденный сбой: {e}", file=sys.stderr)
        sys.exit(2)
    rng = random.Random(args.seed)
    try:
        if args.mode == 1:
            if args.N is not None and args.N > 0:
                res = []
                ctx = ""
                for step in range(args.N):
                    dist = get_symbol_dist(data, step, ctx)
                    sym = sample_symbol(dist, rng)
                    res.append(sym)
                    ctx += sym
                print("".join(res))
            else:
                step = 0
                ctx = ""
                try:
                    while True:
                        dist = get_symbol_dist(data, step, ctx)
                        sym = sample_symbol(dist, rng)
                        print(sym, end="", flush=True)
                        ctx += sym
                        step += 1
                except KeyboardInterrupt:
                    sys.exit(0)
        elif args.mode == 2:
            if "context_models" in data or "default_model" in data:
                print("Ошибочка! режим 2 не поддерживает расширенный формат источников с памятью", file=sys.stderr)
                sys.exit(1)

            if not args.seq:
                print("Ошибочка! для режима 2 необходимо передать --seq", file=sys.stderr)
                sys.exit(1)
            seq = args.seq
            r = len(seq)
            L = len(data["source"])
            n_eval = args.N if (args.N is not None and args.N > 0) else 1000

            if n_eval < r:
                print(f"Ошибочка! параметр N ({n_eval}) не может быть меньше длины оцениваемой последовательности ({r})", file=sys.stderr)
                sys.exit(1)
            p_start = prob_of_sequence(data, seq, start_step=0)
            p_avg = sum(prob_of_sequence(data, seq, j) for j in range(L)) / Fraction(L)
            stream = []
            for step in range(n_eval):
                dist = get_symbol_dist(data, step)
                sym = sample_symbol(dist, rng)
                stream.append(sym)
            full_str = "".join(stream)
            denom = n_eval - r + 1
            matches = sum(1 for i in range(denom) if full_str[i:i+r] == seq)
            freq = Fraction(matches, denom)
            print("1. Pr{X1...Xr}:", str(p_start))
            print("2. Среднее по периоду:", str(p_avg))
            print(f"3. Частотная оценка (N={n_eval}):", str(freq))

            if args.table:
                print("\nТаблица сходимости частотной оценки:")
                print("N | Freq | |Freq - P_start| | |Freq - P_avg|")
                for pwr in [2, 3, 4, 5, 6]:
                    cur_n = 10**pwr
                    s = []
                    for step in range(cur_n):
                        dist = get_symbol_dist(data, step)
                        sym = sample_symbol(dist, rng)
                        s.append(sym)
                    s = "".join(s)
                    m = sum(1 for i in range(cur_n - r + 1) if s[i:i+r] == seq)
                    f_val = Fraction(m, cur_n - r + 1)
                    diff_start = abs(f_val - p_start)
                    diff_avg = abs(f_val - p_avg)
                    print(cur_n, "|", float(f_val), "|", float(diff_start), "|", float(diff_avg))

    except Exception as e:
        print(f"Ошибочка! непредвиденный сбой: {e}", file=sys.stderr)
        sys.exit(2)
if __name__ == "__main__":
    main()