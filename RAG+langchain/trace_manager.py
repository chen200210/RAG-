import os
import json
import uuid
import time
import threading
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel
from trace_schema import Trace, Step


class _StepCtx(BaseModel):
    name: str
    round: int
    input: Dict[str, Any]
    t0: float
    started_at: datetime


class TraceManager:
    def __init__(self) -> None:
        self._trace: Optional[Trace] = None

    def start_trace(self, user_question: str, tags: Optional[Dict[str, Any]] = None) -> str:
        try:
            trace_id = str(uuid.uuid4())
            self._trace = Trace(trace_id=trace_id, user_question=user_question, tags=tags or {})
            return trace_id
        except Exception:
            return ""

    def start_step(self, name: str, round: int, input: Dict[str, Any]) -> _StepCtx:
        try:
            ctx = _StepCtx(name=name, round=round, input=input, t0=time.perf_counter(), started_at=datetime.utcnow())
            return ctx
        except Exception:
            return _StepCtx(name=name, round=round, input={}, t0=time.perf_counter(), started_at=datetime.utcnow())

    def end_step(self, ctx: _StepCtx, output: Dict[str, Any], token_usage: Dict[str, Any], error: Optional[str]) -> None:
        try:
            if self._trace is None:
                return
            dt_ms = (time.perf_counter() - ctx.t0) * 1000.0
            step = Step(
                name=ctx.name,
                round=ctx.round,
                input=ctx.input,
                output=output,
                token_usage=token_usage or {},
                duration_ms=dt_ms,
                started_at=ctx.started_at,
                ended_at=datetime.utcnow(),
                error=error,
            )
            self._trace.steps.append(step)
        except Exception:
            pass

    def end_trace(self, final_answer: str, passed: bool, rounds: int) -> None:
        try:
            if self._trace is None:
                return
            self._trace.final_answer = final_answer
            self._trace.passed = passed
            self._trace.rounds = rounds
            self._trace.ended_at = datetime.utcnow()
        except Exception:
            pass

    def dump_async(self, path: str) -> None:
        try:
            if self._trace is None:
                return
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = self._trace.model_dump()

            def _write(p: str, d: Dict[str, Any]) -> None:
                try:
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(d, f, ensure_ascii=False, indent=2, default=str)
                except Exception:
                    pass

            th = threading.Thread(target=_write, args=(path, data), daemon=False)
            th.start()
            # 在脚本生命周期很短的情况下，等待极短时间以避免空文件
            th.join(timeout=0.2)
        except Exception:
            pass

    def dump_sync(self, path: str) -> None:
        try:
            if self._trace is None:
                return
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = self._trace.model_dump()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception:
            pass


_GLOBAL_MANAGER: Optional[TraceManager] = None


def get_trace_manager() -> TraceManager:
    global _GLOBAL_MANAGER
    if _GLOBAL_MANAGER is None:
        _GLOBAL_MANAGER = TraceManager()
    return _GLOBAL_MANAGER

def _extract_token_usage_auto(result: Any) -> Dict[str, Any]:
    try:
        # LangChain AIMessage usage (0.2+)
        usage = getattr(result, "usage_metadata", None)
        if isinstance(usage, dict):
            tu = {
                "prompt_tokens": usage.get("input_tokens") or usage.get("prompt_tokens"),
                "completion_tokens": usage.get("output_tokens") or usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
            if any(v is not None for v in tu.values()):
                return tu
        # Some models put it into response_metadata
        resp_meta = getattr(result, "response_metadata", None)
        if isinstance(resp_meta, dict):
            raw = resp_meta.get("token_usage") or resp_meta.get("usage") or {}
            if isinstance(raw, dict):
                tu = {
                    "prompt_tokens": raw.get("prompt_tokens") or raw.get("input_tokens"),
                    "completion_tokens": raw.get("completion_tokens") or raw.get("output_tokens"),
                    "total_tokens": raw.get("total_tokens"),
                }
                if any(v is not None for v in tu.values()):
                    return tu
        # If wrapped in dict
        if isinstance(result, dict):
            u = result.get("usage_metadata") or result.get("token_usage") or {}
            if isinstance(u, dict):
                tu = {
                    "prompt_tokens": u.get("prompt_tokens") or u.get("input_tokens"),
                    "completion_tokens": u.get("completion_tokens") or u.get("output_tokens"),
                    "total_tokens": u.get("total_tokens"),
                }
                if any(v is not None for v in tu.values()):
                    return tu
    except Exception:
        pass
    return {}

def _safe_truncate(v: Any, limit: int = 300) -> Any:
    try:
        if isinstance(v, str) and len(v) > limit:
            return v[:limit]
        if isinstance(v, dict):
            return {k: _safe_truncate(v[k], limit) for k in v}
        if isinstance(v, list):
            return [_safe_truncate(x, limit) for x in v]
        return v
    except Exception:
        return v


def _estimate_tokens(text: str) -> int:
    try:
        return max(1, len(text) // 4)
    except Exception:
        return 0


def trace_step(
    name: str,
    round_from: Optional[Callable[..., int]] = None,
    input_fn: Optional[Callable[..., Dict[str, Any]]] = None,
    output_fn: Optional[Callable[[Any], Dict[str, Any]]] = None,
    token_usage_fn: Optional[Callable[[Any], Dict[str, Any]]] = None,
):
    def _decorator(func: Callable):
        def _wrapped(*args, **kwargs):
            tm = get_trace_manager()
            try:
                rnd = 1
                if round_from is not None:
                    try:
                        rnd = int(round_from(*args, **kwargs))
                    except Exception:
                        rnd = 1
                inp = {}
                if input_fn is not None:
                    try:
                        inp = _safe_truncate(input_fn(*args, **kwargs))
                    except Exception:
                        inp = {}
                ctx = tm.start_step(name=name, round=rnd, input=inp)
                err = None
                result = None
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    err = str(e)
                    raise
                finally:
                    out = {}
                    tu = {}
                    try:
                        if output_fn is not None:
                            out = _safe_truncate(output_fn(result))
                    except Exception:
                        out = {}
                    try:
                        if token_usage_fn is not None:
                            tu = token_usage_fn(result) or {}
                        if not tu:
                            tu = _extract_token_usage_auto(result)
                    except Exception:
                        tu = {}
                    tm.end_step(ctx, out, tu, err)
            except Exception:
                return func(*args, **kwargs)

        return _wrapped

    return _decorator
