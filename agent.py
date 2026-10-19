import json
import time
import copy
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from tools import lookup, calculate


# Загружаем API-ключ из файла .env
load_dotenv()

# Создаём клиент OpenAI
client = OpenAI()

# Модель и максимальное количество раундов
MODEL = "gpt-5.6-luna"
MAX_ROUNDS = 6

# Папка для результатов
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


# Описание инструментов для модели
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": "Find a factual value for a district in the local corpus.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string"},
                    "field": {
                        "type": "string",
                        "enum": [
                            "population_2025",
                            "population_2020",
                            "area_km2",
                            "budget_million_tenge",
                            "water_megalitres",
                            "schools",
                            "pupils",
                            "founded",
                            "road_km",
                            "tariff_tenge_per_m3"
                        ]
                    }
                },
                "required": ["district", "field"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Safely calculate an arithmetic expression.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                },
                "required": ["expression"],
                "additionalProperties": False
            }
        }
    }
]


# Проверяем аргументы и выполняем инструмент
def execute_tool(name, arguments):
    if not isinstance(arguments, dict):
        return {"error": "Arguments must be a JSON object"}

    if name == "lookup":
        if set(arguments) != {"district", "field"}:
            return {"error": "Invalid lookup arguments"}

        if not all(isinstance(arguments[key], str) for key in arguments):
            return {"error": "Arguments must be strings"}

        return lookup(arguments["district"], arguments["field"])

    if name == "calculate":
        if set(arguments) != {"expression"}:
            return {"error": "Invalid calculate arguments"}

        if not isinstance(arguments["expression"], str):
            return {"error": "Expression must be a string"}

        return calculate(arguments["expression"])

    return {"error": "Unknown tool"}


# Сохраняем историю работы агента в JSON
def save_log(question_id, history):
    filename = (
        OUTPUT_DIR
        / f"agent_{question_id}_{datetime.now():%Y%m%d_%H%M%S_%f}.json"
    )

    with filename.open("w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)

    return str(filename)


# Основной цикл агента
# vague=False — обычное описание
# vague=True — расплывчатое описание для Part C
def run_agent(question, question_id="test", vague=False):

    # Создаём копию схем, чтобы не изменять оригинал
    schemas = copy.deepcopy(TOOL_SCHEMAS)

    if vague:
        schemas[0]["function"]["description"] = "Get information."

    messages = [
        {
            "role": "system",
            "content": (
                "Answer questions using the available tools. "
                "Use lookup for district facts and calculate for arithmetic. "
                "Do not invent missing facts. "
                "Give a concise final answer in the format ANSWER: ..."
            )
        },
        {"role": "user", "content": question}
    ]

    history = {
        "question_id": question_id,
        "question": question,
        "model": MODEL,
        "max_rounds": MAX_ROUNDS,
        "description_type": "vague" if vague else "original",
        "calls": [],
        "tool_calls": [],
        "answer": None,
        "status": "unanswered",
        "input_tokens": 0,
        "output_tokens": 0
    }

    # Один раунд — один запрос к модели
    for round_number in range(1, MAX_ROUNDS + 1):
        start = time.perf_counter()

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=schemas,
                tool_choice="auto",
                reasoning_effort="none"
            )
        except Exception as error:
            history["status"] = "api_error"
            history["error"] = str(error)
            break

        duration = time.perf_counter() - start

        # Подсчитываем токены
        if response.usage:
            history["input_tokens"] += response.usage.prompt_tokens
            history["output_tokens"] += response.usage.completion_tokens

        message = response.choices[0].message

        history["calls"].append({
            "round": round_number,
            "duration_seconds": duration,
            "input_tokens": (
                response.usage.prompt_tokens if response.usage else None
            ),
            "output_tokens": (
                response.usage.completion_tokens if response.usage else None
            ),
            "content": message.content,
            "tool_calls": [
                call.model_dump(mode="json")
                for call in (message.tool_calls or [])
            ]
        })

        # Добавляем сообщение модели в историю диалога
        messages.append(message.model_dump(exclude_none=True))

        # Если вызовов инструментов нет, сохраняем ответ
        if not message.tool_calls:
            if message.content:
                history["answer"] = message.content
                history["status"] = "answered"
            break

        # Выполняем вызовы инструментов
        for call in message.tool_calls:
            tool_start = time.perf_counter()

            try:
                arguments = json.loads(call.function.arguments)
            except (json.JSONDecodeError, TypeError):
                result = {"error": "Invalid JSON arguments"}
            else:
                try:
                    result = execute_tool(call.function.name, arguments)
                except Exception as error:
                    result = {
                        "error": (
                            f"Tool execution failed: {type(error).__name__}"
                        )
                    }

            tool_duration = time.perf_counter() - tool_start

            history["tool_calls"].append({
                "round": round_number,
                "tool_call_id": call.id,
                "name": call.function.name,
                "arguments": call.function.arguments,
                "result": result,
                "duration_seconds": tool_duration
            })

            # Возвращаем результат инструмента модели
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False)
            })

    # Сохраняем результат запуска
    history["log_file"] = save_log(question_id, history)

    return history
