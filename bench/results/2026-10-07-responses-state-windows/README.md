# Responses state on the rewritten main: Windows validation

Measured on 2026-10-07 for the replacement of [PR #1032](https://github.com/Niko1221/Strata/pull/1032).

Published feature commit: [30ee0c3](https://github.com/mdwsk88/Strata/commit/30ee0c375313266abd3200687e4609358bf5e8f4).
Base: `82f46a8c8f475f001ad76d92f58f4a4f8ffb0253`.
The test ran on local cherry-pick `c580645e5a986aadb1a4aed5b0a89f48e9230f14`; its complete source tree
`ee65a94ab40f8b5d92732446c3c4d4b56e3c97f7` was verified identical to the published commit's tree.

Windows, AMD Radeon RX 7900 XT (HIP), Intel Core i5-13490F, 32 GiB installed RAM.
The already installed Qwen3.8-Flash-Next IQ2_XS engine/model was used with a 32,768-token context, int8 KV,
resident experts, 4 MTP drafts and CJK draft vocabulary. The Responses store was 64 MiB.
This validates the changed Python API against that installed engine; the native engine was not rebuilt.

## Native result

The [same standard-library HTTP helper](../2026-10-06-pr1032-windows-rx7900xt/check_pr1032.py) passed all
10 checks. The OpenAI Python SDK 3.24.0 also passed create, continuation, retrieve, streaming and delete/404 checks.
An allowed CORS origin's DELETE without a body or Content-Type succeeded after its preflight.
The temporary server listened on 127.0.0.1:18080 and unloaded the model on exit.

| Request | Input tokens | Cached input tokens | Output tokens | Whole request time |
| --- | ---: | ---: | ---: | ---: |
| Create/store | 784 | 0 | 2 | 8.531 s |
| New input with previous_response_id | 812 | 777 | 7 | 1.109 s |

The continuation reused 95.69% of its input tokens. These are different prompts/answers in one functional check,
not a controlled speed comparison or a general throughput benchmark. [native-result.json](native-result.json)
contains the measured usage, timings, individual outcomes and source identities.

To repeat, start the PR's Python server with an already installed engine/model and run the linked helper
from a second PowerShell window:

```powershell
$env:NO_PROXY = '127.0.0.1,localhost'
.venv\Scripts\python -m serve.server --engine strata --config strata-iq2_xs.json --port 18080 --responses-store-mib 64
# Once ready, in the second window, using your downloaded helper path:
.venv\Scripts\python check_pr1032.py --url http://127.0.0.1:18080
```

Use the appropriate config filename and API key. Do not load a second model concurrently. Stop the temporary
service after checking. The installed checkout/config were not changed by this validation.

## Unit and service regression tests

476 tests across the two commands below: 470 passed, 6 environment-dependent skips.
The 54 Responses/config tests passed in 20.560 s; the 422 regression tests passed in 168.644 s.
Optional dependencies were `openai==3.24.0` and `jsonschema==4.26.0`.

The initial regression run had one failure in upstream's
`serve.test_slots.Slots.test_relative_save_dir_becomes_absolute`: the default Windows TEMP used an 8.3 user
directory name, while the assertion expected its expanded long path. The same failure was reproduced in a
clean checkout of upstream `82f46a8`. A long-path TEMP/TMP directory made that test and the complete regression
run pass; no production code was changed for this environment issue.

```powershell
python -m unittest serve.test_responses serve.test_response_store serve.test_runconfig
$testTemp = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'strata-test-temp'
New-Item -ItemType Directory -Force $testTemp | Out-Null
$env:TEMP = $testTemp
$env:TMP = $testTemp
python -m unittest serve.test_server serve.test_security serve.test_structured serve.test_lifecycle serve.test_parallel serve.test_monitor serve.test_mcp serve.test_detok serve.test_winjob serve.test_vram serve.test_slots serve.test_restart_waiters serve.test_reasoning_tools serve.test_reasoning_rescue serve.test_reasoning_loop_recovery serve.test_frontend serve.test_fatal_recovery serve.test_control_cancel
```

[Prepared replacement PR description](PR-description.txt).
