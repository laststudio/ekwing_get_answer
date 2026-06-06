# 翼课学生 5.2.7 作业详情与答案接口逆向总结

> 本文由 `ekwing_5.2.7.apk` 静态逆向得到，衔接 `homework_api_doc.md` 中的作业列表接口。本文描述的是登录后、持有本人 `uid/token` 的正常客户端链路：从作业列表项继续获取作业小项、题目内容、作答结果和答案数据。
> 当前 demo 在学习中心列表中默认只保留 `type=exam` 的考试任务；`type=hw` 作业/练习需要显式传 `--task-type hw` 或兼容参数 `--homework-only`。当前学习中心考试从 `/student/Hw/getnewmainlist` 读取，历史学习中心考试从 `/student/exam/getstuexamlist` 读取。考试项不会再请求 `/student/Hw/getHwItems` 或 score detail，而是直接读取列表项自带或由 `self_id + last_model_id + mode_type` 拼出的 `/student/exam/loadexamtest` URL。
> `exam_answer_demo.py` 是单独的学习中心考试答案解析 demo：它不走 `/student/Hw/*` 作业答案接口，而是用 `self_id` 请求 `/student/exam/getstuexamitem` 和 `/student/exam/getscoreinfo`，再从原始 JSON 中抽取题目、标准答案、学生答案、得分和解析候选字段。

## 1. 总体链路

App 获取作业列表后，并不是下载一个完整作业包，而是继续按下面顺序请求接口：

```text
1. /student/Hw/getList 或 /student/Hw/getBasicList
   得到 HwListEntity，关键字段是 hid、archiveId、record_id。

2. /student/Hw/getHwItems 或 /student/Hw/getBasicHwItems
   用 hid + page + archiveId 获取作业内的小项列表。

3. /student/Hw/hwdoitem
   用小项 id 作为 hwcid，按题型和入口获取单个小项的做题内容。

4. 答案/结果接口
   已完成、历史、提交结果页会再请求 getHwAns、gethwcnt、jshistoryitemScore、GetHwResult 或 score detail。
```

关键点：

| 阶段 | 输入来源 | 输出用途 |
| --- | --- | --- |
| 作业列表 | `HwListEntity.hid`、`archiveId` | 进入作业详情 |
| 作业详情 | `HwDetailListEntity.id`、`hid`、`type`、`record_id`、`tk_biz` | 进入具体题型 |
| 单项内容 | `hid` + `hwcid` + `method` + `is_exercise` + `archiveId` | 获取题目内容或上次作答 |
| 答案结果 | `hid` + `hwcid` 或 `unit_id/type/record_id` | 获取答案解析、成绩、历史得分 |

## 2. 获取作业小项列表

### 接口

普通账号：

```http
POST https://mapi.ekwing.com/student/Hw/getHwItems
```

Basic 账号：

```http
POST https://mapi.ekwing.com/student/Hw/getBasicHwItems
```

Basic 分支由 `UserInfoManager.isBasic()` 决定。

### 请求参数

`f/e/u/i/b.smali` 中的 `P()` 是第一页请求，`O()` 是加载更多请求。作业模式下固定传：

```text
hid       = HwListEntity.hid
page      = 1 或 当前 page + 1
archiveId = HwListEntity.archiveId
```

再叠加登录公共参数：

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

客户端把外层 `data` 解包后解析为 `HwDetailEntity`：

```json
{
  "info": {},
  "page": {},
  "list": [
    {
      "id": "作业小项 id，后续作为 hwcid",
      "hid": "作业 id",
      "unit_id": "单元 id",
      "book_id": "书本 id",
      "record_id": "记录 id",
      "type_name": "小项类型名称",
      "vip_type": "VIP 类型",
      "client": "客户端类型",
      "score": "分数",
      "finish": "完成标记",
      "type": "小项题型",
      "num": 1,
      "tk_biz": "题库/业务类型",
      "is_btk": 0,
      "level": "等级",
      "score_type": "分数类型",
      "url": "跳转 URL"
    }
  ]
}
```

`HwDetailListEntity.id` 是后续接口里的 `hwcid`，不要和作业列表里的 `hid` 混用。

## 3. 获取单个作业小项内容

### 接口

```http
POST https://mapi.ekwing.com/student/Hw/hwdoitem
```

这个接口在多个题型 Activity 中调用，例如跟读、朗读、对话、绘本、趣配音等。不同题型会传不同的 `method`、请求码和解析逻辑，但核心字段一致。

