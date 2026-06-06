# ekwing_5.2.7.apk 逆向静态分析摘要

分析日期：2026-06-06  
样本：`D:\Users\34647\Desktop\myProject\ekwing_apk\ekwing_5.2.7.apk`

## 1. 样本信息

- APK：`ekwing_5.2.7.apk`
- 大小：约 96.39 MB
- MD5：`17222531D8CC2017F2FF5A2F0D33A68D`
- SHA256：`323FE4C77CB43962013F5FDAE76FCA211C33E08EDB74693A67517630A377BFE3`
- apktool 解码目录：`D:\Users\34647\Desktop\myProject\ekwing_apk\decoded_ekwing_5.2.7`
- apktool 版本：`3.0.1`
- CodeGraph：当前项目未初始化 `.codegraph/`，本次未使用结构索引。

## 2. APK 基础元数据

来自 `apktool.yml` 和 `AndroidManifest.xml`：

- package：`com.ekwing.students`
- versionName：`5.2.7`
- versionCode：`502070`
- minSdkVersion：`19`
- targetSdkVersion：`31`
- compileSdkVersion：`31`
- Application：`com.ekwing.students.App`
- Launcher Activity：`com.ekwing.students.activity.WelcomeActivity`
- `android:allowBackup="false"`
- `android:requestLegacyExternalStorage="true"`
- `android:usesCleartextTraffic="true"`
- dex/smali：6 组 smali 目录，共约 21,924 个 smali 文件

## 3. 主要目录规模

- `smali*`：约 179 MB，6 个 dex 解出的 smali
- `res`：约 26 MB，约 4,261 个资源文件
- `assets`：约 55.9 MB
- `lib`：约 61.3 MB，包含 `arm64-v8a` 与 `armeabi-v7a`
- `original/META-INF`：存在 `CERT.RSA`、`CERT.SF`、`MANIFEST.MF`

## 4. 启动和初始化流程

### `com.ekwing.students.App`

路径：`decoded_ekwing_5.2.7\smali\com\ekwing\students\App.smali`

- 继承 `com.ekwing.business.application.GlobalApplication`
- `attachBaseContext()` 调用 `Ld/q/a;->k(Context)`，可能是 MultiDex 或加固/插件初始化相关逻辑
- `onCreate()`：
  - 先判断 `GlobalApplication.r()`，满足条件直接返回
  - 调用 `s()` 写入若干全局配置字段
  - 调用父类 `GlobalApplication.onCreate()`
  - 注册若干生命周期观察者
  - 非特定模式下初始化 MobLink

`App.s()` 中可见硬编码配置：

- `5.1.0`
- `1.0`
- `1`
- `373b07f02b874fcd`
- `33a1e64c80e141e2`
- `367bfcbb605e4eb9`

### `com.ekwing.students.activity.WelcomeActivity`

路径：`decoded_ekwing_5.2.7\smali_classes4\com\ekwing\students\activity\WelcomeActivity.smali`

启动后主要行为：

- 检查是否重复启动 launcher task
- 加载启动页布局
- 处理隐私弹窗与隐私更新弹窗
- 初始化服务
- 将 deep link / push URI 交给 `OpenViewManager`
- 拉取启动 banner、活动状态、隐私状态
- 跳转到 `NavigationActivity`、`FlushActivity` 或 `MainActivity.startIfLogin()`

明确请求的接口：

- `https://mapi.ekwing.com/comm/index/getbanner`
- `https://mapi.ekwing.com/student/race/hasshow`
- `https://mapi.ekwing.com/student/user/privacy`

## 5. 登录相关发现

### 登录入口

`com.ekwing.login.core.activity.LoginMainActivity`

路径：`decoded_ekwing_5.2.7\smali_classes3\com\ekwing\login\core\activity\LoginMainActivity.smali`

- ARouter 路由：`/loginCore/ui_loginMain`
- 支持常规登录、扫码、游客登录、一键登录
- 登录后通过 `UserInfoManager.login(uid, token, userType)` 写入用户状态
- 登录完成后组合触发：
  - `UserInfoManager.observable()`
  - `ConfigManager.observable()`

