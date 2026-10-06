"""PR 1032 真机验证（只用 Python 标准库）。把本文件放进 Strata 文件夹，在那里运行：

  第一次，打开存储:   .venv\\Scripts\\python check_pr1032.py enable
  启动 Strata 后验证: .venv\\Scripts\\python check_pr1032.py

有 API key 时加 --key 你的key；端口不是 8080 时加 --url http://127.0.0.1:端口
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL, KEY, RESULTS = "", "", []
LONG = "Strata runs a large mixture-of-experts model on one consumer graphics card plus system RAM. " * 40


def enable(config, mib):
    sys.path.insert(0, str(Path.cwd()))
    try:
        from serve import runconfig
    except ImportError:
        sys.exit("请在 Strata 文件夹里运行（这里要有 serve 目录）。")
    names = [config] if config else sorted(p.name for p in Path.cwd().glob("strata-*.json"))
    if len(names) != 1:
        sys.exit(f"找到的配置文件：{names or '没有'}。请把要用的那个写在 enable 后面，例如：enable strata-iq2_xs.json")
    path = Path(names[0])
    try:
        cfg, changed = runconfig.apply(runconfig.load(path), {"responses_store_mib": mib})
    except ValueError:
        sys.exit("这个 Strata 文件夹还不是 PR 的新代码（不认识 responses_store_mib），请先完成第 2 步换代码。")
    if changed:
        runconfig.save(path, cfg)
    print(f"已设置 {path.name}：responses_store_mib = {mib}（原文件备份为 {path.name}.bak）。现在重新启动 Strata。")


def call(method, path, body=None, stream=False):
    headers = {"Content-Type": "application/json"}
    if KEY:
        headers["Authorization"] = "Bearer " + KEY
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(URL + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            status, raw = r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read().decode("utf-8")
    except OSError as e:
        sys.exit(f"连不上 {URL}（{e}）：请确认 Strata 已启动，窗口里出现了 ready 那一行。")
    if status == 401:
        sys.exit("服务器设置了 API key：请在命令后面加 --key 你的key")
    if stream and status == 200:
        return status, [json.loads(x[6:]) for x in raw.splitlines() if x.startswith("data: ")]
    return status, (json.loads(raw) if raw else {})


def ask(text, **extra):
    body = {"model": "strata", "input": text, "reasoning": {"effort": "none"}, "max_output_tokens": 64, **extra}
    start = time.monotonic()
    status, out = call("POST", "/v1/responses", body, stream=bool(extra.get("stream")))
    return status, out, time.monotonic() - start


def ok(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("[通过] " if cond else "[失败] ") + name + (f"  ({detail})" if detail else ""), flush=True)
    return cond


def check():
    _, health = call("GET", "/health")
    print(f"服务器：{health.get('model')}，上下文 {health.get('max_context')}，已加载={health.get('loaded')}", flush=True)
    status, body = call("GET", "/v1/responses/resp_check/input_items")
    if not ok("服务器运行的是 PR 的新代码", status == 404 and "not supported" in str(body)):
        sys.exit("请先完成第 2 步（换成新代码），并重新启动 Strata。")

    status, r1, t1 = ask("Read this and remember it:\n" + LONG + "\nReply with OK.")
    if not ok("第 1 轮：创建并保存", status == 200 and r1.get("store") is True, f"{t1:.1f} s"):
        sys.exit("存储没有打开：先运行  check_pr1032.py enable  ，再重新启动 Strata。" if status == 200 else str(r1))
    status, r2, t2 = ask("What does the text say runs the model? One short sentence.", previous_response_id=r1["id"])
    usage = r2.get("usage") or {}
    total, cached = usage.get("input_tokens", 0), (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
    ok("第 2 轮：按 ID 续接", status == 200 and r2.get("previous_response_id") == r1["id"],
       f"{t2:.1f} s, input_tokens={total}, cached_tokens={cached}" + (f" ({cached / total:.0%})" if total else ""))
    status, got = call("GET", "/v1/responses/" + r2["id"])
    ok("按 ID 取回", status == 200 and got.get("output") == r2.get("output"))

    status, events, _ = ask("Say it again in five words.", previous_response_id=r2["id"], stream=True)
    r3 = (events[-1] if events else {}).get("response") or {}
    ok("流式续接", status == 200 and events and events[-1].get("type") == "response.completed")
    ok("流式结果可取回", call("GET", "/v1/responses/" + r3.get("id", "resp_none"))[0] == 200)

    status, child, _ = ask("Answer only: how many graphics cards?", previous_response_id=r1["id"])
    status, deleted = call("DELETE", "/v1/responses/" + r1["id"])
    ok("删除", status == 200 and deleted.get("deleted") is True)
    ok("删除后再取回是 404", call("GET", "/v1/responses/" + r1["id"])[0] == 404)
    status, grand, _ = ask("And what else does it use?", previous_response_id=child.get("id"))
    ok("父响应删掉后，子响应仍能续接", status == 200)
    status, unsaved, _ = ask("One word.", previous_response_id=r2["id"], store=False)
    ok("store: false 能续接且不保存",
       status == 200 and unsaved.get("store") is False and call("GET", "/v1/responses/" + unsaved["id"])[0] == 404)
    for r in (r2, r3, child, grand):                  # 清理本脚本存下的记录
        if r.get("id"):
            call("DELETE", "/v1/responses/" + r["id"])

    failed = [name for name, good in RESULTS if not good]
    print("\n==== 把下面这几行整段发给 Claude ====")
    print(f"model={health.get('model')} max_context={health.get('max_context')}")
    print(f"turn1: {t1:.1f} s, input_tokens={(r1.get('usage') or {}).get('input_tokens')}")
    print(f"turn2 (previous_response_id): {t2:.1f} s, input_tokens={total}, cached_tokens={cached}")
    print(f"checks: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed" + (f"; failed: {failed}" if failed else ""))


def main():
    global URL, KEY
    sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="PR 1032 真机验证")
    ap.add_argument("mode", nargs="?", default="check", choices=["check", "enable"])
    ap.add_argument("config", nargs="?", help="enable 时的配置文件名，例如 strata-iq2_xs.json")
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--key", default="")
    ap.add_argument("--mib", type=int, default=64)
    a = ap.parse_args()
    URL, KEY = a.url.rstrip("/"), a.key
    if a.mode == "enable":
        enable(a.config, a.mib)
    else:
        check()


if __name__ == "__main__":
    main()