### 核心参数

常见参数：

```text
hid         = HwDetailListEntity.hid
hwcid       = HwDetailListEntity.id
method      = 题型/入口决定；历史或取上次记录时常见 last
is_exercise = 0 或 1
archiveId   = HwListEntity.archiveId
```

`is_exercise` 的来源：

```text
UNFINISH_OR_HISTORY == 0xc9 时传 0
其他分支传 1
```

部分继续做题、暂停、提交或题型分支还会带：

```text
pause
duration
answer
```

注意：`reqPostParamsHwDoItem(..., tk_biz)` 的最后一个参数会传入 `tk_biz`，但从封装层看它不是普通表单字段的一部分，更像是请求回调或解析时使用的业务标识。写第三方 demo 时，先用详情接口返回的 `tk_biz/type` 做分流，不要直接假设它一定要作为 form 参数提交。

### 推荐下载方式

如果目标是“下载作业内容”，建议先做原始 JSON 下载，不急着解析每种题型：

```text
1. 拉作业列表，选择一条 HwListEntity。
2. 调 getHwItems/getBasicHwItems，保存返回的 HwDetailEntity。
3. 遍历 HwDetailEntity.list：
   - hid = item.hid
   - hwcid = item.id
   - archiveId = 作业列表项 archiveId
   - is_exercise 按当前/历史入口决定
   - method 先从 last 或题型 Activity 中对应值开始验证
4. 保存 hwdoitem 返回原始 data。
5. 再按 item.type、item.tk_biz 写解析器。
```

也就是说，APK 里的“下载作业”本质是接口级抓取：作业列表 JSON、小项列表 JSON、每个小项内容 JSON。

## 4. 获取答案和结果

答案/结果不是只有一个接口。APK 中至少有下面几类路径。

### 4.0 学习中心考试题目和答案

学习中心考试和普通作业/练习不同，不应调用 `/student/Hw/getHwItems`、`/student/Hw/getHwAns` 或 score detail。考试列表项进入 App 后，客户端会携带 `self_id` 进入考试页；查看报告/解析时走考试专用接口。

题目/考试内容接口：

```http
POST https://mapi.ekwing.com/student/exam/getstuexamitem
```

请求参数：

```text
self_id = KSListEntity.self_id 或列表项 id
```

考试结果/答案解析接口：

```http
POST https://mapi.ekwing.com/student/exam/getscoreinfo
```

Basic 账号：

```http
POST https://mapi.ekwing.com/student/exam/getbasicscoreinfo
```

请求参数：

```text
self_id = KSListEntity.self_id 或列表项 id
method  = exam_result
type    = 列表项 url 中存在时透传，例如 type=0
```

demo 用法：

```bash
python exam_answer_demo.py --list-type current --exam-index 0 --save-dir out_exam
python exam_answer_demo.py --list-type study-center-history --exam-index 0 --save-dir out_exam
```

`current` 是 `study-center` 的别名，来源是 `/student/Hw/getnewmainlist` 中的当前学习中心考试任务；`study-center-history` 来源是 `/student/exam/getstuexamlist` 中的历史学习中心考试任务。历史 Basic 考试列表项通常自带 `getbasicscoreinfo?self_id=...&method=exam_result&type=0`，demo 会优先复用该 URL。当前考试若没有成绩 URL，demo 会按 `self_id + method=exam_result` 构造 `/student/exam/getscoreinfo` 或 Basic 的 `/student/exam/getbasicscoreinfo`。

输出文件：

```text
out_exam/exam.json            选中的考试列表项
out_exam/exam_item_raw.json   getstuexamitem 原始响应
out_exam/score_info_raw.json  getscoreinfo/getbasicscoreinfo 原始响应
out_exam/score_info.html      成绩接口返回 HTML 时额外保存的页面源码
out_exam/structured_report.json 结构化考试报告：总分、模块分、题目、作答明细
out_exam/answers_only.json    更干净的答案清单：标准答案、学生作答、分数、录音、词级评分
out_exam/parsed_answers.json  递归抽取的题目/答案/得分/解析候选字段，用于兜底调试
out_exam/result.json          完整聚合结果
```

