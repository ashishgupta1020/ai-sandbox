import os
import sys
from typing import List, Tuple

from taskman.server.task import Task

DEFAULT_SELECTION_PROMPT = "Use ↑/↓ or type a number to choose, and press Enter to select."


class Interaction:
    """
    Handles user input for project and task details.
    """

    @staticmethod
    def select_from_list(
        options: List[str],
        prompt: str = DEFAULT_SELECTION_PROMPT,
        default_index: int = 0,
    ) -> int:
        """
        Present a list of options and let the user pick one.
        Supports arrow-key navigation when running in a TTY, otherwise falls back to numeric input.
        Returns the index (0-based) of the selected option.
        """
        if not options:
            raise ValueError("Options list cannot be empty.")

        interactive = sys.stdin.isatty() and sys.stdout.isatty()
        if interactive:
            try:
                return Interaction._select_with_arrow_keys(
                    options, prompt, default_index
                )
            finally:
                Interaction._show_cursor()
        numeric_prompt = (
            prompt
            if prompt != DEFAULT_SELECTION_PROMPT
            else "Enter the number of your choice (press Enter to accept the default)."
        )
        return Interaction._select_with_numeric_input(
            options, numeric_prompt, default_index
        )

    @staticmethod
    def select_from_grouped_list(
        grouped_options: List[Tuple[str, List[str]]],
        prompt: str = DEFAULT_SELECTION_PROMPT,
        default_index: int = 0,
    ) -> int:
        """
        Present a list of options divided into named groups.
        Keeps the group headings visible while navigating with arrow keys.
        Returns the index (0-based) of the selected option within the flattened list.
        """
        if not any(options for _, options in grouped_options):
            raise ValueError("Grouped options must contain at least one selectable item.")

        interactive = sys.stdin.isatty() and sys.stdout.isatty()
        if interactive:
            try:
                return Interaction._select_grouped_with_arrow_keys(
                    grouped_options,
                    prompt,
                    default_index,
                )
            finally:
                Interaction._show_cursor()

        numeric_prompt = (
            prompt
            if prompt != DEFAULT_SELECTION_PROMPT
            else "Enter the number of your choice (press Enter to accept the default)."
        )
        return Interaction._select_grouped_with_numeric_input(
            grouped_options,
            numeric_prompt,
            default_index,
        )

    @staticmethod
    def _select_with_arrow_keys(
        options: List[str],
        prompt: str,
        default_index: int = 0,
    ) -> int:
        display_options = [f"{idx + 1}. {option}" for idx, option in enumerate(options)]
        current_index = default_index if 0 <= default_index < len(display_options) else 0
        if prompt:
            print(prompt)
        Interaction._hide_cursor()
        Interaction._render_options(display_options, current_index)
        while True:
            key = Interaction._read_key()
            if key in ("UP", "K"):
                current_index = (current_index - 1) % len(display_options)
                Interaction._render_options(display_options, current_index)
            elif key in ("DOWN", "J"):
                current_index = (current_index + 1) % len(display_options)
                Interaction._render_options(display_options, current_index)
            elif key == "ENTER":
                Interaction._render_options(
                    display_options, current_index, move_cursor=False
                )
                print()
                return current_index
            elif key.isdigit():
                numeric_index = int(key) - 1
                if 0 <= numeric_index < len(display_options):
                    current_index = numeric_index
                    Interaction._render_options(display_options, current_index)

    @staticmethod
    def _select_with_numeric_input(
        options: List[str],
        prompt: str,
        default_index: int = 0,
    ) -> int:
        display_options = [f"{idx + 1}. {option}" for idx, option in enumerate(options)]
        if prompt:
            print(prompt)
        for option in display_options:
            print(option)
        if 0 <= default_index < len(display_options):
            print(f"(Press Enter to keep default: {display_options[default_index]})")

        while True:
            raw = input("Enter the number of your choice: ").strip()
            if raw.isdigit():
                numeric_index = int(raw) - 1
                if 0 <= numeric_index < len(display_options):
                    return numeric_index
            if raw == "" and 0 <= default_index < len(display_options):
                return default_index
            print("Invalid choice. Please try again.")

    @staticmethod
    def _select_grouped_with_arrow_keys(
        grouped_options: List[Tuple[str, List[str]]],
        prompt: str,
        default_index: int = 0,
    ) -> int:
        flat_options = Interaction._flatten_grouped_options(grouped_options)
        if not flat_options:
            raise ValueError("Grouped options must contain at least one selectable item.")
        current_index = default_index if 0 <= default_index < len(flat_options) else 0
        if prompt:
            print(prompt)
        Interaction._hide_cursor()
        Interaction._render_grouped_options(grouped_options, current_index)
        while True:
            key = Interaction._read_key()
            if key in ("UP", "K"):
                current_index = (current_index - 1) % len(flat_options)
                Interaction._render_grouped_options(grouped_options, current_index)
            elif key in ("DOWN", "J"):
                current_index = (current_index + 1) % len(flat_options)
                Interaction._render_grouped_options(grouped_options, current_index)
            elif key == "ENTER":
                Interaction._render_grouped_options(
                    grouped_options,
                    current_index,
                    move_cursor=False,
                )
                print()
                return current_index
            elif key.isdigit():
                numeric_index = int(key) - 1
                if 0 <= numeric_index < len(flat_options):
                    current_index = numeric_index
                    Interaction._render_grouped_options(grouped_options, current_index)

    @staticmethod
    def _select_grouped_with_numeric_input(
        grouped_options: List[Tuple[str, List[str]]],
        prompt: str,
        default_index: int = 0,
    ) -> int:
        flat_options = Interaction._flatten_grouped_options(grouped_options)
        if not flat_options:
            raise ValueError("Grouped options must contain at least one selectable item.")
        if prompt:
            print(prompt)

        option_number = 1
        for heading, options in grouped_options:
            if not options:
                continue
            if option_number > 1:
                print()
            print(heading)
            for option in options:
                print(f"{option_number}. {option}")
                option_number += 1

        if default_index >= 0 and default_index < len(flat_options):
            default_label = flat_options[default_index]
            print(f"\n(Press Enter to keep default: {default_index + 1}. {default_label})")

        while True:
            raw = input("Enter the number of your choice: ").strip()
            if raw.isdigit():
                numeric_index = int(raw) - 1
                if 0 <= numeric_index < len(flat_options):
                    return numeric_index
            if raw == "" and 0 <= default_index < len(flat_options):
                return default_index
            print("Invalid choice. Please try again.")

    @staticmethod
    def _render_options(
        options: List[str],
        active_index: int,
        move_cursor: bool = True,
    ) -> None:
        for idx, option in enumerate(options):
            indicator = ">" if idx == active_index else " "
            sys.stdout.write(f"{indicator} {option}\x1b[K\n")
        sys.stdout.flush()
        if move_cursor:
            sys.stdout.write(f"\x1b[{len(options)}F")
            sys.stdout.flush()

    @staticmethod
    def _render_grouped_options(
        grouped_options: List[Tuple[str, List[str]]],
        active_index: int,
        move_cursor: bool = True,
    ) -> None:
        lines: List[str] = []
        option_counter = 0
        for heading, options in grouped_options:
            if not options:
                continue
            if lines:
                lines.append("")
            lines.append(heading)
            for option in options:
                indicator = ">" if option_counter == active_index else " "
                lines.append(f"{indicator} {option_counter + 1}. {option}\x1b[K")
                option_counter += 1
        output = "\n".join(lines) + "\n"
        sys.stdout.write(output)
        sys.stdout.flush()
        if move_cursor:
            sys.stdout.write(f"\x1b[{len(lines)}F")
            sys.stdout.flush()

    @staticmethod
    def _flatten_grouped_options(
        grouped_options: List[Tuple[str, List[str]]]
    ) -> List[str]:
        flat_options: List[str] = []
        for _, options in grouped_options:
            if not options:
                continue
            flat_options.extend(options)
        return flat_options

    @staticmethod
    def _read_key() -> str:
        if os.name == "nt":
            import msvcrt

            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                ch2 = msvcrt.getwch()
                combo = ch + ch2
                if combo in ("\x00H", "\xe0H"):
                    return "UP"
                if combo in ("\x00P", "\xe0P"):
                    return "DOWN"
                return ""
            if ch in ("\r", "\n"):
                return "ENTER"
            if ch.lower() == "k":
                return "K"
            if ch.lower() == "j":
                return "J"
            return ch

        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                next1 = sys.stdin.read(1)
                if next1 == "[":
                    next2 = sys.stdin.read(1)
                    if next2 == "A":
                        return "UP"
                    if next2 == "B":
                        return "DOWN"
                return ""
            if ch in ("\r", "\n"):
                return "ENTER"
            if ch.lower() == "k":
                return "K"
            if ch.lower() == "j":
                return "J"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    @staticmethod
    def _hide_cursor() -> None:
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()

    @staticmethod
    def _show_cursor() -> None:
        sys.stdout.write("\x1b[?25h")
        sys.stdout.flush()

    @staticmethod
    def get_project_name(prompt: str = "Enter the project name: ") -> str:
        """
        Prompt user to enter a project name.
        """
        return input(prompt)

    @staticmethod
    def get_task_details() -> Task:
        """
        Prompt user for all details required to create a Task.
        """
        summary = input("Enter the task summary: ")
        assignee = input("Enter the assignee: ")
        print("Enter remarks (Markdown format is supported).")
        print(
            "Examples: '* Bullet points', '**Bold text**', '[Link](https://example.com)', '1. Numbered list', '`inline code`'"
        )
        print("Press Enter twice to finish:")
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        remarks = "\n".join(lines)

        # Status selection
        status_options = ["Not Started", "In Progress", "Completed"]
        print("Select the status of the task:")
        status_index = Interaction.select_from_list(status_options)
        status = status_options[status_index]

        # Priority selection
        priority_options = ["Low", "Medium", "High"]
        print("Select the priority of the task:")
        priority_index = Interaction.select_from_list(priority_options)
        priority = priority_options[priority_index]
        return Task(summary, assignee, remarks, status, priority)

    @staticmethod
    def edit_task_details(task: Task) -> Task:
        """
        Prompt user to edit details of an existing Task. Allows skipping fields.
        Returns a new Task object with updated details.
        """
        print("Editing Task:")
        # Edit summary
        print(f"Current Summary: {task.summary}")
        new_summary = input("Enter new summary (leave blank to keep current): ")
        summary = new_summary if new_summary else task.summary
        # Edit assignee
        print(f"Current Assignee: {task.assignee}")
        new_assignee = input("Enter new assignee (leave blank to keep current): ")
        assignee = new_assignee if new_assignee else task.assignee
        # Edit remarks
        print(f"Current Remarks: {task.remarks}")
        print("Enter new remarks (Markdown format is supported). Leave blank to keep current.")
        print(
            "Examples: '* Bullet points', '**Bold text**', '[Link](https://example.com)', '1. Numbered list', '`inline code`'"
        )
        print("Press Enter twice to finish:")
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        if lines:
            remarks = "\n".join(lines)
        else:
            remarks = task.remarks
        # Edit status
        status_options = ["Not Started", "In Progress", "Completed"]
        print(f"Current Status: {task.status.value}")
        print("Select new status (press Enter to keep current):")
        default_status = (
            status_options.index(task.status.value)
            if task.status.value in status_options
            else 0
        )
        status_index = Interaction.select_from_list(
            status_options,
            prompt=(
                "Use ↑/↓ or type a number to choose, and press Enter to select a new status."
            ),
            default_index=default_status,
        )
        status = status_options[status_index]
        # Edit priority
        priority_options = ["Low", "Medium", "High"]
        print(f"Current Priority: {task.priority.value}")
        print("Select new priority (press Enter to keep current):")
        default_priority = (
            priority_options.index(task.priority.value)
            if task.priority.value in priority_options
            else 0
        )
        priority_index = Interaction.select_from_list(
            priority_options,
            prompt=(
                "Use ↑/↓ or type a number to choose, and press Enter to select a new priority."
            ),
            default_index=default_priority,
        )
        priority = priority_options[priority_index]
        return Task(summary, assignee, remarks, status, priority)
