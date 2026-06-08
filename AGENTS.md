# Project Constraints

- 本项目中的“当前作业”和“历史作业”均指学习中心里的考试任务，不指普通作业列表里的 `hw` 作业项。
- 当前学习中心考试任务来自 `/student/Hw/getnewmainlist`，脚本侧默认只保留 `type=exam`。
- 历史学习中心考试任务来自 `/student/exam/getstuexamlist`，请求参数使用 `type=his`。
- 修改登录、作业列表、考试答案解析相关代码时，需要同步维护对应的 Markdown 文档。
- `out_exam/` 是本地运行输出目录，不应提交或上传。
