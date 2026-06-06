#!/usr/bin/env python3
"""Homework detail/content/answer demo for Ekwing Student 5.2.7.

Usage:
    python homework_detail_answer_demo.py
    python homework_detail_answer_demo.py --name 张三 --password 123456 --school-name 某某学校 --school-id 12345
    python homework_detail_answer_demo.py --list-type finished --homework-index 0 --all-items --save-dir out_detail
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from demo import fill_interactive_args, login_by_real_name, save_login_cache
from homework_demo import (
    common_params,
    fill_interactive_homework_args,
    get_all_homework,
    get_all_exam_history,
    get_exam_history_page,
    get_homework_page,
    get_study_center_tasks,
    post_form,
    safe_int,
    summarize_exam_history_item,
    summarize_homework_item,
    summarize_task_item,
    STUDY_CENTER_TASK_TYPES,
)


HOMEWORK_ITEMS_PATH = "/student/Hw/getHwItems"
BASIC_HOMEWORK_ITEMS_PATH = "/student/Hw/getBasicHwItems"
SCORE_DETAIL_PATH = "/student/Hw/stuscoredetail"
BASIC_SCORE_DETAIL_PATH = "/student/Hw/stubasicscoredetail"
HW_DO_ITEM_PATH = "/student/Hw/hwdoitem"
HW_ANSWER_PATH = "/student/Hw/getHwAns"
HW_COUNT_PATH = "/student/Hw/gethwcnt"
HW_HISTORY_SCORE_PATH = "/student/Hw/jshistoryitemScore"
HW_RESULT_PATH = "/student/Hw/GetHwResult"


def homework_items_path(args: argparse.Namespace) -> str:
    return BASIC_HOMEWORK_ITEMS_PATH if args.basic else HOMEWORK_ITEMS_PATH


def score_detail_path(args: argparse.Namespace) -> str:
    return BASIC_SCORE_DETAIL_PATH if args.basic else SCORE_DETAIL_PATH


def get_homework_items_page(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
    page: int,
) -> dict[str, Any]:
    hid = homework_hid(homework)
    if not hid:
        raise RuntimeError(f"选中的作业缺少 hid/id：{json.dumps(homework, ensure_ascii=False)}")

    payload = common_params(args, uid, token)
    payload.update(
        {
            "hid": str(hid),
            "page": str(page),
            "archiveId": str(homework.get("archiveId") or ""),
        }
    )
    body = post_form(homework_items_path(args), payload, args.timeout)
    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"作业小项返回缺少 data 对象：{json.dumps(body, ensure_ascii=False)}")
    return data


def get_score_detail_page(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
    page: int,
) -> dict[str, Any]:
    hid = homework_hid(homework)
    if not hid:
        raise RuntimeError(f"选中的作业缺少 hid/id：{json.dumps(homework, ensure_ascii=False)}")

    payload = common_params(args, uid, token)
    payload.update(
        {
            "hid": str(hid),
            "page": str(page),
            "archiveId": str(homework.get("archiveId") or ""),
        }
    )
    if args.score_detail_training:
        payload.update(
            {
                "self_id": str(hid),
                "is_exercise": args.is_exercise,
            }
        )

    body = post_form(score_detail_path(args), payload, args.timeout)
    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"成绩详情返回缺少 data 对象：{json.dumps(body, ensure_ascii=False)}")
    return data


def get_all_homework_items(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
) -> dict[str, Any]:
    first = get_homework_items_page(uid, token, args, homework, page=1)
    items = list(first.get("list") or [])
    page_info = first.get("page") or {}
    current = safe_int(page_info.get("currentPage"), 1)
    total = safe_int(page_info.get("totalPage"), current)

    while current < total:
        current += 1
        page_data = get_homework_items_page(uid, token, args, homework, page=current)
        next_items = page_data.get("list") or []
        items.extend(next_items)
        page_info = page_data.get("page") or page_info
        total = safe_int(page_info.get("totalPage"), total)
        if not next_items:
            break

    return {
        **first,
        "list": items,
        "page": {
            **page_info,
            "currentPage": current,
            "loadedCount": len(items),
        },
    }


def get_all_score_detail_items(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
) -> dict[str, Any]:
    first = get_score_detail_page(uid, token, args, homework, page=1)
    items = list(first.get("list") or [])
    page_info = first.get("page") or {}
    current = safe_int(page_info.get("currentPage"), 1)
    total = safe_int(page_info.get("totalPage"), current)

    while current < total:
        current += 1
        page_data = get_score_detail_page(uid, token, args, homework, page=current)
        next_items = page_data.get("list") or []
        items.extend(next_items)
        page_info = page_data.get("page") or page_info
        total = safe_int(page_info.get("totalPage"), total)
        if not next_items:
            break

    return {
        **first,
        "list": items,
        "page": {
            **page_info,
            "currentPage": current,
            "loadedCount": len(items),
        },
    }


def get_detail_items_with_fallback(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    if is_exam_task(homework):
        return get_exam_detail(homework), "study-center-exam-url"

    errors: list[str] = []

    if args.detail_api in {"items", "auto"}:
        try:
            return get_all_homework_items(uid, token, args, homework), homework_items_path(args)
        except Exception as exc:
            errors.append(f"{homework_items_path(args)}：{exc}")
            if args.detail_api == "items":
                raise RuntimeError("；".join(errors)) from exc

    if args.detail_api in {"score", "auto"}:
        try:
            return get_all_score_detail_items(uid, token, args, homework), score_detail_path(args)
        except Exception as exc:
            errors.append(f"{score_detail_path(args)}：{exc}")
            raise RuntimeError("；".join(errors)) from exc

    raise RuntimeError(f"未知详情接口模式：{args.detail_api}")


def get_hw_do_item(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    payload = common_params(args, uid, token)
    payload.update(
        {
            "hid": str(item.get("hid") or homework_hid(homework)),
            "hwcid": str(item.get("id") or ""),
            "method": args.content_method,
            "is_exercise": args.is_exercise,
            "archiveId": str(homework.get("archiveId") or ""),
        }
    )
    body = post_form(HW_DO_ITEM_PATH, payload, args.timeout)
    return {"path": HW_DO_ITEM_PATH, "payload": payload, "data": body.get("data")}


def with_query_defaults(url: str, defaults: dict[str, str]) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in defaults.items():
        query.setdefault(key, value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def get_item_page(
    uid: str,
    token: str,
    args: argparse.Namespace,
    item: dict[str, Any],
) -> dict[str, Any]:
    url = item.get("url")
    if not url:
        raise RuntimeError("作业小项没有 url，无法用页面方式读取题目内容")

    url = with_query_defaults(str(url), common_params(args, uid, token))
    response = requests.get(
        url,
        timeout=args.timeout,
        headers={
            "User-Agent": args.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    text = response.text

    data: Any = text
    if "json" in content_type.lower():
        try:
            data = response.json()
        except ValueError:
            data = text

    return {
        "path": url,
        "payload": {},
        "content_type": content_type,
        "data": data,
    }


def is_exam_task(homework: dict[str, Any]) -> bool:
    return homework.get("type") == "exam" or bool(homework.get("self_id") or homework.get("last_model_id"))


def get_exam_detail(homework: dict[str, Any]) -> dict[str, Any]:
    exam_url = homework.get("url") or homework.get("start_url") or build_exam_history_url(homework)
    if not exam_url:
        raise RuntimeError(f"选中的考试缺少 url：{json.dumps(homework, ensure_ascii=False)}")
    return {
        "info": homework,
        "page": {"currentPage": 1, "totalPage": 1, "loadedCount": 1},
        "list": [
            {
                "id": homework_hid(homework),
                "hid": homework_hid(homework),
                "type": homework.get("type"),
                "type_name": "考试",
                "record_id": homework.get("record_id"),
                "url": exam_url,
            }
        ],
    }


def build_exam_history_url(homework: dict[str, Any]) -> str | None:
    self_id = homework.get("self_id") or homework.get("id")
    model_id = homework.get("last_model_id") or homework.get("model_id")
    if not self_id or not model_id:
        return None
    query = {
        "self_id": str(self_id),
        "model_id": str(model_id),
        "self_mode_type": str(homework.get("mode_type") or "1"),
    }
    return "https://mapi.ekwing.com/student/exam/loadexamtest?" + urlencode(query)


def get_hw_answer(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    payload = common_params(args, uid, token)
    payload.update(
        {
            "hid": str(item.get("hid") or homework_hid(homework)),
            "hwcid": str(item.get("id") or ""),
            "method": args.answer_method,
            "archiveId": str(homework.get("archiveId") or ""),
        }
    )
    body = post_form(HW_ANSWER_PATH, payload, args.timeout)
    return {"path": HW_ANSWER_PATH, "payload": payload, "data": body.get("data")}


def get_hw_count_or_answer(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    payload = common_params(args, uid, token)
    payload.update(
        {
            "hid": str(item.get("hid") or homework_hid(homework)),
            "hwcid": str(item.get("id") or ""),
            "archiveId": str(homework.get("archiveId") or ""),
            "is_exercise": args.is_exercise,
        }
    )
    body = post_form(HW_COUNT_PATH, payload, args.timeout)
    return {"path": HW_COUNT_PATH, "payload": payload, "data": body.get("data")}


def get_hw_history_score(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    payload = common_params(args, uid, token)
    payload.update(
        {
            "hid": str(item.get("hid") or homework_hid(homework)),
            "hwcid": str(item.get("id") or ""),
            "archiveId": str(homework.get("archiveId") or ""),
            "is_exercise": args.is_exercise,
        }
    )
    if args.history_method:
        payload["method"] = args.history_method
    body = post_form(HW_HISTORY_SCORE_PATH, payload, args.timeout)
    return {"path": HW_HISTORY_SCORE_PATH, "payload": payload, "data": body.get("data")}


def get_hw_result(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    payload = common_params(args, uid, token)
    payload.update(
        {
            "hid": str(item.get("hid") or homework_hid(homework)),
            "hwcid": str(item.get("id") or ""),
            "archiveId": str(homework.get("archiveId") or ""),
            "is_exercise": args.is_exercise,
        }
    )
    body = post_form(HW_RESULT_PATH, payload, args.timeout)
    return {"path": HW_RESULT_PATH, "payload": payload, "data": body.get("data")}


def fetch_answer_bundle(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    fetchers = {
        "getHwAns": get_hw_answer,
        "gethwcnt": get_hw_count_or_answer,
        "jshistoryitemScore": get_hw_history_score,
        "GetHwResult": get_hw_result,
    }

    result: dict[str, Any] = {}
    for api_name in args.answer_api:
        fetcher = fetchers[api_name]
        try:
            result[api_name] = {"ok": True, **fetcher(uid, token, args, homework, item)}
        except Exception as exc:
            result[api_name] = {"ok": False, "error": str(exc)}
            if args.strict_answer:
                raise
    return result


def fetch_item_bundle(
    uid: str,
    token: str,
    args: argparse.Namespace,
    homework: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "item": item,
        "item_summary": summarize_detail_item(item),
    }

    if is_exam_task(homework):
        bundle["content"] = {"ok": True, "fallback": True, **get_item_page(uid, token, args, item)}
        bundle["answers"] = {}
        return bundle

    content_errors: list[str] = []
    try:
        bundle["content"] = {"ok": True, **get_hw_do_item(uid, token, args, homework, item)}
    except Exception as exc:
        content_errors.append(f"{HW_DO_ITEM_PATH}：{exc}")
        if args.strict_content or not args.content_url_fallback:
            raise
        try:
            bundle["content"] = {"ok": True, "fallback": True, **get_item_page(uid, token, args, item)}
        except Exception as page_exc:
            content_errors.append(f"item.url：{page_exc}")
            bundle["content"] = {"ok": False, "error": "；".join(content_errors)}
            if args.strict_content:
                raise

    bundle["answers"] = fetch_answer_bundle(uid, token, args, homework, item)
    return bundle


def get_homework_list(uid: str, token: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.list_type == "study-center":
        items = get_study_center_tasks(uid, token, args)
    elif args.list_type == "study-center-history":
        if args.all_pages:
            items = get_all_exam_history(uid, token, args).get("list") or []
        else:
            items = get_exam_history_page(uid, token, args, page=args.page).get("list") or []
    elif args.all_pages:
        items = get_all_homework(uid, token, args).get("list") or []
    else:
        items = get_homework_page(uid, token, args, page=args.page).get("list") or []

    homework_items = [item for item in items if isinstance(item, dict)]
    return homework_items


def homework_hid(homework: dict[str, Any]) -> Any:
    return homework.get("hid") or homework.get("id")


def select_item_interactively(
    label: str,
    items: list[dict[str, Any]],
    summarizer: Any,
) -> int:
    if not items:
        raise RuntimeError(f"{label}列表为空")

    print(f"请选择{label}：", file=sys.stderr)
    for index, item in enumerate(items):
        print(f"[{index}] {json.dumps(summarizer(item), ensure_ascii=False)}", file=sys.stderr)

    while True:
        raw = input(f"请输入 0..{len(items) - 1}：").strip()
        try:
            selected_index = int(raw)
        except ValueError:
            print("请输入数字序号。", file=sys.stderr)
            continue
        if 0 <= selected_index < len(items):
            return selected_index
        print("序号超出范围。", file=sys.stderr)


def selected_homework_index(args: argparse.Namespace, homework_items: list[dict[str, Any]]) -> int:
    if args.hid:
        for index, item in enumerate(homework_items):
            if str(homework_hid(item)) == args.hid:
                return index
        raise RuntimeError(f"作业列表中没有找到 hid/id={args.hid}")

    if args.homework_index is not None:
        if 0 <= args.homework_index < len(homework_items):
            return args.homework_index
        raise RuntimeError(f"--homework-index 超出范围：0..{len(homework_items) - 1}")

    if args.list_type == "study-center-history":
        summarizer = summarize_exam_history_item
    else:
        summarizer = summarize_task_item if args.list_type == "study-center" else summarize_homework_item
    label = "考试" if args.list_type in {"study-center", "study-center-history"} and args.task_type == "exam" else "作业"
    return select_item_interactively(label, homework_items, summarizer)


def selected_detail_items(args: argparse.Namespace, detail_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if args.all_items:
        return detail_items

    if args.item_id:
        for item in detail_items:
            if str(item.get("id")) == args.item_id:
                return [item]
        raise RuntimeError(f"作业小项列表中没有找到 id={args.item_id}")

    if args.item_index is not None:
        if 0 <= args.item_index < len(detail_items):
            return [detail_items[args.item_index]]
        raise RuntimeError(f"--item-index 超出范围：0..{len(detail_items) - 1}")

    selected_index = select_item_interactively("作业小项", detail_items, summarize_detail_item)
    return [detail_items[selected_index]]


def summarize_detail_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "hid": item.get("hid"),
        "type_name": item.get("type_name"),
        "type": item.get("type"),
        "tk_biz": item.get("tk_biz"),
        "finish": item.get("finish"),
        "score": item.get("score"),
        "num": item.get("num"),
        "unit_id": item.get("unit_id"),
        "record_id": item.get("record_id"),
        "url": item.get("url"),
    }


def preview_value(value: Any, limit: int = 500) -> Any:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    if len(text) <= limit:
        return value
    return text[:limit] + "...(truncated)"


def parse_json_text(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def summarize_answer_data(value: Any) -> dict[str, Any]:
    parsed = parse_json_text(value)
    if not isinstance(parsed, dict):
        return {"preview": preview_value(parsed)}

    ans = parsed.get("ans")
    if not isinstance(ans, dict):
        return {"keys": list(parsed.keys()), "preview": preview_value(parsed)}

    answers = ans.get("answers")
    answer_items = answers if isinstance(answers, list) else []
    return {
        "hw_id": ans.get("hw_id"),
        "hw_cnt_id": ans.get("hw_cnt_id"),
        "study_part_id": ans.get("study_part_id"),
        "txt": ans.get("txt"),
        "answer_count": len(answer_items),
        "answers_preview": [
            summarize_single_answer(item)
            for item in answer_items[:5]
            if isinstance(item, dict)
        ],
    }


def summarize_single_answer(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "score": item.get("score") or item.get("total_score"),
        "text": item.get("text") or item.get("txt") or item.get("word") or item.get("sentence"),
        "audio": item.get("audio"),
        "accuracy": item.get("accuracy"),
        "fluency": item.get("fluency"),
        "integrity": item.get("integrity"),
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def output_result(result: dict[str, Any], args: argparse.Namespace) -> None:
    if args.save_dir:
        save_dir = Path(args.save_dir)
        write_json(save_dir / "homework.json", result["homework"])
        write_json(save_dir / "detail_items.json", result["detail_items"])
        for index, item_result in enumerate(result["selected_item_results"]):
            item_id = item_result.get("item", {}).get("id") or index
            write_json(save_dir / f"item_{index}_{item_id}.json", item_result)
        print(f"原始 JSON 已保存到：{save_dir}", file=sys.stderr)

    if args.raw_detail:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    summary = {
        "homework": result["homework_summary"],
        "detail_source": result.get("detail_source"),
        "detail_count": len(result["detail_items"]),
        "selected_items": [],
    }
    for item_result in result["selected_item_results"]:
        content = item_result.get("content") or {}
        answers = item_result.get("answers") or {}
        summary["selected_items"].append(
            {
                "item": item_result.get("item_summary"),
                "content_ok": content.get("ok"),
                "content_source": content.get("path"),
                "content_fallback": content.get("fallback", False),
                "content_error": content.get("error"),
                "content_preview": preview_value(content.get("data")),
                "answers": {
                    key: {
                        "ok": value.get("ok"),
                        "summary": summarize_answer_data(value.get("data")) if value.get("ok") else None,
                        "preview": preview_value(value.get("data") if value.get("ok") else value.get("error")),
                    }
                    for key, value in answers.items()
                },
            }
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="翼课学生 5.2.7 读取题目内容和答案 demo")

    parser.add_argument("--name", help="学生姓名，对应 nicename；不传则交互式输入")
    parser.add_argument("--school-name", help="学校名称，对应 schoolName；不传则交互式输入")
    parser.add_argument("--school-id", help="学校 ID，对应 schoolId；不传则交互式输入")
    parser.add_argument("--password", help="明文密码；不传则交互式输入")
    parser.add_argument("--choose-index", type=int, help="同名账号分支选择序号；不传则交互选择")

    parser.add_argument(
        "--list-type",
        choices=("current", "finished", "study-center", "study-center-history"),
        default=None,
        help="复用 homework_demo.py 的列表类型；study-center-history 为历史学习中心考试任务；不传则交互选择",
    )
    parser.add_argument("--page", type=int, default=None, help="作业分页页码；不传则交互输入")
    parser.add_argument(
        "--all-pages",
        action="store_true",
        default=None,
        help="拉取全部作业分页；仅 current/finished 生效；不传则交互选择",
    )
    parser.add_argument(
        "--basic",
        action="store_true",
        default=None,
        help="使用 Basic 账号接口；不传则交互选择",
    )
    parser.add_argument(
        "--homework-only",
        action="store_true",
        default=None,
        help="兼容旧参数：study-center 只保留 type=hw 的作业项；默认改为只保留 type=exam",
    )
    parser.add_argument(
        "--task-type",
        choices=STUDY_CENTER_TASK_TYPES,
        default="exam",
        help="study-center 保留的任务类型，默认 exam；可选 hw/train/all 用于手动排查",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        default=False,
        help="保留给 homework_demo.py 兼容；本脚本不会用它打印作业列表",
    )

    parser.add_argument("--hid", help="直接选择指定 hid/id 的作业")
    parser.add_argument("--homework-index", type=int, help="选择作业列表中的序号，从 0 开始")
    parser.add_argument("--item-id", help="直接选择指定 id 的作业小项")
    parser.add_argument("--item-index", type=int, help="选择作业小项列表中的序号，从 0 开始")
    parser.add_argument("--all-items", action="store_true", help="读取选中作业下所有小项")

    parser.add_argument(
        "--detail-api",
        choices=("auto", "items", "score"),
        default="auto",
        help="作业小项来源：auto 先试 getHwItems，失败后试 score detail；items 只用 getHwItems；score 只用 score detail",
    )
    parser.add_argument(
        "--score-detail-training",
        action="store_true",
        help="请求 score detail 时额外带 self_id 和 is_exercise，用于训练模式尝试",
    )
    parser.add_argument("--content-method", default="last", help="hwdoitem 的 method，默认 last")
    parser.add_argument(
        "--no-content-url-fallback",
        action="store_false",
        dest="content_url_fallback",
        help="hwdoitem 失败时不再尝试作业小项 url",
    )
    parser.add_argument("--is-exercise", default="0", choices=("0", "1"), help="is_exercise，默认 0")
    parser.add_argument("--answer-method", default="LAST", choices=("LAST", "MAX"), help="getHwAns 的 method，默认 LAST")
    parser.add_argument(
        "--answer-api",
        action="append",
        choices=("getHwAns", "gethwcnt", "jshistoryitemScore", "GetHwResult"),
        help="要请求的答案/结果接口；可重复传。默认请求 getHwAns 和 gethwcnt",
    )
    parser.add_argument("--history-method", default="last", help="jshistoryitemScore 的 method；传空字符串则不带 method")
    parser.add_argument("--strict-content", action="store_true", help="题目内容接口失败时直接退出")
    parser.add_argument("--strict-answer", action="store_true", help="任一答案接口失败时直接退出")
    parser.add_argument("--save-dir", help="保存作业、小项、题目内容和答案原始 JSON 的目录")
    parser.add_argument("--raw-detail", action="store_true", help="向 stdout 输出完整结果 JSON")

    parser.add_argument("--timeout", type=int, default=15, help="请求超时时间，默认 15 秒")
    parser.add_argument("--api-version", default="5.1.0", help="公共参数 v，默认 5.1.0")
    parser.add_argument("--osv", default="Android", help="公共参数 osv")
    parser.add_argument("--driver-code", default="5.2.7", help="公共参数 driverCode")
    parser.add_argument("--driver-type", default="demo", help="公共参数 driverType")
    parser.add_argument("--device-token", default="demo-device-token", help="公共参数 deviceToken")
    parser.add_argument(
        "--user-agent",
        default="Mozilla/5.0 (Linux; Android 10; demo) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Mobile Safari/537.36 EkwingStudent/5.2.7",
        help="请求作业页面 url 时使用的 User-Agent",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.answer_api = args.answer_api or ["getHwAns", "gethwcnt"]

    try:
        args = fill_interactive_homework_args(fill_interactive_args(args))
        login_result = login_by_real_name(args)
        save_login_cache(args)
        uid = str(login_result["uid"])
        token = str(login_result["token"])

        homework_items = get_homework_list(uid, token, args)
        homework_index = selected_homework_index(args, homework_items)
        homework = homework_items[homework_index]

        detail, detail_source = get_detail_items_with_fallback(uid, token, args, homework)
        detail_items = [item for item in detail.get("list") or [] if isinstance(item, dict)]
        selected_items = selected_detail_items(args, detail_items)

        selected_item_results = [
            fetch_item_bundle(uid, token, args, homework, item)
            for item in selected_items
        ]

        if args.list_type == "study-center-history":
            homework_summarizer = summarize_exam_history_item
        else:
            homework_summarizer = summarize_task_item if args.list_type == "study-center" else summarize_homework_item
        result = {
            "homework": homework,
            "homework_summary": homework_summarizer(homework),
            "detail_source": detail_source,
            "detail": detail,
            "detail_items": detail_items,
            "selected_item_results": selected_item_results,
        }
    except Exception as exc:
        print(f"读取题目内容和答案失败：{exc}", file=sys.stderr)
        return 1

    output_result(result, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
