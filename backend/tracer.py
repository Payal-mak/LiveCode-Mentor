import sys
import io
import contextlib
import ast
import builtins

def trace_code(code: str, max_steps: int = 50, mock_inputs: list = None):
    steps = []
    stdout_capture = io.StringIO()

    # Mock input() so it never hangs
    input_values = iter(mock_inputs or ["5", "1 2 3 4 5", "0", "10", "hello", "3"])

    def mock_input(prompt=""):
        try:
            val = next(input_values)
            stdout_capture.write(str(prompt))
            return val
        except StopIteration:
            return "0"

    def tracer(frame, event, arg):
        if event == 'line' and len(steps) < max_steps:
            if frame.f_code.co_filename == '<string>':
                local_vars = {}
                for k, v in frame.f_locals.items():
                    if not k.startswith('_'):
                        try:
                            # Handle different types nicely
                            if isinstance(v, (int, float, bool, str)):
                                local_vars[k] = repr(v)
                            elif isinstance(v, (list, tuple)):
                                if len(v) <= 10:
                                    local_vars[k] = repr(v)
                                else:
                                    local_vars[k] = f"{type(v).__name__}[{len(v)} items]"
                            elif isinstance(v, dict):
                                if len(v) <= 5:
                                    local_vars[k] = repr(v)
                                else:
                                    local_vars[k] = f"dict({len(v)} keys)"
                            elif callable(v):
                                pass  # Skip functions
                            else:
                                val = str(v)
                                local_vars[k] = val[:40] + "..." if len(val) > 40 else val
                        except:
                            local_vars[k] = "<?>"

                # Get the actual source line
                try:
                    source_lines = code.split('\n')
                    line_content = source_lines[frame.f_lineno - 1].strip()
                except:
                    line_content = ""

                steps.append({
                    "line": frame.f_lineno,
                    "line_content": line_content,
                    "vars": local_vars,
                })
        return tracer

    try:
        compiled = compile(code, '<string>', 'exec')

        safe_globals = {
            "__name__": "__main__",
            "__builtins__": {
                k: v for k, v in vars(builtins).items()
                if k not in ('open', 'eval', 'exec', '__import__')
            }
        }
        # Override input with mock
        safe_globals["__builtins__"]["input"] = mock_input
        safe_globals["input"] = mock_input

        with contextlib.redirect_stdout(stdout_capture):
            sys.settrace(tracer)
            exec(compiled, safe_globals)
            sys.settrace(None)

        return {
            "success": True,
            "steps": steps,
            "output": stdout_capture.getvalue(),
            "total_steps": len(steps)
        }

    except Exception as e:
        sys.settrace(None)
        return {
            "success": len(steps) > 0,
            "steps": steps,
            "error": str(e),
            "output": stdout_capture.getvalue(),
            "total_steps": len(steps)
        }
    finally:
        sys.settrace(None)