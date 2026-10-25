	import sys
	import json
	import argparse
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
			raise ValueError(f"распределение в {place_name} не нормировано: сумма = {total}")

	def main():
		parser = argparse.ArgumentParser()
		parser.add_argument("--variant", action="store_true")
		parser.add_argument("--file", type=str)
		parser.add_argument("--mode", type=int, choices=[1, 2])
		parser.add_argument("-R", type=float, default=1.6)
		parser.add_argument("--eps", type=float, default=1e-4)
		parser.add_argument("-q", type=int, default=3)
		parser.add_argument("--nmax", type=int, default=50)
		parser.add_argument("--code-out", type=str, default="codebook.txt")
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
		except FileNotFoundError:
			print(f"Ошибочка! входной файл не найден: {args.file}", file=sys.stderr)
			sys.exit(2)
		except json.JSONDecodeError as e:
			print(f"Ошибочка! некорректный JSON в файле {args.file}: {e}", file=sys.stderr)
			sys.exit(2)
		except Exception as e:
			print(f"Ошибочка! непредвиденный сбой: {e}", file=sys.stderr)
			sys.exit(2)
		try:
			if not isinstance(data, dict):
				raise ValueError("корневая структура JSON должна быть объектом")
			if "context_models" in data or "memory_depth" in data:
				print("Ошибочка! источник обладает памятью (обнаружен блок context_models/memory_depth)", file=sys.stderr)
				sys.exit(1)
			if "source" not in data or not isinstance(data["source"], list) or len(data["source"]) == 0:
				print("Ошибочка! список 'source' пуст либо отсутствует", file=sys.stderr)
				sys.exit(1)
			if "models" not in data or "switches" not in data:
				print("Ошибочка! отсутствуют обязательные блоки 'models' или 'switches'", file=sys.stderr)
				sys.exit(1)
			for m_name, dist in data["models"].items():
				check_dist(dist, f"модели '{m_name}'")
			for sw_name, dist in data["switches"].items():
				check_dist(dist, f"переключателе '{sw_name}'")
				for m_name in dist.keys():
					if m_name not in data["models"]:
						raise ValueError(f"в переключателе '{sw_name}' ссылка на неизвестную модель '{m_name}'")
			for sw_name in data["source"]:
				if sw_name not in data["switches"]:
					raise ValueError(f"в списке 'source' указан неизвестный переключатель '{sw_name}'")
			L = len(data["source"])
			distributions = []
			all_symbols = set()
			for step in range(L):
				sw_name = data["source"][step]
				sw_dist = data["switches"][sw_name]
				cur_dist = {}
				for m_name, m_prob in sw_dist.items():
					pm = to_frac(m_prob)
					for sym, s_prob in data["models"][m_name].items():
						ps = to_frac(s_prob)
						cur_dist[sym] = cur_dist.get(sym, Fraction(0)) + pm * ps
				distributions.append(cur_dist)
				all_symbols.update(cur_dist.keys())
			base_dist = distributions[0]
			for step_idx, dist in enumerate(distributions[1:], 1):
				for s in all_symbols:
					if dist.get(s, Fraction(0)) != base_dist.get(s, Fraction(0)):
						print(f"Ошибочка! нарушено условие стационарности: на такте {step_idx} распределение отличается от такта 0", file=sys.stderr)
						sys.exit(1)
			alphabet = sorted(list(all_symbols))
			if len(alphabet) != 3:
				print(f"Ошибочка! мощность алфавита источника равна {len(alphabet)}, алгоритм оптимизирован для k=3 по варианту", file=sys.stderr)
				sys.exit(1)
			probs = [base_dist.get(s, Fraction(0)) for s in alphabet]
			H = 0.0
			for p in probs:
				if p > 0:
					pf = float(p)
					H -= pf * math.log2(pf)
			if args.mode == 1:
				print("Источник стационарный и не имеет памяти.")
				print("Алфавит:", alphabet)
				print("Вероятности символов:", [str(p) for p in probs])
				print("Собственная энтропия H(X):", H)
				return
			if args.mode == 2:
				if args.q <= 1:
					print("Ошибочка! мощность алфавита кодера q должна быть строго больше 1", file=sys.stderr)
					sys.exit(1)
				if args.R <= 0:
					print("Ошибочка! скорость кода R должна быть строго положительной", file=sys.stderr)
					sys.exit(1)
				if args.eps <= 0 or args.eps >= 1:
					print("Ошибочка! допустимая вероятность ошибки eps должна лежать в (0, 1)", file=sys.stderr)
					sys.exit(1)
				if args.nmax < 1:
					print("Ошибочка! параметр nmax должен быть не меньше 1", file=sys.stderr)
					sys.exit(1)
				eps_frac = Fraction(str(args.eps))
				log2_q = math.log2(args.q)
				min_n = None
				best_types_info = None
				print("n | l(n) | q^l | Pe(n)")
				for n in range(1, args.nmax + 1):
					l_n = math.floor(n * args.R / log2_q)
					capacity = args.q ** l_n
					types = []
					for c1 in range(n + 1):
						for c2 in range(n - c1 + 1):
							c3 = n - c1 - c2
							count = math.comb(n, c1) * math.comb(n - c1, c2)
							block_p = (probs[0] ** c1) * (probs[1] ** c2) * (probs[2] ** c3)
							types.append((block_p, count, (c1, c2, c3)))
					types.sort(key=lambda item: item[0], reverse=True)
					coded_prob = Fraction(0)
					accumulated_count = 0
					chosen_types = []
					for block_p, count, counts_tuple in types:
						if accumulated_count + count <= capacity:
							coded_prob += block_p * count
							accumulated_count += count
							chosen_types.append((counts_tuple, count, block_p))
						else:
							needed = capacity - accumulated_count
							coded_prob += block_p * needed
							accumulated_count += needed
							if needed > 0:
								chosen_types.append((counts_tuple, needed, block_p))
							break
					pe = Fraction(1) - coded_prob
					pe_float = float(pe)

					print(n, "|", l_n, "|", capacity, "|", pe_float)

					if min_n is None and pe <= eps_frac:
						min_n = n
						best_types_info = (n, l_n, capacity, pe_float, chosen_types)

				if min_n is None and best_types_info is None:
					best_types_info = (args.nmax, l_n, capacity, pe_float, chosen_types)

				if min_n is not None:
					print("Минимальное n, при котором Pe(n) <= eps:", min_n)
				else:
					print("На отрезке [1,", args.nmax, "] значение Pe(n) <= eps не достигнуто.")

				if args.R > H:
					print("Существует n0 такое, что Pe(n) <= eps для всех n >= n0, так как R =", args.R, "> H(X) =", H)
				else:
					print("Такого n0 для всех n >= n0 не существует, так как R =", args.R, "<= H(X) =", H)
				target_n, target_l, target_cap, target_pe, target_types = best_types_info
				with open(args.code_out, "w", encoding="utf-8") as f_out:
					f_out.write(f"Параметры кода: n={target_n}, l={target_l}, q={args.q}, R={args.R}\n")
					f_out.write(f"Число кодовых слов: {target_cap}, Pe={target_pe}\n")
					f_out.write("Вектора кратностей (c0, c1, c2) кодируемых типов, число блоков и вероятность блока:\n")
					for counts_tuple, cnt, bp in target_types:
						f_out.write(f"{counts_tuple}: взято {cnt} блоков, P_block={bp}\n")
				print("Описание кода сохранено в файл:", args.code_out)

		except ValueError as e:
			print(f"Ошибочка! в описании источника: {e}", file=sys.stderr)
			sys.exit(2)
		except Exception as e:
			print(f"Ошибочка! непредвиденный сбой: {e}", file=sys.stderr)
			sys.exit(2)
	if __name__ == "__main__":
		main()