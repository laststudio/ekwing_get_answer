#!/usr/bin/env python3
"""Homework list demo for Ekwing Student 5.2.7.

Usage:
    python homework_demo.py
    python homework_demo.py --name 张三 --password 123456 --school-name 某某学校 --school-id 12345
    python homework_demo.py --list-type finished --all-pages
    python homework_demo.py --list-type study-center --task-type exam
    python homework_demo.py --list-type study-center-history
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - only used when dependency is missing
    print("缺少 requests 依赖，请先执行：python -m pip install requests", file=sys.stderr)
    raise

from demo import fill_interactive_args, login_by_real_name, save_login_cache


BASE_URL = "https://mapi.ekwing.com"
HOMEWORK_LIST_PATH = "/student/Hw/getList"
BASIC_HOMEWORK_LIST_PATH = "/student/Hw/getBasicList"
STUDY_CENTER_PATH = "/student/Hw/getnewmainlist"
BASIC_STUDY_CENTER_PATH = "/student/Hw/getbasicnewmainlist"
EXAM_HISTORY_PATH = "/student/exam/getstuexamlist"
BASIC_EXAM_HISTORY_PATH = "/student/exam/getstubasicexamlist"
STUDY_CENTER_TASK_TYPES = ("exam", "hw", "train", "all")


def common_params(args: argparse.Namespace, uid: str, token: str) -> dict[str, str]:
    return {
        "v": args.api_version,
        "is_http": "1",
        "os": "Android",
        "client": "student",
        "up_version": "1.0",
        "osv": args.osv,
        "driverCode": args.driver_code,
        "driverType": args.driver_type,
        "deviceToken": args.device_token,
        "uid": uid,
        "author_id": uid,
        "token": token,
    }


def error_message(body: dict[str, Any]) -> str:
    data = body.get("data")
    if isinstance(data, dict):
        return (
            data.get("msg")
            or data.get("error_msg")
            or data.get("errlog")
            or json.dumps(data, ensure_ascii=False)
        )
    return json.dumps(body, ensure_ascii=False)


def post_form(path: str, data: dict[str, str], timeout: int) -> dict[str, Any]:
    response = requests.post(f"{BASE_URL}{path}", data=data, timeout=timeout)
    response.raise_for_status()
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError(f"接口返回不是 JSON：{response.text[:300]}") from exc

    if body.get("status") != 0:
        raise RuntimeError(error_message(body))
    return body


def homework_list_path(args: argparse.Namespace) -> str:
    return BASIC_HOMEWORK_LIST_PATH if args.basic else HOMEWORK_LIST_PATH


def study_center_path(args: argparse.Namespace) -> str:
    return BASIC_STUDY_CENTER_PATH if args.basic else STUDY_CENTER_PATH


def exam_history_path(args: argparse.Namespace) -> str:
    return BASIC_EXAM_HISTORY_PATH if args.basic else EXAM_HISTORY_PATH


def get_homework_page(
    uid: str,
    token: str,
    args: argparse.Namespace,
    page: int,
    archive_id: str | None = None,
) -> dict[str, Any]:
    if args.list_type == "finished":
        method = "finish"
        sort_field = "finish_times"
    else:
        method = "new"
        sort_field = "publish_times"

    payload = common_params(args, uid, token)
    payload.update(
        {
            "method": method,
            "page": str(page),
            "sortMethod": "desc",
            "sortField": sort_field,
        }
    )
    if archive_id:
        payload["archiveId"] = archive_id

    body = post_form(homework_list_path(args), payload, args.timeout)
    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"作业列表返回缺少 data 对象：{json.dumps(body, ensure_ascii=False)}")
    return data


def get_all_homework(uid: str, token: str, args: argparse.Namespace) -> dict[str, Any]:
    first = get_homework_page(uid, token, args, page=args.page)
    items = list(first.get("list") or [])
    page_info = first.get("page") or {}
    current = safe_int(page_info.get("currentPage"), args.page)
    total = safe_int(page_info.get("totalPage"), current)

    while current < total and items:
        archive_id = last_archive_id(items)
        current += 1
        page_data = get_homework_page(uid, token, args, page=current, archive_id=archive_id)
        next_items = page_data.get("list") or []
        items.extend(next_items)
        page_info = page_data.get("page") or page_info
        total = safe_int(page_info.get("totalPage"), total)

    return {
        "list": items,
        "page": {
            **page_info,
            "currentPage": current,
            "loadedCount": len(items),
        },
    }


def get_study_center_tasks(uid: str, token: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    body = post_form(study_center_path(args), common_params(args, uid, token), args.timeout)
    data = body.get("data")
    if not isinstance(data, list):
        raise RuntimeError(f"学习中心返回 data 不是列表：{json.dumps(body, ensure_ascii=False)}")

    items = [item for item in data if isinstance(item, dict)]
    task_type = getattr(args, "task_type", "exam") or "exam"
    if getattr(args, "homework_only", False):
        task_type = "hw"
    if task_type != "all":
        items = [item for item in items if item.get("type") == task_type]
    return items


def get_exam_history_page(
    uid: str,
    token: str,
    args: argparse.Namespace,
    page: int,
    archive_id: str | None = None,
) -> dict[str, Any]:
    payload = common_params(args, uid, token)
    payload.update(
        {
            "type": "his",
            "page": str(page),
        }
    )
    if archive_id:
        payload["archiveId"] = archive_id

    body = post_form(exam_history_path(args), payload, args.timeout)
    data = body.get("data")
    if isinstance(data, list):
        return {"list": data, "page": {"currentPage": page, "totalPage": page}}
    if isinstance(data, dict):
        return normalize_exam_history_data(data, page)
    raise RuntimeError(f"历史考试返回缺少 data 对象：{json.dumps(body, ensure_ascii=False)}")


def normalize_exam_history_data(data: dict[str, Any], page: int) -> dict[str, Any]:
    items = data.get("list")
    if not isinstance(items, list):
        for value in data.values():
            if isinstance(value, list):
                items = value
                break
    items = items if isinstance(items, list) else []

    current = safe_int(data.get("page") or data.get("currentPage"), page)
    total = safe_int(data.get("total_page") or data.get("totalPage"), current)
    return {
        "list": items,
        "page": {
            **{key: value for key, value in data.items() if key != "list"},
            "currentPage": current,
            "totalPage": total,
        },
    }


def get_all_exam_history(uid: str, token: str, args: argparse.Namespace) -> dict[str, Any]:
    first = get_exam_history_page(uid, token, args, page=args.page)
    items = list(first.get("list") or [])
    page_info = first.get("page") or {}
    current = safe_int(page_info.get("currentPage"), args.page)
    total = safe_int(page_info.get("totalPage"), current)

    while current < total:
        archive_id = last_archive_id(items)
        current += 1
        page_data = get_exam_history_page(uid, token, args, page=current, archive_id=archive_id)
        next_items = page_data.get("list") or []
        items.extend(next_items)
        page_info = page_data.get("page") or page_info
        total = safe_int(page_info.get("totalPage"), total)
        if not next_items:
            break

    return {
        "list": items,
        "page": {
            **page_info,
            "currentPage": current,
            "loadedCount": len(items),
        },
    }


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def last_archive_id(items: list[Any]) -> str | None:
    for item in reversed(items):
        if isinstance(item, dict) and item.get("archiveId"):
            return str(item["archiveId"])
    return None


def summarize_homework_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "hid": item.get("hid"),
        "title": item.get("title"),
        "book_name": item.get("book_name"),
        "status": item.get("status"),
        "finish": item.get("finish"),
        "score": item.get("score"),
        "cntTotal": item.get("cntTotal"),
        "finishCntNum": item.get("finishCntNum"),
        "end_time": item.get("end_time"),
        "archiveId": item.get("archiveId"),
        "record_id": item.get("record_id"),
    }


def summarize_task_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "type": item.get("type"),
        "title": item.get("title"),
        "status": item.get("status"),
        "book_name": item.get("book_name"),
        "end_time": item.get("end_time"),
        "archiveId": item.get("archiveId"),
        "record_id": item.get("record_id"),
        "url": item.get("url") or item.get("start_url"),
    }


def summarize_exam_history_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "type": item.get("type", "exam"),
        "title": item.get("title") or item.get("self_title"),
        "status": item.get("status") or item.get("self_status"),
        "score": item.get("score") or item.get("self_score"),
        "start_time": item.get("start_time") or item.get("self_start_time"),
        "end_time": item.get("end_time") or item.get("self_end_time"),
        "archiveId": item.get("archiveId"),
        "self_id": item.get("self_id"),
        "last_model_id": item.get("last_model_id"),
        "mode_type": item.get("mode_type"),
        "url": item.get("url") or item.get("start_url"),
    }


def print_result(result: Any, args: argparse.Namespace) -> None:
    if args.raw:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if isinstance(result, dict):
        items = [item for item in result.get("list") or [] if isinstance(item, dict)]
        page = result.get("page") or {}
        item_name = "历史学习中心考试" if args.list_type == "study-center-history" else "作业"
        summarizer = summarize_exam_history_item if args.list_type == "study-center-history" else summarize_homework_item
        print(f"共获取 {len(items)} 条{item_name}")
        print(json.dumps({"page": page}, ensure_ascii=False, indent=2))
        print(json.dumps([summarizer(item) for item in items], ensure_ascii=False, indent=2))
        return

    if isinstance(result, list):
        print(f"共获取 {len(result)} 条学习中心任务")
        print(json.dumps([summarize_task_item(item) for item in result], ensure_ascii=False, indent=2))


def prompt_choice(label: str, choices: list[tuple[str, str]]) -> str:
    print(label)
    for index, (_, text) in enumerate(choices, start=1):
        print(f"[{index}] {text}")

    while True:
        raw = input(f"请输入 1..{len(choices)}：").strip()
        try:
            selected_index = int(raw)
        except ValueError:
            print("请输入数字序号。", file=sys.stderr)
            continue
        if 1 <= selected_index <= len(choices):
            return choices[selected_index - 1][0]
        print("序号超出范围。", file=sys.stderr)


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


def prompt_int(label: str, default: int = 1, minimum: int = 1) -> int:
    while True:
        raw = input(f"{label}（默认 {default}）：").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("请输入数字。", file=sys.stderr)
            continue
        if value >= minimum:
            return value
        print(f"请输入不小于 {minimum} 的数字。", file=sys.stderr)


def fill_interactive_homework_args(args: argparse.Namespace) -> argparse.Namespace:
    if args.list_type is None:
        args.list_type = prompt_choice(
            "请选择要获取的列表：",
            [
                ("current", "当前/未完成作业"),
                ("finished", "历史/已完成作业"),
                ("study-center", "当前学习中心考试任务"),
                ("study-center-history", "历史学习中心考试任务"),
            ],
        )

    if args.basic is None:
        args.basic = prompt_yes_no("是否使用 Basic 账号接口", default=False)

    if args.raw is None:
        args.raw = prompt_yes_no("是否输出接口原始 data", default=False)

    if args.list_type in {"study-center", "study-center-history"}:
        args.task_type = getattr(args, "task_type", "exam") or "exam"
        args.homework_only = False if args.homework_only is None else args.homework_only
        args.page = 1 if args.page is None else args.page
        if args.all_pages is None:
            args.all_pages = False
        return args

    if args.page is None:
        args.page = prompt_int("请输入起始页码", default=1, minimum=1)
    if args.all_pages is None:
        args.all_pages = prompt_yes_no("是否拉取全部分页", default=False)
    args.homework_only = False if args.homework_only is None else args.homework_only
    return args


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="翼课学生 5.2.7 登录后获取作业列表 demo")

    parser.add_argument("--name", help="学生姓名，对应 nicename；不传则交互式输入")
    parser.add_argument("--school-name", help="学校名称，对应 schoolName；不传则交互式输入")
    parser.add_argument("--school-id", help="学校 ID，对应 schoolId；不传则交互式输入")
    parser.add_argument("--password", help="明文密码；不传则交互式输入")
    parser.add_argument("--choose-index", type=int, help="同名账号分支选择序号；不传则交互选择")

    parser.add_argument(
        "--list-type",
        choices=("current", "finished", "study-center", "study-center-history"),
        default=None,
        help="列表类型：study-center-history 为历史学习中心考试任务；不传则交互选择",
    )
    parser.add_argument("--page", type=int, default=None, help="作业分页页码；不传则交互输入")
    parser.add_argument(
        "--all-pages",
        action="store_true",
        default=None,
        help="拉取全部分页；current/finished/study-center-history 生效；不传则交互选择",
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
        default=None,
        help="输出接口原始 data，不做字段摘要；不传则交互选择",
    )

    parser.add_argument("--timeout", type=int, default=15, help="请求超时时间，默认 15 秒")
    parser.add_argument("--api-version", default="5.1.0", help="公共参数 v，默认 5.1.0")
    parser.add_argument("--osv", default="Android", help="公共参数 osv")
    parser.add_argument("--driver-code", default="5.2.7", help="公共参数 driverCode")
    parser.add_argument("--driver-type", default="demo", help="公共参数 driverType")
    parser.add_argument("--device-token", default="demo-device-token", help="公共参数 deviceToken")
    return parser.parse_args()


def main() -> int:
    args = fill_interactive_homework_args(fill_interactive_args(parse_args()))
    try:
        login_result = login_by_real_name(args)
        save_login_cache(args)
        uid = str(login_result["uid"])
        token = str(login_result["token"])

        if args.list_type == "study-center":
            result = get_study_center_tasks(uid, token, args)
        elif args.list_type == "study-center-history":
            result = get_all_exam_history(uid, token, args) if args.all_pages else get_exam_history_page(uid, token, args, page=args.page)
        elif args.all_pages:
            result = get_all_homework(uid, token, args)
        else:
            result = get_homework_page(uid, token, args, page=args.page)
    except Exception as exc:
        print(f"获取作业列表失败：{exc}", file=sys.stderr)
        return 1

    print_result(result, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
