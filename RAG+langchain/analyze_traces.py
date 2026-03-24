import os
import json
import argparse
from datetime import datetime
from collections import defaultdict


def _parse_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")
        except Exception:
            try:
                return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None


def _safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def _load_traces(dir_path):
    data = []
    if not os.path.isdir(dir_path):
        return data
    for fn in os.listdir(dir_path):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(dir_path, fn)
        try:
            with open(p, "r", encoding="utf-8") as f:
                j = json.load(f)
                data.append(j)
        except Exception:
            pass
    return data

def _load_single(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _estimate_tokens(step):
    tu = step.get("token_usage") or {}
    if tu:
        if "total_tokens" in tu:
            return int(tu.get("total_tokens") or 0), False
        pt = int(tu.get("prompt_tokens") or 0)
        ct = int(tu.get("completion_tokens") or 0)
        if pt or ct:
            return pt + ct, False
    out = step.get("output") or {}
    text = ""
    for k in ("answer", "content", "text"):
        if k in out and isinstance(out[k], str):
            text = out[k]
            break
    if not text:
        text = ""
    return max(1, len(text) // 4), True


def analyze(traces):
    n = len(traces)
    if n == 0:
        return {"n": 0}
    totals = []
    rounds = []
    step_stats = defaultdict(lambda: {"time_ms": 0.0, "calls": 0, "tokens": 0})
    bad_cases = []
    for t in traces:
        started = _parse_dt(t.get("started_at")) if t.get("started_at") else None
        ended = _parse_dt(t.get("ended_at")) if t.get("ended_at") else None
        steps = t.get("steps") or []
        if started and ended:
            totals.append((ended - started).total_seconds() * 1000.0)
        else:
            s = sum(float(sx.get("duration_ms") or 0.0) for sx in steps)
            totals.append(s)
        r = int(t.get("rounds") or 0)
        rounds.append(r)
        p = t.get("passed")
        if p is False or r > 3:
            bad_cases.append({"trace_id": t.get("trace_id"), "question": t.get("user_question"), "rounds": r, "passed": p})
        for s in steps:
            name = s.get("name") or "Unknown"
            dms = float(s.get("duration_ms") or 0.0)
            tokens, _ = _estimate_tokens(s)
            step_stats[name]["time_ms"] += dms
            step_stats[name]["tokens"] += tokens
            step_stats[name]["calls"] += 1
    total_time = sum(totals)
    avg_time = total_time / n if n else 0.0
    avg_rounds = sum(rounds) / n if n else 0.0
    return {
        "n": n,
        "avg_time_ms": avg_time,
        "avg_rounds": avg_rounds,
        "step_stats": dict(step_stats),
        "bad_cases": bad_cases,
    }

def _render_single_trace(trace):
    tid = trace.get("trace_id")
    q = trace.get("user_question")
    rounds = trace.get("rounds")
    passed = trace.get("passed")
    steps = trace.get("steps") or []
    print(f"trace_id: {tid}")
    print(f"question: {q}")
    print(f"rounds: {rounds}  passed: {passed}")
    print("")
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", justify="right")
        table.add_column("Step")
        table.add_column("Round", justify="right")
        table.add_column("ms", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Output(summary)")
        for i, s in enumerate(steps, 1):
            name = s.get("name")
            rnd = s.get("round")
            ms = f"{float(s.get('duration_ms') or 0.0):.1f}"
            tu = s.get("token_usage") or {}
            tok = tu.get("total_tokens") or ( (tu.get("prompt_tokens") or 0)+(tu.get("completion_tokens") or 0) )
            out = s.get("output") or {}
            # 简要拼接关键字段
            if name in ("Retriever", "Rerank"):
                size = out.get("size")
                srcs = out.get("sources") or []
                snippet = f"size={size}, src={srcs[:1]}"
            elif name == "Grader":
                snippet = f"{out.get('verdict')} score={out.get('score')}"
            elif name == "Rewriter":
                snippet = f"new={out.get('new_query')}"
            elif name == "Generator":
                snippet = f"answer={str(out.get('answer'))[:60]}"
            else:
                snippet = str(out)[:60]
            table.add_row(str(i), str(name), str(rnd), ms, str(tok), snippet)
        console.print(table)
    except Exception:
        print("#\tStep\tRound\tms\tTokens\tOutput")
        for i, s in enumerate(steps, 1):
            name = s.get("name")
            rnd = s.get("round")
            ms = f"{float(s.get('duration_ms') or 0.0):.1f}"
            tu = s.get("token_usage") or {}
            tok = tu.get("total_tokens") or ( (tu.get("prompt_tokens") or 0)+(tu.get("completion_tokens") or 0) )
            print(f"{i}\t{name}\t{rnd}\t{ms}\t{tok}\t...")  # 简略行


def _render_table(step_stats, total_time_ms):
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Step")
        table.add_column("Calls", justify="right")
        table.add_column("Avg ms", justify="right")
        table.add_column("% Time", justify="right")
        table.add_column("Avg Tokens", justify="right")
        for name, v in sorted(step_stats.items(), key=lambda kv: kv[1]["time_ms"], reverse=True):
            calls = v["calls"] or 1
            avg_ms = v["time_ms"] / calls
            pct = (v["time_ms"] / total_time_ms * 100.0) if total_time_ms > 0 else 0.0
            avg_tok = v["tokens"] / calls
            table.add_row(str(name), f"{calls}", f"{avg_ms:.1f}", f"{pct:.1f}%", f"{avg_tok:.1f}")
        console.print(table)
    except Exception:
        print("Step\tCalls\tAvg ms\t% Time\tAvg Tokens")
        for name, v in sorted(step_stats.items(), key=lambda kv: kv[1]["time_ms"], reverse=True):
            calls = v["calls"] or 1
            avg_ms = v["time_ms"] / calls
            pct = (v["time_ms"] / total_time_ms * 100.0) if total_time_ms > 0 else 0.0
            avg_tok = v["tokens"] / calls
            print(f"{name}\t{calls}\t{avg_ms:.1f}\t{pct:.1f}%\t{avg_tok:.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join("logs", "traces"))
    ap.add_argument("--file", help="analyze a specific trace JSON file")
    ap.add_argument("--id", dest="trace_id", help="only analyze traces with this trace_id")
    args = ap.parse_args()
    if args.file:
        tr = _load_single(args.file)
        if not tr:
            print("invalid file or cannot read")
            return
        _render_single_trace(tr)
        return

    traces = _load_traces(args.dir)
    if args.trace_id:
        traces = [t for t in traces if t.get("trace_id") == args.trace_id]
    res = analyze(traces)
    if res.get("n", 0) == 0:
        print("no traces")
        return
    print(f"requests: {res['n']}")
    print(f"avg_time_ms: {res['avg_time_ms']:.1f}")
    print(f"avg_rounds: {res['avg_rounds']:.2f}")
    total_time_ms = sum(v["time_ms"] for v in res["step_stats"].values())
    print("")
    _render_table(res["step_stats"], total_time_ms)
    print("")
    bad = res["bad_cases"]
    if bad:
        print("bad_cases:")
        for b in bad:
            tid = b.get("trace_id")
            q = b.get("question")
            r = b.get("rounds")
            p = b.get("passed")
            print(f"- {tid} | rounds={r} passed={p} | {q}")
    else:
        print("bad_cases: none")


if __name__ == "__main__":
    main()

