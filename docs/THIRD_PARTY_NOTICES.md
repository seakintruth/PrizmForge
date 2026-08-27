# Third-Party Notices

## mini-swe-agent (MIT)

Portions of `workflow/shell_developer.py` — specifically the query/execute control
loop, the fenced ```bash command protocol, consecutive-format-error handling, and
finish-sentinel session semantics — are derived from
[mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent).

```
MIT License

Copyright (c) 2025 SWE-agent contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The PrizmForge implementation differs materially from upstream: all model calls are
routed through PrizmForge's governed `call_endpoint()` stack (rate limiting, token
budget, endpoint health/fallback), execution occurs inside a disposable git worktree,
and all mutations pass through the proposal/Reviewer/materialize pipeline before
reaching the governed tree.
