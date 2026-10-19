# HW4 — submission

**AI assistance:** I used ChatGPT to understand the assignment, plan the solution, review tool specifications and get guidance on Python implementation and testing.

---

## Part A — Plan on paper (Easy)

> Commit this whole part before any `.py` file exists.

### A1 — The steps

| # | Step | What goes in (types) | What comes out (types) | When it goes wrong | Tool, loop, or model? |
|---|---|---|---|---|---|
| 1 | Understand the question | Question (`str`) | District names (`list[str]`), required metrics (`list[str]`), year (`int`) | If the question is unclear, report an error | Model |
| 2 | Find information | District name (`str`), field (`str`) | Value (`float` or `str`), unit (`str`), source ID (`str`) | Return an error if the district or field is missing or ambiguous | lookup tool |
| 3 | Validate data | Retrieved records (`dict`) | Correct values and units (`dict`) | Reject archived records, use corrections, report invalid units | lookup tool |
| 4 | Prepare calculation | Valid values (`dict`) | Arithmetic expression (`str`) | Report missing or invalid values | Model |
| 5 | Calculate result | Arithmetic expression (`str`) | Result (`float`) | Reject unsafe expressions, division by zero and very large numbers | calculate tool |
| 6 | Compare results | Calculated values (`float`) | Selected district (`str`), difference (`float`) | Report an error if comparison is impossible | Model |
| 7 | Return final answer | District (`str`), difference (`float`), decimals (`int`) | Formatted answer (`str`) | Return unanswered if required information is missing | Model |

**How the steps connect:**
Question → Understand question → Lookup information → Validate data → Prepare calculation → Calculate → Compare results → Final answer.
The model identifies the required information. The lookup tool retrieves facts from the documents. The calculate tool performs arithmetic. Finally, the model compares the results and produces the answer.


**What I am assuming:**
- I use 2025 census data for population questions.
- For school questions, I use the 2025/26 academic year.
- Archived documents NR-13 and NR-14 are not used as current data.
- Corrections in NR-16 take priority over incorrect original values.
- District names must match the correct records, especially Ossbridge and Ossford.
- Different measurement units must be converted before calculations.
- Intermediate calculations use full precision.
- Rounding is applied only to the final answer.
- If a tool returns an error, the model should correct its request or report that the question cannot be answered.


### A2 — The two tools

#### `lookup`

