# Подключаем pytest для автоматического тестирования.
import pytest

# Импортируем две функции из нашего файла tools.py.
from tools import lookup, calculate


# ===== ТЕСТЫ ДЛЯ LOOKUP =====

# Проверяем, что функция находит население Brightwater за 2025 год.
def test_lookup_population():
    result = lookup("Brightwater", "population_2025")
    assert result["value"] == 44675
    assert result["source"] == "NR-05"


# Проверяем исправление площади Brightwater из документа NR-16.
def test_lookup_correction():
    result = lookup("Brightwater", "area_km2")
    assert result["value"] == 921.4
    assert result["source"] == "NR-16"


# Проверяем, что ошибка в названии района не приводит к сбою программы.
def test_lookup_misspelled_name():
    result = lookup("Ossbrige", "population_2025")
    assert "error" in result


# Проверяем, что похожие районы Ossbridge и Ossford не путаются.
def test_lookup_similar_names():
    first = lookup("Ossbridge", "population_2025")
    second = lookup("Ossford", "population_2025")

    assert "error" not in first
    assert "error" not in second
    assert first["source"] == "NR-01"
    assert second["source"] == "NR-02"


# Проверяем, что архивные данные не используются.
def test_lookup_archived():
    result = lookup("Ossbridge archived 2019", "population_2025")
    assert "error" in result


# Проверяем обработку неизвестного поля.
def test_lookup_unknown_field():
    result = lookup("Brightwater", "unknown_field")
    assert "error" in result


# Проверяем обработку пустого названия района.
def test_lookup_empty_name():
    result = lookup("", "population_2025")
    assert "error" in result


# ===== ТЕСТЫ ДЛЯ CALCULATE =====

# Проверяем обычное умножение из задания преподавателя.
def test_calculate_multiplication():
    result = calculate("48317 * 1.0947")
    assert result["result"] == pytest.approx(52892.6199)


# Проверяем деление для расчёта плотности населения.
def test_calculate_division():
    result = calculate("44675 / 921.4")
    assert result["result"] == pytest.approx(48.48599956587801)


# Проверяем, что деление на ноль возвращает ошибку.
def test_calculate_zero_division():
    result = calculate("10 / 0")
    assert "error" in result


# Проверяем, что опасный Python-код не выполняется.
def test_calculate_dangerous_import():
    result = calculate("__import__('os').system('echo hi')")
    assert "error" in result


# Проверяем запрет доступа к внутренним атрибутам Python.
def test_calculate_class_access():
    result = calculate("(1).__class__")
    assert "error" in result


# Проверяем защиту от очень больших степеней.
def test_calculate_large_power():
    result = calculate("9**9**9")
    assert "error" in result


# Проверяем пустое выражение.
def test_calculate_empty_expression():
    result = calculate("")
    assert "error" in result


# Проверяем обычное сложение и вычитание.
def test_calculate_add_subtract():
    result = calculate("100 + 50 - 20")
    assert result["result"] == 130
