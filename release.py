#!/usr/bin/env python3
"""Release entry for Ekwing Student 5.2.7 study-center exam answer export.

Usage:
    python release.py
    python release.py --list-type current --exam-index 0 --save-dir out_exam
    python release.py --list-type study-center-history --exam-index 0 --save-dir out_exam
    python release.py --self-id 8820442 --raw-response
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, parse_qs, urlsplit

import requests
from demo import fill_interactive_args, login_by_real_name, save_login_cache
from exam_answer_json_parse_demo import build_answers_only as build_json_answers_only
from exam_answer_json_parse_demo import parse_exam_answers as parse_json_exam_answers
from homework_demo import (
    BASE_URL,
    STUDY_CENTER_TASK_TYPES,
    common_params,
    get_all_exam_history,
    get_exam_history_page,
    get_study_center_tasks,
    post_form,
    summarize_exam_history_item,
    summarize_task_item,
)


EXAM_ITEM_PATH = "/student/exam/getstuexamitem"
EXAM_SCORE_PATH = "/student/exam/getscoreinfo"
BASIC_EXAM_SCORE_PATH = "/student/exam/getbasicscoreinfo"
GET_MODEL_SCORE_PATH = "/student/exam/getmodelscoreinfo"
DEFAULT_SAVE_DIR = "out_exam"

ID_KEYS = (
    "id",
    "qid",
    "ques_id",
    "question_id",
    "item_id",
    "model_id",
    "self_id",
)
TYPE_KEYS = ("type", "type_name", "qtype", "tk_biz", "model_type", "name")
QUESTION_KEYS = (
    "title",
    "question",
    "question_text",
    "ques_title",
    "q_title",
    "stem",
    "content",
    "txt",
    "text",
    "sentence",
    "word",
    "topic",
)
ANSWER_KEYS = (
    "answer",
    "answers",
    "ans",
    "right_answer",
    "rightAnswer",
    "standard_answer",
    "standardAnswer",
    "correct_answer",
    "correctAnswer",
    "std_answer",
    "real_answer",
    "reference_answer",
    "answer_info",
)
USER_ANSWER_KEYS = (
    "user_answer",
    "userAnswer",
    "stu_answer",
    "stuAnswer",
    "student_answer",
    "studentAnswer",
    "my_answer",
    "myAnswer",
    "record_answer",
    "recordAnswer",
    "answer_content",
)
SCORE_KEYS = (
    "score",
    "self_score",
    "total_score",
    "get_score",
    "user_score",
    "stu_score",
    "point",
    "accuracy",
    "fluency",
    "integrity",
)
ANALYSIS_KEYS = (
    "analysis",
    "answer_analysis",
    "analysis_text",
    "explain",
    "explanation",
    "parse",
    "jx",
    "comment",
)


def prompt_yes_no(label: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{label}（{suffix}）：").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes", "1", "true"}:
            return True
        if raw in {"n", "no", "0", "false"}:
            return False
        print("请输入 y 或 n。", file=sys.stderr)


def prompt_choice(label: str, choices: list[tuple[str, str]]) -> str:
    print(label, file=sys.stderr)
    for index, (_, text) in enumerate(choices, start=1):
        print(f"[{index}] {text}", file=sys.stderr)
    while True:
        raw = input(f"请输入 1..{len(choices)}：").strip()
        try:
            selected = int(raw)
        except ValueError:
            print("请输入数字序号。", file=sys.stderr)
            continue
        if 1 <= selected <= len(choices):
            return choices[selected - 1][0]
        print("序号超出范围。", file=sys.stderr)


def fill_interactive_exam_args(args: argparse.Namespace) -> argparse.Namespace:
    if args.basic is None:
        args.basic = prompt_yes_no("是否使用 Basic 账号接口", default=False)
    if args.list_type is None and not args.self_id:
        args.list_type = prompt_choice(
            "请选择考试来源：",
            [
                ("current", "当前学习中心考试任务"),
                ("study-center-history", "历史学习中心考试任务"),
            ],
        )
    args.list_type = args.list_type or "study-center-history"
    args.page = 1 if args.page is None else args.page
    args.task_type = "exam"
    args.homework_only = False
    return args


def exam_score_path(args: argparse.Namespace) -> str:
    return BASIC_EXAM_SCORE_PATH if args.basic else EXAM_SCORE_PATH


def path_from_url(url: Any) -> str | None:
    if not url:
        return None
    parts = urlsplit(str(url))
    if not parts.path:
        return None
    return parts.path


def query_params(url: Any) -> dict[str, str]:
    if not url:
        return {}
    return dict(parse_qsl(urlsplit(str(url)).query, keep_blank_values=True))


def query_value(url: Any, key: str) -> str | None:
    if not url:
        return None
    values = parse_qs(urlsplit(str(url)).query).get(key)
    if not values:
        return None
    return values[0]


def exam_self_id(exam: dict[str, Any]) -> str | None:
    return first_non_empty(
        exam.get("self_id"),
        query_value(exam.get("url"), "self_id"),
        query_value(exam.get("start_url"), "self_id"),
        exam.get("record_id"),
        exam.get("id"),
    )


def exam_model_id(exam: dict[str, Any]) -> str | None:
    return first_non_empty(
        exam.get("last_model_id"),
        exam.get("model_id"),
        query_value(exam.get("url"), "model_id"),
        query_value(exam.get("start_url"), "model_id"),
    )


def first_non_empty(*values: Any) -> str | None:
    for value in values:
        if value is not None and str(value) != "":
            return str(value)
    return None


def get_exam_item(uid: str, token: str, args: argparse.Namespace, self_id: str) -> dict[str, Any]:
    payload = common_params(args, uid, token)
    payload["self_id"] = self_id
    body = post_form(EXAM_ITEM_PATH, payload, args.timeout)
    return {"path": EXAM_ITEM_PATH, "payload": payload, "data": normalize_json(body.get("data"))}


def score_url(exam: dict[str, Any]) -> Any:
    url = exam.get("url") or exam.get("start_url")
    path = path_from_url(url)
    if path and "scoreinfo" in path.lower():
        return url
    return None


def get_exam_score_info(
    uid: str,
    token: str,
    args: argparse.Namespace,
    exam: dict[str, Any],
    self_id: str,
) -> dict[str, Any]:
    payload = common_params(args, uid, token)
    url = score_url(exam)
    path = path_from_url(url) or exam_score_path(args)
    payload.update(query_params(url))
    payload.update({"self_id": self_id, "method": args.score_method})
    if "type" not in payload and args.score_type is not None:
        payload["type"] = args.score_type
    if "type" not in payload and "basic" in path.lower():
        payload["type"] = "0"
    return post_score_form(path, payload, args.timeout)


def post_score_form(path: str, payload: dict[str, str], timeout: int) -> dict[str, Any]:
    response = requests.post(f"{BASE_URL}{path}", data=payload, timeout=timeout)
    return parse_score_response(response, path, payload)


def get_score_page(path: str, payload: dict[str, str], timeout: int) -> dict[str, Any]:
    response = requests.get(f"{BASE_URL}{path}", params=payload, timeout=timeout)
    return parse_score_response(response, path, payload)


def parse_score_response(response: requests.Response, path: str, payload: dict[str, str]) -> dict[str, Any]:
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    text = decode_response_text(response)

    try:
        body = response.json()
    except ValueError:
        extracted = extract_json_from_html(text)
        return {
            "path": path,
            "payload": payload,
            "content_type": content_type,
            "response_kind": "html",
            "raw_text": text,
            "data": extracted,
        }

    if body.get("status") != 0:
        raise RuntimeError(json.dumps(body, ensure_ascii=False))
    return {
        "path": path,
        "payload": payload,
        "content_type": content_type,
        "response_kind": "json",
        "data": normalize_json(body.get("data")),
    }


def get_model_score_info(uid: str, token: str, args: argparse.Namespace, request: dict[str, Any]) -> dict[str, Any]:
    url = request.get("url")
    payload = common_params(args, uid, token)
    payload.update(query_params(url))
    if request.get("self_id") not in (None, ""):
        payload["self_id"] = str(request["self_id"])
    if request.get("model_id") not in (None, ""):
        payload["model_id"] = str(request["model_id"])
    path = path_from_url(url) or GET_MODEL_SCORE_PATH
    return get_score_page(path, payload, args.timeout)


def get_model_score_infos(
    uid: str,
    token: str,
    args: argparse.Namespace,
    score_info: dict[str, Any],
) -> list[dict[str, Any]]:
    requests_to_fetch = extract_model_score_requests(score_info.get("data"))
    results: list[dict[str, Any]] = []
    for request in requests_to_fetch:
        try:
            results.append({"ok": True, "request": request, **get_model_score_info(uid, token, args, request)})
        except Exception as exc:
            results.append({"ok": False, "request": request, "path": GET_MODEL_SCORE_PATH, "error": str(exc), "data": None})
            if args.strict:
                raise
    return results


def extract_model_score_requests(score_data: Any) -> list[dict[str, Any]]:
    requests_to_fetch: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, item in iter_dicts(normalize_json(score_data), "$"):
        url = item.get("url")
        path = path_from_url(url)
        if path != GET_MODEL_SCORE_PATH:
            continue
        model_id = first_non_empty(item.get("model_id"), query_value(url, "model_id"))
        self_id = first_non_empty(item.get("self_id"), query_value(url, "self_id"))
        stable_key = f"{self_id or ''}:{model_id or ''}:{url or ''}"
        if stable_key in seen:
            continue
        seen.add(stable_key)
        requests_to_fetch.append(
            {
                "url": url,
                "self_id": self_id,
                "model_id": model_id,
                "status": item.get("status"),
            }
        )
    return requests_to_fetch


def decode_response_text(response: requests.Response) -> str:
    content_type = response.headers.get("content-type", "").lower()
    if "charset=" in content_type:
        return response.text
    try:
        return response.content.decode("utf-8")
    except UnicodeDecodeError:
        return repair_mojibake(response.text)


def repair_mojibake_text(value: str) -> str:
    try:
        repaired = value.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    if count_cjk(repaired) > count_cjk(value):
        return repaired
    return value


def repair_mojibake(value: Any) -> Any:
    if isinstance(value, str):
        return repair_mojibake_text(value)
    if isinstance(value, list):
        return [repair_mojibake(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_mojibake(item) for key, item in value.items()}
    return value


def count_cjk(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


def extract_json_from_html(text: str) -> dict[str, Any]:
    decoded = repair_mojibake_text(html.unescape(text))
    candidates = extract_json_parse_candidates(decoded)
    candidates.extend(extract_raw_json_candidates(decoded, max_candidates=80))
    useful = [candidate for candidate in candidates if has_answerish_content(candidate)]
    return {
        "html_title": extract_html_title(decoded),
        "json_candidate_count": len(candidates),
        "useful_candidate_count": len(useful),
        "useful_candidates": useful[:20],
    }


def extract_html_title(text: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return repair_mojibake_text(re.sub(r"\s+", " ", match.group(1)).strip())


def extract_json_parse_candidates(text: str) -> list[Any]:
    candidates: list[Any] = []
    pattern = re.compile(r"JSON\.parse\(\s*(['\"])(.*?)\1\s*\)", re.DOTALL)
    for match in pattern.finditer(text):
        raw = match.group(2)
        for value in (raw, bytes(raw, "utf-8").decode("unicode_escape", errors="ignore")):
            try:
                candidates.append(normalize_json(json.loads(value)))
                break
            except ValueError:
                continue
    return candidates


def extract_raw_json_candidates(text: str, max_candidates: int) -> list[Any]:
    decoder = json.JSONDecoder()
    candidates: list[Any] = []
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(text[index:])
        except ValueError:
            continue
        if end < 8:
            continue
        candidates.append(normalize_json(value))
        if len(candidates) >= max_candidates:
            break
    return candidates


def has_answerish_content(value: Any) -> bool:
    if isinstance(value, dict):
        keys = set(value.keys())
        if keys.intersection(ANSWER_KEYS + USER_ANSWER_KEYS + SCORE_KEYS + ANALYSIS_KEYS):
            return True
        return any(has_answerish_content(child) for child in value.values())
    if isinstance(value, list):
        return any(has_answerish_content(child) for child in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(token in lowered for token in ("answer", "score", "analysis", "stuanswer", "right_answer"))
    return False


def get_exam_list(uid: str, token: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.self_id:
        return [
            {
                "id": args.self_id,
                "self_id": args.self_id,
                "last_model_id": args.model_id,
                "title": args.title or f"考试 {args.self_id}",
                "type": "exam",
            }
        ]
    if args.list_type in {"current", "study-center"}:
        items = get_study_center_tasks(uid, token, args)
    elif args.all_pages:
        items = get_all_exam_history(uid, token, args).get("list") or []
    else:
        items = get_exam_history_page(uid, token, args, page=args.page).get("list") or []
    return [item for item in items if isinstance(item, dict)]


def select_exam(args: argparse.Namespace, exams: list[dict[str, Any]]) -> dict[str, Any]:
    if not exams:
        raise RuntimeError("考试列表为空")
    if args.exam_index is not None:
        if 0 <= args.exam_index < len(exams):
            return exams[args.exam_index]
        raise RuntimeError(f"--exam-index 超出范围：0..{len(exams) - 1}")

    summarizer = summarize_task_item if args.list_type in {"current", "study-center"} else summarize_exam_history_item
    print("请选择考试：", file=sys.stderr)
    for index, exam in enumerate(exams):
        print(f"[{index}] {json.dumps(summarizer(exam), ensure_ascii=False)}", file=sys.stderr)
    while True:
        raw = input(f"请输入 0..{len(exams) - 1}：").strip()
        try:
            selected = int(raw)
        except ValueError:
            print("请输入数字序号。", file=sys.stderr)
            continue
        if 0 <= selected < len(exams):
            return exams[selected]
        print("序号超出范围。", file=sys.stderr)


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
        return repair_mojibake({key: normalize_json(item) for key, item in value.items()})
    return value


def preview(value: Any, limit: int = 240) -> Any:
    value = normalize_json(value)
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = "" if value is None else str(value)
    if len(text) <= limit:
        return value
    return text[:limit] + "...(truncated)"


def first_field(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def selected_fields(item: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: preview(item[key]) for key in keys if key in item and item[key] not in (None, "")}


def looks_like_answer_record(item: dict[str, Any]) -> bool:
    if any(key in item for key in ANSWER_KEYS + USER_ANSWER_KEYS + ANALYSIS_KEYS):
        return True
    if any(key in item for key in QUESTION_KEYS) and any(key in item for key in SCORE_KEYS + TYPE_KEYS):
        return True
    return False


def iter_dicts(value: Any, path: str = "$") -> list[tuple[str, dict[str, Any]]]:
    found: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, dict):
        found.append((path, value))
        for key, child in value.items():
            found.extend(iter_dicts(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(iter_dicts(child, f"{path}[{index}]"))
    return found


def parse_answer_records(sources: dict[str, Any], max_items: int) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source_name, source_value in sources.items():
        for path, item in iter_dicts(normalize_json(source_value), source_name):
            if not looks_like_answer_record(item):
                continue
            stable_key = json.dumps(
                {
                    "id": first_field(item, ID_KEYS),
                    "question": first_field(item, QUESTION_KEYS),
                    "answer": first_field(item, ANSWER_KEYS),
                    "user_answer": first_field(item, USER_ANSWER_KEYS),
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            if stable_key in seen:
                continue
            seen.add(stable_key)
            records.append(
                {
                    "source": source_name,
                    "path": path,
                    "id": preview(first_field(item, ID_KEYS)),
                    "type": preview(first_field(item, TYPE_KEYS)),
                    "question": preview(first_field(item, QUESTION_KEYS)),
                    "standard_answer": selected_fields(item, ANSWER_KEYS),
                    "student_answer": selected_fields(item, USER_ANSWER_KEYS),
                    "score": selected_fields(item, SCORE_KEYS),
                    "analysis": selected_fields(item, ANALYSIS_KEYS),
                    "keys": list(item.keys()),
                }
            )
            if len(records) >= max_items:
                return {"count": len(records), "truncated": True, "items": records}

    return {"count": len(records), "truncated": False, "items": records}


def parse_structured_exam_report(score_data: Any) -> dict[str, Any]:
    reports = find_report_roots(normalize_json(score_data))
    if not reports:
        return {"found": False, "sections": [], "questions": []}

    report = reports[0]
    self_info = report.get("self_info") if isinstance(report.get("self_info"), dict) else {}
    ans_info = report.get("ans_info") if isinstance(report.get("ans_info"), dict) else {}
    model_titles = build_model_title_map(report)
    sections = parse_report_sections(report)
    questions = parse_report_questions(ans_info, model_titles)
    answers_only = build_answers_only(questions)
    return {
        "found": True,
        "self_info": {
            "self_id": self_info.get("self_id"),
            "title": self_info.get("title"),
            "user_score": self_info.get("user_score"),
            "total_score": self_info.get("total_score"),
            "user_score_level": self_info.get("user_score_level"),
            "start_time": self_info.get("start_time"),
            "end_time": self_info.get("end_time"),
            "submit_time": self_info.get("submit_time"),
            "use_time": self_info.get("use_time"),
        },
        "answer_info": {
            "id": ans_info.get("id"),
            "score": ans_info.get("score"),
            "status": ans_info.get("status"),
            "use_time": ans_info.get("use_time"),
            "content_id": ans_info.get("content_id"),
        },
        "sections": sections,
        "questions": questions,
        "answers_only": answers_only,
        "section_count": len(sections),
        "question_count": len(questions),
    }


def merge_structured_reports(primary: dict[str, Any], model_reports: list[dict[str, Any]]) -> dict[str, Any]:
    questions = list(primary.get("questions") if isinstance(primary.get("questions"), list) else [])
    for report in model_reports:
        report_questions = report.get("questions")
        if isinstance(report_questions, list):
            questions.extend(report_questions)

    merged = dict(primary)
    merged["questions"] = dedupe_questions(questions)
    merged["answers_only"] = build_answers_only(merged["questions"])
    merged["question_count"] = len(merged["questions"])
    merged["model_report_count"] = len(model_reports)
    return merged


def parse_model_score_questions(model_score_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for item in model_score_infos:
        if not item.get("ok"):
            continue
        data = normalize_json(item.get("data"))
        model_info = data.get("model_info") if isinstance(data, dict) else None
        if isinstance(model_info, dict):
            questions.extend(parse_model_info_questions(model_info))
    return questions


def parse_model_info_questions(model_info: dict[str, Any]) -> list[dict[str, Any]]:
    model_id = first_non_empty(model_info.get("id"), model_info.get("model_id"))
    model_type = first_non_empty(model_info.get("model_type"), model_info.get("type"))
    model_title = first_non_empty(model_info.get("model_type_name"), model_info.get("name"))
    common = {
        "section_index": None,
        "model_id": model_id,
        "model_type": model_type,
        "model_title": model_title,
        "model_score": model_info.get("score"),
    }

    ques_list = model_info.get("ques_list")
    if isinstance(ques_list, list) and ques_list:
        questions: list[dict[str, Any]] = []
        for index, question in enumerate(ques_list, start=1):
            if not isinstance(question, dict):
                continue
            questions.append(
                {
                    **common,
                    "question_index": index,
                    "question_id": first_non_empty(question.get("id"), question.get("qid"), question.get("ques_id")),
                    "title": first_non_empty(question.get("title_text"), question.get("title"), model_title),
                    "text": first_non_empty(question.get("title_text"), question.get("question"), question.get("text")),
                    "standard_answer": normalize_answer_candidates(question.get("answer")),
                    "student_answer": normalize_answer_candidates(question.get("user_ans")),
                    "score": selected_fields({**model_info, **question}, SCORE_KEYS),
                    "audio": first_non_empty(question.get("title_audio"), question.get("audio"), question.get("record_url")),
                    "details_count": 0,
                    "details_preview": [],
                }
            )
        return questions

    direct_answers = normalize_answer_candidates(model_info.get("answer"))
    if direct_answers:
        return [
            {
                **common,
                "question_index": 1,
                "question_id": model_id,
                "title": first_non_empty(
                    model_info.get("answer_tip"),
                    model_info.get("title_text"),
                    model_info.get("desc"),
                    model_title,
                ),
                "text": first_non_empty(
                    model_info.get("answer_tip"),
                    model_info.get("title_text"),
                    model_info.get("desc"),
                ),
                "standard_answer": direct_answers,
                "student_answer": normalize_answer_candidates(model_info.get("user_ans")),
                "score": selected_fields(model_info, SCORE_KEYS),
                "audio": first_non_empty(model_info.get("title_audio"), model_info.get("audio"), model_info.get("record_url")),
                "details_count": 0,
                "details_preview": [],
            }
        ]

    standard_text = first_non_empty(model_info.get("real_text"), model_info.get("dis_text"))
    if standard_text:
        return [
            {
                **common,
                "question_index": 1,
                "question_id": model_id,
                "title": model_title,
                "text": standard_text,
                "standard_answer": [standard_text],
                "student_answer": normalize_answer_candidates(model_info.get("user_ans")),
                "score": selected_fields(model_info, SCORE_KEYS),
                "audio": first_non_empty(model_info.get("real_audio"), model_info.get("analysis_audio"), model_info.get("intro_audio")),
                "details_count": 0,
                "details_preview": [],
            }
        ]

    return []


def normalize_answer_candidates(value: Any) -> list[str]:
    value = normalize_json(value)
    flattened: list[str] = []

    def collect(item: Any) -> None:
        if item in (None, ""):
            return
        if isinstance(item, list):
            for child in item:
                collect(child)
            return
        if isinstance(item, dict):
            for key in ANSWER_KEYS + USER_ANSWER_KEYS + ("text", "content"):
                if key in item:
                    collect(item[key])
            return
        text = str(item)
        if text not in flattened:
            flattened.append(text)

    collect(value)
    return flattened


def dedupe_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for question in questions:
        stable_key = json.dumps(
            {
                "model_id": question.get("model_id"),
                "question_id": question.get("question_id"),
                "standard_answer": question.get("standard_answer"),
                "text": question.get("text"),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        if stable_key in seen:
            continue
        seen.add(stable_key)
        unique.append(question)
    return unique


def find_report_roots(value: Any) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    for _, item in iter_dicts(value, "$"):
        if isinstance(item.get("self_info"), dict) and isinstance(item.get("ans_info"), dict):
            roots.append(item)
    return roots


def parse_report_sections(report: dict[str, Any]) -> list[dict[str, Any]]:
    model_list = report.get("model_list")
    if not isinstance(model_list, list):
        return []

    sections: list[dict[str, Any]] = []
    for index, section in enumerate(model_list, start=1):
        if not isinstance(section, dict):
            continue
        sections.append(
            {
                "index": index,
                "title": section.get("title"),
                "desc": section.get("desc"),
                "score": section.get("score"),
                "user_score": section.get("user_score"),
                "user_score_level": section.get("user_score_level"),
                "ques_num": section.get("ques_num"),
                "has_score": section.get("has_score"),
            }
        )
    return sections


def build_model_title_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    title_map: dict[str, dict[str, Any]] = {}
    for _, item in iter_dicts(report.get("self"), "$.self"):
        model_id = item.get("model_id")
        if model_id in (None, "") or not item.get("title"):
            continue
        title_map[str(model_id)] = {
            "title": item.get("title"),
            "model_type": item.get("model_type"),
            "score": item.get("score"),
            "name_id": item.get("name_id"),
        }
    return title_map


def parse_report_questions(ans_info: dict[str, Any], model_titles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    content = ans_info.get("content")
    if not isinstance(content, list):
        return []

    questions: list[dict[str, Any]] = []
    for section_index, section in enumerate(content, start=1):
        if not isinstance(section, dict):
            continue
        ques_list = section.get("ques_list")
        if not isinstance(ques_list, list):
            continue
        for question_index, question in enumerate(ques_list, start=1):
            if isinstance(question, dict):
                questions.append(parse_report_question(section_index, question_index, section, question, model_titles))
    return questions


def parse_report_question(
    section_index: int,
    question_index: int,
    section: dict[str, Any],
    question: dict[str, Any],
    model_titles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    details = question.get("details")
    detail_items = [item for item in details if isinstance(item, dict)] if isinstance(details, list) else []
    detail_texts = [str(item.get("text")) for item in detail_items if item.get("text") not in (None, "")]
    model_id = first_non_empty(question.get("model_id"), section.get("model_id"))
    model_meta = model_titles.get(str(model_id), {}) if model_id is not None else {}
    standard_answers = normalize_ref_text(question.get("refText"))
    spoken_text = first_non_empty(
        question.get("hypothesis"),
        collect_sentence_text(question),
        collect_detail_hypothesis(detail_items),
        " ".join(detail_texts) if detail_texts else None,
    )
    return {
        "section_index": section_index,
        "question_index": question_index,
        "model_id": model_id,
        "model_type": first_non_empty(question.get("model_type"), section.get("model_type"), model_meta.get("model_type")),
        "model_title": model_meta.get("title"),
        "model_score": model_meta.get("score"),
        "question_id": first_non_empty(
            question.get("id"),
            question.get("qid"),
            question.get("ques_id"),
            question.get("question_id"),
        ),
        "title": first_non_empty(question.get("title"), question.get("name"), section.get("title")),
        "text": first_non_empty(
            question.get("text"),
            question.get("txt"),
            question.get("question"),
            question.get("content"),
            standard_answers[0] if standard_answers else None,
            spoken_text,
        ),
        "standard_answer": standard_answers,
        "student_answer": first_non_empty(first_field(question, USER_ANSWER_KEYS), question.get("hypothesis"), collect_sentence_text(question)),
        "score": selected_fields(question, SCORE_KEYS),
        "audio": first_non_empty(question.get("audioUrl"), question.get("audio"), question.get("record_url")),
        "details_count": len(detail_items),
        "details_preview": [summarize_detail_score(item) for item in detail_items[:20]],
    }


def normalize_ref_text(value: Any) -> list[str]:
    value = normalize_json(value)
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if value not in (None, ""):
        return [str(value)]
    return []


def collect_sentence_text(question: dict[str, Any]) -> str | None:
    sentences = question.get("sentences")
    if not isinstance(sentences, list):
        return None
    texts = [str(item.get("text")) for item in sentences if isinstance(item, dict) and item.get("text")]
    return " ".join(texts) if texts else None


def collect_detail_hypothesis(details: list[dict[str, Any]]) -> str | None:
    texts = [str(item.get("hypothesis")) for item in details if item.get("hypothesis") not in (None, "")]
    return " ".join(texts) if texts else None


def summarize_detail_score(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": item.get("text"),
        "score": item.get("score"),
        "hypothesis": item.get("hypothesis"),
        "pronunciation": item.get("pronunciation"),
        "fluency": item.get("fluency"),
        "integrity": item.get("integrity"),
    }


def build_answers_only(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    answers: list[dict[str, Any]] = []
    for index, question in enumerate(questions, start=1):
        answers.append(
            {
                "index": index,
                "model_title": question.get("model_title"),
                "model_id": question.get("model_id"),
                "model_type": question.get("model_type"),
                "question_id": question.get("question_id"),
                "prompt_or_reference": question.get("text"),
                "standard_answer": question.get("standard_answer"),
                "student_answer": question.get("student_answer"),
                "score": question.get("score"),
                "audio": question.get("audio"),
                "word_scores": question.get("details_preview"),
            }
        )
    return answers


def build_answer_values(answers_only: list[dict[str, Any]]) -> list[Any]:
    answers: list[Any] = []
    for item in answers_only:
        answer = item.get("standard_answer")
        if answer in (None, "", []):
            continue
        answers.append(answer)
    return answers


def summarize_exam(exam: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": exam.get("id"),
        "self_id": exam_self_id(exam),
        "model_id": exam_model_id(exam),
        "type": exam.get("type", "exam"),
        "title": exam.get("title") or exam.get("self_title"),
        "status": exam.get("status") or exam.get("self_status"),
        "score": exam.get("score") or exam.get("self_score"),
        "record_id": exam.get("record_id"),
        "url": exam.get("url") or exam.get("start_url"),
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def output_result(result: dict[str, Any], args: argparse.Namespace) -> None:
    if args.save_dir:
        save_dir = Path(args.save_dir)
        write_json(save_dir / "exam.json", result["exam"])
        write_json(save_dir / "exam_item_raw.json", result["exam_item"])
        write_json(save_dir / "score_info_raw.json", result["score_info"])
        write_json(save_dir / "model_score_raw.json", result["model_score_infos"])
        raw_text = result["score_info"].get("raw_text")
        if isinstance(raw_text, str):
            (save_dir / "score_info.html").write_text(raw_text, encoding="utf-8")
        write_json(save_dir / "structured_report.json", result["structured_report"])
        write_json(save_dir / "answers.json", result["answers"])
        write_json(save_dir / "answers_by_question.json", result["answers_by_question"])
        write_json(save_dir / "answers_only.json", result["answers_only"])
        write_json(save_dir / "parsed_answers.json", result["parsed_answers"])
        write_json(save_dir / "result.json", result)
        print(f"考试原始响应和答案 JSON 已保存到：{save_dir}", file=sys.stderr)

    if args.raw_response:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    structured_summary = summarize_structured_report(result["structured_report"], args.max_summary_questions)
    summary = {
        "exam": summarize_exam(result["exam"]),
        "exam_item_ok": result["exam_item"].get("ok"),
        "exam_item_error": result["exam_item"].get("error"),
        "score_info_ok": result["score_info"].get("ok"),
        "score_info_error": result["score_info"].get("error"),
        "score_info_kind": result["score_info"].get("response_kind"),
        "score_info_title": ((result["score_info"].get("data") or {}).get("html_title") if isinstance(result["score_info"].get("data"), dict) else None),
        "structured_report": structured_summary,
        "answers_count": len(result["answers"]),
        "answers_preview": result["answers"][: args.max_summary_questions],
        "answers_by_question_preview": result["answers_by_question"][: args.max_summary_questions],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def summarize_structured_report(report: dict[str, Any], max_questions: int) -> dict[str, Any]:
    questions = report.get("questions")
    question_items = questions if isinstance(questions, list) else []
    return {
        **{key: value for key, value in report.items() if key not in {"questions", "answers_only"}},
        "questions_preview": question_items[:max_questions],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="翼课学生 5.2.7 学习中心考试答案导出 release")
    parser.add_argument("--name", help="学生姓名，对应 nicename；不传则交互式输入")
    parser.add_argument("--school-name", help="学校名称，对应 schoolName；不传则交互式输入")
    parser.add_argument("--school-id", help="学校 ID，对应 schoolId；不传则交互式输入")
    parser.add_argument("--password", help="明文密码；不传则交互式输入")
    parser.add_argument("--choose-index", type=int, help="同名账号分支选择序号；不传则交互选择")

    parser.add_argument(
        "--list-type",
        choices=("current", "study-center", "study-center-history"),
        default=None,
        help="考试来源：current/study-center 为当前学习中心考试；study-center-history 为历史学习中心考试；不传则交互选择",
    )
    parser.add_argument("--page", type=int, default=None, help="历史考试页码，默认 1")
    parser.add_argument("--all-pages", action="store_true", help="历史考试拉取全部分页")
    parser.add_argument("--exam-index", type=int, help="选择考试列表中的序号，从 0 开始")
    parser.add_argument("--self-id", help="直接指定考试 self_id，跳过列表选择")
    parser.add_argument("--model-id", help="配合 --self-id 记录 model_id，便于输出摘要")
    parser.add_argument("--title", help="配合 --self-id 记录标题，便于输出摘要")
    parser.add_argument(
        "--basic",
        action="store_true",
        default=None,
        help="使用 Basic 账号考试成绩接口；不传则交互选择",
    )
    parser.add_argument("--score-method", default="exam_result", help="getscoreinfo 的 method，默认 exam_result")
    parser.add_argument("--score-type", default=None, help="成绩接口额外 type 参数；列表 URL 有 type 时优先使用 URL 中的值")
    parser.add_argument("--max-items", type=int, default=80, help="最多输出多少条疑似题目/答案记录")
    parser.add_argument("--max-summary-questions", type=int, default=8, help="stdout 最多展示多少条结构化题目")
    parser.add_argument("--save-dir", default=DEFAULT_SAVE_DIR, help=f"保存原始响应和解析结果的目录，默认 {DEFAULT_SAVE_DIR}")
    parser.add_argument("--raw-response", action="store_true", help="输出完整原始响应和解析结果")
    parser.add_argument("--strict", action="store_true", help="题目或成绩接口失败时直接退出")

    parser.add_argument("--timeout", type=int, default=15, help="请求超时时间，默认 15 秒")
    parser.add_argument("--api-version", default="5.1.0", help="公共参数 v，默认 5.1.0")
    parser.add_argument("--osv", default="Android", help="公共参数 osv")
    parser.add_argument("--driver-code", default="5.2.7", help="公共参数 driverCode")
    parser.add_argument("--driver-type", default="demo", help="公共参数 driverType")
    parser.add_argument("--device-token", default="demo-device-token", help="公共参数 deviceToken")

    parser.set_defaults(task_type="exam", homework_only=False, raw=False)
    return parser.parse_args()


def main() -> int:
    args = fill_interactive_exam_args(fill_interactive_args(parse_args()))
    try:
        login_result = login_by_real_name(args)
        save_login_cache(args)
        uid = str(login_result["uid"])
        token = str(login_result["token"])

        exams = get_exam_list(uid, token, args)
        exam = select_exam(args, exams)
        self_id = exam_self_id(exam)
        if not self_id:
            raise RuntimeError(f"选中的考试缺少 self_id：{json.dumps(exam, ensure_ascii=False)}")
        if score_url(exam) and "basic" in str(score_url(exam)).lower():
            args.basic = True

        try:
            exam_item = {"ok": True, **get_exam_item(uid, token, args, self_id)}
        except Exception as exc:
            exam_item = {"ok": False, "path": EXAM_ITEM_PATH, "error": str(exc), "data": None}
            if args.strict:
                raise

        try:
            score_info = {"ok": True, **get_exam_score_info(uid, token, args, exam, self_id)}
        except Exception as exc:
            score_info = {"ok": False, "path": exam_score_path(args), "error": str(exc), "data": None}
            if args.strict:
                raise

        model_score_infos = get_model_score_infos(uid, token, args, score_info) if score_info.get("ok") else []
        main_report = parse_structured_exam_report(score_info.get("data"))
        model_reports = [parse_structured_exam_report(item.get("data")) for item in model_score_infos if item.get("ok")]
        structured_report = merge_structured_reports(main_report, model_reports)
        model_questions = parse_model_score_questions(model_score_infos)
        if model_questions:
            structured_report["questions"] = dedupe_questions(
                list(structured_report.get("questions") if isinstance(structured_report.get("questions"), list) else [])
                + model_questions
            )
            structured_report["answers_only"] = build_answers_only(structured_report["questions"])
            structured_report["question_count"] = len(structured_report["questions"])
        parsed_answers = parse_answer_records(
            {
                "exam_item": exam_item.get("data"),
                "score_info": score_info.get("data"),
                "model_score_infos": [item.get("data") for item in model_score_infos],
            },
            max_items=args.max_items,
        )
        answers_only = structured_report.get("answers_only")
        answers_only = answers_only if isinstance(answers_only, list) else []
        answers_by_question = parse_json_exam_answers({"model_score_infos": repair_mojibake(model_score_infos)})
        answers = build_json_answers_only(answers_by_question)
        if not answers:
            answers = build_answer_values(answers_only)
        result = {
            "exam": exam,
            "self_id": self_id,
            "model_id": exam_model_id(exam),
            "exam_item": exam_item,
            "score_info": score_info,
            "model_score_infos": model_score_infos,
            "structured_report": structured_report,
            "answers": answers,
            "answers_by_question": answers_by_question,
            "answers_only": answers_only,
            "parsed_answers": parsed_answers,
        }
    except Exception as exc:
        print(f"解析考试答案失败：{exc}", file=sys.stderr)
        return 1

    output_result(result, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
