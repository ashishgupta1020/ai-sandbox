import builtins
from io import StringIO
from contextlib import redirect_stdout


def test_cli_fails_when_api_unavailable():
    # No server started here; CLI should fail fast
    from taskman.cli import task_manager
    from tempfile import TemporaryDirectory
    import json, os
    original_input = builtins.input
    # Provide any input; CLI should return before reading input
    with TemporaryDirectory() as tmp:
        cfg = os.path.join(tmp, "config.json")
        with open(cfg, "w") as fh:
            json.dump({"DATA_STORE_PATH": tmp}, fh)
        args = ["--config", cfg]
        builtins.input = lambda prompt=None: "4"
        try:
            with StringIO() as buf, redirect_stdout(buf):
                task_manager.main_cli(args)
                output = buf.getvalue()
            assert "Error: Taskman API is not available." in output
        finally:
            builtins.input = original_input
