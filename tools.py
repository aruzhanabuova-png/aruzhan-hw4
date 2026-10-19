# Подключаем библиотеки для работы с файлами, текстом и вычислениями.
import ast
import json
import math
import operator
import re
from pathlib import Path

# Указываем путь к файлу, в котором находятся 17 документов.
CORPUS = Path(__file__).resolve().parent / "data" / "corpus.jsonl"

# Список полей, которые инструмент lookup может искать.
FIELDS = {
    "population_2025", "population_2020", "area_km2",
    "budget_million_tenge", "water_megalitres",
    "schools", "pupils", "founded", "road_km",
    "tariff_tenge_per_m3"
}

# Единицы измерения для каждого поля.
UNITS = {
    "population_2025": "residents",
    "population_2020": "residents",
    "area_km2": "km2",
    "budget_million_tenge": "million tenge",
    "water_megalitres": "megalitres",
    "schools": "schools",
    "pupils": "pupils",
    "founded": "year",
    "road_km": "km",
    "tariff_tenge_per_m3": "tenge per m3"
}


# Функция ищет число в тексте по заданному шаблону.
# Если число найдено, возвращает его. Иначе возвращает None.
def _number(pattern, text):
    match = re.search(pattern, text, re.I)

    if match:
        return float(match.group(1).replace(",", ""))

    return None


# Функция извлекает данные из текста одного документа.
# Например: население, площадь, бюджет, количество школ.
def _fields(text):
    facts = {}

    # Вспомогательная функция проверяет несколько вариантов записи поля.
    # Найденное значение добавляется в словарь facts.
    def put(field, patterns):
        for pattern in patterns:
            value = _number(pattern, text)

            if value is not None:
                facts[field] = int(value) if value.is_integer() else value
                return

    # Ищем год основания района.
    put("founded", [
        r"\bfounded in (\d{4})"
    ])

    # Ищем площадь района в квадратных километрах.
    put("area_km2", [
        r"\bcovers ([\d,]+(?:\.\d+)?) square kilometres",
        r"\bover ([\d,]+(?:\.\d+)?) square kilometres",
        r"\barea of ([\d,]+(?:\.\d+)?) square kilometres"
    ])

    # Ищем бюджет района за 2025 год.
    put("budget_million_tenge", [
        r"budget for 2025 was set at ([\d,]+(?:\.\d+)?) million",
        r"2025 budget was ([\d,]+(?:\.\d+)?) million",
        r"2025 budget amounted to ([\d,]+(?:\.\d+)?) million"
    ])

    # Ищем объём воды, использованной домохозяйствами.
    put("water_megalitres", [
        r"\bwater use in 2025 came to ([\d,]+(?:\.\d+)?) megalitres",
        r"\bhouseholds used ([\d,]+(?:\.\d+)?) megalitres",
        r"\bhouseholds used ([\d,]+(?:\.\d+)?) cubic metres"
    ])

    # Если вода указана в кубических метрах,
    # переводим её в мегалитры: 1 ML = 1000 м³.
    if "cubic metres of water" in text and "water_megalitres" in facts:
        facts["water_megalitres"] /= 1000

    # Ищем количество школ.
    put("schools", [
        r"\bthere are (\d+) schools",
        r"\bhas (\d+) schools",
        r"\bruns (\d+) schools"
    ])

    # Ищем количество учеников.
    put("pupils", [
        r"\battended by ([\d,]+) pupils",
        r"\benrolled ([\d,]+) pupils",
        r"\bwith ([\d,]+) pupils enrolled"
    ])

    # Ищем население района по переписи 2025 года.
    put("population_2025", [
        r"\b2025 census recorded ([\d,]+) residents",
        r"\b2025 census counted ([\d,]+) residents",
        r"\band ([\d,]+) in 2025"
    ])

    # Ищем население района по переписи 2020 года.
    put("population_2020", [
        r"\b2020 census had recorded ([\d,]+)",
        r"\bup from ([\d,]+) at the 2020 census",
        r"\bpopulation: ([\d,]+) in 2020"
    ])

    # Ищем протяжённость асфальтированных дорог.
    put("road_km", [
        r"\bnetwork is ([\d,]+(?:\.\d+)?) km long",
        r"\bkeeps ([\d,]+(?:\.\d+)?) km of paved road",
        r"\bmaintains ([\d,]+(?:\.\d+)?) km of paved road"
    ])

    # Возвращаем все найденные значения.
    return facts