### 游客登录硬编码参数

`LoginMainActivity.loginTourist()` 中发现：

- URL：`https://mapi.ekwing.com/student/User/login`
- 参数 `username = 10279447`
- 参数 `password` 的明文源字符串为 `16666661`
- `password` 传参前调用 `Lf/e/y/s;->a(String)`，疑似本地 hash/加密/编码

### 一键登录

`LoginMainActivity.oneKeyLogin()`：

- URL：`https://mapi.ekwing.com/student/user/loginsantong`
- 参数：
  - `token`
  - `appId = 1ee12f2ab627b3d11ef7a38762c7cd2b`
  - `authCode`
  - `channel`
- 运营商映射：
  - `CM -> 0`
  - `CT -> 1`
  - `CU -> 2`

## 6. 权限与组件暴露面

Manifest 中可见敏感权限：

- `android.permission.INTERNET`
- `android.permission.ACCESS_NETWORK_STATE`
- `android.permission.ACCESS_WIFI_STATE`
- `android.permission.CHANGE_NETWORK_STATE`
- `android.permission.CHANGE_WIFI_STATE`
- `android.permission.CAMERA`
- `android.permission.RECORD_AUDIO`
- `android.permission.SYSTEM_ALERT_WINDOW`
- `android.permission.SYSTEM_OVERLAY_WINDOW`
- `android.permission.WRITE_EXTERNAL_STORAGE`
- `android.permission.READ_EXTERNAL_STORAGE`
- `android.permission.REQUEST_INSTALL_PACKAGES`
- `android.permission.POST_NOTIFICATIONS`
- `android.permission.READ_PRIVILEGED_PHONE_STATE`
- `android.permission.QUERY_ALL_PACKAGES`

Manifest 中 `android:exported="true"` 命中 26 处，重点包括：

- `WelcomeActivity`：Launcher
- `WXEntryActivity`：微信回调
- `AgainLoginActivity`：deep link `ekwingstudent://ncetqrcode.student`
- `LoginInfoProvider`：`authorities="com.ekwing.students.db.UserInfoContentProvider"`，导出 provider，需重点审计读写保护
- 华为、小米、OPPO、VIVO、魅族推送相关 receiver/service/provider
- `MobLinkActivity`：
  - `ekwingstudent://splash`
  - `http://7843.t4m.cn`
  - `https://7843.t4m.cn`
- `ShareTransActivity`、`ReceiveActivity`、`MobUIShell` 等分享/三方 SDK 组件

## 7. 网络与 API

静态分析器在解码工程中提取到：

- URL：282 个
- IP：25 个
- API endpoint：351 个

主要业务域名：

- `https://mapi.ekwing.com`
- `http://mapi.ekwing.com`
- `https://www.ekwing.com`
- `https://zgd.ekwing.com/APIPOOL/`

典型业务接口：

- 登录/用户：
  - `/student/User/login`
  - `/student/User/loginschool`
  - `/student/user/loginsantong`
  - `/student/user/verify`
  - `/student/user/forgetpwd`
  - `/student/user/privacy`
  - `/student/User/updatedevice`
- 作业/答题：
  - `/student/Hw/getHwItems`
  - `/student/Hw/GetHwResult`
  - `/student/Hw/hwSubmit`
  - `/student/Hw/getHwAns`
  - `/student/Hw/hwdoitem`
- 考试：
  - `/student/exam/search`
  - `/student/exam/saveexamdraft`
  - `/student/exam/getscoreinfo`
- 口语/配音：
  - `/student/spoken/getcnt`
  - `/student/spoken/record`
  - `/student/spoken/do`
  - `/student/spoken/share`
- 智能刷题：
  - `/student/brush/getIndexInfo`
  - `/student/brush/startbrush`

## 8. 第三方 SDK 与硬编码配置

识别到的 SDK/能力：

