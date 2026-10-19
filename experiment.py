
import json
import re
import statistics
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# Пути к вопросам, документам и папке с результатами
QUESTIONS_FILE = Path("data/questions.json")
CORPUS_FILE = Path("data/corpus.jsonl")
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# Настройки подключения к API
load_dotenv()
client = OpenAI()
MODEL = "gpt-5.6-luna"


# Загружаем вопросы из JSON-файла
def load_questions():
    with QUESTIONS_FILE.open("r", encoding="utf-8") as file:
        questions = json.load(file)

    if not isinstance(questions, list):
        raise ValueError("Файл вопросов должен содержать список.")

    return questions


# Загружаем документы: один JSON-объект на каждой строке
def load_corpus():
    documents = []

    with CORPUS_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                documents.append(json.loads(line))

    return documents


# Объединяем документы в контекст для модели
def prepare_context(documents):
    parts = []

    for document in documents:
        parts.append(
            f"Document ID: {document['id']}\n"
            f"Title: {document['title']}\n"
            f"Text: {document['text']}"
        )

    return "\n\n".join(parts)


# S1: один прямой запрос модели без инструментов
def run_s1(question, context, decimals=1):
    system_prompt = f"""
You answer questions about the fictional Nine Rivers Region.

Use only the supplied documents.

Rules:
1. Identify the exact districts, year, fields, and units requested.
2. Use current profiles, ignore archived profiles, and apply later corrections.
3. Calculate each requested value separately before comparing them.
4. For population density, divide population by area in square kilometres.
5. Convert units to exactly those requested in the question.
6. Budgets are recorded in million tenge. If the question asks for
   thousand tenge per pupil, multiply million tenge per pupil by 1000.
7. Keep full precision during intermediate calculations.
8. Round the final answer to {decimals} decimal place(s).
9. Do not guess or invent facts.
10. Check the final district name and numerical value against the question.

Return exactly one line:
ANSWER: <name or yes/no> | <number>

Put only the number after the vertical bar.
Do not include units, explanations, or Markdown.
If the question cannot be answered from the documents, return:
ANSWER: unanswered | unknown
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": (
                f"DOCUMENTS:\n{context}\n\n"
                f"QUESTION:\n{question}"
            )
        }
    ]

    # Измеряем время выполнения запроса
    start = time.perf_counter()

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        reasoning_effort="medium"
    )

    duration = time.perf_counter() - start
    usage = response.usage

    # Возвращаем ответ, токены и время выполнения
    return {
        "answer": response.choices[0].message.content or "",
        "input_tokens": usage.prompt_tokens if usage else None,
        "output_tokens": usage.completion_tokens if usage else None,
        "duration_seconds": round(duration, 3)
    }


# Формируем путь к сохранённому результату
def result_path(strategy, run_number, question_id):
    return OUTPUT_DIR / (
        f"{strategy}_run{run_number}_{question_id}.json"
    )


# Сохраняем результат, не перезаписывая существующий файл
def save_result(strategy, run_number, question_id, result):
    filename = result_path(strategy, run_number, question_id)

    if filename.exists():
        raise FileExistsError(
            f"Результат уже существует: {filename}"
        )

    with filename.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    return str(filename)


# Загружаем ранее сохранённый результат
def load_saved_result(strategy, run_number, question_id):
    filename = result_path(strategy, run_number, question_id)

    if not filename.exists():
        return None

    with filename.open("r", encoding="utf-8") as file:
        return json.load(file)


# Проверяем формат ответа и извлекаем название и число
def parse_answer(model_answer):
    if not isinstance(model_answer, str):
        return None

    match = re.fullmatch(
        r"\s*ANSWER:\s*([^|\n]+?)\s*\|\s*"
        r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*",
        model_answer,
        re.IGNORECASE
    )

    if not match:
        return None

    return match.group(1).strip(), float(match.group(2))


# Сравниваем ответ модели с эталоном из questions.json
def check_answer(model_answer, question):
    parsed = parse_answer(model_answer)

    if parsed is None:
        return False

    predicted_name, predicted_value = parsed
    correct_name = str(question["answer"]).strip()

    # Проверяем название района или ответ yes/no
    if predicted_name.casefold() != correct_name.casefold():
        return False

    # Сравниваем числовые ответы с заданной точностью
    decimals = int(question["decimals"])
    correct_value = float(question["value"])

    return (
        round(predicted_value, decimals)
        == round(correct_value, decimals)
    )


# Определяем, отсутствует ли корректно оформленный ответ
def is_unanswered(answer):
    if not isinstance(answer, str) or not answer.strip():
        return True

    return (
        "ANSWER: unanswered" in answer.casefold()
        or parse_answer(answer) is None
    )


# Запускаем S1 на всех выбранных вопросах
def run_s1_experiment(questions, context, run_number):
    rows = []

    for question in questions:
        question_id = question["id"]

        print(
            f"S1 Run {run_number}: {question_id} ...",
            flush=True
        )

        # Повторно используем ответ, если он уже сохранён
        result = load_saved_result(
            "S1", run_number, question_id
        )

        if result is None:
            try:
                result = run_s1(
                    question["question"],
                    context,
                    decimals=int(question["decimals"])
                )

                # Сохраняем результат сразу после получения
                save_result(
                    "S1", run_number, question_id, result
                )

            except Exception as error:
                print(
                    f"Ошибка для {question_id}: {error}",
                    flush=True
                )

                result = {
                    "answer": "",
                    "input_tokens": None,
                    "output_tokens": None,
                    "duration_seconds": 0,
                    "error": str(error)
                }

        answer = result.get("answer", "")
        correct = check_answer(answer, question)

        row = {
            "question_id": question_id,
            "answer": answer,
            "correct": correct,
            "unanswered": is_unanswered(answer),
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
            "duration_seconds": result.get("duration_seconds", 0),
            "error": result.get("error")
        }

        rows.append(row)

        print(
            f"  {answer or 'No answer'} | correct: {correct}",
            flush=True
        )

    # Считаем токены только для ответов с измеренными значениями
    valid_rows = [
        row for row in rows
        if row["input_tokens"] is not None
        and row["output_tokens"] is not None
    ]

    durations = [
        row["duration_seconds"] for row in rows
    ]

    # Вычисляем медианное время ответа
    median_seconds = (
        statistics.median(durations) if durations else 0
    )

    summary = {
        "strategy": "S1",
        "run": run_number,
        "questions": len(rows),
        "correct": sum(row["correct"] for row in rows),
        "unanswered": sum(row["unanswered"] for row in rows),
        "input_tokens": sum(
            row["input_tokens"] for row in valid_rows
        ),
        "output_tokens": sum(
            row["output_tokens"] for row in valid_rows
        ),
        "token_split_complete": len(valid_rows) == len(rows),
        "total_seconds": round(sum(durations), 3),
        "median_seconds": round(median_seconds, 3),
        "cost_usd": None
    }

    # Сохраняем сводку для отчёта
    summary_path = OUTPUT_DIR / (
        f"run{run_number}_S1_summary.json"
    )

    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    print("\nSUMMARY:", summary, flush=True)
    print("Сводка сохранена:", summary_path)

    return summary

# S2: выбираем ответ большинством голосов
def majority_vote(answers, decimals):
    votes = {}

    # Приводим ответы к единому формату
    for answer in answers:
        parsed = parse_answer(answer)

        if parsed is None:
            continue

        name, value = parsed
        key = (name.casefold(), round(value, decimals))

        votes[key] = votes.get(key, 0) + 1

    # Если корректных ответов нет, возвращаем отсутствие ответа
    if not votes:
        return "ANSWER: unanswered | unknown"

    # Находим максимальное количество голосов
    maximum = max(votes.values())

    winners = [
        key for key, count in votes.items()
        if count == maximum
    ]

    # При равенстве голосов не выбираем ответ случайно
    if len(winners) != 1:
        return "ANSWER: unanswered | unknown"

    name, value = winners[0]
    return f"ANSWER: {name} | {value:.{decimals}f}"

# S2: пять независимых ответов на один вопрос
def run_s2(question, context, decimals=1):
    client = OpenAI()
    results = []

    # Один и тот же вопрос задаём модели пять раз
    for i in range(5):
        start = time.perf_counter()

        response = client.responses.create(
            model="gpt-5.6-luna",
            reasoning={"effort": "medium"},
            instructions=(
                "You are a careful data analyst. "
                "Use only the provided documents. "
                "Think through the calculations carefully. "
                "Check units, comparisons, and rounding. "
                f"Round the final number to {decimals} decimal places. "
                "Give the final answer in this exact format: "
                "ANSWER: <district or yes/no> | <number>"
            ),
            input=f"{context}\n\nQUESTION:\n{question}"
        )

        elapsed = time.perf_counter() - start

        results.append({
            "vote": i + 1,
            "answer": response.output_text.strip(),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "seconds": elapsed
        })

    # Собираем ответы пяти запусков
    answers = [r["answer"] for r in results]

    # Выбираем ответ большинством голосов
    final_answer = majority_vote(answers, decimals)

    return {
        "answer": final_answer,
        "votes": results,
        "input_tokens": sum(r["input_tokens"] for r in results),
        "output_tokens": sum(r["output_tokens"] for r in results),
        "duration_seconds": sum(r["seconds"] for r in results)
    }

# Сохраняем результаты S2 для каждого вопроса
def save_s2_result(question_id, run_number, result):
    path = Path("outputs") / f"S2_run{run_number}_{question_id}.json"

    # Не перезаписываем существующий результат
    if path.exists():
        raise FileExistsError(f"Файл уже существует: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    print("Сохранено:", path)

# Полный эксперимент S2 на 20 вопросах
def run_s2_experiment(questions, context, run_number):
    results = []

    for q in questions:
        question_id = q["id"]
        decimals = int(q["decimals"])

        print(f"S2 Run {run_number}: {question_id} ...", flush=True)

        # Проверяем, есть ли уже сохранённый результат
        path = Path("outputs") / f"S2_run{run_number}_{question_id}.json"

        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                result = json.load(file)
            print("  Загружен сохранённый результат")
        else:
            # Получаем пять ответов и итог голосования
            result = run_s2(q["question"], context, decimals=decimals)
            result["question_id"] = question_id
            result["strategy"] = "S2"
            result["run"] = run_number
            result["correct"] = check_answer(result["answer"], q)

            save_s2_result(question_id, run_number, result)

        results.append(result)

        print(
            "  ANSWER:", result["answer"],
            "| correct:", result["correct"],
            flush=True
        )

    # Рассчитываем общую статистику
    summary = {
        "strategy": "S2",
        "run": run_number,
        "questions": len(results),
        "correct": sum(r["correct"] for r in results),
        "unanswered": sum(is_unanswered(r["answer"]) for r in results),
        "input_tokens": sum(r["input_tokens"] for r in results),
        "output_tokens": sum(r["output_tokens"] for r in results),
        "total_seconds": round(
            sum(r["duration_seconds"] for r in results), 3
        ),
        "median_seconds": round(
            statistics.median(r["duration_seconds"] for r in results), 3
        ),
        "cost_usd": None
    }

    # Сохраняем сводку
    summary_path = Path("outputs") / f"run{run_number}_S2_summary.json"

    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    print("\nSUMMARY:", summary)
    print("Сводка сохранена:", summary_path)

# Проверяем ответ агента, включая ответ полным предложением
def check_s3_answer(answer, question):
    # Сначала проверяем стандартный формат
    if check_answer(answer, question):
        return True

    # Если агент ответил предложением, извлекаем название и число
    import re

    expected_name = str(question["answer"]).casefold()
    text = answer.casefold()

    if expected_name not in text:
        return False

    # Находим числа, включая числа с запятыми
    numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", text)

    expected_value = float(question["value"])
    decimals = int(question["decimals"])

    for number in numbers:
        value = float(number.replace(",", ""))

        if round(value, decimals) == round(expected_value, decimals):
            return True

    return False

# Полный эксперимент S3 с агентом
def run_s3_experiment(questions, run_number):
    from agent import run_agent

    results = []

    for q in questions:
        question_id = q["id"]
        path = Path("outputs") / f"S3_run{run_number}_{question_id}.json"

        print(f"S3 Run {run_number}: {question_id} ...", flush=True)

        # Не повторяем уже выполненные вопросы
        if path.exists():
            with path.open("r", encoding="utf-8") as file:
                result = json.load(file)
            print("  Загружен сохранённый результат")
        else:
            start = time.perf_counter()

            # Запускаем агента без передачи документов и правильных ответов
            history = run_agent(
                q["question"],
                question_id=f"S3_run{run_number}_{question_id}"
            )

            elapsed = time.perf_counter() - start

            result = {
                "strategy": "S3",
                "run": run_number,
                "question_id": question_id,
                "answer": history.get("answer") or "",
                "status": history.get("status"),
                "correct": check_s3_answer(
                    history.get("answer") or "", q
                ),
                "input_tokens": history.get("input_tokens", 0),
                "output_tokens": history.get("output_tokens", 0),
                "duration_seconds": elapsed,
                "api_calls": len(history.get("calls", [])),
                "tool_calls": len(history.get("tool_calls", [])),
                "agent_log": history.get("log_file")
            }

            path.parent.mkdir(parents=True, exist_ok=True)

            with path.open("w", encoding="utf-8") as file:
                json.dump(result, file, ensure_ascii=False, indent=2)

        results.append(result)

        print(
            "  ANSWER:", result["answer"],
            "| correct:", result["correct"],
            flush=True
        )

    # Считаем итоговые показатели
    summary = {
        "strategy": "S3",
        "run": run_number,
        "questions": len(results),
        "correct": sum(r["correct"] for r in results),
        "unanswered": sum(
            r["status"] != "answered" or not r["answer"]
            for r in results
        ),
        "input_tokens": sum(r["input_tokens"] for r in results),
        "output_tokens": sum(r["output_tokens"] for r in results),
        "total_seconds": round(
            sum(r["duration_seconds"] for r in results), 3
        ),
        "median_seconds": round(
            statistics.median(r["duration_seconds"] for r in results), 3
        ),
        "api_calls": sum(r["api_calls"] for r in results),
        "tool_calls": sum(r["tool_calls"] for r in results),
        "cost_usd": None
    }

    summary_path = Path("outputs") / f"run{run_number}_S3_summary.json"

    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    print("\nSUMMARY:", summary)
    print("Сводка сохранена:", summary_path)

# Основная точка запуска программы
if __name__ == "__main__":
    questions = load_questions()
    documents = load_corpus()
    context = prepare_context(documents)

    print("Количество вопросов:", len(questions))
    print("Количество документов:", len(documents))
    print("Длина текста документов:", len(context))

    # Запуск 3 сохраняет результаты отдельно от запусков 1 и 2
    run_s1_experiment(
        questions,
        context,
        run_number=3
    )
