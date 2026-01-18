// Bootstrap for the Taskman index page.
/** Initialize the Taskman index page. */
(function init() {
  const Taskman = window.Taskman || {};
  const projects = Taskman.projects;
  const highlights = Taskman.highlights;
  const people = Taskman.people;
  projects.wireFilterControls();
  projects.wireProjectActions();
  people.wireAssigneeActions();

  void Promise.all([
    projects.refreshProjects(),
    highlights.refreshHighlights(),
    people.refreshPeople()
  ]);
})();
