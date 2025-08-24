from project_manager import ProjectManager  # Handles project listing and saving
from project import Project  # Represents a project and its tasks
from interaction import Interaction  # Handles user input interactions

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
        print("3. Exit")
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
        print("1. Add a task to the current project")
        print("2. List all tasks in the current project")
        print("3. Edit a task in the current project")
        print("4. List all projects")
        print("5. Switch project")
        print("6. Export tasks to Markdown")
        print("7. Exit")
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
            # Edit a task in the current project
            print(f"\nEditing tasks in project: '{current_project.name}'")
            print("-" * 30)
            current_project.list_tasks()
            try:
                task_index = int(input("\nEnter the index of the task to edit: "))
                current_project.edit_task(task_index)
            except ValueError:
                print("\nInvalid input. Please enter a valid task index.")
        elif choice == "4":
            # List all available projects
            print("\nListing all projects:")
            print("-" * 30)
            ProjectManager.list_projects()
        elif choice == "5":
            # Switch to another project
            print("\nSwitching project:")
            print("-" * 30)
            project_name = interaction.get_project_name()
            ProjectManager.save_project_name(project_name)
            current_project = Project(project_name)
            print(f"\nSwitched to project: '{current_project.name}'")
        elif choice == "6":
            # Export tasks to a Markdown file
            current_project.export_tasks_to_markdown_file()
        elif choice == "7":
            # Exit the application
            print("\nExiting Task Manager. Goodbye!")
            break
        else:
            print("\nInvalid choice. Please try again.")

# Run the CLI if this file is executed directly
if __name__ == "__main__":
    main_cli()