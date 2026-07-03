# Your First Switch

## Add a Project

If CC doesn't know about your project yet, add it:

```bash
cc switch my-project
```

If `my-project` isn't in the database yet, CC will:
1. Search your filesystem for a matching directory
2. Ask you to confirm the path, version, and database
3. Ask which modules to associate with this environment
4. Save everything and switch

## Switch to an Existing Project

```bash
cc switch my-project
```

If the project has multiple environments, you'll get an interactive selector:

```
Project 'my-project' has multiple environments:
Choose environment:
    my-project_v17    Branch: 17.0-feature-x    Database: my_project_v17
  ❯ my-project_v18    Branch: 18.0-feature-y    Database: my_project_v18
```

After selecting, CC will:
- Set the project as active
- Check out the configured branch
- Update your VS Code / Cursor `settings.json` (database, addons, modules, Python interpreter); `launch.json` debug templates are written once via [`cc config ide setup`](../commands/config/ide.md) and not touched per switch
- Open the project in your IDE
- Log the switch for timesheet tracking

<!-- 📸 IMAGE: Screenshot of the environment selector prompt in the terminal -->

## Useful Flags

| Flag | Description |
|------|-------------|
| `cc switch my-project -s` | Switch without opening the IDE |
| `cc switch my-project -n` | Open in a new IDE window |
| `cc switch --env staging` | Switch directly to a named environment |

## Navigate to the Project

After switching, `cc cd` will take you to the active project directory:

```bash
cc cd
```

---

Next: [Core Concepts](../concepts/projects-environments.md)
