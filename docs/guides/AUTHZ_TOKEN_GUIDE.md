# 授权令牌发布与密钥运维指南

本指南说明如何生成并发布授权令牌，及在客户端中的强绑定与复检逻辑。

相关文件：
- [damai/authz.py](damai/authz.py)
- [start_gui.pyw](start_gui.pyw)
- [damai_gui.py](damai_gui.py)

一、设置原始仓库绑定
1. 打开 [damai/authz.py](damai/authz.py)，将 OWNER 更新为你的 GitHub 用户名或组织名。
2. 获取仓库数值ID repo_id：访问 https://api.github.com/repos/{owner}/damai-ticket-assistant ，取响应中的 id。
3. 将 REPO_ID_LOCK 设置为该数值ID，用于强绑定原始仓库，防止 fork 授权。

二、令牌格式
令牌以 AUTHZ:<BASE64> 的形式发布在 Releases 最新版本的 body 文本中。
BASE64 解码后为 JSON：
```json
{
  "exp": 1735660800,
  "nonce": "random-string",
  "repo_id": 123456789,
  "sig": "BASE64-Ed25519-Signature"
}
```

签名消息为字符串: "{exp}:{nonce}:{repo_id}" 的 UTF-8 字节。
使用你的 Ed25519 私钥进行签名，客户端用内置公钥验签。

三、生成令牌示例（Python）
以下脚本使用你已有的私钥（Base64 原始 32 字节）生成令牌并输出 AUTHZ:<BASE64>：
```python
import base64, json, time, os
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

SK_B64 = os.environ.get('AUTHZ_SK_B64')  # 将你的私钥Base64放入环境变量
REPO_ID = int(os.environ.get('AUTHZ_REPO_ID', '0'))  # 你的仓库数值ID
TTL_SECONDS = int(os.environ.get('AUTHZ_TTL', '86400'))  # 默认令牌有效期1天

assert SK_B64 and REPO_ID > 0, '缺少私钥或仓库ID'
sk = ed25519.Ed25519PrivateKey.from_private_bytes(base64.b64decode(SK_B64))
exp = int(time.time()) + TTL_SECONDS
nonce = base64.b64encode(os.urandom(16)).decode()
message = f"{exp}:{nonce}:{REPO_ID}".encode('utf-8')
sig = sk.sign(message)

payload = {
  'exp': exp,
  'nonce': nonce,
  'repo_id': REPO_ID,
  'sig': base64.b64encode(sig).decode()
}
raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
print('AUTHZ:' + base64.b64encode(raw).decode())
```

用法（Windows CMD）：
```
set AUTHZ_SK_B64=NrpzdgUb5S+YfS96sgV4KsGN1y8fGE0ErhzgZiz9Cyo=
set AUTHZ_REPO_ID=你的仓库ID
set AUTHZ_TTL=86400
python generate_authz.py
```

四、发布令牌
1. 在 GitHub 仓库创建 Release 或编辑最新 Release。
2. 在 body 文本中新增一行：
   AUTHZ:<BASE64-OUTPUT>
3. 保存发布。客户端将在启动时强制拉取 releases/latest 验证令牌；GUI 运行期间每10分钟复检一次。

五、吊销与更新
- 吊销：删除 Release 中的 AUTHZ 行或发布新的过期令牌（exp 设为过去时间）。客户端将在复检时立即退出。
- 更新：生成新令牌（更长 TTL 或不同 nonce），覆盖 Release body 中的 AUTHZ 行。

六、安全建议
- 私钥严格离线保存，不要提交到仓库或公开渠道。
- 建议定期轮换令牌（短TTL，例如 24-72 小时）。
- 如需更强保护，可在 [damai/authz.py](damai/authz.py) 中拆分常量并做轻混淆（已内置 _unfuse）。

七、客户端行为回顾
- 启动硬闸：在 [start_gui.pyw](start_gui.pyw) 和 [damai_gui.py](damai_gui.py) 的入口处调用授权校验，未授权直接闪退。
- 强绑定：客户端比对远端仓库 id 与令牌中的 repo_id，且（可选）对 REPO_ID_LOCK 做锁定。
- 复检线程：GUI 启动后定期调用 ensure_authorized()，若失效则弹窗并 os._exit(1)。

八、故障排查
- 缺少 cryptography 依赖：请确保 [requirements.txt](requirements.txt) 已含 cryptography>=39.0.0，并安装。
- GitHub API 速率限制：建议使用已登录浏览器或配置环境变量 GITHUB_TOKEN 并在 _http_get 中添加 Authorization 头（如需）。
- 网络错误：首次启动必须成功授权；失败将闪退。请检查网络或稍后重试。

