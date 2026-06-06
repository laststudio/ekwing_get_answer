#!/usr/bin/env python3
"""Real-name login demo for Ekwing Student 5.2.7.

Usage:
    python demo.py
    python demo.py --name 张三 --password 123456 --school-name 某某学校 --school-id 12345
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - only used when dependency is missing
    print("缺少 requests 依赖，请先执行：python -m pip install requests", file=sys.stderr)
    raise


BASE_URL = "https://mapi.ekwing.com"
LOGIN_SCHOOL_PATH = "/student/User/loginschool"
LOGIN_ACCOUNT_PATH = "/student/User/login"
LOGIN_CACHE_PATH = Path(__file__).with_name(".ekwing_login_cache.json")
LOGIN_CACHE_KEYS = ("name", "school_name", "school_id", "choose_index")


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest().lower()


def common_params(args: argparse.Namespace) -> dict[str, str]:
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
    }


def post_form(path: str, data: dict[str, str], timeout: int) -> dict[str, Any]:
    response = requests.post(f"{BASE_URL}{path}", data=data, timeout=timeout)
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"接口返回不是 JSON：{response.text[:300]}") from exc


def error_state(data: dict[str, Any]) -> Any:
    return data.get("state", data.get("intent", data.get("intend")))


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


def normalize_login_result(body: dict[str, Any]) -> dict[str, Any]:
    if body.get("status") != 0:
        raise RuntimeError(error_message(body))

    user = body.get("data")
    if not isinstance(user, dict):
        raise RuntimeError(f"登录成功返回缺少 data：{json.dumps(body, ensure_ascii=False)}")

    uid = user.get("uid")
    token = user.get("token")
    if not uid or not token:
        raise RuntimeError(f"登录成功返回缺少 uid/token：{json.dumps(body, ensure_ascii=False)}")

    return {
        "uid": uid,
        "token": token,
        "userType": user.get("userType"),
    }


def login_by_account(
    username: str,
    pwd_md5: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    payload = common_params(args)
    payload.update(
        {
            "username": username,
            "password": pwd_md5,
        }
    )
    body = post_form(LOGIN_ACCOUNT_PATH, payload, args.timeout)
    return normalize_login_result(body)


def choose_overname(overname: list[dict[str, Any]], choose_index: int | None) -> dict[str, Any]:
    if not overname:
        raise RuntimeError("实名登录返回同名分支，但 overname 为空")

    if choose_index is not None:
        if choose_index < 0 or choose_index >= len(overname):
            raise RuntimeError(f"--choose-index 超出范围：0..{len(overname) - 1}")
        return overname[choose_index]

    print("实名登录匹配到多个账号，请选择：", file=sys.stderr)
    for index, item in enumerate(overname):
        username = item.get("username", "")
        classname = item.get("classname", "")
        user_type = item.get("type", "")
        uid = item.get("uid", "")
        print(
            f"[{index}] username={username} uid={uid} type={user_type} classname={classname}",
            file=sys.stderr,
        )

    while True:
        raw = input(f"请输入序号 0..{len(overname) - 1}：").strip()
        try:
            selected_index = int(raw)
        except ValueError:
            print("请输入数字序号。", file=sys.stderr)
            continue
        if 0 <= selected_index < len(overname):
            return overname[selected_index]
        print("序号超出范围。", file=sys.stderr)


def login_by_real_name(args: argparse.Namespace) -> dict[str, Any]:
    password = args.password or getpass.getpass("密码：")
    pwd_md5 = md5_hex(password)

    payload = common_params(args)
    payload.update(
        {
            "nicename": args.name,
            "pwd": pwd_md5,
            "schoolName": args.school_name,
            "schoolId": args.school_id,
        }
    )

    body = post_form(LOGIN_SCHOOL_PATH, payload, args.timeout)
    if body.get("status") == 0:
        return normalize_login_result(body)

    data = body.get("data") or {}
    if isinstance(data, dict) and error_state(data) == 10001:
        selected = choose_overname(data.get("overname") or [], args.choose_index)
        username = selected.get("username")
        if not username:
            raise RuntimeError(f"选中的 overname 缺少 username：{json.dumps(selected, ensure_ascii=False)}")
        return login_by_account(str(username), pwd_md5, args)

    raise RuntimeError(error_message(body))


def load_login_cache() -> dict[str, Any]:
    try:
        data = json.loads(LOGIN_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_login_cache(args: argparse.Namespace) -> None:
    data = {
        key: getattr(args, key, None)
        for key in LOGIN_CACHE_KEYS
        if getattr(args, key, None) not in (None, "")
    }
    if not data:
        return
    LOGIN_CACHE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="翼课学生 5.2.7 实名登录获取 token demo")
    parser.add_argument("--name", help="学生姓名，对应 nicename；不传则交互式输入")
    parser.add_argument("--school-name", help="学校名称，对应 schoolName；不传则交互式输入")
    parser.add_argument("--school-id", help="学校 ID，对应 schoolId；不传则交互式输入")
    parser.add_argument("--password", help="明文密码；不传则交互式输入")
    parser.add_argument("--choose-index", type=int, help="同名账号分支选择序号；不传则交互选择")
    parser.add_argument("--timeout", type=int, default=15, help="请求超时时间，默认 15 秒")
    parser.add_argument("--api-version", default="5.1.0", help="公共参数 v，默认 5.1.0")
    parser.add_argument("--osv", default="Android", help="公共参数 osv")
    parser.add_argument("--driver-code", default="5.2.7", help="公共参数 driverCode")
    parser.add_argument("--driver-type", default="demo", help="公共参数 driverType")
    parser.add_argument("--device-token", default="demo-device-token", help="公共参数 deviceToken")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON；默认只额外打印 token")
    return parser.parse_args()


def prompt_required(label: str) -> str:
    while True:
        value = input(f"{label}：").strip()
        if value:
            return value
        print(f"{label}不能为空。", file=sys.stderr)


def fill_interactive_args(args: argparse.Namespace) -> argparse.Namespace:
    cache = load_login_cache()
    for key in LOGIN_CACHE_KEYS:
        if getattr(args, key, None) in (None, "") and cache.get(key) not in (None, ""):
            setattr(args, key, cache[key])

    if not args.name:
        args.name = prompt_required("姓名")
    if not args.school_name:
        args.school_name = prompt_required("学校名称")
    if not args.school_id:
        args.school_id = prompt_required("学校 ID")
    return args


def main() -> int:
    args = fill_interactive_args(parse_args())
    try:
        result = login_by_real_name(args)
        save_login_cache(args)
    except Exception as exc:
        print(f"登录失败：{exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.json:
        print(f"token={result['token']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