# Главный инструмент поиска данных.
# district — название района, field — нужное поле.
# Возвращает значение, единицу измерения и ID документа.
def lookup(district, field):

    # Проверяем, что оба аргумента являются непустыми строками.
    if (
        not isinstance(district, str)
        or not isinstance(field, str)
        or not district.strip()
        or not field.strip()
    ):
        return {"error": "Invalid district or field"}

    # Убираем лишние пробелы.
    district = district.strip()
    field = field.strip()

    # Ограничиваем длину входных данных.
    if len(district) > 100 or len(field) > 100:
        return {"error": "Invalid district or field"}

    # Проверяем, существует ли запрошенное поле.
    if field not in FIELDS:
        return {
            "error": "Field not found",
            "allowed_fields": sorted(FIELDS)
        }

    # Читаем документы из corpus.jsonl.
    # Каждая строка файла содержит один JSON-документ.
    try:
        with CORPUS.open(encoding="utf-8") as file:
            docs = [
                json.loads(line)
                for line in file
                if line.strip()
            ]

    # Если файл отсутствует или повреждён, возвращаем ошибку.
    except (OSError, ValueError, KeyError, TypeError):
        return {"error": "Unable to read corpus"}

    # Для тарифа воды используем отдельный документ NR-15.
    if field == "tariff_tenge_per_m3":
        tariff = next(
            (doc for doc in docs if doc.get("id") == "NR-15"),
            None
        )

        if tariff is None:
            return {"error": "Tariff document not found"}

        # Извлекаем стоимость воды за один кубический метр.
        value = _number(
            r"2025 the regional household water tariff is ([\d.]+) tenge",
            tariff["text"]
        )

        if value is None:
            return {"error": "Field not found"}

        return {
            "value": value,
            "unit": UNITS[field],
            "source": "NR-15"
        }

    # Выбираем только актуальные профили районов NR-01 ... NR-12.
    # Архивные документы NR-13 и NR-14 сюда не попадают.
    current = [
        doc for doc in docs
        if re.fullmatch(
            r"NR-(?:0[1-9]|1[0-2])",
            doc.get("id", "")
        )
    ]

    # Создаём словарь: название района -> его документ.
    names = {
        doc["title"].split(" district profile")[0].casefold(): doc
        for doc in current
    }

    # Игнорируем регистр букв при поиске названия.
    name = district.casefold()

    # Запрещаем использование архивных данных.
    if "archived" in name or "2019" in name:
        return {"error": "Archived data cannot be used"}

    # Если район не найден, возвращаем ошибку и список районов.
    if name not in names:
        return {
            "error": "District not found",
            "available_districts": sorted(
                doc["title"].split(" district profile")[0]
                for doc in current
            )
        }

    # Получаем документ выбранного района.
    doc = names[name]

    # Извлекаем все доступные числовые данные.
    facts = _fields(doc["text"])

    # Проверяем, удалось ли найти нужное поле.
    if field not in facts:
        return {"error": "Field not found"}

    value = facts[field]
    source = doc["id"]

    # Для Brightwater используем исправленную площадь из NR-16.
    if name == "brightwater" and field == "area_km2":
        correction = next(
            (doc for doc in docs if doc.get("id") == "NR-16"),
            None
        )

        if correction is None:
            return {"error": "Correction document not found"}

        # Находим исправленное значение площади.
        corrected = _number(
            r"correct area is ([\d.]+) square kilometres",
            correction["text"]
        )

        if corrected is None:
            return {"error": "Correction cannot be read"}

        # Заменяем старое значение новым.
        value = corrected
        source = "NR-16"

    # Возвращаем найденное значение вместе с единицей и источником.
    return {
        "value": value,
        "unit": UNITS[field],
        "source": source
    }


# Разрешённые арифметические операции для калькулятора.
# Сложение, вычитание, умножение и деление.
OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv
}

# Максимальное допустимое абсолютное значение числа.
MAX_NUMBER = 1e15


# Инструмент для безопасных математических вычислений.
# Принимает выражение строкой, например "44675 / 921.4".
def calculate(expression):

    # Проверяем тип входных данных.
    if not isinstance(expression, str):
        return {"error": "Invalid arithmetic expression"}

    # Проверяем, что выражение не пустое.
    if not expression.strip():
        return {"error": "Empty expression"}

    # Не разрешаем слишком длинные выражения.
    if len(expression) > 200:
        return {"error": "Number exceeds the allowed limit"}

    # Преобразуем выражение в дерево AST.
    # AST позволяет анализировать выражение без запуска Python-кода.
    try:
        tree = ast.parse(expression, mode="eval")

    except (SyntaxError, ValueError, RecursionError):
        return {"error": "Invalid arithmetic expression"}

    # Рекурсивно вычисляем только разрешённые элементы AST.
    def walk(node, depth=0):

        # Ограничиваем глубину вложенных выражений.
        if depth > 25:
            raise OverflowError

        # Начинаем вычисление с основного выражения.
        if isinstance(node, ast.Expression):
            return walk(node.body, depth + 1)

        # Разрешаем только обычные числа.
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value

        # Обрабатываем положительные и отрицательные числа.
        elif isinstance(node, ast.UnaryOp) and isinstance(
            node.op, (ast.UAdd, ast.USub)
        ):
            value = walk(node.operand, depth + 1)

            if isinstance(node.op, ast.USub):
                value = -value

        # Выполняем только операции из словаря OPS.
        elif isinstance(node, ast.BinOp) and type(node.op) in OPS:
            left = walk(node.left, depth + 1)
            right = walk(node.right, depth + 1)

            value = OPS[type(node.op)](left, right)

        # Запрещаем вызовы функций, доступ к атрибутам и другие операции.
        else:
            raise ValueError("Unsupported operation")

        # Проверяем, что результат конечный и не слишком большой.
        if not math.isfinite(value) or abs(value) > MAX_NUMBER:
            raise OverflowError

        return value

    try:
        # Возвращаем результат успешного вычисления.
        return {"result": walk(tree)}

    # Обрабатываем деление на ноль.
    except ZeroDivisionError:
        return {"error": "Division by zero"}

    # Обрабатываем слишком большие числа и выражения.
    except OverflowError:
        return {"error": "Number exceeds the allowed limit"}

    # Обрабатываем запрещённые операции и некорректные выражения.
    except (ValueError, TypeError, ArithmeticError):
        return {"error": "Unsupported operation"}
