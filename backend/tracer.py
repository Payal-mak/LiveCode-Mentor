# backend/tracer.py
# Execution tracer — uses sys.settrace to walk Python code line by line.
# Returns steps with line number, source content, and variable snapshot.

import sys
import io
import copy
import textwrap
import traceback
from typing import Any


# ── Helpers ────────────────────────────────────────────────────────────────────

_SAFE_TYPES = (int, float, bool, str, type(None))

def _safe_repr(val: Any, depth: int = 0) -> str:
    """Return a short, safe string representation of a value."""
    if depth > 2:
        return "..."
    if isinstance(val, _SAFE_TYPES):
        r = repr(val)
        return r if len(r) <= 60 else r[:57] + "..."
    if isinstance(val, (list, tuple)):
        bracket = ("[", "]") if isinstance(val, list) else ("(", ")")
        inner = [_safe_repr(v, depth + 1) for v in val[:6]]
        suffix = ", ..." if len(val) > 6 else ""
        return bracket[0] + ", ".join(inner) + suffix + bracket[1]
    if isinstance(val, dict):
        items = [f"{_safe_repr(k, depth+1)}: {_safe_repr(v, depth+1)}" for k, v in list(val.items())[:5]]
        suffix = ", ..." if len(val) > 5 else ""
        return "{" + ", ".join(items) + suffix + "}"
    if isinstance(val, set):
        items = [_safe_repr(v, depth + 1) for v in list(val)[:5]]
        suffix = ", ..." if len(val) > 5 else ""
        return "{" + ", ".join(items) + suffix + "}"
    try:
        r = repr(val)
        return r if len(r) <= 60 else r[:57] + "..."
    except Exception:
        return "<unprintable>"


def _snapshot_vars(frame_locals: dict) -> dict:
    """
    Extract user-visible variables from a frame's locals.
    Skips dunder names, imported modules, functions, classes.
    """
    import types
    skip_types = (types.ModuleType, types.FunctionType, type)
    result = {}
    for k, v in frame_locals.items():
        if k.startswith("__"):
            continue
        if isinstance(v, skip_types):
            continue
        try:
            result[k] = _safe_repr(v)
        except Exception:
            pass
    return result


# ── Core tracer ────────────────────────────────────────────────────────────────

def trace_code(code: str, max_steps: int = 60, mock_inputs: list[str] | None = None) -> dict:
    """
    Execute `code` under sys.settrace and return a step-by-step trace.

    Returns:
        {
          "steps":       [ {"line": int, "line_content": str, "vars": dict}, ... ],
          "output":      str,
          "success":     bool,
          "error":       str | None,
          "total_steps": int,
        }
    """
    # Normalise indentation (handles pasted code with leading spaces)
    code = textwrap.dedent(code)
    source_lines = code.splitlines()

    steps: list[dict] = []
    output_buf = io.StringIO()
    error_msg: str | None = None
    success = True

    # Mock input() if needed
    mock_iter = iter(mock_inputs or [])

    def mock_input(prompt=""):
        try:
            val = next(mock_iter)
            # Echo prompt + value to output so the stepper shows it
            if prompt:
                output_buf.write(str(prompt))
            output_buf.write(str(val) + "\n")
            return val
        except StopIteration:
            return ""

    # The trace function called by Python on every line/call/return
    # We only care about 'line' events in the top-level frame (and called frames).
    target_filename = "<string>"

    def tracer(frame, event, arg):
        nonlocal steps
        if event != "line":
            return tracer  # keep tracing sub-calls
        if frame.f_code.co_filename != target_filename:
            return tracer  # skip stdlib internals

        lineno = frame.f_lineno
        if len(steps) >= max_steps:
            return None  # stop tracing — too many steps

        line_content = ""
        if 1 <= lineno <= len(source_lines):
            line_content = source_lines[lineno - 1].rstrip()

        # Snapshot locals — copy so later mutations don't affect earlier steps
        try:
            vars_snap = _snapshot_vars(dict(frame.f_locals))
        except Exception:
            vars_snap = {}

        steps.append({
            "line":         lineno,
            "line_content": line_content,
            "vars":         vars_snap,
        })
        return tracer

    # Build sandbox globals — give access to builtins but override input/print
    sandbox_globals = {
        "__name__":    "__main__",
        "__builtins__": __builtins__,
        "input":        mock_input,
        "print":        lambda *a, **kw: output_buf.write(
                            " ".join(str(x) for x in a) +
                            kw.get("end", "\n")
                        ),
    }

    old_trace = sys.gettrace()
    try:
        compiled = compile(code, target_filename, "exec")
        sys.settrace(tracer)
        exec(compiled, sandbox_globals)  # noqa: S102
    except Exception as exc:
        success = False
        tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        # Filter out our own frames from the traceback
        filtered = [l for l in tb_lines if 'tracer.py' not in l and 'exec(compiled' not in l]
        error_msg = "".join(filtered).strip()
        if not error_msg:
            error_msg = f"{type(exc).__name__}: {exc}"
    finally:
        sys.settrace(old_trace)

    output = output_buf.getvalue()

    # If we got zero steps (e.g. empty/comment-only code), return a clear message
    if not steps and not error_msg:
        return {
            "steps":       [],
            "output":      output,
            "success":     False,
            "error":       "No executable lines found. Add some Python code and try again.",
            "total_steps": 0,
        }

    return {
        "steps":       steps,
        "output":      output,
        "success":     success,
        "error":       error_msg,
        "total_steps": len(steps),
    }
