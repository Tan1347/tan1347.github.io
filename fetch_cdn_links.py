#!/usr/bin/env python3
"""
从腾讯CDN配置获取下载链接
- 基础链接: 从JS配置提取，长期有效
- 签名链接: 跟踪重定向获取，带token会过期
"""

import urllib.request
import urllib.error
import re
import json
import ssl
import sys
from datetime import datetime, timezone

# 忽略SSL验证（某些环境需要）
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch_url(url, timeout=10, follow_redirects=True):
    """获取URL内容"""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    if follow_redirects:
        # 获取最终URL（处理重定向）
        final_url = resp.url
        content = resp.read().decode('utf-8', errors='ignore')
        return final_url, content
    return resp.url, resp.read().decode('utf-8', errors='ignore')

def fetch_js_config():
    """从腾讯JS配置提取基础链接"""
    url = "https://img.itop.qq.com/js/1110613799.js"
    try:
        _, text = fetch_url(url)

        # 提取各字段
        def extract(field):
            m = re.search(rf"{field}:\s*'([^']+)'", text)
            return m.group(1) if m else None

        return {
            "version": extract("version"),
            "timestamp": extract("timestamp"),
            "androidURL": extract("androidURL"),
            "androidWechatURL": extract("androidWechatURL"),
            "androidMqqURL": extract("androidMqqURL"),
            "androidDefaultURL": extract("androidDefaultURL"),
        }
    except Exception as e:
        print(f"Failed to fetch JS config: {e}", file=sys.stderr)
        return None

def get_signed_url(intermediate_url, label):
    """跟踪重定向获取签名后的CDN链接"""
    try:
        final_url, _ = fetch_url(intermediate_url, timeout=15)
        # 检查是否是有效的CDN链接
        if any(domain in final_url for domain in ['dlied', 'cdntips', 'myapp.com', 'gtimg.cn']):
            return {"label": label, "url": final_url, "signed": True}
    except Exception as e:
        print(f"Failed to get signed URL for {label}: {e}", file=sys.stderr)
    return None

def check_url(url):
    """验证URL是否可访问"""
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=5, context=ctx)
        return resp.status == 200
    except:
        return False

def main():
    print("Fetching CDN links...")

    # 1. 获取JS配置中的基础链接
    config = fetch_js_config()
    if not config:
        print("Failed to fetch JS config, exiting", file=sys.stderr)
        sys.exit(1)

    print(f"Version: {config['version']}")

    # 2. 构建基础链接列表
    base_links = []
    if config['androidDefaultURL']:
        base_links.append({"label": "Android默认(基础)", "url": config['androidDefaultURL'], "signed": False})
    if config['androidWechatURL']:
        base_links.append({"label": "Android微信(基础)", "url": config['androidWechatURL'], "signed": False})
    if config['androidMqqURL']:
        base_links.append({"label": "AndroidQQ(基础)", "url": config['androidMqqURL'], "signed": False})
    if config['androidURL']:
        base_links.append({"label": "Android直链(基础)", "url": config['androidURL'], "signed": False})

    # 3. 跟踪重定向获取签名链接
    signed_links = []
    redirect_sources = [
        ("https://rocom.qq.com/zlkdatasys/mct/d/play.shtml?device=android", "Android签名CDN"),
    ]

    for src_url, label in redirect_sources:
        print(f"Following redirect: {src_url}")
        signed = get_signed_url(src_url, label)
        if signed:
            signed_links.append(signed)
            print(f"  -> {signed['url'][:80]}...")
        else:
            print(f"  -> Failed")

    # 4. 合并所有链接
    all_links = base_links + signed_links

    # 5. 验证链接可用性
    print("\nVerifying links...")
    for link in all_links:
        link['verified'] = check_url(link['url'])
        status = "OK" if link['verified'] else "FAIL"
        print(f"  [{status}] {link['label']}")

    # 6. 输出JSON
    output = {
        "version": config['version'],
        "timestamp": config['timestamp'],
        "fetchTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "links": all_links
    }

    with open('cdn-links.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(all_links)} links to cdn-links.json")
    print(f"  Base links: {len(base_links)}")
    print(f"  Signed links: {len(signed_links)}")

if __name__ == '__main__':
    main()
