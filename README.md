# ekwing_get_answer

这个项目是通过逆向 Android 版翼课学生客户端实现的一个 demo，用于验证登录账号、获取学习中心考试任务列表，以及解析部分考试答案内容。

## 功能

- 支持实名登录：姓名、学校、密码。
- 支持账号密码登录：账号、密码。
- 获取学习中心当前考试任务。
- 获取学习中心历史考试任务。
- 拉取考试题目、成绩页和模块分数接口的原始响应。
- 从部分响应结构中解析标准答案、题目和作答结果。

## 口径约束

本项目里的“当前作业”和“历史作业”指的是学习中心的考试任务：

- 当前作业：学习中心当前考试任务，来源于 `/student/Hw/getnewmainlist`，脚本默认过滤 `type=exam`。
- 历史作业：学习中心历史考试任务，来源于 `/student/exam/getstuexamlist`，请求参数为 `type=his`。

它们不表示普通作业列表里的 `type=hw` 作业项。

## 项目结构

主程序和 demo：

- `study_center_exam_downloader.py`：主入口，登录后获取学习中心考试任务，下载考试题目、成绩页和模块分数响应，并解析部分答案。
- `demo.py`：登录 demo，封装实名登录、账号密码登录和学校搜索。
- `homework_demo.py`：学习中心任务和作业列表接口 demo。
- `exam_answer_demo.py`：学习中心考试答案解析 demo。
- `homework_detail_answer_demo.py`：普通作业小项内容和答案接口 demo。
- `exam_answer_json_parse_demo.py`：解析 `model_score_raw.json` 的离线工具。
- `school_id_demo.py`：学校搜索和学校 ID 获取 demo。

逆向文档：

- `login_api_doc.md`：登录接口逆向说明。
- `homework_api_doc.md`：作业/学习中心列表接口逆向说明。
- `homework_detail_answer_api_doc.md`：作业详情、考试答案接口逆向说明。
- `exam_answer_json_format.md`：考试答案 JSON 解析格式说明。
- `reverse_report.md`：逆向记录占位或补充文档。

逆向来源和产物：

- `ekwing_5.2.7.apk`：逆向分析来源 APK。
- `decoded_ekwing_5.2.7/`：APK 反编译目录，属于本地逆向产物，不提交。
- `out_exam/`：脚本运行输出目录，属于本地下载和解析产物，不提交。
- `.ekwing_login_cache.json`：本地登录信息缓存，不保存明文密码，不提交。

## 登录示例

实名登录：

```bash
python study_center_exam_downloader.py --login-method real-name --name 张三 --school-keyword 某某学校
```

账号密码登录：

```bash
python study_center_exam_downloader.py --login-method account --username your_account
```

如果不传 `--password`，脚本会交互式输入密码。项目不会保存明文密码。

## 输出

默认输出目录是 `out_exam/`，用于保存运行过程中产生的原始响应和解析结果，例如：

- `exam.json`
- `exam_item_raw.json`
- `score_info_raw.json`
- `model_score_raw.json`
- `answers.json`
- `answers_by_question.json`
- `answers_only.json`
- `result.json`

`out_exam/` 是本地运行产物，已在 `.gitignore` 中忽略，不应提交到仓库。

## APK

仓库中包含用于逆向分析的安装包：

```text
ekwing_5.2.7.apk
```

对应的反编译目录 `decoded_*/` 是本地分析产物，已被忽略，不提交到仓库。

## 说明

这是一个 demo 项目，接口和字段来自对 Android 客户端的静态逆向与本地脚本验证，不保证覆盖所有账号类型、题型和服务端返回形态。
