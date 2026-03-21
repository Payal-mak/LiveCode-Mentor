import sys
import io
import contextlib
import ast

def trace_code(code: str, max_steps: int = 30):
    steps = []
    output_lines = []

    def tracer(frame, event, arg):
        if event == 'line' and len(steps) < max_steps:
            # Only trace the main script, not stdlib
            if frame.f_code.co_filename == '<string>':
                local_vars = {}
                for k, v in frame.f_locals.items():
                    if not k.startswith('_'):
                        try:
                            # Safely convert to string, limit length
                            val = str(v)
                            if len(val) > 40:
                                val = val[:40] + '...'
                            local_vars[k] = val
                        except:
                            local_vars[k] = '<?>'
                steps.append({
                    "line": frame.f_lineno,
                    "vars": local_vars,
                    "event": event
                })
        return tracer

    stdout_capture = io.StringIO()

    try:
        # Compile first to check syntax
        compiled = compile(code, '<string>', 'exec')

        # Run with tracer and captured stdout
        with contextlib.redirect_stdout(stdout_capture):
            sys.settrace(tracer)
            exec(compiled, {"__name__": "__main__"})
            sys.settrace(None)

        output = stdout_capture.getvalue()
        return {
            "success": True,
            "steps": steps,
            "output": output,
            "total_steps": len(steps)
        }

    except SyntaxError as e:
        sys.settrace(None)
        return {
            "success": False,
            "steps": [],
            "error": f"Syntax error on line {e.lineno}: {e.msg}",
            "output": ""
        }
    except Exception as e:
        sys.settrace(None)
        return {
            "success": False,
            "steps": steps,
            "error": str(e),
            "output": stdout_capture.getvalue()
        }
    finally:
        sys.settrace(None)