#!/usr/bin/env python3
"""Parse Ekwing exam answers from saved model_score_raw.json.

Usage:
    python exam_answer_json_parse_demo.py
    python exam_answer_json_parse_demo.py --input out_exam/model_score_raw.json --output-dir out_exam
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("out_exam/model_score_raw.json")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_json(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return normalize_json(json.loads(text))
            except ValueError:
                return value
        return value
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_json(item) for key, item in value.items()}
    return value


def first_non_empty(*values: Any) -> str | None:
    for value in values:
        if value not in (None, "", []):
            return str(value)
    return None


def dedupe_append(values: list[str], value: Any) -> None:
    if value in (None, ""):
        return
    text = str(value)
    if text and text not in values:
        values.append(text)


def flatten_answer(value: Any) -> list[str]:
    """Turn nested Ekwing answer arrays into a clean unique string list."""
    value = normalize_json(value)
    answers: list[str] = []

    def collect(item: Any) -> None:
        if item in (None, ""):
            return
        if isinstance(item, list):
            for child in item:
                collect(child)
            return
        if isinstance(item, dict):
            for key in (
                "answer",
                "answers",
                "right_answer",
                "standard_answer",
                "refText",
                "text",
                "content",
            ):
                if key in item:
                    collect(item[key])
            return
        dedupe_append(answers, item)

    collect(value)
    return answers


def extract_model_score_items(root: Any) -> list[dict[str, Any]]:
    """Accept model_score_raw.json, result.json, or a single model score object."""
    root = normalize_json(root)
    if isinstance(root, list):
        return [item for item in root if isinstance(item, dict)]
    if not isinstance(root, dict):
        return []
    if isinstance(root.get("model_score_infos"), list):
        return [item for item in root["model_score_infos"] if isinstance(item, dict)]
    if isinstance(root.get("data"), dict) and isinstance(root["data"].get("model_info"), dict):
        return [root]
    if isinstance(root.get("model_info"), dict):
        return [{"data": root}]
    return []


def parse_exam_answers(root: Any) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for model_index, item in enumerate(extract_model_score_items(root), start=1):
        data = normalize_json(item.get("data"))
        model_info = data.get("model_info") if isinstance(data, dict) else None
        model_base_info = data.get("model_base_info") if isinstance(data, dict) else None
        if isinstance(model_info, dict):
            questions.extend(parse_model_info(model_info, model_index, model_base_info if isinstance(model_base_info, dict) else None))
    return reindex_questions(questions)


def parse_model_info(
    model_info: dict[str, Any],
    model_index: int,
    model_base_info: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    model_id = first_non_empty(model_info.get("id"), model_info.get("model_id"))
    model_type = first_non_empty(model_info.get("model_type"), model_info.get("type"))
    model_name = first_non_empty(
        known_model_type_name(model_type),
        title_from_model_base_info(model_base_info),
        model_info.get("model_type_name"),
        model_info.get("name"),
    )
    common = {
        "model_index": model_index,
        "model_id": model_id,
        "model_type": model_type,
        "model_name": model_name,
    }

    ques_list = model_info.get("ques_list")
    if isinstance(ques_list, list) and ques_list:
        return [
            build_question_record(common, question, question_index)
            for question_index, question in enumerate(ques_list, start=1)
            if isinstance(question, dict)
        ]

    direct_answers = flatten_answer(model_info.get("answer"))
    if direct_answers:
        return [
            {
                **common,
                "question_index": 1,
                "question_id": model_id,
                "question": first_non_empty(
                    model_info.get("answer_tip"),
                    model_info.get("title_text"),
                    model_info.get("desc"),
                    model_name,
                ),
                "answers": direct_answers,
            }
        ]

    reading_text = first_non_empty(model_info.get("real_text"), model_info.get("dis_text"))
    if reading_text:
        return [
            {
                **common,
                "question_index": 1,
                "question_id": model_id,
                "question": reading_text,
                "answers": [reading_text],
            }
        ]

    return []


def title_from_model_base_info(model_base_info: dict[str, Any] | None) -> str | None:
    if not isinstance(model_base_info, dict):
        return None
    title_info = model_base_info.get("title_info")
    if isinstance(title_info, dict):
        return first_non_empty(title_info.get("title"), title_info.get("name"))
    return first_non_empty(model_base_info.get("title"), model_base_info.get("name"))


def known_model_type_name(model_type: str | None) -> str | None:
    return {
        "1": "模仿朗读",
        "6": "信息转述",
        "7": "听选信息",
        "8": "回答问题",
        "9": "询问信息",
    }.get(str(model_type)) if model_type is not None else None


def build_question_record(common: dict[str, Any], question: dict[str, Any], question_index: int) -> dict[str, Any]:
    return {
        **common,
        "question_index": question_index,
        "question_id": first_non_empty(question.get("id"), question.get("qid"), question.get("ques_id")),
        "question": first_non_empty(
            question.get("title_text"),
            question.get("question"),
            question.get("title"),
            question.get("text"),
        ),
        "answers": flatten_answer(question.get("answer")),
    }


def reindex_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for index, question in enumerate(questions, start=1):
        parsed.append({"index": index, **question})
    return parsed


def build_answers_only(questions: list[dict[str, Any]]) -> list[list[str]]:
    return [question["answers"] for question in questions if question.get("answers")]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按翼课考试 model_score_raw.json 格式解析每道题答案")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help=f"输入 JSON，默认 {DEFAULT_INPUT}")
    parser.add_argument("--output-dir", type=Path, help="输出目录；默认使用输入文件所在目录")
    parser.add_argument("--answers-file", default="answers.json", help="纯答案数组文件名，默认 answers.json")
    parser.add_argument(
        "--by-question-file",
        default="answers_by_question.json",
        help="每道题答案明细文件名，默认 answers_by_question.json",
    )
    parser.add_argument("--print", action="store_true", help="同时打印每道题答案明细")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = load_json(args.input)
    questions = parse_exam_answers(root)
    answers_only = build_answers_only(questions)
    output_dir = args.output_dir or args.input.parent
    write_json(output_dir / args.by_question_file, questions)
    write_json(output_dir / args.answers_file, answers_only)

    summary = {
        "input": str(args.input),
        "answers_by_question": str(output_dir / args.by_question_file),
        "answers": str(output_dir / args.answers_file),
        "question_count": len(questions),
        "answers_count": len(answers_only),
    }
    if args.print:
        summary["items"] = questions
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