九、后续操作
- 提供 OWNER 与 repo_id 后，更新 [damai/authz.py](damai/authz.py) 中的常量并提交。
- 运行脚本生成 AUTHZ 令牌并发布到 Release body。
- 在全新环境启用 GUI，验证未授权闪退、授权后正常运行。
# 简化授权方案（当前生效）

本项目已切换为极简授权模型：仅在你的 GitHub 原仓库 Release body 中放置一行 AUTHZ:&lt;BASE64&gt;。客户端在启动硬闸与运行时复检时，会通过标准库联网校验：
- 拉取你的仓库数值 repo_id 并与强绑定的 REPO_ID_LOCK 比对（防 fork）
- 解析 AUTHZ Base64 JSON，校验 exp（过期时间）和 JSON 内 repo_id 必须等于远端仓库的 repo_id
- 校验通过才允许进入 GUI，否则在入口处闪退

关联实现与入口
- 授权校验：[python.def ensure_authorized()](damai/authz.py:105)
- 入口硬闸（启动前闪退）：[python.def block_if_unauthorized_with_ui()](damai/authz.py:146) 于 [python.def try…](start_gui.pyw:14) 和 [python.def main()](damai_gui.py:2899) 调用
- 强绑定常量（已填充你的信息）：OWNER/REPO_ID_LOCK 位于 [damai/authz.py](damai/authz.py:39)
  - OWNER: 10000ge10000
  - REPO_ID_LOCK: 1059334334

无需第三方依赖
- 仅使用 Python 标准库 urllib/json/time，不再依赖加密与签名库，运维更简洁
- requirements.txt 无需新增依赖项

一、令牌格式（简化版）
- 你在 Release 的 body 文本中放置一行：
  AUTHZ:&lt;BASE64(JSON)&gt;

- JSON 示例（Base64 解码后）：
  {
    "exp": 1735660800,
    "repo_id": 1059334334,
    "nonce": "任意字符串（可选）"
  }

字段说明
- exp：Unix 时间戳（秒），到期后客户端启动与复检都会判定未授权
- repo_id：你的原仓库数值 ID，客户端会与远端实际 repo_id 对比，防止 fork 仓库绕过
- nonce：可选，随机字符串，用于区分不同令牌版本

二、直接可用的授权令牌（为你生成）
- 复制以下整行，粘贴到“最新 Release”的正文中（单独成行）：
  AUTHZ:eyJleHAiOiAxNzU5MjIzNDY0LCAicmVwb19pZCI6IDEwNTkzMzQzMzQsICJub25jZSI6ICJPM2FGT0lrWVFQbDhBSzdjZmFKL29nPT0ifQ==

该令牌包含：
- repo_id=1059334334（已锁定你的仓库）
- exp=当前时间+3天（过期后需重新生成粘贴）
- nonce=随机字符串

三、发布与验证
1) 打开你的仓库 GitHub Releases，创建或编辑“最新 Release”
2) 在 body 文本中新增一行上面的 AUTHZ:....（保持单行、不要额外空格）
3) 保存后，运行脚本启动 GUI
   - 若授权正确：GUI 正常打开
   - 若授权缺失/过期/不匹配：在 [python.def block_if_unauthorized_with_ui()](damai/authz.py:146) 处弹窗并立即退出
4) 运行期间每约 10 分钟，后台复检会再次调用 [python.def ensure_authorized()](damai/authz.py:105)；若你删除/修改 Release 中的 AUTHZ 导致无效，客户端会弹窗并快速退出

四、更新与吊销
- 更新：生成新的 AUTHZ（例如更长有效期），覆盖 Release body 中的那一行
- 吊销：删除或替换为已过期的令牌，运行中复检会立即退出
- Fork 防护：客户端先获取你的原仓库 repo_id 并对比 REPO_ID_LOCK，fork 仓库不满足强绑定校验，无法获得授权

五、常见问题
- 看不到授权生效？
  - 确认 OWNER 与 REPO_ID_LOCK 已在 [damai/authz.py](damai/authz.py:39) 写入真实值（已为你配置）
  - 确认 Release body 中只有一行 AUTHZ:BASE64 且 BASE64 可正确解码为包含 exp 与 repo_id 的 JSON
  - 网络/速率限制：若 GitHub API 访问受限，请稍后重试或使用更稳定网络
- 想缩短更新窗口？
  - 缩短 exp 的 TTL（例如 24~72 小时）以便频繁轮换
  - 任何时候删除 AUTHZ 行都可立即吊销（复检生效）

六、回顾
- 启动时硬闸 + 运行时复检，双重保障
- 无签名与私钥运维，仅需发布/替换一行 AUTHZ
- 强绑定到你的原仓库（owner=10000ge10000，repo_id=1059334334），fork 无法通过授权
