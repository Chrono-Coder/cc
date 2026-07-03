"""Completion kinds for sources that aren't a plain ORM entity or fixed list
(module dirs, filesystem paths, action-aware env targets, cc command names)."""
from enum import Enum


class CompleteKind(Enum):
    MODULE = "module"
    PATH = "path"
    ENV_TARGET = "env_target"
    COMMAND = "command"
