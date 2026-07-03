# Projects & Environments

## The Model

CC organizes your work in a hierarchy:

```
Project
  └── Environment (one or many)
        ├── Path         (where the code lives)
        ├── Version      (v17, v18, v19...)
        ├── Branch       (git branch name)
        ├── Database     (PostgreSQL database name)
        └── Modules      (which modules to -u on launch)
```

### Project

A **Project** is a client or codebase — e.g. `acme`, `globex`, `initech`.

It's just a name and an optional Odoo SH project slug. It groups one or more environments together.

### Environment

An **Environment** is a specific working configuration for a project. Most projects have one environment, but you might have multiple when:

- Working on separate feature branches simultaneously
- The project spans multiple Odoo versions (v18 for one module, v19 for another)
- You have a "production-like" and a "dev" setup locally

Each environment stores everything CC needs to switch to it instantly.

## Creating a Project

```bash
cc project create my-project
# or just switch to it — CC will create it if it doesn't exist
cc switch my-project
```

## Creating an Environment in an Existing Project

```bash
cc env create my-project
```

## Listing Projects

```bash
cc project
```

## Listing Environments

```bash
cc env
# or for a specific project:
cc env list my-project
```

## Deleting

```bash
cc project delete my-project   # deletes project + all environments
cc env delete                  # interactive picker
```