```json
{
  "type": "function",
  "function": {
    "name": "lookup",
    "description": "Find district facts from current documents, apply corrections, and return values with source IDs.",
    "parameters": {
      "type": "object",
      "properties": {
        "district": {
          "type": "string",
          "description": "Exact district name"
        },
        "field": {
          "type": "string",
          "description": "Required data field"
        }
      },
      "required": ["district", "field"],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| Success | `{"value": 1000, "unit": "residents", "source": "NR-05"}` |
| District not found | `{"error": "District not found"}` |
| Field not found | `{"error": "Field not found"}` |
| Archived document | `{"error": "Archived data cannot be used"}` |
| Corrected value | The corrected value and its source document ID |
| Invalid input | `{"error": "Invalid district or field"}` |


**Worst thing it could do with strange or dangerous input:**
The lookup tool could return incorrect information if it uses archived records or ignores corrections. It could also return the wrong district if names are similar. To prevent this, the tool will validate inputs, reject archived records, apply corrections, and return source document IDs.

#### `calculate`

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Safely calculate arithmetic expressions for differences, percentages, ratios, and population density.",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "Arithmetic expression using numbers, parentheses, +, -, *, and /."
        }
      },
      "required": ["expression"],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| Success | `{"result": 48.5}` |
| Division by zero | `{"error": "Division by zero"}` |
| Invalid expression | `{"error": "Invalid arithmetic expression"}` |
| Dangerous code | `{"error": "Unsupported operation"}` |
| Very large numbers | `{"error": "Number exceeds the allowed limit"}` |
| Empty expression | `{"error": "Empty expression"}` |

**Worst thing it could do with strange or dangerous input:**
A dangerous expression could execute malicious Python code or use too many system resources. To prevent this, the calculate tool will use the ast module instead of eval or exec. It will allow only basic arithmetic operations and limit expression length, complexity, and number size.

### A3 — Q-09 by hand

```json
[
  {
    "role": "user",
    "content": "Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_01",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\":\"Brightwater\",\"field\":\"population_2025\"}"
        }
      },
      {
        "id": "call_02",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\":\"Brightwater\",\"field\":\"area_km2\"}"
        }
      },
      {
        "id": "call_03",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\":\"Millbrook\",\"field\":\"population_2025\"}"
        }
      },
      {
        "id": "call_04",
        "type": "function",
        "function": {
          "name": "lookup",
          "arguments": "{\"district\":\"Millbrook\",\"field\":\"area_km2\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_01",
    "name": "lookup",
    "content": "{\"value\":44675,\"unit\":\"residents\",\"source\":\"NR-05\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_02",
    "name": "lookup",
    "content": "{\"value\":921.4,\"unit\":\"km2\",\"source\":\"NR-16\",\"note\":\"Corrected value replaces NR-05 area\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_03",
    "name": "lookup",
    "content": "{\"value\":37203,\"unit\":\"residents\",\"source\":\"NR-11\"}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_04",
    "name": "lookup",
    "content": "{\"value\":758.6,\"unit\":\"km2\",\"source\":\"NR-11\"}"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_05",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\":\"44675 / 921.4\"}"
        }
      },
      {
        "id": "call_06",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\":\"37203 / 758.6\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_05",
    "name": "calculate",
    "content": "{\"result\":48.48599956587801}"
  },
  {
    "role": "tool",
    "tool_call_id": "call_06",
    "name": "calculate",
    "content": "{\"result\":49.041655681518584}"
  },
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_07",
        "type": "function",
        "function": {
          "name": "calculate",
          "arguments": "{\"expression\":\"49.041655681518584 - 48.48599956587801\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_07",
    "name": "calculate",
    "content": "{\"result\":0.5556561156405735}"
  },
  {
    "role": "assistant",
    "content": "ANSWER: Millbrook | 0.6"
  }
]
```

**My arithmetic:**

Population density = population / area.

Brightwater:
44675 / 921.4 = 48.4860 residents/km^2.

Millbrook:
37203 / 758.6 = 49.0417 residents/km^2.

Difference:
49.0416556815 - 48.4859995659 = 0.5556561156.

Rounded to one decimal place: 0.6 residents/km^2.

Millbrook has the higher population density in 2025. I used NR-05 and NR-11 for population data and NR-16 for the corrected Brightwater area.

Final answer: ANSWER: Millbrook | 0.6

### A4 — Why I split it this way

An alternative approach would be to use one large tool that searches the documents, performs calculations, and returns the final answer.
I did not choose this approach because it would be harder to test and debug. I separated the task into two tools: `lookup` for retrieving reliable information and `calculate` for safe arithmetic.
This design makes it easier to check the source of each value, handle archived documents and corrections, and prevent unsafe calculations. The model is responsible for understanding the question and combining the results into the final answer.

---

## Part B — Build it and run it (Medium)

### What I changed from Part A while coding

<!-- what changed in your plan, and why. "None" is an answer too. -->

### B2 — Tests

```text
<!-- pytest output -->
```

### B3 — The loop

- Round limit, and why:
- Where the logs are:
- Real Q-09 conversation compared with my A3 version, what is different:

### B4 — Three strategies

**What I kept the same:**

<!-- model, temperature, k, prompts, answer format, anything else -->

**My rule for a correct answer** (written before the first full run):

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | | | | | | | |
| 1 | S2 think and vote (k = ) | | | | | | | |
| 1 | S3 tools | | | | | | | |
| 2 | S1 direct | | | | | | | |
| 2 | S2 think and vote (k = ) | | | | | | | |
| 2 | S3 tools | | | | | | | |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | | | |
| Q-02 | | | |
| Q-03 | | | |
| Q-04 | | | |
| Q-05 | | | |
| Q-06 | | | |
| Q-07 | | | |
| Q-08 | | | |
| Q-09 | | | |
| Q-10 | | | |
| Q-11 | | | |
| Q-12 | | | |
| Q-13 | | | |
| Q-14 | | | |
| Q-15 | | | |
| Q-16 | | | |
| Q-17 | | | |
| Q-18 | | | |
| Q-19 | | | |
| Q-20 | | | |

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| | | | | |

### C2 — Three mistakes explained

### C3 — Which strategy I would use, and what would change it

### C4 — How sure I can be

### Final questions

1.
2.
3.
4.
5.
6.
7.
8.
