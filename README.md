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

## 登录示例

实名登录：

```bash
python release.py --login-method real-name --name 张三 --school-keyword 某某学校
```

账号密码登录：

```bash
python release.py --login-method account --username your_account
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
