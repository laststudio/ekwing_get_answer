# 翼课学生 5.2.7 登录 API 文档

> 本文由 `ekwing_5.2.7.apk` 静态逆向得到，目标是让第三方 demo 能完成登录并拿到 `token`。字段结构来自 smali 实体类与调用链还原，未包含服务端实时抓包样本。

## 1. 基础信息

- Base URL：`https://mapi.ekwing.com`
- 请求方式：`POST`
- 参数格式：`application/x-www-form-urlencoded`
- 网络库：OkGo / RxHttp / RxHttps
- JSON 解析：Gson
- 成功判定：外层 `status == 0`
- 登录成功 token 路径：`data.token`

密码处理函数：

```text
md5(raw_password).hexdigest().lower()
```

APK 中对应：

```text
Lf/e/y/s;->a(String)
```

## 2. 公共参数

所有 `RxHttp/RxHttps.post()` 会自动追加 `Config.getParams()` 中的公共参数。登录 demo 建议至少带上能静态确认的固定参数，设备参数可按实际设备构造。

```text
v          = 5.1.0
is_http    = 1
os         = Android
client     = student
up_version = 1.0
osv        = Android 系统版本
driverCode = App 版本号或版本标识
driverType = 设备型号
deviceToken = 设备标识
```

已有登录态后还会追加：

```text
uid
author_id = uid
token
```

首次登录时通常没有 `uid/token`，demo 可以先不带。

## 3. 账号密码登录

### 接口

```http
POST https://mapi.ekwing.com/student/User/login
```

### 请求参数

```text
username = 账号
password = md5(明文密码)
```

加上公共参数后的示例：

```text
username=your_account
password=md5_password
v=5.1.0
is_http=1
os=Android
client=student
up_version=1.0
```

### 成功返回结构

```json
{
  "status": 0,
  "data": {
    "uid": "123456",
    "token": "token_string",
    "userType": "student_type",
    "show_race": false,
    "overname": null
  }
}
```

客户端成功处理：

```text
uid = data.uid
token = data.token
userType = data.userType
UserInfoManager.login(uid, token, userType)
```

demo 只需要保存：

```text
uid
token
userType
```

后续请求公共参数中加入：

```text
uid=...
author_id=...
token=...
```

### 失败返回结构

登录实体继承 `ErrorEntity`，错误字段支持多个别名。常见结构可按以下方式兼容：

```json
{
  "status": 1,
  "data": {
    "state": 10001,
    "msg": "错误提示"
  }
}
```

兼容字段：

```text
错误码：data.state，别名 data.intent / data.intend
错误信息：data.msg，别名 data.errlog / data.error_msg
```

### Python demo

```python
import hashlib
import requests


BASE = "https://mapi.ekwing.com"


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def common_params():
    return {
        "v": "5.1.0",
        "is_http": "1",
        "os": "Android",
        "client": "student",
        "up_version": "1.0",
        "osv": "Android",
        "driverCode": "5.2.7",
        "driverType": "demo",
        "deviceToken": "demo-device-token",
    }


def login_by_account(username: str, password: str):
    data = common_params()
    data.update({
        "username": username,
        "password": md5_hex(password),
    })
    r = requests.post(f"{BASE}/student/User/login", data=data, timeout=15)
    r.raise_for_status()
    body = r.json()

    if body.get("status") != 0:
        err = body.get("data") or {}
        raise RuntimeError(err.get("msg") or err.get("error_msg") or err.get("errlog") or body)

    user = body["data"]
    return {
        "uid": user["uid"],
        "token": user["token"],
        "userType": user.get("userType"),
    }
```

## 4. 学校 ID 获取

实名登录的 `schoolId` 来自 App 选中的 `LoginSchoolBean.id`。最简单的 demo 路径是直接搜索学校，然后取返回项里的 `school_id`。

APK 证据链：

```text
SearchSchoolActivity.w() -> POST /student/user/searchschool
SearchSchoolEntity.school_id -> LoginSchoolBean.id
LoginSchoolBean.getId() -> /student/User/loginschool 参数 schoolId
LoginSchoolBean.getName() -> /student/User/loginschool 参数 schoolName
```

