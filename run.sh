#!/usr/bin/env bash
set -e
python3 src/task1.py --variant
python3 src/task1.py --file tests_data/source_s5.json --mode 2 --seq 01 --table -N 100000 --seed 42
python3 src/task2.py --file tests_data/memoryless_s5.json --mode 1
python3 src/task2.py --file tests_data/memoryless_s5.json --mode 2 -R 1.6 --eps 1e-4 -q 3 --nmax 50
python3 src/task3.py --compress tests_data/text_ru.txt -o tests_data/text_ru.txt.zmh
python3 src/task3.py --decompress tests_data/text_ru.txt.zmh -o tests_data/text_ru.txt.out
cmp tests_data/text_ru.txt tests_data/text_ru.txt.out
rm tests_data/text_ru.txt.zmh tests_data/text_ru.txt.out
echo "Все тесты успешно пройдены!"