注意：部分 Basic 历史考试的 `getbasicscoreinfo` 返回的是 WebView HTML 页面，不是 JSON。demo 会把 HTML 当作成功响应保存，并尝试从页面脚本中提取内嵌 JSON 候选。优先看 `answers_only.json` 和 `structured_report.json`；前者适合直接读答案，后者保留总分、模块分、题目和作答明细。`parsed_answers.json` 是字段级通用抽取，只用于排查未知题型。

### 4.1 作业答案 getHwAns

```http
POST https://mapi.ekwing.com/student/Hw/getHwAns
```

在普通作业结果页中，`HWSubmitResultActivity` 对作业模式传：

```text
hid       = HwDetailListEntity.hid
hwcid     = HwDetailListEntity.id
method    = LAST 或 MAX
archiveId = HwListEntity.archiveId
```

`method` 来源：

```text
FLAG_FROM_SUBMIT 为 true  时使用 LAST
FLAG_FROM_SUBMIT 为 false 时使用 MAX
```

部分题型或训练模式不走 `hid/hwcid`，而是走训练答案接口，参数形态变成：

```text
unit_id   = HwDetailListEntity.unit_id
type      = HwDetailListEntity.type
record_id = HwDetailListEntity.record_id
archiveId = HwListEntity.archiveId
method    = LAST 或 MAX
```

这些分支会请求：

```http
POST https://mapi.ekwing.com/student/train/getitemans
POST https://mapi.ekwing.com/student/train/getjsitemans
```

### 4.2 答题数量/答案内容 gethwcnt

```http
POST https://mapi.ekwing.com/student/Hw/gethwcnt
```

`f/e/u/i/a.smali` 中构造参数：

```text
hid         = HwDetailListEntity.hid
hwcid       = HwDetailListEntity.id
archiveId   = HwListEntity.archiveId
is_exercise = d.v(boolean)
```

该接口通常在结果页点击查看答案/解析时被调用。返回内容还会被本地缓存工具处理，后续再进入答案解析页面。

### 4.3 历史小项成绩 jshistoryitemScore

```http
POST https://mapi.ekwing.com/student/Hw/jshistoryitemScore
```

`f/e/u/i/b.smali` 中有两个分支：

带 `method=last` 的分支：

```text
hid         = HwDetailListEntity.hid
hwcid       = HwDetailListEntity.id
archiveId   = HwListEntity.archiveId
method      = last
is_exercise = 0 或 1
```

不带 `method` 的分支：

```text
hid         = HwDetailListEntity.hid
hwcid       = HwDetailListEntity.id
archiveId   = HwListEntity.archiveId
is_exercise = 0 或 1
```

这个接口更像是“历史小项分数/结果”接口，不一定直接返回完整答案解析。

### 4.4 小项结果 GetHwResult

```http
POST https://mapi.ekwing.com/student/Hw/GetHwResult
```

`f/e/u/i/b.smali` 的 `N()` 构造参数：

```text
hid         = HwDetailListEntity.hid
hwcid       = HwDetailListEntity.id
archiveId   = HwListEntity.archiveId
is_exercise = 0 或 1
```

该接口用于获取某个小项的结果数据，成功后客户端取外层 `data` 字符串回调给页面。

### 4.5 成绩详情 stuscoredetail

普通账号：

```http
POST https://mapi.ekwing.com/student/Hw/stuscoredetail
```

Basic 账号：

```http
POST https://mapi.ekwing.com/student/Hw/stubasicscoredetail
```

作业模式下由 `f/e/u/i/b.smali` 选择接口，基础参数和详情列表类似：

```text
hid       = HwListEntity.hid
page      = 1 或 当前 page + 1
archiveId = HwListEntity.archiveId
```

训练模式还会额外带：

```text
self_id     = HwListEntity.hid
is_exercise = 0 或 1
```

## 5. Python 调用骨架

下面只给“下载原始 JSON”的骨架。具体题型解析需要继续按 `type/tk_biz` 分支补。

