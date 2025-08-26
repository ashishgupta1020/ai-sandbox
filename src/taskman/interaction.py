from taskman.task import Task

class Interaction:
    """
    Handles user input for project and task details.
    """
    @staticmethod
    def get_project_name() -> str:
        """
        Prompt user to enter a project name.
        """
        return input("Enter the project name: ")

    @staticmethod
    def get_task_details() -> Task:
        """
        Prompt user for all details required to create a Task.
        """
        summary = input("Enter the task summary: ")
        assignee = input("Enter the assignee: ")
        print("Enter remarks (Markdown format is supported).")
        print("Examples: '* Bullet points', '**Bold text**', '[Link](https://example.com)', '1. Numbered list', '`inline code`'")
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
        for idx, option in enumerate(status_options, start=1):
            print(f"{idx}. {option}")
        status = None
        while status not in range(1, len(status_options) + 1):
            try:
                status = int(input("Enter the number corresponding to the status: "))
            except ValueError:
                pass
        status = status_options[status - 1]

        # Priority selection
        priority_options = ["Low", "Medium", "High"]
        print("Select the priority of the task:")
        for idx, option in enumerate(priority_options, start=1):
            print(f"{idx}. {option}")
        priority = None
        while priority not in range(1, len(priority_options) + 1):
            try:
                priority = int(input("Enter the number corresponding to the priority: "))
            except ValueError:
                pass
        priority = priority_options[priority - 1]

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
        print("Examples: '* Bullet points', '**Bold text**', '[Link](https://example.com)', '1. Numbered list', '`inline code`'")
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
        print("Select new status:")
        for idx, option in enumerate(status_options, start=1):
            print(f"{idx}. {option}")
        new_status = None
        status_input = input("Enter the number corresponding to the new status (leave blank to keep current): ")
        if status_input.isdigit():
            num = int(status_input)
            if 1 <= num <= len(status_options):
                new_status = status_options[num - 1]
        status = new_status if new_status else task.status.value
        # Edit priority
        priority_options = ["Low", "Medium", "High"]
        print(f"Current Priority: {task.priority.value}")
        print("Select new priority:")
        for idx, option in enumerate(priority_options, start=1):
            print(f"{idx}. {option}")
        new_priority = None
        priority_input = input("Enter the number corresponding to the new priority (leave blank to keep current): ")
        if priority_input.isdigit():
            num = int(priority_input)
            if 1 <= num <= len(priority_options):
                new_priority = priority_options[num - 1]
        priority = new_priority if new_priority else task.priority.value
        return Task(summary, assignee, remarks, status, priority)
