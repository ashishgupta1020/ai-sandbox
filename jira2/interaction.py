from .task import Task

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
    def get_task_details() -> 'Task':
        """
        Prompt user for all details required to create a Task.
        """
        summary = input("Enter the task summary: ")
        assignee = input("Enter the assignee: ")
        remarks = input("Enter remarks: ")

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
