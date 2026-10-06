# PR 1032: Responses state on Windows

Measured on 2026-10-06 for [Niko1221/Strata#1032](https://github.com/Niko1221/Strata/pull/1032).
Server source: `7b95e1979a3f14fb7e7949a30c25c1ea12da5240`.

Windows, AMD Radeon RX 7900 XT (HIP), Intel Core i5-13490F, 32 GiB installed system RAM (31.77 GiB reported by Windows).
Qwen3.8-Flash-Next IQ2_XS, 32,768-token context, int8 KV, resident experts, MTP speculation with 4 drafts
and the CJK draft vocabulary. The Responses store was 64 MiB with its default 3,600 s lifetime.
The temporary service listened only on 127.0.0.1:18080 and unloaded the model on exit.

## Result

[check_pr1032.py](check_pr1032.py), the standard-library Python HTTP client supplied for this PR, passed
all 10 checks: save, continuation, retrieval, streamed continuation and retrieval, deletion,
404 after deletion, continuation from a surviving child after parent deletion, and `store: false`.

| Request | Input tokens | Cached input tokens | Output tokens | Elapsed request time |
| --- | ---: | ---: | ---: | ---: |
| First turn, create/store | 784 | 0 | 2 | 6.969 s |
| Second turn, new input + previous_response_id | 812 | 777 | 7 | 0.875 s |

The second request reused 95.69% of its input tokens. This shows that the stored continuation used the
existing conversation cache in this run. These are two different prompts/answers in one small functional test,
not a controlled speed comparison or a general throughput benchmark. Elapsed time covers the whole HTTP request.

The official OpenAI Python SDK 3.24.0 also passed create, continuation, retrieval, streaming, deletion and
404-after-delete checks on this revision. An allowed CORS origin's DELETE without a body or Content-Type
returned 200 after an OPTIONS preflight. Model settings registration was exercised by enabling the store with
the helper's `enable` mode on a copy of the installed config.

[Native results](native-result.json) contain per-request usage and timings, check outcomes and the original
helper's SHA-256. The test harness also checked that the second turn reported a positive cached-token count.
The installed checkout and production config were not changed for this test.

## Unit and HTTP tests

Windows: 292 run, 0 failed, 5 environment-dependent skips (287 passed), in 136.044 s.
Optional test packages: `openai==3.24.0`, `jsonschema==4.26.0`.

```powershell
python -m unittest serve.test_responses serve.test_response_store serve.test_runconfig serve.test_server serve.test_security serve.test_structured serve.test_lifecycle serve.test_parallel serve.test_monitor serve.test_mcp serve.test_detok serve.test_winjob serve.test_vram
```

## Repeating the native checks

Use the PR's source revision and an already installed IQ2_XS engine/model. From its Strata checkout, start a
temporary localhost service in one PowerShell window (use your own config filename):

```powershell
$env:NO_PROXY = '127.0.0.1,localhost'
.venv\Scripts\python -m serve.server --engine strata --config strata-iq2_xs.json --port 18080 --responses-store-mib 64
```

Once it is ready, in a second window run the helper from this results folder, passing `--key` if required:

```powershell
$env:NO_PROXY = '127.0.0.1,localhost'
.venv\Scripts\python bench/results/2026-10-06-pr1032-windows-rx7900xt/check_pr1032.py --url http://127.0.0.1:18080
```

Stop the temporary service after the checks. Do not start a second engine while another model server is loaded.
The helper checks the API lifecycle; it does not assert answer quality or benchmark throughput.

[Prepared PR description](PR-description.txt) includes these measurements for the upstream PR.
