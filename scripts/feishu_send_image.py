#!/usr/bin/env python3
"""
直接通过飞书 API 发送图片给用户。
绕过 main agent 的消息重写，确保用户在飞书看到思维导图图片。

用法:
  # 直连场景（agent 从消息头提取 account_id 和 open_id 传入）
  python3 feishu_send_image.py <图片路径> --channel feishu --account_id <account_id> --open_id <open_id>

  # 分发场景（脚本自动从 main agent session 读取凭证）
  python3 feishu_send_image.py <图片路径> --channel feishu --dispatch

  # 非飞书渠道（静默退出）
  python3 feishu_send_image.py <图片路径> --channel other
"""

import sys
import os
import json
import urllib.request
import urllib.error

OPENCLAW_CONFIG = os.path.expanduser(os.path.join("~", ".openclaw", "openclaw.json"))


def is_feishu_channel():
    if "--channel" in sys.argv:
        idx = sys.argv.index("--channel")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1].lower() == "feishu"
    return False


def is_dispatch_mode():
    return "--dispatch" in sys.argv


def get_argv(flag):
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


def load_config():
    try:
        with open(OPENCLAW_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"读取配置文件失败，跳过发图: {e}")
        sys.exit(0)


def resolve_credentials():
    """根据调用模式解析 appId、appSecret、open_id。

    直连模式：--account_id 和 --open_id 由 agent 从消息头提取后传入
    分发模式：--dispatch，从 main agent sessions.json 自动读取
    """
    config = load_config()
    feishu = config.get("channels", {}).get("feishu", {})
    accounts = feishu.get("accounts", {})

    if is_dispatch_mode():
        # 分发场景：从 main agent session 读取 accountId 和 open_id
        # 但必须确认 main agent 最后一次会话是飞书渠道，否则静默退出
        main_file = os.path.expanduser(
            os.path.join("~", ".openclaw", "agents", "main", "sessions", "sessions.json")
        )
        try:
            with open(main_file, "r", encoding="utf-8") as f:
                main_sessions = json.load(f)
            session = main_sessions.get("agent:main:main", {})
            last_channel = session.get("lastChannel", "")
            account_id = session.get("lastAccountId") or \
                         session.get("deliveryContext", {}).get("accountId")
            last_to = session.get("lastTo", "")
        except Exception as e:
            print(f"读取 main agent session 失败，跳过发图: {e}")
            sys.exit(0)

        if last_channel != "feishu":
            print(f"分发来源非飞书渠道（{last_channel}），跳过发图。")
            sys.exit(0)

        print("分发场景，从 main agent session 读取凭证")
        import re
        open_id_match = re.search(r'(ou_[a-z0-9]+)', last_to)
        open_id = open_id_match.group(1) if open_id_match else None

    else:
        # 直连场景：从命令行参数读取
        account_id = get_argv("--account_id")
        open_id = get_argv("--open_id")
        # 兜底：如果 account_id 被截断漏掉前缀，自动补全
        if account_id and not account_id.startswith("account_"):
            account_id = "account_" + account_id
            print(f"account_id 前缀修正: {account_id}")

    print(f"account_id: {account_id}")
    print(f"open_id: {open_id}")

    if not open_id:
        print("未获取到 open_id，跳过发图。")
        sys.exit(0)

    # 根据 account_id 找对应的 appId/appSecret
    if account_id and account_id in accounts:
        acct = accounts[account_id]
        app_id = acct.get("appId")
        app_secret = acct.get("appSecret")
        print(f"使用账号 {account_id} 的 appId: {app_id}")
    else:
        # 兜底用顶层配置
        app_id = feishu.get("appId")
        app_secret = feishu.get("appSecret")
        print(f"使用默认 appId: {app_id}")

    if not app_id or not app_secret:
        print("飞书 appId 或 appSecret 未配置，跳过发图。")
        sys.exit(0)

    return app_id, app_secret, open_id


def get_tenant_access_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    if result.get("code") != 0:
        print(f"获取 token 失败，跳过发图: {result.get('msg')}")
        sys.exit(0)
    return result["tenant_access_token"]


def upload_image(token, image_path):
    url = "https://open.feishu.cn/open-apis/im/v1/images"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    filename = os.path.basename(image_path)

    with open(image_path, "rb") as f:
        image_data = f.read()

    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="image_type"\r\n\r\n'.encode())
    body.extend(b"message\r\n")
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode())
    body.extend(b"Content-Type: image/png\r\n\r\n")
    body.extend(image_data)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(url, data=bytes(body), headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    })

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    if result.get("code") != 0:
        print(f"上传图片失败，跳过发图: code={result.get('code')} msg={result.get('msg')}")
        sys.exit(0)

    image_key = result.get("data", {}).get("image_key")
    print(f"图片上传成功: image_key={image_key}")
    return image_key


def send_image_message(token, open_id, image_key):
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    data = json.dumps({
        "receive_id": open_id,
        "msg_type": "image",
        "content": json.dumps({"image_key": image_key}),
    }).encode()

    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"发送消息失败，跳过发图: HTTP {e.code} {e.read().decode()[:200]}")
        sys.exit(0)

    if result.get("code") != 0:
        print(f"发送消息失败，跳过发图: code={result.get('code')} msg={result.get('msg')}")
        sys.exit(0)

    print(f"图片已发送到飞书用户: {open_id}")
    return result


def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <图片路径> [--channel feishu|other] [--account_id <id>] [--open_id <id>] [--dispatch]")
        sys.exit(1)

    if not is_feishu_channel():
        print("当前任务非飞书渠道发起，跳过发图。")
        sys.exit(0)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"图片不存在，跳过发图: {image_path}")
        sys.exit(0)

    app_id, app_secret, open_id = resolve_credentials()

    token = get_tenant_access_token(app_id, app_secret)
    print("Token 获取成功")

    print(f"准备发送图片: {image_path}")
    image_key = upload_image(token, image_path)
    send_image_message(token, open_id, image_key)
    print("完成!")


if __name__ == "__main__":
    main()
