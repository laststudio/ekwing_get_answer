# 翼课考试答案 JSON 解析格式

本文档说明 `model_score_raw.json` 中答案字段的位置，以及 `exam_answer_json_parse_demo.py` 如何按格式解析出每道题答案。

## 1. 输入文件

默认输入：

```bash
python exam_answer_json_parse_demo.py
```

等价于读取：

```text
out_exam/model_score_raw.json
```

也可以指定文件：

```bash
python exam_answer_json_parse_demo.py --input out_exam/model_score_raw.json --output-dir out_exam
```

输入可以是三种形态：

```text
1. model_score_raw.json：模块响应数组
2. result.json：包含 model_score_infos 字段的完整结果
3. 单个 getmodelscoreinfo 响应对象
```

## 2. 模块响应结构

`model_score_raw.json` 是一个数组，每一项对应一个考试模块：

```json
[
  {
    "ok": true,
    "path": "/student/exam/getmodelscoreinfo",
    "payload": {
      "self_id": "8820442",
      "model_id": "1277627"
    },
    "data": {
      "model_info": {
        "id": "1277627",
        "model_type": "7",
        "name": "听选信息",
        "ques_list": []
      }
    }
  }
]
```

核心入口固定是：

```text
[模块].data.model_info
```

## 3. 答案字段位置

### 3.1 小题列表题型

听选信息、回答问题、询问信息这类题通常有 `ques_list`。

答案路径：

```text
[模块].data.model_info.ques_list[].answer
```

题干路径：

```text
[模块].data.model_info.ques_list[].title_text
```

示例：

```json
{
  "id": "4202933",
  "model_id": "1277627",
  "title_text": "What will they buy for their mother?",
  "answer": [
    ["A watch.", "A watch."],
    ["They will buy a watch.", "They will buy a watch."]
  ]
}
```

解析后会去重并摊平成：

```json
[
  "A watch.",
  "They will buy a watch."
]
```

### 3.2 大题直接挂答案

信息转述这类题可能没有 `ques_list`，答案直接挂在 `model_info.answer`。

答案路径：

```text
[模块].data.model_info.answer
```

题干/提示优先级：

```text
answer_tip -> title_text -> desc -> name
```

### 3.3 模仿朗读

模仿朗读通常没有 `answer`，标准答案就是朗读原文。

答案路径优先级：

```text
[模块].data.model_info.real_text -> [模块].data.model_info.dis_text
```

## 4. 输出文件

脚本会输出两个 JSON 文件。

### 4.1 answers.json

只包含答案本体，每道题一个数组：

```json
[
  ["A watch.", "They will buy a watch."],
  ["A Chinese restaurant.", "They have chosen a Chinese restaurant."]
]
```

这是最适合直接读取答案的文件。

### 4.2 answers_by_question.json

包含题目和答案的对应关系：

```json
[
  {
    "index": 1,
    "model_index": 2,
    "model_id": "1277627",
    "model_type": "7",
    "model_name": "听选信息",
    "question_index": 1,
    "question_id": "4202933",
    "question": "What will they buy for their mother?",
    "answers": [
      "A watch.",
      "They will buy a watch."
    ]
  }
]
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `index` | 全卷题目序号，从 1 开始 |
| `model_index` | 模块序号，从 1 开始 |
| `model_id` | 翼课模块 ID |
| `model_type` | 翼课题型类型 |
| `model_name` | 模块名称，如听选信息、信息转述 |
| `question_index` | 模块内题号 |
| `question_id` | 小题 ID；无小题 ID 时使用模块 ID |
| `question` | 题干、提示或朗读原文 |
| `answers` | 该题标准答案列表 |

## 5. 当前样本已确认题型

| model_type | 名称 | 答案来源 |
| --- | --- | --- |
| `1` | 模仿朗读 | `real_text`，备用 `dis_text` |
| `6` | 信息转述 | `model_info.answer` |
| `7` | 听选信息 | `ques_list[].answer` |
| `8` | 回答问题 | `ques_list[].answer` |
| `9` | 询问信息 | `ques_list[].answer` |

## 6. 接到抓取流程后的用法

发布入口是：

```bash
python study_center_exam_downloader.py
```

`study_center_exam_downloader.py` 在拉完成绩页后，会继续请求 `getmodelscoreinfo`，调用 `exam_answer_json_parse_demo.py` 的解析函数，并保存：

```text
out_exam/model_score_raw.json
```

之后可以单独运行：

```bash
python exam_answer_json_parse_demo.py --input out_exam/model_score_raw.json --output-dir out_exam
```

得到：

```text
out_exam/answers.json
out_exam/answers_by_question.json
```
