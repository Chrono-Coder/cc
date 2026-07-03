"""ORM models owned by the intel plugin — registered via the `cc.models`
entry point so sync_schema builds their tables. They relate to each other by
string name (resolved from the entity registry at runtime), so there's no hard
import coupling; they import only cc's ORM commons from core."""
from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.constraint import UniqueConstraint
from cc.base.arm.common.property import Property


class Repository(BaseEntity):
    """
    A git repository on disk that intel indexes for skill telemetry.

    Decoupled from Environment: a repo can exist without any env pointing at
    it (archived work, pre-cc projects, open-source contributions). When an
    env is created against a project_path, the intel service can opt to
    auto-register that path as a Repository — but it's never required.
    """
    _name = "repository"

    name = Property(type=str, required=True)
    path = Property(type=str, semantic="path", required=True, unique=True)
    origin_url = Property(type=str, semantic="url")

    # Indexer state
    last_indexed_commit_sha = Property(type=str)
    last_indexed_at = Property(type=str, semantic="datetime")
    enabled = Property(type=bool, default=True)

    # Inverse o2m
    skill_tag_ids = Property(one2many="skill_tag", inverse_name="repository_id")
    knowledge_index_ids = Property(one2many="knowledge_index", inverse_name="repository_id")
    sync_id = Property(type=str)
    synced_at = Property(type=str, semantic="datetime")


class SkillTag(BaseEntity):
    """
    One row per (repository, commit_sha, tag). Records that a single commit
    you authored exhibited a particular skill pattern (e.g. "wizard",
    "compute_method", "model_override"), with the LOC under that pattern.

    Cross-repo dedup happens at query time by grouping on
    Repository.origin_url — two clones of the same repo will produce the
    same commit_sha and we filter accordingly.
    """
    _name = "skill_tag"

    repository_id = Property(relation="repository", required=True)
    commit_sha = Property(type=str, required=True)
    tag = Property(type=str, required=True)

    # Ranking weight: capped per-(commit, tag) so a single huge refactor
    # can't dominate. Configurable via setting `intel.weight_cap`.
    weight = Property(type=int)

    # Raw lines added under this pattern, uncapped — used for "you wrote
    # N LOC of X" style stats, not for ranking.
    raw_loc = Property(type=int)

    committed_at = Property(type=str, semantic="datetime")

    # Comma-separated file paths from the commits that triggered this tag.
    top_files = Property(type=str)

    sync_id = Property(type=str)
    synced_at = Property(type=str, semantic="datetime")

    _constraints = [
        UniqueConstraint("repository_id", "commit_sha", "tag",
                         name="uq_skill_tag_repo_sha_tag"),
    ]


class KnowledgeIndex(BaseEntity):
    """
    One row per (repository, symbol, symbol_kind). Aggregates how much you've
    touched a given symbol — model name, method name, file path — across
    every commit you authored in this repository.

    Used by `cc who-knows <symbol>` to rank repos by your familiarity with
    that symbol. Updated incrementally by the indexer.
    """
    _name = "knowledge_index"

    repository_id = Property(relation="repository", required=True)
    symbol = Property(type=str, required=True)

    # "model" | "method" | "field" | "file" — drives how queries widen
    # (e.g. searching for a model name should also match files that
    # `_inherit` from it).
    symbol_kind = Property(type=str)

    commit_count = Property(type=int)
    loc_authored = Property(type=int)
    last_touched = Property(type=str, semantic="datetime")

    # Top files that contributed to this aggregate, comma-separated.
    # Capped to 5 entries by the indexer.
    top_files = Property(type=str, semantic="csv")

    sync_id = Property(type=str)
    synced_at = Property(type=str, semantic="datetime")

    _constraints = [
        UniqueConstraint("repository_id", "symbol", "symbol_kind",
                         name="uq_knowledge_repo_sym_kind"),
    ]
