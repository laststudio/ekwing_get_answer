# Project Constraints

- 本项目中的“当前作业”和“历史作业”均指学习中心里的考试任务，不指普通作业列表里的 `hw` 作业项。
- 当前学习中心考试任务来自 `/student/Hw/getnewmainlist`，脚本侧默认只保留 `type=exam`。
- 历史学习中心考试任务来自 `/student/exam/getstuexamlist`，请求参数使用 `type=his`。
- 修改登录、作业列表、考试答案解析相关代码时，需要同步维护对应的 Markdown 文档。
- `out_exam/` 是本地运行输出目录，不应提交或上传。

## Project Layout

- 主入口是 `study_center_exam_downloader.py`，职责是登录、读取学习中心考试任务列表、下载考试相关响应并解析部分答案。
- 登录公共逻辑在 `demo.py`，包括实名登录、账号密码登录、学校搜索和登录信息缓存。
- 列表接口 demo 在 `homework_demo.py`，可用于学习中心任务、当前/历史列表等接口验证。
- 考试答案解析 demo 在 `exam_answer_demo.py`，离线 JSON 解析工具在 `exam_answer_json_parse_demo.py`。
- 普通作业小项内容和答案接口 demo 在 `homework_detail_answer_demo.py`。
- 学校 ID 查询 demo 在 `school_id_demo.py`。
- 逆向文档是根目录下的 `*_doc.md`、`exam_answer_json_format.md` 和 `reverse_report.md`，修改对应代码时需要同步更新。
- 逆向来源 APK 是 `ekwing_5.2.7.apk`。
- 逆向出来的本地产物包括 `decoded_ekwing_5.2.7/`、`out_exam/` 和 `.ekwing_login_cache.json`，这些不作为主程序源码维护。
