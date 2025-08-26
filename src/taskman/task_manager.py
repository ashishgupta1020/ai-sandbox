from taskman.project_manager import ProjectManager  # Handles project listing and saving
from taskman.project import Project  # Represents a project and its tasks
from taskman.interaction import Interaction  # Handles user input interactions

def main_cli() -> None:
    """
    Main entry point for the CLI application.
    Handles project selection, task management, and user interaction.
    """
    interaction = Interaction()
    current_project = None

    print("\nWelcome to the Task Manager!")
    print("=" * 30)

    # Main menu loop until a project is opened
    while not current_project:
        print("\nMain Menu:")
        print("-" * 30)
        print("1. List all projects")
        print("2. Open a project")
        print("3. Edit a project name")
        print("4. Exit")
        print("-" * 30)
        choice = input("Enter your choice: ")

        if choice == "1":
            # List all available projects
            print("\nListing all projects:")
            print("-" * 30)
            ProjectManager.list_projects()
        elif choice == "2":
            # Open a project by name
            project_name = interaction.get_project_name()
            ProjectManager.save_project_name(project_name)
            current_project = Project(project_name)
            print(f"\nOpened project: '{current_project.name}'")
        elif choice == "3":
            # Edit a project name
            print("\nEditing a project name:")
            print("-" * 30)
            projects = ProjectManager.list_projects()
            if projects:
                old_name = interaction.get_project_name("Enter the project name to rename: ")
                new_name = interaction.get_project_name("Enter the new project name: ")
                ProjectManager.edit_project_name(old_name, new_name)
        elif choice == "4":
            # Exit the application
            print("\nExiting Task Manager. Goodbye!")
            return
        else:
            print("\nInvalid choice. Please try again.")

    # Project menu loop for task operations
    while True:
        print("\nProject Menu:")
        print("=" * 30)
        print(f"Current Project: {current_project.name}")
        print("-" * 30)
        # Task Management
        print("-- Task Management --")
        print("1. Add a task")
        print("2. List all tasks")
        print("3. List tasks with custom sort")
        print("4. Edit a task")
        print("5. Export tasks to Markdown\n")
        # Project Management
        print("-- Project Management --")
        print("6. Edit current project name")
        print("7. List all projects")
        print("8. Switch project\n")
        # Application
        print("-- Application --")
        print("9. Exit")
        print("-" * 30)
        choice = input("Enter your choice: ")

        if choice == "1":
            # Add a new task to the current project
            print("\nAdding a new task:")
            print("-" * 30)
            task = interaction.get_task_details()
            current_project.add_task(task)
            print(f"\nTask added successfully to project: '{current_project.name}'")
        elif choice == "2":
            # List all tasks in the current project
            print(f"\nListing tasks in project: '{current_project.name}'")
            print("-" * 30)
            current_project.list_tasks()
        elif choice == "3":
            # List tasks with custom sort
            print(f"\nCustom Sort - List tasks in project: '{current_project.name}'")
            print("-" * 30)
            print("Sort by:")
            print("1. Status")
            print("2. Priority")
            sort_choice = input("Enter your choice (1 or 2): ")
            if sort_choice == "1":
                current_project.list_tasks(sort_by="status")
            elif sort_choice == "2":
                current_project.list_tasks(sort_by="priority")
            else:
                print("\nInvalid sort choice. Showing unsorted tasks.")
                current_project.list_tasks()
        elif choice == "4":
            # Edit a task in the current project
            print(f"\nEditing tasks in project: '{current_project.name}'")
            print("-" * 30)
            current_project.list_tasks()
            try:
                task_index = int(input("\nEnter the index of the task to edit: "))
                if task_index < 1 or task_index > len(current_project.tasks):
                    print("Invalid task index.")
                else:
                    old_task = current_project.tasks[task_index - 1]
                    new_task = interaction.edit_task_details(old_task)
                    current_project.edit_task(task_index, new_task)
            except ValueError:
                print("\nInvalid input. Please enter a valid task index.")
        elif choice == "5":
            # Export tasks to a Markdown file
            current_project.export_tasks_to_markdown_file()
        elif choice == "6":
            # Edit current project name
            print("\nEditing current project name:")
            print("-" * 30)
            old_name = current_project.name
            new_name = interaction.get_project_name(f"Enter the new name for project '{old_name}': ")
            if new_name and new_name != old_name:
                if ProjectManager.edit_project_name(old_name, new_name):
                    current_project = Project(new_name)
                    print(f"Project renamed. Current project is now '{current_project.name}'.")
            else:
                print("Rename cancelled or new name is the same as the old name.")
        elif choice == "7":
            # List all available projects
            print("\nListing all projects:")
            print("-" * 30)
            ProjectManager.list_projects()
        elif choice == "8":
            # Switch to another project
            print("\nSwitching project:")
            print("-" * 30)
            project_name = interaction.get_project_name()
            ProjectManager.save_project_name(project_name)
            current_project = Project(project_name)
            print(f"\nSwitched to project: '{current_project.name}'")
        elif choice == "9":
            # Exit the application
            print("\nExiting Task Manager. Goodbye!")
            break
        else:
            print("\nInvalid choice. Please try again.")

# Run the CLI if this file is executed directly
if __name__ == "__main__":
    main_cli()