### 方式一：按关键字搜索学校

推荐 demo 使用这个方式，不需要先选择省市区县。

```http
POST https://mapi.ekwing.com/student/user/searchschool
```

请求参数：

```text
key  = 学校关键字
page = 页码，从 1 开始
```

返回项实体为 `SearchSchoolEntity`，关键字段：

```json
{
  "school_id": "12345",
  "school_name": "某某学校",
  "province_id": "省 ID",
  "province_name": "省名称",
  "city_id": "市 ID",
  "city_name": "市名称",
  "county_id": "区县 ID",
  "county_name": "区县名称",
  "study_section": "学段 ID",
  "status": "状态",
  "url": "学校相关 URL"
}
```

字段映射：

```text
schoolId   = school_id
schoolName = school_name.trim()
countyId   = county_id
st_id      = study_section
zone       = province_name + "-" + city_name + "-" + county_name
```

实际 demo 流程：

```text
1. 调 searchschool(key=学校名, page=1)
2. 展示返回列表，让用户确认具体学校
3. 取选中项的 school_id 作为 schoolId
4. 取选中项的 school_name 作为 schoolName
5. 调实名登录 /student/User/loginschool
```

### 方式二：按区县和学段获取学校列表

这是 App 省市区县选择后的学校列表接口。

```http
POST https://mapi.ekwing.com/student/user/scgetschool
```

请求参数：

```text
id    = countyId，区县 ID
st_id = 学段 ID；0 表示默认/全部
```

返回项实体为 `LoginSchoolBean`，关键字段：

```json
{
  "id": "12345",
  "name": "某某学校",
  "city_id": "市 ID",
  "countyId": "区县 ID",
  "st_id": "学段 ID",
  "zone": "省-市-区县",
  "status": "状态",
  "url": "学校相关 URL"
}
```

字段映射：

```text
schoolId   = id
schoolName = name.trim()
```

### Python helper

```python
def search_school(keyword: str, page: int = 1):
    data = common_params()
    data.update({
        "key": keyword,
        "page": str(page),
    })
    r = requests.post(f"{BASE}/student/user/searchschool", data=data, timeout=15)
    r.raise_for_status()
    body = r.json()

    if body.get("status") != 0:
        err = body.get("data") or {}
        raise RuntimeError(err.get("msg") or err.get("error_msg") or err.get("errlog") or body)

    # APK converter 目标是 List<SearchSchoolEntity>。
    # 服务端 data 常见形态可能是 list，也可能包一层列表字段；demo 可按实际返回兼容。
    data_obj = body.get("data") or []
    if isinstance(data_obj, list):
        return data_obj
    for key in ("list", "rows", "data"):
        if isinstance(data_obj.get(key), list):
            return data_obj[key]
    return []


def choose_school(keyword: str, index: int = 0):
    schools = search_school(keyword, 1)
    if not schools:
        raise RuntimeError("未搜索到学校")
    item = schools[index]
    return {
        "schoolId": item["school_id"],
        "schoolName": item["school_name"].strip(),
        "countyId": item.get("county_id"),
        "st_id": item.get("study_section"),
        "zone": "-".join([
            item.get("province_name", ""),
            item.get("city_name", ""),
            item.get("county_name", ""),
        ]).strip("-"),
    }
```

## 5. 实名登录

实名登录是登录页第 0 个 tab，对应“选学校 + 姓名 + 密码”。

### 接口

```http
POST https://mapi.ekwing.com/student/User/loginschool
```

### 请求参数

```text
nicename   = 姓名
pwd        = md5(明文密码)
schoolName = 学校名称
schoolId   = 学校 ID
```

加上公共参数后的示例：

```text
nicename=张三
pwd=md5_password
schoolName=某某学校
schoolId=12345
v=5.1.0
is_http=1
os=Android
client=student
up_version=1.0
```

### 成功返回结构

