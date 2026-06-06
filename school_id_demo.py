#!/usr/bin/env python3
"""School ID lookup demo for Ekwing Student 5.2.7.

Usage:
    python school_id_demo.py
    python school_id_demo.py --keyword 某某学校
    python school_id_demo.py --mode county --county-id 123 --study-section 0
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


BASE_URL = "https://mapi.ekwing.com"
SEARCH_SCHOOL_PATH = "/student/user/searchschool"
COUNTY_SCHOOL_PATH = "/student/user/scgetschool"


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


def extract_list(data_obj: Any) -> list[dict[str, Any]]:
    if isinstance(data_obj, list):
        return [item for item in data_obj if isinstance(item, dict)]
    if isinstance(data_obj, dict):
        for key in ("list", "rows", "data"):
            value = data_obj.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def search_school(keyword: str, page: int, args: argparse.Namespace) -> list[dict[str, Any]]:
    payload = common_params(args)
    payload.update(
        {
            "key": keyword,
            "page": str(page),
        }
    )
    body = post_form(SEARCH_SCHOOL_PATH, payload, args.timeout)
    if body.get("status") != 0:
        raise RuntimeError(error_message(body))
    return extract_list(body.get("data") or [])


def get_schools_by_county(county_id: str, study_section: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    payload = common_params(args)
    payload.update(
        {
            "id": county_id,
            "st_id": study_section,
        }
    )
    body = post_form(COUNTY_SCHOOL_PATH, payload, args.timeout)
    if body.get("status") != 0:
        raise RuntimeError(error_message(body))
    return extract_list(body.get("data") or [])


def normalize_search_item(item: dict[str, Any]) -> dict[str, Any]:
    province = item.get("province_name") or ""
    city = item.get("city_name") or ""
    county = item.get("county_name") or ""
    zone = "-".join(part for part in (province, city, county) if part)
    return {
        "schoolId": item.get("school_id"),
        "schoolName": str(item.get("school_name") or "").strip(),
        "countyId": item.get("county_id"),
        "st_id": item.get("study_section"),
        "zone": zone,
        "raw": item,
    }


def normalize_county_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "schoolId": item.get("id"),
        "schoolName": str(item.get("name") or "").strip(),
        "countyId": item.get("countyId"),
        "st_id": item.get("st_id"),
        "zone": item.get("zone"),
        "raw": item,
    }


def print_schools(schools: list[dict[str, Any]]) -> None:
    for index, school in enumerate(schools):
        school_id = school.get("schoolId") or ""
        school_name = school.get("schoolName") or ""
        zone = school.get("zone") or ""
        county_id = school.get("countyId") or ""
        st_id = school.get("st_id") or ""
        print(f"[{index}] id={school_id} name={school_name} zone={zone} countyId={county_id} st_id={st_id}")


def choose_school(schools: list[dict[str, Any]], choose_index: int | None) -> dict[str, Any]:
    if not schools:
        raise RuntimeError("未获取到学校列表")

    print_schools(schools)

    if choose_index is not None:
        if choose_index < 0 or choose_index >= len(schools):
            raise RuntimeError(f"--choose-index 超出范围：0..{len(schools) - 1}")
        return schools[choose_index]

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


def prompt_required(label: str) -> str:
    while True:
        value = input(f"{label}：").strip()
        if value:
            return value
        print(f"{label}不能为空。", file=sys.stderr)


def prompt_mode() -> str:
    print("请选择学校 ID 获取方式：")
    print("[1] 按学校关键字搜索")
    print("[2] 按区县 ID + 学段获取学校列表")
    while True:
        raw = input("请输入 1 或 2：").strip()
        if raw == "1":
            return "search"
        if raw == "2":
            return "county"
        print("请输入 1 或 2。", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="翼课学生 5.2.7 学校 ID 获取 demo")
    parser.add_argument("--mode", choices=("search", "county"), help="获取方式；不传则交互选择")
    parser.add_argument("--keyword", help="学校关键字，mode=search 使用；不传则交互输入")
    parser.add_argument("--page", type=int, default=1, help="搜索页码，默认 1")
    parser.add_argument("--county-id", help="区县 ID，mode=county 使用；不传则交互输入")
    parser.add_argument("--study-section", default="0", help="学段 ID，默认 0")
    parser.add_argument("--choose-index", type=int, help="直接选择返回列表序号；不传则交互选择")
    parser.add_argument("--timeout", type=int, default=15, help="请求超时时间，默认 15 秒")
    parser.add_argument("--api-version", default="5.1.0", help="公共参数 v，默认 5.1.0")
    parser.add_argument("--osv", default="Android", help="公共参数 osv")
    parser.add_argument("--driver-code", default="5.2.7", help="公共参数 driverCode")
    parser.add_argument("--driver-type", default="demo", help="公共参数 driverType")
    parser.add_argument("--device-token", default="demo-device-token", help="公共参数 deviceToken")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mode = args.mode or prompt_mode()

    try:
        if mode == "search":
            keyword = args.keyword or prompt_required("学校关键字")
            raw_schools = search_school(keyword, args.page, args)
            schools = [normalize_search_item(item) for item in raw_schools]
        else:
            county_id = args.county_id or prompt_required("区县 ID")
            raw_schools = get_schools_by_county(county_id, args.study_section, args)
            schools = [normalize_county_item(item) for item in raw_schools]

        selected = choose_school(schools, args.choose_index)
    except Exception as exc:
        print(f"获取学校 ID 失败：{exc}", file=sys.stderr)
        return 1

    print("\n选中的学校：")
    print(json.dumps({key: value for key, value in selected.items() if key != "raw"}, ensure_ascii=False, indent=2))
    print(f"schoolId={selected.get('schoolId')}")
    print(f"schoolName={selected.get('schoolName')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
