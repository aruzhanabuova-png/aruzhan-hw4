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
I followed my original plan. I added a 6-round limit to prevent infinite loops and saved the results in JSON files to make them easier to check.

### B2 — Tests

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.1.1
collected 15 items

tests/test_tools.py::test_lookup_population PASSED
tests/test_tools.py::test_lookup_correction PASSED
tests/test_tools.py::test_lookup_misspelled_name PASSED
tests/test_tools.py::test_lookup_similar_names PASSED
tests/test_tools.py::test_lookup_archived PASSED
tests/test_tools.py::test_lookup_unknown_field PASSED
tests/test_tools.py::test_lookup_empty_name PASSED
tests/test_tools.py::test_calculate_multiplication PASSED
tests/test_tools.py::test_calculate_division PASSED
tests/test_tools.py::test_calculate_zero_division PASSED
tests/test_tools.py::test_calculate_dangerous_import PASSED
tests/test_tools.py::test_calculate_class_access PASSED
tests/test_tools.py::test_calculate_large_power PASSED
tests/test_tools.py::test_calculate_empty_expression PASSED
tests/test_tools.py::test_calculate_add_subtract PASSED

============================= 15 passed in 0.12s ==============================
```

### B3 — The loop

- Round limit, and why: I set the maximum to 6 rounds to prevent infinite tool-calling loops and unnecessary API costs. If the agent reaches the limit without a final answer, its status is marked as unanswered.
- Where the logs are: The logs are saved as JSON files in the outputs/ folder. For Q-09, the log is outputs/agent_Q-09_20261020_014115_756282.json. It contains tool arguments, results, execution times, model calls, and token usage.
- Real Q-09 conversation compared with my A3 version, what is different: The real agent followed the same tool call sequence as my A3 plan: 4 lookup calls, 2 calculate calls, and 1 final calculate call. Both used 4 model rounds and produced the correct result. The difference was the final answer format. In A3, I planned "ANSWER: Millbrook | 0.6", but the real agent gave a longer explanation and included the population densities of both districts.

### B4 — Three strategies

**What I kept the same:**
I used the same model (GPT-5.6 Luna) and the same 20 questions for all three strategies. I used the same answer key and evaluation rules. For S2, I used k = 5 votes. S1 and S2 received the same documents, while S3 used lookup and calculate tools.

**My rule for a correct answer** (written before the first full run):
An answer is correct if the district name (or yes/no) matches the answer key and the numerical result matches the expected value after rounding to the required decimal places. I will check the name and number separately. Missing answers and incorrect answers will not receive credit. The answer key will only be used for evaluation, never included in model prompts.

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | 18 | 0 | 49540 | 8824 | 4.175 | 104.483 | 0.020497 |
| 1 | S2 think and vote (k = 5) | 18 | 1 | 228000 | 22631 | 17.309 | 334.229 | 0.072757 |
| 1 | S3 tools | 15 | 0 | 30945 | 4351 | 5.267 | 110.217 | 0.011410 |
| 2 | S1 direct | 18 | 0 | 48880 | 4419 | 2.939 | 63.162 | 0.015079 |
| 2 | S2 think and vote (k = 5) | 20 | 0 | 228000 | 22575 | 16.230 | 333.295 | 0.072690 |
| 2 | S3 tools | 15 | 0 | 30110 | 4304 | 4.886 | 101.299 | 0.011187 |

Cost: I calculated the cost using the model's token prices: $0.20 for 1 million input tokens and $1.20 for 1 million output tokens.
Note: For S1, I used runs 2 and 3 because I changed the prompt between tests. This means the results are not fully comparable.

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | ✓ | ✓ | ✓ |
| Q-02 | ✓ | ✓ | ✓ |
| Q-03 | ✓ | ✓ | ✓ |
| Q-04 | ✓ | ✓ | ✗ |
| Q-05 | ✓ | ✓ | ✓ |
| Q-06 | ✓ | ✓ | ✓ |
| Q-07 | ✓ | ✓ | ✓ |
| Q-08 | ✓ | ✓ | ✗ |
| Q-09 | ✓ | ✓ | ✓ |
| Q-10 | ✓ | ✓ | ✓ |
| Q-11 | ✓ | ✓ | ✓ |
| Q-12 | ✗ | ✓ | ✓ |
| Q-13 | ✓ | U | ✓ |
| Q-14 | ✓ | ✓ | ✗ |
| Q-15 | ✗ | ✓ | ✗ |
| Q-16 | ✓ | ✓ | ✓ |
| Q-17 | ✓ | ✓ | ✓ |
| Q-18 | ✓ | ✓ | ✓ |
| Q-19 | ✓ | ✗ | ✓ |
| Q-20 | ✓ | ✓ | ✗ |

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| Q-01 | 7 | 7 | Ossbridge, 4.57 | Ossbridge, 4.57 |
| Q-02 | 6 | 7 | Harrowfield, 1.69 | Harrowfield, 1.69 |
| Q-03 | 7 | 6 | Lindenmoor, 5.3 | Lindenmoor, 5.34 |
| Q-04 | 7 | 7 | Millbrook, 2.6 | Millbrook, 2.6 |
| Q-05 | 7 | 7 | Coldharbour, 14235 | Coldharbour, 14235 |

I tested five questions using two lookup descriptions. My original description was "Find a factual value for a district in the local corpus." The vague description was "Get information."
Both descriptions produced answers for all five questions. The number of tool calls changed for Q-02 and Q-03. Q-03 also had a small difference in numerical precision. In this small experiment, the vague description did not cause unanswered questions, but the results show that tool descriptions can affect the agent's behavior.
The lookup inputs were the same for all five questions. Only the calculations changed. In Q-02, the vague version used one more calculate call. In Q-03, it used one less calculate call. This happened because the model can choose different steps to solve a question. Both versions gave similar answers.

### C2 — Three mistakes explained

**Mistake 1 — S1, Q-12**
The model gave a wrong answer: "Harrowfield | 322.0 thousand tenge per pupil". The number was wrong. The model may have made a mistake with the calculation or units. I would check the numbers and units.

**Mistake 2 — S2, Q-13**
The final answer was "unanswered | unknown". But all five votes gave the same answer: "Coldharbour | 4.16%". The problem was probably in the voting code. I would check how the code reads and compares answers.

**Mistake 3 — S3, Q-20**
The agent answered: "Harrowfield had the largest 2025 budget per resident" and calculated 2,103.41. But the correct answer was Ashgrove with 2,993. The agent did not compare all districts correctly. I would calculate and check each district.

1. Why does voting help sometimes but not always?
Voting helps when the model gives different answers. If most answers are correct, voting can choose the correct one. But it cannot fix a mistake in the code or when most answers are wrong.

2. Why is a calculator useful?
A calculator gives exact math results. It helps avoid calculation mistakes. But the model must use the correct numbers and formula.

3. Why does the agent need many rounds?
The agent needs rounds to find data, calculate numbers, and give the final answer. Each new round can use more tokens because the model also reads the previous messages, tool calls, and results.

### C3 — Which strategy I would use, and what would change it

I would choose S2 (think and vote) when accuracy is the most important factor. It answered 18 out of 20 questions correctly in Run 1 and 20 out of 20 in Run 2. However, it was the slowest and most expensive strategy because it used five model calls per question.
If speed and cost were more important, I would choose S1. It answered 18 out of 20 questions correctly in both runs and was much faster than S2. I would not choose S3 for this task because it answered only 15 out of 20 questions correctly in both runs.
S1 used about 49,000 input tokens and took 63–104 seconds. S2 used 228,000 input tokens and took about 334 seconds. S3 used about 30,000 input tokens and took 101–110 seconds.

**When would I change my choice?**
Small budget: I would choose S1 because it uses fewer tokens than S2 and gives good results.
Strict time limit: I would choose S1 because it is much faster than S2.
Questions without math: I would choose S1 because a calculator is not needed.

### C4 — How sure can I be?

**1. How different were the two runs?**
S1 got 18/20 correct answers in both runs.
S2 got 18/20 in Run 1 and 20/20 in Run 2.
S3 got 15/20 in both runs.
So, S2 changed the most, with 2 more correct answers.

**2. Is the difference between the two best strategies bigger than that?**
The two best strategies were S1 and S2.
S1 got an average of 18/20, and S2 got an average of 19/20.
The difference is only 1 question. This is smaller than the difference between S2's two runs, which was 2 questions.

**3. How many questions would I need?**
I would test at least 200 questions and repeat each test 5 times. This would help me trust the results more.
I am not fully sure about my results because 20 questions are not enough. Also, I changed the S1 prompt between tests, so the comparison is not completely fair.

### Final questions

**1. When the model sends a `tool_calls` message, what has actually run so far?**
The model has only asked to use a tool. The tool has not run yet. My Python code must read the request, run the tool, and send the result back to the model.

**2. Why does `arguments` arrive as a string, and what goes wrong if you pass it straight into your function?**
The arguments arrive as a JSON string. I use `json.loads()` to change it into a Python dictionary. If I pass the string directly, my function may get the wrong input or give an error.

**3. How many tokens do your two tool definitions add to every S3 request?**
My two tool definitions use about 201 tokens. I measured this using tiktoken. These tokens are added to every S3 request because the model needs to know how to use the tools.

**4. How much more did S2 cost than S1?**
In Run 1, S2 cost $0.072757 and S1 cost $0.020497. S2 cost **$0.052260 more**, about 3.55 times as much. This is because S2 asks the model five times for each question.

**5. Which question needed the most rounds in S3, and why?**
The maximum was 3 rounds. In Run 1, Q-07, Q-11, Q-12, and Q-15 needed 3 rounds. Q-11 also used 11 tool calls. The agent needed several steps to find data, make calculations, and give the final answer.

**6. What would you change in `lookup` if there were 100,000 documents?**
I would add a database and a search index. This would help `lookup` find the correct document faster without checking every document one by one.

**7. What stops your `calculate` from running dangerous code? Could the model still make it misbehave?**
My calculator uses safe AST operations instead of `eval()`. It does not allow dangerous Python commands. But the model can still send a wrong formula or invalid input.

**8. For which kind of question did tools help most, and for which did they not help at all?**
Tools were useful for finding exact numbers and doing calculations. For example, S3 used `lookup` and `calculate` in Q-20. But tools did not help when the agent chose the wrong data or comparison, so S3 still gave a wrong answer.