```json
{
  "status": 0,
  "data": {
    "uid": "123456",
    "token": "token_string",
    "userType": "student_type",
    "show_race": false,
    "overname": null
  }
}
```

客户端处理与账号密码登录相同：

```text
uid = data.uid
token = data.token
userType = data.userType
```

### 同名/多账号分支

实名登录可能出现 `overname` 分支。APK 中判断逻辑：

```text
外层 status == 1
并且 data.state == 10001
```

`10001` 十六进制是 `0x2711`，客户端将其视为 `OverNameException`，要求用户选择具体账号。

可能返回结构：

```json
{
  "status": 1,
  "data": {
    "state": 10001,
    "msg": "请选择账号",
    "overname": [
      {
        "uid": 123456,
        "username": "student_account",
        "type": "student_type",
        "classname": "班级名称",
        "headerUrl": "头像地址"
      }
    ]
  }
}
```

APK 的二次处理逻辑：

1. 展示 `overname` 列表。
2. 用户点选某一项。
3. 取选中项的 `username`。
4. 再调用账号密码登录接口 `/student/User/login`：

```text
username = overname[i].username
password = 上一次实名登录使用的 md5 密码
```

因此 demo 处理实名登录时要支持两步：

```text
loginschool 成功 -> 直接取 data.token
loginschool 返回 status=1 且 data.state=10001 -> 选择 overname.username -> 调 /student/User/login -> 取 data.token
```

### Python demo

```python
def login_by_real_name(nicename: str, password: str, school_name: str, school_id: str, choose_index: int = 0):
    pwd_md5 = md5_hex(password)
    data = common_params()
    data.update({
        "nicename": nicename,
        "pwd": pwd_md5,
        "schoolName": school_name,
        "schoolId": school_id,
    })

    r = requests.post(f"{BASE}/student/User/loginschool", data=data, timeout=15)
    r.raise_for_status()
    body = r.json()

    if body.get("status") == 0:
        user = body["data"]
        return {
            "uid": user["uid"],
            "token": user["token"],
            "userType": user.get("userType"),
        }

    err = body.get("data") or {}
    state = err.get("state", err.get("intent", err.get("intend")))

    if state == 10001:
        overname = err.get("overname") or []
        if not overname:
            raise RuntimeError("实名登录返回同名分支，但 overname 为空")
        selected = overname[choose_index]

        login_data = common_params()
        login_data.update({
            "username": selected["username"],
            "password": pwd_md5,
        })

        r2 = requests.post(f"{BASE}/student/User/login", data=login_data, timeout=15)
        r2.raise_for_status()
        body2 = r2.json()

        if body2.get("status") != 0:
            err2 = body2.get("data") or {}
            raise RuntimeError(err2.get("msg") or err2.get("error_msg") or err2.get("errlog") or body2)

        user = body2["data"]
        return {
            "uid": user["uid"],
            "token": user["token"],
            "userType": user.get("userType"),
        }

    raise RuntimeError(err.get("msg") or err.get("error_msg") or err.get("errlog") or body)
```

## 6. 字段实体还原

### HttpResult

```json
{
  "status": 0,
  "data": {}
}
```

### LoginEntity

```json
{
  "uid": "string",
  "token": "string",
  "userType": "string",
  "show_race": false,
  "overname": []
}
```

### ErrorEntity

```json
{
  "state": 0,
  "msg": "string"
}
```

Gson 注解兼容：

```text
state aliases: intent, intend
msg aliases: errlog, error_msg
```

### OverNameEntity

```json
{
  "uid": 123456,
  "username": "string",
  "type": "string",
  "classname": "string",
  "headerUrl": "string"
}
```

## 7. 两种登录方式区别

| 登录方式 | 接口 | 核心身份参数 | 密码参数名 | 是否需要学校 |
|---|---|---|---|---|
| 账号密码登录 | `/student/User/login` | `username` | `password` | 否 |
| 实名登录 | `/student/User/loginschool` | `nicename` | `pwd` | 是，`schoolName/schoolId` |

两者最终成功返回都落到同一个实体 `LoginEntity`，都从 `data.token` 取登录 token。