- Mob / ShareSDK / MobPush / MobLink
- 微信 OpenSDK
- QQ / QZone
- 微博 SDK
- 支付宝分享入口
- 华为 HMS Push
- 小米 Push
- 魅族 Push
- OPPO / VIVO Push
- 腾讯 Bugly
- 诸葛统计
- OkGo / RxJava 网络栈
- 腾讯 X5 / TBS
- IJKPlayer / FFmpeg
- SQLCipher

Manifest 中硬编码：

- `Mob-AppKey = 1c9167cbac73b`
- `Mob-AppSecret = 4549ec14426ef83e45d22b47948d112c`
- `com.huawei.hms.client.appid = 10239797`
- `com.mob.push.meizu.appid = 112555`
- `com.mob.push.meizu.appkey = 698685f76d8444728382cb69f733236f`
- `com.mob.push.xiaomi.appid = 2882303761517304942`
- `com.mob.push.xiaomi.appkey = 5291730498942`
- `com.mob.push.oppo.appkey = E14apd52zm040W4sosgwKS0Sk`
- `com.mob.push.oppo.appsecret = 6Fc34888ded8e672F9a450edCD293F4A`
- `com.vivo.push.api_key = f1fc7eef-388f-4730-9f09-aadd7a1c0578`
- `com.vivo.push.app_id = 19735`

`assets/ShareSDK.xml` 中硬编码：

- Weibo AppKey/AppSecret
- WeChat AppId/AppSecret
- QQ/QZone AppId/AppKey
- Alipay AppId

`res/values/strings.xml` 中有：

- `security_public_key`：RSA 公钥字符串
- `push_cat_body = 99A9343CEC0A64112FD2496EF752F719`
- `push_cat_head = 767499AE5B2DFC9D873AF46032E13B00`

## 9. native 库与资产

`lib/arm64-v8a` 和 `lib/armeabi-v7a` 各 20 个 so，主要包括：

- `libijkffmpeg.so`
- `libijkplayer.so`
- `libijksdl.so`
- `libsoe.so`
- `libssound.so`
- `libvadnn.so`
- `libspeech-eval-sdk.so`
- `libsqlcipher.so`
- `libBugly_Native.so`
- `libweibosdkcore.so`
- `libopus.so`
- `liblamemp3.so`

语音/测评相关资产：

- `assets/en-US.tar`：约 38.54 MB
- `assets/resource_en.zip`：约 8.33 MB
- `assets/vad.0.1.bin`：约 1.30 MB
- `assets/sdk.json`：语音测评开关、超时、在线/离线配置
- `assets/en-US.txt`
- `assets/iattest.wav`
- 多个音频资源：`good.mp3`、`bad.wav` 等

## 10. 工具限制

- `apksigner` 不在当前 PATH，MCP 签名验证失败。
- `keytool` 不在当前 PATH，无法直接打印 jar 签名证书。
- `openssl` 不在当前 PATH，无法解析 `original/META-INF/CERT.RSA`。
- 静态分析器直接分析原 APK 时 Manifest 解析失败；解码后分析正常。

## 11. 后续建议

建议优先继续深挖这些方向：

1. `LoginInfoProvider`：导出 provider 是否能被外部读取用户信息或 token。
2. `Lf/e/y/s;->a(String)`：确认登录密码参数的加密/hash 算法。
3. `com.ekwing.http.okgoclient`：请求签名、公共参数、token 注入、证书校验逻辑。
4. `OpenViewManager` 与 deep link：确认外部 URI 能打开哪些内部页面或 WebView。
5. `BaseEkwingWebViewAct` / `BaseAndroidWebViewAct`：JSBridge、URL 白名单、文件访问配置。
6. `REQUEST_INSTALL_PACKAGES` 与 `UpdateDownloadService`：检查更新下载、安装触发和校验逻辑。
7. native 语音库：如果目标是协议/算法逆向，需要进一步对 `libsoe.so`、`libssound.so`、`libvadnn.so` 做 strings 和符号分析。
