#!/usr/bin/env python3
"""Login demo for Ekwing Student 5.2.7.

Usage:
    python demo.py
    python demo.py --name 张三 --password 123456 --school-name 某某学校 --school-id 12345
    python demo.py --login-method account --username student_account --password 123456
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
SEARCH_SCHOOL_PATH = "/student/user/searchschool"
LOGIN_CACHE_PATH = Path(__file__).with_name(".ekwing_login_cache.json")
LOGIN_METHOD_REAL_NAME = "real-name"
LOGIN_METHOD_ACCOUNT = "account"
REAL_NAME_LOGIN_CACHE_KEYS = ("name", "school_name", "school_id", "choose_index")
ACCOUNT_LOGIN_CACHE_KEYS = ("username",)


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


def login_by_username_password(args: argparse.Namespace) -> dict[str, Any]:
    if not getattr(args, "username", None):
        args.username = prompt_required("账号")
    password = args.password or getpass.getpass("密码：")
    return login_by_account(args.username, md5_hex(password), args)


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
    if not args.name:
        args.name = prompt_required("姓名")
    ensure_school_info(args)
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


def login(args: argparse.Namespace) -> dict[str, Any]:
    method = getattr(args, "login_method", None) or LOGIN_METHOD_REAL_NAME
    if method == LOGIN_METHOD_ACCOUNT:
        return login_by_username_password(args)
    if method == LOGIN_METHOD_REAL_NAME:
        return login_by_real_name(args)
    raise RuntimeError(f"未知登录方式：{method}")


def load_login_cache() -> dict[str, Any]:
    try:
        data = json.loads(LOGIN_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_login_cache(args: argparse.Namespace) -> None:
    method = getattr(args, "login_method", LOGIN_METHOD_REAL_NAME)
    keys = ACCOUNT_LOGIN_CACHE_KEYS if method == LOGIN_METHOD_ACCOUNT else REAL_NAME_LOGIN_CACHE_KEYS
    data = {
        "login_method": method,
        **{
            key: getattr(args, key, None)
            for key in keys
            if getattr(args, key, None) not in (None, "")
        },
    }
    data = {
        key: value
        for key, value in data.items()
        if getattr(args, key, None) not in (None, "")
    }
    if not data:
        return
    LOGIN_CACHE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_login_cache_interactive(args: argparse.Namespace) -> None:
    save_login = getattr(args, "save_login", None)
    if save_login is None:
        save_login = prompt_yes_no("是否保存本次登录信息（不保存密码）", default=False)
    if save_login:
        save_login_cache(args)


def search_school(keyword: str, page: int, args: argparse.Namespace) -> list[dict[str, Any]]:
    payload = common_params(args)
    payload.update({"key": keyword, "page": str(page)})
    body = post_form(SEARCH_SCHOOL_PATH, payload, args.timeout)
    if body.get("status") != 0:
        raise RuntimeError(error_message(body))
    return [normalize_school_item(item) for item in extract_list(body.get("data") or [])]


def extract_list(data_obj: Any) -> list[dict[str, Any]]:
    if isinstance(data_obj, list):
        return [item for item in data_obj if isinstance(item, dict)]
    if isinstance(data_obj, dict):
        for key in ("list", "rows", "data"):
            value = data_obj.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def normalize_school_item(item: dict[str, Any]) -> dict[str, Any]:
    province = item.get("province_name") or ""
    city = item.get("city_name") or ""
    county = item.get("county_name") or ""
    zone = "-".join(part for part in (province, city, county) if part)
    return {
        "school_id": first_non_empty(item.get("school_id"), item.get("id")),
        "school_name": str(first_non_empty(item.get("school_name"), item.get("name")) or "").strip(),
        "zone": zone or item.get("zone") or "",
        "raw": item,
    }


def first_non_empty(*values: Any) -> str | None:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return None


def choose_school(schools: list[dict[str, Any]], choose_index: int | None = None) -> dict[str, Any]:
    if not schools:
        raise RuntimeError("未搜索到学校")
    for index, school in enumerate(schools):
        zone = f" zone={school.get('zone')}" if school.get("zone") else ""
        print(f"[{index}] id={school.get('school_id')} name={school.get('school_name')}{zone}", file=sys.stderr)
    if choose_index is not None:
        if 0 <= choose_index < len(schools):
            return schools[choose_index]
        raise RuntimeError(f"--school-choose-index 超出范围：0..{len(schools) - 1}")
    while True:
        raw = input(f"请选择学校序号 0..{len(schools) - 1}：").strip()
        try:
            selected_index = int(raw)
        except ValueError:
            print("请输入数字序号。", file=sys.stderr)
            continue
        if 0 <= selected_index < len(schools):
            return schools[selected_index]
        print("序号超出范围。", file=sys.stderr)


def ensure_school_info(args: argparse.Namespace) -> None:
    if args.school_id and args.school_name:
        return

    if args.school_id and not args.school_name:
        keyword = args.school_keyword or prompt_required("已输入学校 ID，请输入学校关键字用于反查学校名称")
        schools = search_school(keyword, args.school_search_page, args)
        matched = [school for school in schools if str(school.get("school_id")) == str(args.school_id)]
        if not matched:
            print("搜索结果中没有匹配该学校 ID，请从搜索结果中手动选择：", file=sys.stderr)
            matched = schools
        selected = choose_school(matched, args.school_choose_index)
        args.school_id = str(selected["school_id"])
        args.school_name = selected["school_name"]
        return

    if not args.school_id or not args.school_name:
        keyword = args.school_keyword or prompt_required("学校关键字")
        schools = search_school(keyword, args.school_search_page, args)
        selected = choose_school(schools, args.school_choose_index)
        args.school_id = str(selected["school_id"])
        args.school_name = selected["school_name"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="翼课学生 5.2.7 登录获取 token demo")
    parser.add_argument(
        "--login-method",
        choices=(LOGIN_METHOD_REAL_NAME, LOGIN_METHOD_ACCOUNT),
        default=None,
        help="登录方式：real-name 为实名登录，account 为账号密码登录；不传则交互选择",
    )
    parser.add_argument("--username", help="账号密码登录的账号，对应 username；不传则交互式输入")
    parser.add_argument("--name", help="学生姓名，对应 nicename；不传则交互式输入")
    parser.add_argument("--school-name", help="学校名称，对应 schoolName；不传则交互式输入")
    parser.add_argument("--school-id", help="学校 ID，对应 schoolId；不传则交互式输入")
    parser.add_argument("--school-keyword", help="学校搜索关键字；未提供学校名称时用于搜索选择")
    parser.add_argument("--school-search-page", type=int, default=1, help="学校搜索页码，默认 1")
    parser.add_argument("--school-choose-index", type=int, help="学校搜索结果选择序号；不传则交互选择")
    parser.add_argument("--password", help="明文密码；不传则交互式输入")
    parser.add_argument("--save-login", dest="save_login", action="store_true", default=None, help="登录成功后保存登录信息（不保存密码）")
    parser.add_argument("--no-save-login", dest="save_login", action="store_false", help="登录成功后不保存登录信息")
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


def fill_interactive_args(args: argparse.Namespace) -> argparse.Namespace:
    cache = load_login_cache()
    cached_method = cache.get("login_method")
    if getattr(args, "login_method", None) is None and cached_method in {LOGIN_METHOD_REAL_NAME, LOGIN_METHOD_ACCOUNT}:
        args.login_method = cached_method
    if getattr(args, "login_method", None) is None:
        args.login_method = prompt_login_method()
    if args.login_method == LOGIN_METHOD_ACCOUNT:
        apply_login_cache(args, cache, ACCOUNT_LOGIN_CACHE_KEYS)
        if not args.username:
            args.username = prompt_required("账号")
    elif args.login_method == LOGIN_METHOD_REAL_NAME:
        apply_login_cache(args, cache, REAL_NAME_LOGIN_CACHE_KEYS)
        if not args.name:
            args.name = prompt_required("姓名")
        ensure_school_info(args)
    else:
        raise RuntimeError(f"未知登录方式：{args.login_method}")
    if not args.password:
        args.password = getpass.getpass("密码：")
    if getattr(args, "save_login", None) is None:
        args.save_login = prompt_yes_no("是否保存本次登录信息（不保存密码）", default=False)
    return args


def apply_login_cache(args: argparse.Namespace, cache: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        if hasattr(args, key) and getattr(args, key, None) in (None, "") and cache.get(key) not in (None, ""):
            setattr(args, key, cache[key])


def prompt_login_method() -> str:
    print("请选择登录方式：", file=sys.stderr)
    choices = (
        (LOGIN_METHOD_REAL_NAME, "实名登录（姓名 + 学校 + 密码）"),
        (LOGIN_METHOD_ACCOUNT, "账号密码登录（账号 + 密码）"),
    )
    for index, (_, label) in enumerate(choices, start=1):
        print(f"[{index}] {label}", file=sys.stderr)
    while True:
        raw = input("请输入 1..2：").strip()
        try:
            selected = int(raw)
        except ValueError:
            print("请输入数字序号。", file=sys.stderr)
            continue
        if 1 <= selected <= len(choices):
            return choices[selected - 1][0]
        print("序号超出范围。", file=sys.stderr)


def main() -> int:
    args = fill_interactive_args(parse_args())
    try:
        result = login(args)
        save_login_cache_interactive(args)
    except Exception as exc:
        print(f"登录失败：{exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.json:
        print(f"token={result['token']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
