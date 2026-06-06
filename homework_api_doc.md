# 翼课学生 5.2.7 作业列表 API 文档

> 本文由 `ekwing_5.2.7.apk` 静态逆向得到，目标是让第三方 demo 在已经登录并持有 `uid/token` 后获取作业列表。本文只描述登录后接口，不包含验证码、账号获取或越权逻辑。

## 1. 基础信息

- Base URL：`https://mapi.ekwing.com`
- 请求方式：`POST`
- 参数格式：`application/x-www-form-urlencoded`
- 成功判定：外层 `status == 0`
- 失败判定：外层 `status == 1` 时客户端会走 `EkwCommonJsonParser.StatusOneException`
- 响应解包：客户端从外层 JSON 的 `data` 字段取字符串，再解析为实体

登录后所有作业接口都需要带公共参数和登录态参数：

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
uid        = 登录返回 uid
author_id  = uid
token      = 登录返回 token
```

## 2. 接口总览

| 用途 | 普通账号接口 | Basic 账号接口 | 返回类型 |
| --- | --- | --- | --- |
| 学习中心混合列表 | `/student/Hw/getnewmainlist` | `/student/Hw/getbasicnewmainlist` | `List<StudyCenterListEntity>` |
| 作业分页列表 | `/student/Hw/getList` | `/student/Hw/getBasicList` | `HwEntity` |
| 学习首页模块 | `/student/Hw/getmain` | 未见 Basic 分支 | `List<StudyTopModeEntity>` |

推荐 demo 直接使用：

```text
GET 当前作业分页列表：POST /student/Hw/getList，method=new，page=1，sortMethod=desc，sortField=publish_times
GET 历史/已完成作业：POST /student/Hw/getList，method=finish，page=1，sortMethod=desc，sortField=finish_times
GET 首页混合任务：POST /student/Hw/getnewmainlist，只带公共参数和登录态
```

说明：`method=new` 是作业页调用方实际传入的当前作业值；`method=finish` 是历史分支在 DataManager 内强制写入的值。

## 3. 学习中心混合列表

### 接口

普通账号：

```http
POST https://mapi.ekwing.com/student/Hw/getnewmainlist
```

Basic 账号：

```http
POST https://mapi.ekwing.com/student/Hw/getbasicnewmainlist
```

### 请求参数

APK 中该接口业务参数 `HashMap` 为空，只依赖公共参数和登录态参数。

```text
uid
author_id
token
v
is_http
os
client
up_version
osv
driverCode
driverType
deviceToken
```

### 返回结构

客户端将外层 `data` 解析为 `List<StudyCenterListEntity>`：

```json
{
  "status": 0,
  "data": [
    {
      "id": "作业/考试/训练 id",
      "type": "hw",
      "title": "标题",
      "status": "状态",
      "archiveId": "归档/分页游标相关 id",
      "archiveName": "归档名称",
      "book_name": "书名",
      "finish_num": "已完成数量",
      "total_num": "总数量",
      "left_time": "剩余时间",
      "end_time": "结束时间",
      "start_time": "开始时间",
      "submit_time": "提交时间",
      "record_id": "记录 id",
      "all_vip_ques": "VIP 题标记",
      "mode_type": "模式类型",
      "self_status": "个人状态",
      "start_url": "开始地址",
      "url": "跳转地址",
      "undo": "未完成标记",
      "is_new": false,
      "sys_time": 0
    }
  ]
}
```

`type` 在点击处理里至少出现：

```text
hw    = 作业
exam  = 考试
train = 训练
```

如果只想要作业，demo 可过滤：

```python
homework_items = [item for item in items if item.get("type") == "hw"]
```

## 4. 作业分页列表

### 接口

普通账号：

```http
POST https://mapi.ekwing.com/student/Hw/getList
```

Basic 账号：

```http
POST https://mapi.ekwing.com/student/Hw/getBasicList
```

Basic 分支由 `UserInfoManager.isBasic()` 决定。第三方 demo 如果不确定账号类型，可以先请求普通接口；若服务端返回 Basic 相关错误，再切换 Basic 接口。

### 当前/未完成作业第一页

App 作业页调用方实际传入 `method=new`，DataManager 固定使用 `publish_times` 排序。

```text
method     = new
page       = 1
sortMethod = desc
sortField  = publish_times
```

请求示例：

```http
POST https://mapi.ekwing.com/student/Hw/getList
```

```text
method=new&page=1&sortMethod=desc&sortField=publish_times&uid=...&author_id=...&token=...
```

### 历史/已完成作业第一页

历史分支固定：

```text
method     = finish
page       = 1
sortMethod = desc
sortField  = finish_times
```

### 加载更多

加载更多由当前页对象和已加载列表共同决定：

```text
method     = 当前列表 method；历史列表强制 finish
page       = currentPage + 1
sortMethod = desc
sortField  = 当前列表 publish_times；历史列表 finish_times
archiveId  = 当前已加载列表最后一条作业的 archiveId
```

分页继续条件：客户端比较 `currentPage` 和 `totalPage`，当前页小于总页数时才继续请求下一页。

## 5. 作业分页返回结构

外层：

```json
{
  "status": 0,
  "data": {
    "list": [],
    "page": {}
  }
}
```

`data` 对应 `HwEntity`：

```json
{
  "list": [
    {
      "hid": "作业 id",
      "title": "作业标题",
      "book_name": "书名",
      "status": "状态",
      "finish": "完成标记",
      "score": "分数",
      "left_time": "剩余时间",
      "finish_time": "完成时间",
      "end_time": "截止时间",
      "leave_msg": "留言/提示",
      "cntTotal": 10,
      "finishCntNum": "3",
      "archiveName": "归档名称",
      "archiveId": "归档/分页游标相关 id",
      "record_id": "记录 id",
      "score_type": "分数类型",
      "level": "等级",
      "submit_time": "提交时间",
      "all_vip_ques": "VIP 题标记"
    }
  ],
  "page": {
    "archiveId": "归档 id",
    "currentPage": 1,
    "next": "下一页标记",
    "per": 10,
    "totalPage": 3
  }
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `hid` | 作业 id，后续进入作业详情通常会用到 |
| `title` | 作业标题 |
| `book_name` | 所属书本 |
| `status` | 作业状态 |
| `finish` | 完成状态标记 |
| `score` | 分数，默认值为字符串 `0` |
| `left_time` | 剩余时间 |
| `finish_time` | 完成时间 |
| `end_time` | 截止时间 |
| `cntTotal` | 总题数 |
| `finishCntNum` | 已完成题数，实体内是字符串，getter 会转 int |
| `archiveId` | 加载更多时作为游标参数 |
| `record_id` | 作答记录 id |
| `submit_time` | 提交时间 |

## 6. Python demo

下面示例假设你已经通过 `demo.py` 登录拿到了 `uid/token`。

```python
import json
import requests

BASE_URL = "https://mapi.ekwing.com"


def common_params(uid: str, token: str) -> dict[str, str]:
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
        "uid": uid,
        "author_id": uid,
        "token": token,
    }


def post_form(path: str, payload: dict[str, str]) -> dict:
    r = requests.post(f"{BASE_URL}{path}", data=payload, timeout=15)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != 0:
        raise RuntimeError(json.dumps(body, ensure_ascii=False))
    return body


def get_current_homework(uid: str, token: str, page: int = 1, archive_id: str | None = None) -> dict:
    payload = common_params(uid, token)
    payload.update({
        "method": "new",
        "page": str(page),
        "sortMethod": "desc",
        "sortField": "publish_times",
    })
    if archive_id:
        payload["archiveId"] = archive_id
    return post_form("/student/Hw/getList", payload)["data"]


def get_finished_homework(uid: str, token: str, page: int = 1, archive_id: str | None = None) -> dict:
    payload = common_params(uid, token)
    payload.update({
        "method": "finish",
        "page": str(page),
        "sortMethod": "desc",
        "sortField": "finish_times",
    })
    if archive_id:
        payload["archiveId"] = archive_id
    return post_form("/student/Hw/getList", payload)["data"]


def get_study_center_tasks(uid: str, token: str) -> list[dict]:
    payload = common_params(uid, token)
    return post_form("/student/Hw/getnewmainlist", payload)["data"]


def get_all_current_homework(uid: str, token: str) -> list[dict]:
    first = get_current_homework(uid, token, page=1)
    items = first.get("list") or []
    page = first.get("page") or {}
    current = int(page.get("currentPage") or 1)
    total = int(page.get("totalPage") or current)

    while current < total and items:
        archive_id = items[-1].get("archiveId")
        current += 1
        data = get_current_homework(uid, token, page=current, archive_id=archive_id)
        next_items = data.get("list") or []
        items.extend(next_items)
        page = data.get("page") or {}
        total = int(page.get("totalPage") or total)
    return items


if __name__ == "__main__":
    UID = "替换为登录返回 uid"
    TOKEN = "替换为登录返回 token"
    data = get_current_homework(UID, TOKEN)
    print(json.dumps(data, ensure_ascii=False, indent=2))
```

## 7. 逆向证据

关键 smali 位置：

```text
作业分页接口选择：decoded_ekwing_5.2.7/smali_classes4/f/e/u/e/s/a.smali:456-475
getnewmainlist 接口：decoded_ekwing_5.2.7/smali_classes4/f/e/u/e/s/a.smali:2020-2070
历史列表第一页参数：decoded_ekwing_5.2.7/smali_classes4/f/e/u/e/s/a.smali:2075-2124
加载更多入口：decoded_ekwing_5.2.7/smali_classes4/f/e/u/e/s/a.smali:2129-2380
刷新/第一页参数：decoded_ekwing_5.2.7/smali_classes4/f/e/u/e/s/a.smali:2382-2474
当前列表第一页参数：decoded_ekwing_5.2.7/smali_classes4/f/e/u/e/s/a.smali:2479-2526
接口成功分发：decoded_ekwing_5.2.7/smali_classes4/f/e/u/e/s/a.smali:2882-3128
学习首页调用 getnewmainlist：decoded_ekwing_5.2.7/smali_classes4/com/ekwing/study/core/StudyMainFragmentOld.smali:1598-1606
全部作业页 method=new 调用：decoded_ekwing_5.2.7/smali_classes4/com/ekwing/study/core/HwAllTypeListActivity.smali:2717-2723
加载更多 method=new 调用：decoded_ekwing_5.2.7/smali_classes4/com/ekwing/study/core/HwAllTypeListActivity$n.smali:77-85
响应 data 解包：decoded_ekwing_5.2.7/smali_classes4/f/e/u/l/d.smali:6736-6775
```

实体类：

```text
HwEntity：com.ekwing.study.entity.HwEntity
HwListEntity：com.ekwing.study.entity.HwListEntity
HwPageEntity：com.ekwing.study.entity.HwPageEntity
StudyCenterListEntity：com.ekwing.study.entity.StudyCenterListEntity
```