```python
BASE_URL = "https://mapi.ekwing.com"


def get_homework_items(uid, token, args, hw, page=1, basic=False):
    path = "/student/Hw/getBasicHwItems" if basic else "/student/Hw/getHwItems"
    payload = common_params(args, uid, token)
    payload.update({
        "hid": str(hw["hid"]),
        "page": str(page),
        "archiveId": str(hw.get("archiveId", "")),
    })
    return post_form(path, payload, args.timeout)["data"]


def get_hw_do_item(uid, token, args, hw, item, method="last", is_exercise="0"):
    payload = common_params(args, uid, token)
    payload.update({
        "hid": str(item.get("hid") or hw["hid"]),
        "hwcid": str(item["id"]),
        "method": method,
        "is_exercise": is_exercise,
        "archiveId": str(hw.get("archiveId", "")),
    })
    return post_form("/student/Hw/hwdoitem", payload, args.timeout)["data"]


def get_hw_answer(uid, token, args, hw, item, method="LAST"):
    payload = common_params(args, uid, token)
    payload.update({
        "hid": str(item.get("hid") or hw["hid"]),
        "hwcid": str(item["id"]),
        "method": method,
        "archiveId": str(hw.get("archiveId", "")),
    })
    return post_form("/student/Hw/getHwAns", payload, args.timeout)["data"]


def get_hw_count_or_answer(uid, token, args, hw, item, is_exercise="0"):
    payload = common_params(args, uid, token)
    payload.update({
        "hid": str(item.get("hid") or hw["hid"]),
        "hwcid": str(item["id"]),
        "archiveId": str(hw.get("archiveId", "")),
        "is_exercise": is_exercise,
    })
    return post_form("/student/Hw/gethwcnt", payload, args.timeout)["data"]
```

## 6. 字段对应表

| API 参数 | 来源字段 |
| --- | --- |
| `hid` | 作业列表 `HwListEntity.hid`，或小项 `HwDetailListEntity.hid` |
| `hwcid` | 小项 `HwDetailListEntity.id` |
| `archiveId` | 作业列表 `HwListEntity.archiveId` |
| `record_id` | 小项 `HwDetailListEntity.record_id` |
| `unit_id` | 小项 `HwDetailListEntity.unit_id` |
| `book_id` | 小项 `HwDetailListEntity.book_id` |
| `type` | 小项 `HwDetailListEntity.type` |
| `tk_biz` | 小项 `HwDetailListEntity.tk_biz`，用于题型/业务分流 |
| `is_exercise` | 当前/历史入口决定，`0xc9` 分支为 `0`，其他分支为 `1` |

## 7. 已确认的逆向证据

```text
作业详情数据管理器：
decoded_ekwing_5.2.7/smali_classes4/f/e/u/i/b.smali

详情接口选择 getHwItems/getBasicHwItems：
f/e/u/i/b.smali -> z()

详情第一页参数 hid/page/archiveId：
f/e/u/i/b.smali -> P()

详情加载更多参数：
f/e/u/i/b.smali -> O()

GetHwResult 参数：
f/e/u/i/b.smali -> N()

jshistoryitemScore 参数：
f/e/u/i/b.smali -> Q()
f/e/u/i/b.smali -> R()

score detail 接口选择：
f/e/u/i/b.smali -> w()

gethwcnt 参数：
decoded_ekwing_5.2.7/smali_classes4/f/e/u/i/a.smali -> o()

训练内容/训练答案参数：
f/e/u/i/a.smali -> p()

getHwAns 参数和 LAST/MAX 分支：
decoded_ekwing_5.2.7/smali_classes4/com/ekwing/study/core/result/HWSubmitResultActivity.smali -> y()
decoded_ekwing_5.2.7/smali_classes4/com/ekwing/study/core/result/HWSubmitResultActivity.smali -> z()

hwdoitem 封装：
decoded_ekwing_5.2.7/smali/com/ekwing/business/activity/NetworkActivity.smali
decoded_ekwing_5.2.7/smali/com/ekwing/business/activity/BaseEkwingWebViewAct.smali

HwDetailListEntity 字段：
decoded_ekwing_5.2.7/smali_classes4/com/ekwing/study/entity/HwDetailListEntity.smali
```

## 8. 仍需继续跟的点

目前静态逆向已经确认“作业列表之后该请求哪些接口”和主要参数来源，但下面这些属于题型级差异：

```text
1. hwdoitem 的 method 值并非全局固定，需按 Activity/题型继续跟。
2. hwdoitem 返回 data 的结构会随 type/tk_biz 改变。
3. getHwAns、gethwcnt 返回的答案结构也需要按题型解析。
4. 口语类题型可能包含音频地址、评分字段和提交答案字段。
5. WebView 类小项可能直接走 url 或 studyweb 分支。
```

因此，下一步实现脚本时建议先做“原始 JSON 下载器”，把列表、详情、小项内容、答案结果都保存下来；再基于真实返回样本补解析器。
