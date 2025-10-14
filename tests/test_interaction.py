import types
import unittest
from io import StringIO
from unittest.mock import Mock, patch

from taskman.cli.interaction import DEFAULT_SELECTION_PROMPT, Interaction
from taskman.server.task import Task


class _FakeStdin:
    def __init__(self, chars):
        self._chars = iter(chars)

    def fileno(self):
        return 0

    def read(self, _):
        return next(self._chars)


class InteractionSelectionTests(unittest.TestCase):
    # --- select_from_list -------------------------------------------------
    def test_select_from_list_numeric_choice(self):
        options = ["Alpha", "Beta", "Gamma"]
        with patch("sys.stdin.isatty", return_value=False), patch(
            "sys.stdout.isatty", return_value=False
        ), patch("builtins.input", side_effect=["2"]):
            result = Interaction.select_from_list(options)
        self.assertEqual(result, 1)

    def test_select_from_list_accepts_default_on_enter(self):
        options = ["Alpha", "Beta", "Gamma"]
        with patch("sys.stdin.isatty", return_value=False), patch(
            "sys.stdout.isatty", return_value=False
        ), patch("builtins.input", side_effect=[""]):
            result = Interaction.select_from_list(options, default_index=2)
        self.assertEqual(result, 2)

    def test_select_from_list_tty_path_calls_arrow_handler(self):
        options = ["Only choice"]
        with patch("sys.stdin.isatty", return_value=True), patch(
            "sys.stdout.isatty", return_value=True
        ), patch.object(
            Interaction, "_select_with_arrow_keys", return_value=0
        ) as arrow_handler, patch.object(Interaction, "_show_cursor") as show_cursor:
            result = Interaction.select_from_list(options)
        arrow_handler.assert_called_once_with(options, DEFAULT_SELECTION_PROMPT, 0)
        show_cursor.assert_called()
        self.assertEqual(result, 0)

    def test_select_from_list_raises_on_empty(self):
        with self.assertRaises(ValueError):
            Interaction.select_from_list([])

    # --- _select_with_numeric_input / _render_options ---------------------
    def test_select_with_numeric_input_loops_until_valid(self):
        options = ["One", "Two", "Three"]
        with patch("builtins.input", side_effect=["invalid", "", "3"]):
            result = Interaction._select_with_numeric_input(options, "Prompt", default_index=1)
        self.assertEqual(result, 1)

    def test_select_with_numeric_input_handles_exact_choice(self):
        options = ["First", "Second", "Third"]
        with patch("builtins.input", side_effect=["5", "3"]):
            result = Interaction._select_with_numeric_input(options, "Prompt", default_index=0)
        self.assertEqual(result, 2)

    def test_select_with_arrow_keys_supports_digit_shortcut(self):
        options = ["One", "Two", "Three"]
        display_options = [f"{idx + 1}. {option}" for idx, option in enumerate(options)]
        with patch.object(Interaction, "_read_key", side_effect=["2", "ENTER"]), patch.object(
            Interaction, "_hide_cursor"
        ), patch.object(Interaction, "_render_options") as render_mock:
            result = Interaction._select_with_arrow_keys(options, "Prompt", default_index=0)
        self.assertEqual(result, 1)
        render_mock.assert_any_call(display_options, 1)
        render_mock.assert_any_call(display_options, 1, move_cursor=False)

    def test_select_with_arrow_keys_resets_out_of_range_default(self):
        options = ["A", "B"]
        display_options = [f"{idx + 1}. {option}" for idx, option in enumerate(options)]
        with patch.object(Interaction, "_read_key", side_effect=["ENTER"]), patch.object(
            Interaction, "_hide_cursor"
        ), patch.object(Interaction, "_render_options") as render_mock:
            result = Interaction._select_with_arrow_keys(options, "Prompt", default_index=99)
        self.assertEqual(result, 0)
        render_mock.assert_any_call(display_options, 0, move_cursor=False)

    def test_select_with_arrow_keys_handles_up_and_down(self):
        options = ["One", "Two", "Three"]
        display_options = [f"{idx + 1}. {option}" for idx, option in enumerate(options)]
        with patch.object(
            Interaction, "_read_key", side_effect=["DOWN", "UP", "ENTER"]
        ), patch.object(Interaction, "_hide_cursor"), patch.object(
            Interaction, "_render_options"
        ) as render_mock:
            result = Interaction._select_with_arrow_keys(options, "Prompt", default_index=0)
        self.assertEqual(result, 0)
        render_mock.assert_any_call(display_options, 1)
        render_mock.assert_any_call(display_options, 0, move_cursor=False)

    def test_render_options_outputs_indicator(self):
        buf = StringIO()
        with patch("taskman.cli.interaction.sys.stdout", buf):
            Interaction._render_options(["1. Foo", "2. Bar"], 1, move_cursor=True)
        output = buf.getvalue()
        self.assertIn("> 2. Bar", output)
        self.assertIn("\x1b[2F", output)

    def test_hide_and_show_cursor_write_escape_sequences(self):
        buf = StringIO()
        with patch("taskman.cli.interaction.sys.stdout", buf):
            Interaction._hide_cursor()
        self.assertIn("\x1b[?25l", buf.getvalue())

        buf = StringIO()
        with patch("taskman.cli.interaction.sys.stdout", buf):
            Interaction._show_cursor()
        self.assertIn("\x1b[?25h", buf.getvalue())

    # --- Grouped selection helpers ---------------------------------------
    def test_select_from_grouped_list_numeric_choice(self):
        groups = [("Group A", ["One", "Two"]), ("Group B", ["Three"])]
        with patch("sys.stdin.isatty", return_value=False), patch(
            "sys.stdout.isatty", return_value=False
        ), patch("builtins.input", side_effect=["3"]):
            result = Interaction.select_from_grouped_list(groups)
        self.assertEqual(result, 2)

    def test_select_from_grouped_list_tty_path_calls_arrow_handler(self):
        groups = [("Group A", ["One"]), ("Group B", ["Two"])]
        with patch("sys.stdin.isatty", return_value=True), patch(
            "sys.stdout.isatty", return_value=True
        ), patch.object(
            Interaction, "_select_grouped_with_arrow_keys", return_value=1
        ) as arrow_handler, patch.object(Interaction, "_show_cursor") as show_cursor:
            result = Interaction.select_from_grouped_list(groups)
        arrow_handler.assert_called_once_with(groups, DEFAULT_SELECTION_PROMPT, 0)
        show_cursor.assert_called()
        self.assertEqual(result, 1)

    def test_select_from_grouped_list_raises_when_no_options(self):
        with self.assertRaises(ValueError):
            Interaction.select_from_grouped_list([("Empty", [])])

    def test_select_from_grouped_list_accepts_default_on_enter(self):
        groups = [("Group", ["First", "Second"])]
        with patch("sys.stdin.isatty", return_value=False), patch(
            "sys.stdout.isatty", return_value=False
        ), patch("builtins.input", side_effect=[""]):
            result = Interaction.select_from_grouped_list(groups, default_index=1)
        self.assertEqual(result, 1)

    def test_select_grouped_with_numeric_input_accepts_default(self):
        groups = [("A", ["One", "Two"]), ("B", ["Three"])]
        with patch("builtins.input", side_effect=["invalid", "", "2"]):
            result = Interaction._select_grouped_with_numeric_input(groups, "Prompt", default_index=1)
        self.assertEqual(result, 1)

    def test_select_grouped_with_numeric_input_handles_exact_choice(self):
        groups = [("Section", ["First", "Second", "Third"])]
        with patch("builtins.input", side_effect=["5", "3"]):
            result = Interaction._select_grouped_with_numeric_input(groups, "Prompt", default_index=0)
        self.assertEqual(result, 2)

    def test_select_grouped_with_numeric_input_raises_without_options(self):
        with self.assertRaises(ValueError):
            Interaction._select_grouped_with_numeric_input([("Empty", [])], "Prompt")

    def test_select_grouped_with_numeric_input_skips_empty_groups(self):
        groups = [("Empty", []), ("Filled", ["Only Choice"])]
        with patch("builtins.input", side_effect=["", "1"]):
            result = Interaction._select_grouped_with_numeric_input(groups, "Prompt", default_index=0)
        self.assertEqual(result, 0)

    def test_render_grouped_options_outputs_headings(self):
        groups = [("Section A", ["Alpha", "Beta"]), ("Section B", ["Gamma"])]
        buf = StringIO()
        with patch("taskman.cli.interaction.sys.stdout", buf):
            Interaction._render_grouped_options(groups, 2, move_cursor=True)
        output = buf.getvalue()
        self.assertIn("Section A", output)
        self.assertIn("> 3. Gamma", output)
        self.assertIn("\x1b[", output.splitlines()[-1])

    def test_render_grouped_options_skips_empty_groups(self):
        groups = [("Empty", []), ("Non-empty", ["Item"])]
        buf = StringIO()
        with patch("taskman.cli.interaction.sys.stdout", buf):
            Interaction._render_grouped_options(groups, 0, move_cursor=False)
        output = buf.getvalue()
        self.assertIn("Non-empty", output)
        self.assertNotIn("Empty", output)

    def test_select_grouped_with_arrow_keys_navigates(self):
        groups = [("A", ["One", "Two"]), ("B", ["Three"])]
        with patch.object(
            Interaction, "_read_key", side_effect=["DOWN", "DOWN", "ENTER"]
        ), patch.object(Interaction, "_hide_cursor"), patch.object(
            Interaction, "_render_grouped_options"
        ) as render_mock:
            result = Interaction._select_grouped_with_arrow_keys(groups, "Prompt", default_index=0)
        self.assertEqual(result, 2)
        render_mock.assert_any_call(groups, 2, move_cursor=False)

    def test_select_grouped_with_arrow_keys_resets_out_of_range_default(self):
        groups = [("G", ["A", "B"])]
        with patch.object(
            Interaction, "_read_key", side_effect=["ENTER"]
        ), patch.object(Interaction, "_hide_cursor"), patch.object(
            Interaction, "_render_grouped_options"
        ) as render_mock:
            result = Interaction._select_grouped_with_arrow_keys(groups, "Prompt", default_index=99)
        self.assertEqual(result, 0)
        render_mock.assert_any_call(groups, 0, move_cursor=False)

    def test_select_grouped_with_arrow_keys_handles_up(self):
        groups = [("A", ["One", "Two", "Three"])]
        with patch.object(
            Interaction, "_read_key", side_effect=["UP", "ENTER"]
        ), patch.object(Interaction, "_hide_cursor"), patch.object(
            Interaction, "_render_grouped_options"
        ) as render_mock:
            result = Interaction._select_grouped_with_arrow_keys(groups, "Prompt", default_index=1)
        self.assertEqual(result, 0)
        render_mock.assert_any_call(groups, 0)
        render_mock.assert_any_call(groups, 0, move_cursor=False)

    def test_select_grouped_with_arrow_keys_accepts_numeric_shortcut(self):
        groups = [("A", ["One", "Two", "Three"])]
        with patch.object(
            Interaction, "_read_key", side_effect=["3", "ENTER"]
        ), patch.object(Interaction, "_hide_cursor"), patch.object(
            Interaction, "_render_grouped_options"
        ) as render_mock:
            result = Interaction._select_grouped_with_arrow_keys(groups, "Prompt", default_index=0)
        self.assertEqual(result, 2)
        render_mock.assert_any_call(groups, 2)

    def test_select_grouped_with_arrow_keys_raises_without_options(self):
        with self.assertRaises(ValueError):
            Interaction._select_grouped_with_arrow_keys([("Empty", [])], "Prompt")

    def test_flatten_grouped_options(self):
        groups = [("A", ["One"]), ("B", ["Two", "Three"]), ("C", [])]
        flattened = Interaction._flatten_grouped_options(groups)
        self.assertEqual(flattened, ["One", "Two", "Three"])

    # --- CLI data entry helpers ------------------------------------------
    def test_get_task_details_collects_inputs(self):
        inputs = ["Summary", "Assignee", "Remark line 1", "Remark line 2", ""]
        with patch("builtins.input", side_effect=inputs), patch.object(
            Interaction, "select_from_list", side_effect=[1, 2]
        ):
            task = Interaction.get_task_details()
        self.assertEqual(task.summary, "Summary")
        self.assertEqual(task.assignee, "Assignee")
        self.assertEqual(task.remarks, "Remark line 1\nRemark line 2")
        self.assertEqual(task.status.value, "In Progress")
        self.assertEqual(task.priority.value, "High")

    def test_edit_task_details_updates_fields(self):
        existing = Task("Old summary", "Old assignee", "Old remarks", "Not Started", "Low")
        inputs = ["New summary", "New assignee", "Updated remark", ""]
        with patch("builtins.input", side_effect=inputs), patch.object(
            Interaction, "select_from_list", side_effect=[2, 1]
        ):
            updated = Interaction.edit_task_details(existing)
        self.assertEqual(updated.summary, "New summary")
        self.assertEqual(updated.assignee, "New assignee")
        self.assertEqual(updated.remarks, "Updated remark")
        self.assertEqual(updated.status.value, "Completed")
        self.assertEqual(updated.priority.value, "Medium")

    def test_edit_task_details_keeps_existing_remarks_on_blank(self):
        existing = Task("Summary", "Assignee", "Keep remarks", "In Progress", "Medium")
        inputs = ["", "", ""]
        with patch("builtins.input", side_effect=inputs), patch.object(
            Interaction, "select_from_list", side_effect=[1, 1]
        ):
            updated = Interaction.edit_task_details(existing)
        self.assertEqual(updated.remarks, "Keep remarks")

    def test_get_project_name_uses_input(self):
        with patch("builtins.input", return_value="My Project") as mock_input:
            name = Interaction.get_project_name("Prompt?")
        self.assertEqual(name, "My Project")
        mock_input.assert_called_once_with("Prompt?")

    # --- _read_key -------------------------------------------------------
    def test_read_key_windows_arrow_sequence(self):
        fake_msvcrt = types.SimpleNamespace()
        fake_msvcrt.getwch = Mock(side_effect=["\x00", "H"])
        with patch.dict("sys.modules", {"msvcrt": fake_msvcrt}, clear=False):
            with patch("taskman.cli.interaction.os.name", "nt"):
                key = Interaction._read_key()
        self.assertEqual(key, "UP")

    def test_read_key_windows_down_and_unknown(self):
        fake_msvcrt = types.SimpleNamespace()
        fake_msvcrt.getwch = Mock(side_effect=["\x00", "P"])
        with patch.dict("sys.modules", {"msvcrt": fake_msvcrt}, clear=False):
            with patch("taskman.cli.interaction.os.name", "nt"):
                key = Interaction._read_key()
        self.assertEqual(key, "DOWN")

        fake_msvcrt.getwch = Mock(side_effect=["\x00", "X"])
        with patch.dict("sys.modules", {"msvcrt": fake_msvcrt}, clear=False):
            with patch("taskman.cli.interaction.os.name", "nt"):
                key = Interaction._read_key()
        self.assertEqual(key, "")

    def test_read_key_windows_enter(self):
        fake_msvcrt = types.SimpleNamespace()
        fake_msvcrt.getwch = Mock(return_value="\r")
        with patch.dict("sys.modules", {"msvcrt": fake_msvcrt}, clear=False):
            with patch("taskman.cli.interaction.os.name", "nt"):
                key = Interaction._read_key()
        self.assertEqual(key, "ENTER")

    def test_read_key_windows_k_and_j(self):
        fake_msvcrt = types.SimpleNamespace()
        fake_msvcrt.getwch = Mock(return_value="k")
        with patch.dict("sys.modules", {"msvcrt": fake_msvcrt}, clear=False):
            with patch("taskman.cli.interaction.os.name", "nt"):
                key = Interaction._read_key()
        self.assertEqual(key, "K")

        fake_msvcrt.getwch = Mock(return_value="j")
        with patch.dict("sys.modules", {"msvcrt": fake_msvcrt}, clear=False):
            with patch("taskman.cli.interaction.os.name", "nt"):
                key = Interaction._read_key()
        self.assertEqual(key, "J")

    def test_read_key_windows_passthrough_character(self):
        fake_msvcrt = types.SimpleNamespace()
        fake_msvcrt.getwch = Mock(return_value="x")
        with patch.dict("sys.modules", {"msvcrt": fake_msvcrt}, clear=False):
            with patch("taskman.cli.interaction.os.name", "nt"):
                key = Interaction._read_key()
        self.assertEqual(key, "x")

    def test_read_key_posix_arrow_sequence(self):
        fake_termios = types.SimpleNamespace(
            tcgetattr=Mock(return_value="orig"),
            tcsetattr=Mock(),
            TCSADRAIN="drain",
        )
        fake_tty = types.SimpleNamespace(setraw=Mock())
        fake_stdin = _FakeStdin(["\x1b", "[", "B"])
        with patch.dict(
            "sys.modules",
            {"termios": fake_termios, "tty": fake_tty},
            clear=False,
        ):
            with patch("taskman.cli.interaction.os.name", "posix"), patch(
                "taskman.cli.interaction.sys.stdin", fake_stdin
            ):
                key = Interaction._read_key()
        self.assertEqual(key, "DOWN")
        fake_termios.tcsetattr.assert_called_once_with(0, "drain", "orig")
        fake_tty.setraw.assert_called_once()

    def test_read_key_posix_enter_and_letters(self):
        fake_termios = types.SimpleNamespace(
            tcgetattr=Mock(return_value="orig"),
            tcsetattr=Mock(),
            TCSADRAIN="drain",
        )
        fake_tty = types.SimpleNamespace(setraw=Mock())

        for chars, expected in (
            (["\r"], "ENTER"),
            (["k"], "K"),
            (["j"], "J"),
        ):
            fake_termios.tcsetattr.reset_mock()
            fake_tty.setraw.reset_mock()
            fake_stdin = _FakeStdin(chars)
            with patch.dict(
                "sys.modules",
                {"termios": fake_termios, "tty": fake_tty},
                clear=False,
            ):
                with patch("taskman.cli.interaction.os.name", "posix"), patch(
                    "taskman.cli.interaction.sys.stdin", fake_stdin
                ):
                    key = Interaction._read_key()
            self.assertEqual(key, expected)

    def test_read_key_posix_unknown_escape_returns_empty(self):
        fake_termios = types.SimpleNamespace(
            tcgetattr=Mock(return_value="orig"),
            tcsetattr=Mock(),
            TCSADRAIN="drain",
        )
        fake_tty = types.SimpleNamespace(setraw=Mock())
        fake_stdin = _FakeStdin(["\x1b", "[", "Z"])
        with patch.dict(
            "sys.modules",
            {"termios": fake_termios, "tty": fake_tty},
            clear=False,
        ):
            with patch("taskman.cli.interaction.os.name", "posix"), patch(
                "taskman.cli.interaction.sys.stdin", fake_stdin
            ):
                key = Interaction._read_key()
        self.assertEqual(key, "")

    def test_read_key_posix_up_and_passthrough(self):
        fake_termios = types.SimpleNamespace(
            tcgetattr=Mock(return_value="orig"),
            tcsetattr=Mock(),
            TCSADRAIN="drain",
        )
        fake_tty = types.SimpleNamespace(setraw=Mock())

        fake_stdin = _FakeStdin(["\x1b", "[", "A"])
        with patch.dict(
            "sys.modules",
            {"termios": fake_termios, "tty": fake_tty},
            clear=False,
        ):
            with patch("taskman.cli.interaction.os.name", "posix"), patch(
                "taskman.cli.interaction.sys.stdin", fake_stdin
            ):
                key = Interaction._read_key()
        self.assertEqual(key, "UP")

        fake_termios.tcsetattr.reset_mock()
        fake_tty.setraw.reset_mock()
        fake_stdin = _FakeStdin(["x"])
        with patch.dict(
            "sys.modules",
            {"termios": fake_termios, "tty": fake_tty},
            clear=False,
        ):
            with patch("taskman.cli.interaction.os.name", "posix"), patch(
                "taskman.cli.interaction.sys.stdin", fake_stdin
            ):
                key = Interaction._read_key()
        self.assertEqual(key, "x")


if __name__ == "__main__":
    unittest.main()
