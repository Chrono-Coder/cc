"""
Odoo language pack — Odoo-specific patterns.

Detects this pack should run by looking for a `__manifest__.py` somewhere
under the repo root.

Tags emitted:
    model_definition      _name = "..."
    model_override        _inherit = "..."
    wizard                TransientModel subclass
    compute_method        @api.depends decorator
    constraint            @api.constrains or _sql_constraints
    controller            http.Controller subclass
    controller_json       @http.route(..., type='json')
    controller_public     @http.route(..., auth='public')
    report                files in report/ or qweb report templates

    --- frontend (content-based, not path-based) ---
    owl_component         OWL imports / Component subclass / OWL hooks
    js_widget             legacy publicWidget / Widget.extend / odoo.define
    assets_backend        files in web.assets_backend bundle (admin UI)
    assets_frontend       files in web.assets_frontend / website / portal
    assets_pos            files in point_of_sale.* bundles
    assets_qweb           files in web.assets_qweb
    website               fallback content match (publicWidget, /website/)
    owl_template          XML files in static/src/ (QWeb / OWL templates)
    style                 SCSS/CSS/LESS in static/src/
    js_test               JS files in static/tests/
    tour_test             JS files in static/tests/tours/

    --- business domain (parent + subdomain from model name) ---
    Each commit emits one parent tag + (optionally) one more specific
    subdomain tag. Lets reports roll up ("80% HR") or drill down
    ("HR work is 60% timeoff, 30% payroll").

    Parents:           Subdomains (when model matches a more specific pattern):
    domain_hr          hr_timeoff, hr_payroll, hr_recruitment, hr_attendance,
                       hr_expense, hr_timesheet, hr_appraisal, hr_skills
    domain_accounting  accounting_assets, accounting_reports, accounting_analytic,
                       accounting_bank, accounting_budget, accounting_tax,
                       accounting_payment, accounting_consolidation
    domain_inventory   inventory_lots, inventory_valuation, inventory_warehouse
    domain_mrp         mrp_bom, mrp_workorder, mrp_subcontracting
    domain_sales       sales_subscription, sales_commission
    domain_crm         crm_leads, crm_teams
    domain_pos         pos_config, pos_session, pos_order
    domain_website     website_ecommerce
    domain_purchase, domain_project, domain_email, domain_delivery,
    domain_payment, domain_helpdesk, domain_survey, domain_event,
    domain_quality, domain_documents, domain_fleet, domain_loyalty,
    domain_subscription, domain_field_service

    Custom models (e.g. `acme.foo`) get no domain tag — that's an
    accepted limitation; we don't trust manifest categories enough to
    guess. Dev's whose work is mostly custom models will see lower
    domain coverage in their skill report.

    NOTE: manifest `category` was considered as a fallback signal but
    rejected — devs leave it as default, OCA modules sometimes pick
    inaccurate categories, custom modules omit it. Model name patterns
    from `_inherit` / `_name` are direct evidence from the code itself.

    odoo_test             files in tests/ + TransactionCase / HttpCase
    migration             files in migrations/X.Y.Z/ (parent — always fires)
    migration_pre         pre-migration.py — schema changes before reload
    migration_post        post-migration.py — data fixups after reload
    migration_end         end-migration.py — cleanup at the end
    odoo_external_api     non-stdlib HTTP/cloud SDK imports
    security              ir.model.access.csv or <record model="ir.rule">
    performance           model_create_multi / prefetch / new INDEX
    cron_or_queue         ir.cron records or @queue.job decorator
"""
from __future__ import annotations

import ast
import fnmatch
import logging
import re
from pathlib import Path
from typing import Iterator, List

from . import LanguagePack, TagTuple, added_text_only

log = logging.getLogger("CC")


# Parent domain — keyed on the first dotted segment of the model name.
# Standard Odoo apps. ir.*, res.*, base.* are infrastructure and skipped.
_DOMAIN_BY_MODEL_PREFIX: dict[str, str] = {
    "account":     "domain_accounting",
    "sale":        "domain_sales",
    "purchase":    "domain_purchase",
    "stock":       "domain_inventory",
    "mrp":         "domain_mrp",
    "quality":     "domain_quality",
    "hr":          "domain_hr",
    "crm":         "domain_crm",
    "project":     "domain_project",
    "pos":         "domain_pos",
    "website":     "domain_website",
    "mail":        "domain_email",
    "delivery":    "domain_delivery",
    "payment":     "domain_payment",
    "helpdesk":    "domain_helpdesk",
    "survey":      "domain_survey",
    "event":       "domain_event",
    "documents":   "domain_documents",
    "fleet":       "domain_fleet",
    "loyalty":     "domain_loyalty",
    "subscription":"domain_subscription",
    "contract":    "domain_subscription",
    "fsm":         "domain_field_service",
    "industry_fsm":"domain_field_service",
}


# Subdomain — checked BEFORE parent prefix; emitted ALONGSIDE the parent
# so reports can roll up or drill down. Order matters (most specific first).
# A commit modifying `hr.leave` fires both `domain_hr_timeoff` and
# `domain_hr`. Model patterns that don't match any subdomain only get the
# parent tag.
_SUBDOMAIN_PATTERNS: list[tuple] = [
    # ---- HR ----
    (r"^hr\.(leave|holidays?|public_holidays)\b",      "domain_hr_timeoff"),
    (r"^hr\.(payslip|salary|payroll)\b",               "domain_hr_payroll"),
    (r"^hr\.(applicant|job\b|recruitment)",            "domain_hr_recruitment"),
    (r"^hr\.attendance\b",                             "domain_hr_attendance"),
    (r"^hr\.expense\b",                                "domain_hr_expense"),
    (r"^hr\.timesheet\b",                              "domain_hr_timesheet"),
    (r"^hr\.appraisal\b",                              "domain_hr_appraisal"),
    (r"^hr\.(skill|resume\.line)\b",                   "domain_hr_skills"),

    # ---- Accounting ----
    (r"^account\.asset\b",                             "domain_accounting_assets"),
    (r"^account\.(report|financial\.html\.report)\b",  "domain_accounting_reports"),
    (r"^account\.analytic\b",                          "domain_accounting_analytic"),
    (r"^account\.(bank|reconcile)\b",                  "domain_accounting_bank"),
    (r"^account\.budget\b",                            "domain_accounting_budget"),
    (r"^account\.tax\b",                               "domain_accounting_tax"),
    (r"^account\.payment\b",                           "domain_accounting_payment"),
    (r"^account\.consolidation\b",                     "domain_accounting_consolidation"),

    # ---- Inventory ----
    (r"^stock\.(lot|production\.lot|quant\.package)\b","domain_inventory_lots"),
    (r"^stock\.(valuation|inventory)\b",               "domain_inventory_valuation"),
    (r"^stock\.(warehouse|location|route)\b",          "domain_inventory_warehouse"),

    # ---- MRP ----
    (r"^mrp\.bom\b",                                   "domain_mrp_bom"),
    (r"^mrp\.workorder\b",                             "domain_mrp_workorder"),
    (r"^mrp\.subcontract",                             "domain_mrp_subcontracting"),

    # ---- Sales ----
    (r"^sale\.subscription\b",                         "domain_sales_subscription"),
    (r"^sale\.commission\b",                           "domain_sales_commission"),

    # ---- CRM ----
    (r"^crm\.lead\b",                                  "domain_crm_leads"),
    (r"^crm\.team\b",                                  "domain_crm_teams"),

    # ---- POS ----
    (r"^pos\.config\b",                                "domain_pos_config"),
    (r"^pos\.session\b",                               "domain_pos_session"),
    (r"^pos\.order\b",                                 "domain_pos_order"),

    # ---- Website / ecommerce ----
    (r"^website\.sale\b",                              "domain_website_ecommerce"),
]
# Pre-compile the patterns once.
_SUBDOMAIN_PATTERNS = [(re.compile(p), t) for p, t in _SUBDOMAIN_PATTERNS]

# Map asset-bundle name → tag we emit when a file lives in that bundle.
# Bundles not listed here fall through to generic frontend classification.
_BUNDLE_TAG_MAP: dict[str, str] = {
    # POS — both Odoo 16- and 17+ conventions
    "point_of_sale.assets":             "assets_pos",
    "point_of_sale._assets_pos":        "assets_pos",
    "point_of_sale.assets_pos":         "assets_pos",
    "point_of_sale.pos_assets_backend": "assets_pos",
    # Backend admin UI
    "web.assets_backend":            "assets_backend",
    "web._assets_backend_helpers":   "assets_backend",
    # Public-facing website / portal
    "web.assets_frontend":           "assets_frontend",
    "website.assets_wysiwyg":        "assets_frontend",
    "portal.assets_frontend":        "assets_frontend",
    # QWeb / mail / tests
    "web.assets_qweb":               "assets_qweb",
    "mail.assets_messaging":         "assets_frontend",
    "web.assets_tests":              "js_test",
}


class OdooPack(LanguagePack):
    name = "odoo"

    def __init__(self, repo_path: Path | None = None):
        super().__init__(repo_path)
        # Build a {tag: [glob, ...]} map from every manifest's `assets` dict.
        # Used in tag_diff to classify JS files by bundle membership.
        self._bundle_globs: dict[str, list[str]] = {}
        if repo_path is not None:
            self._load_manifest_assets(repo_path)

    # ------------------------------------------------------------------
    # Manifest parsing
    # ------------------------------------------------------------------

    def _load_manifest_assets(self, repo_path: Path) -> None:
        """
        For every __manifest__.py in the repo, extract its top-level dict
        literal via `ast.literal_eval`, pull the `assets` dict, and remember
        which bundle each file glob belongs to. Errors are logged at debug
        and silently skipped — we never want a malformed manifest to break
        indexing.
        """
        for manifest in repo_path.rglob("__manifest__.py"):
            try:
                src = manifest.read_text(encoding="utf-8")
                node = ast.parse(src, mode="exec")
                # The manifest is conventionally a single top-level Expression
                # holding a dict literal: `{ ... }`
                expr = next(
                    (n for n in ast.walk(node) if isinstance(n, ast.Dict)),
                    None,
                )
                if expr is None:
                    continue
                manifest_dict = ast.literal_eval(expr)
                module_dir = manifest.parent.name
                assets = manifest_dict.get("assets")
                if not isinstance(assets, dict):
                    continue
                for bundle, entries in assets.items():
                    if not isinstance(entries, (list, tuple)):
                        continue
                    tag = _BUNDLE_TAG_MAP.get(bundle)
                    if tag is None:
                        continue
                    bucket = self._bundle_globs.setdefault(tag, [])
                    for entry in entries:
                        # Entries are typically strings, but Odoo allows
                        # tuples like ('include', glob) or ('replace', a, b).
                        if isinstance(entry, str):
                            bucket.append(_normalize_glob(entry, module_dir))
                        elif isinstance(entry, (list, tuple)) and entry:
                            # Take the last element — usually the actual path
                            for el in entry:
                                if isinstance(el, str) and (
                                    "/" in el or el.endswith((".js", ".scss",
                                                              ".css", ".xml"))
                                ):
                                    bucket.append(_normalize_glob(el, module_dir))
            except (SyntaxError, ValueError, OSError) as e:
                log.debug(f"intel.odoo: skipping manifest {manifest}: {e}")
                continue

    def _classify_bundle(self, file_path: str) -> str | None:
        """Return the bundle tag for a file path, or None if not in any."""
        for tag, globs in self._bundle_globs.items():
            for g in globs:
                if fnmatch.fnmatch(file_path, g):
                    return tag
        return None

    def _domains_for_model(self, model_name: str) -> set[str]:
        """
        Return the set of domain tags for an Odoo model name.

        Includes the parent domain (e.g. `domain_hr`) AND, when a more
        specific pattern matches, the subdomain (e.g. `domain_hr_timeoff`).
        Empty set if the model name doesn't map to any known Odoo app.
        """
        out: set[str] = set()
        if not model_name or "." not in model_name:
            return out
        for pattern, sub_tag in _SUBDOMAIN_PATTERNS:
            if pattern.match(model_name):
                out.add(sub_tag)
                break  # most specific match wins
        prefix = model_name.split(".", 1)[0]
        parent = _DOMAIN_BY_MODEL_PREFIX.get(prefix)
        if parent:
            out.add(parent)
        return out

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        """
        Real Odoo modules sit at `<root>/<module_name>/__manifest__.py` with a
        sibling `models/` (or `controllers/`, `wizard/`, `views/`) directory.

        A standalone manifest under a `templates/` or `examples/` path —
        like cc's `cc new` scaffolding — is rejected.
        """
        for manifest in project_path.rglob("__manifest__.py"):
            # Reject template / scaffolding paths.
            parts = {p.lower() for p in manifest.parts}
            if parts & {"templates", "template", "examples", "example", "fixtures"}:
                continue
            # Real module: parent has at least one of these companion dirs.
            mod = manifest.parent
            if any((mod / d).is_dir()
                   for d in ("models", "controllers", "wizard", "views",
                             "data", "security", "report")):
                return True
        return False

    # --- regex catalog --------------------------------------------------

    _RX_INHERIT = re.compile(r"""_inherit\s*=\s*['"]([^'"]+)['"]""")
    _RX_NAME    = re.compile(r"""_name\s*=\s*['"]([^'"]+)['"]""")
    _RX_WIZARD  = re.compile(r"class\s+\w+\s*\([^)]*TransientModel[^)]*\)")
    _RX_DEPENDS = re.compile(r"@api\.depends\s*\(([^)]+)\)")
    _RX_CONSTR  = re.compile(r"@api\.constrains|_sql_constraints\s*=")
    _RX_CTRL    = re.compile(r"class\s+\w+\s*\([^)]*http\.Controller[^)]*\)")
    _RX_CTRL_JSON   = re.compile(r"""@http\.route\s*\([^)]*type\s*=\s*['"]json['"]""")
    _RX_CTRL_PUBLIC = re.compile(r"""@http\.route\s*\([^)]*auth\s*=\s*['"]public['"]""")

    # OWL detection — content-based, robust to whatever layout you choose
    # under static/src/. Triggers on any of:
    #   - OWL package import
    #   - Component subclass
    #   - OWL lifecycle hooks
    #   - service registration via Odoo's registry
    _RX_OWL = re.compile(
        r"""from\s+["']@odoo/owl["']|"""
        r"""\bextends\s+Component\b|"""
        r"""\b(useState|useRef|useEffect|onMounted|onWillStart|onWillUnmount|"""
        r"""onWillUpdateProps|onWillDestroy)\s*\(|"""
        r"""\bxmlTemplate\s*=|"""
        r"""\bregistry\.category\s*\(\s*['"][^'"]+['"]\s*\)\s*\.add"""
    )

    # Legacy frontend — Widget.extend, publicWidget, odoo.define
    _RX_LEGACY_WIDGET = re.compile(
        r"""\.Widget\.extend\s*\(|"""
        r"""\bpublicWidget\.\s*Widget\.extend\b|"""
        r"""\bpublicWidget\.\s*registry\b|"""
        r"""\bodoo\.define\s*\("""
    )

    # POS — point_of_sale module work
    _RX_POS = re.compile(
        r"""@point_of_sale/|/point_of_sale/|/pos_[a-z_]*/|"""
        r"""\b(PosStore|PosOrderline|PosScreen|registerPaymentMethod|PaymentScreen)\b"""
    )

    # Website / portal frontend
    _RX_WEBSITE = re.compile(
        r"""@website/|/website/|/portal/|"""
        r"""\bpublicWidget\.|"""
        r"""\b(WebsiteSale|websiteFormCustom|wysiwyg)\b"""
    )

    _RX_TXNCASE = re.compile(
        r"class\s+\w+\s*\([^)]*(TransactionCase|HttpCase|SavepointCase|TestCase)[^)]*\)"
    )
    # Captures the version segment so it can be emitted as a knowledge_index
    # symbol — supports Odoo's `server_version.module_version` style
    # (16.0.1.0.0) and shorter variants.
    _RX_MIGR_PATH = re.compile(r"/migrations/(\d+(?:\.\d+){1,4})/([^/]+)$")
    _RX_EXTAPI  = re.compile(
        r"\bimport\s+(requests|stripe|boto3|paramiko)|"
        r"\bfrom\s+(requests|stripe|boto3|paramiko)\b|"
        r"\bxmlrpc\.client\b"
    )
    _RX_PERF    = re.compile(
        r"@api\.model_create_multi|"
        r"\bprefetch_fields\b|"
        r"CREATE\s+INDEX|CREATE\s+UNIQUE\s+INDEX"
    )
    _RX_CRON    = re.compile(
        r"<record\s+[^>]*ir\.cron[^>]*>|@queue\.job|\.with_delay\s*\("
    )
    _RX_RULE    = re.compile(r"""<record\s+[^>]*model=["']ir\.rule["']""")
    _RX_METHOD_DEF = re.compile(r"^\s+def\s+([a-z_]\w*)\s*\(self", re.MULTILINE)

    # --- pattern detection ---------------------------------------------

    def tag_diff(self, diff_text: str, file_paths: List[str]) -> Iterator[TagTuple]:
        added = added_text_only(diff_text)
        loc = added.count("\n") + (1 if added and not added.endswith("\n") else 0)

        # Model-shape patterns ------------------------------------------
        # Track which domains we've emitted for this commit so we don't
        # repeat (one commit = one domain tag per domain). Both parent
        # and subdomain are emitted when applicable.
        domains_seen: set[str] = set()

        def _emit_domains(model_name: str):
            for d in self._domains_for_model(model_name):
                if d not in domains_seen:
                    domains_seen.add(d)
                    # Yields handled in caller via list collection
                    yield (d, loc, [(model_name, "model")])

        for model_name in self._RX_INHERIT.findall(added):
            yield ("model_override", loc, [(model_name, "model")])
            for tag_tuple in _emit_domains(model_name):
                yield tag_tuple

        for model_name in self._RX_NAME.findall(added):
            yield ("model_definition", loc, [(model_name, "model")])
            for tag_tuple in _emit_domains(model_name):
                yield tag_tuple

        if self._RX_WIZARD.search(added):
            yield ("wizard", loc, [])

        if self._RX_DEPENDS.search(added):
            yield ("compute_method", loc, [])

        if self._RX_CONSTR.search(added):
            yield ("constraint", loc, [])

        if self._RX_CTRL.search(added):
            yield ("controller", loc, [])
        if self._RX_CTRL_JSON.search(added):
            yield ("controller_json", loc, [])
        if self._RX_CTRL_PUBLIC.search(added):
            yield ("controller_public", loc, [])

        # File-path patterns ---------------------------------------------
        for f in file_paths:
            fl = f.lower()
            if "/report/" in fl or fl.endswith(".rml"):
                yield ("report", loc, [(f, "file")])
                break

        # ---- Frontend: content-based, not path-based ------------------
        # Odoo's static/src/ has no enforced layout — POS, website,
        # OWL, and legacy widgets can sit anywhere. So we classify by
        # what's IN the diff, with file paths only as additional context.
        has_static_src = any("/static/src/" in f for f in file_paths)
        has_static_tests = any("/static/tests/" in f for f in file_paths)

        if has_static_src or has_static_tests:
            js_files = [f for f in file_paths
                        if ("/static/src/" in f or "/static/tests/" in f)
                        and f.endswith((".js", ".esm.js"))]
            symbols = [(js_files[0], "file")] if js_files else []

            # ---- Manifest-driven bundle classification (canonical) ----
            # If a JS file is declared in a known asset bundle, that's
            # our strongest signal — emit the matching bundle tag.
            bundle_tags_seen: set[str] = set()
            for f in js_files:
                bundle_tag = self._classify_bundle(f)
                if bundle_tag and bundle_tag not in bundle_tags_seen:
                    yield (bundle_tag, loc, [(f, "file")])
                    bundle_tags_seen.add(bundle_tag)

            # ---- OWL / legacy widget tags (orthogonal to bundle) ----
            has_esm = any(f.endswith(".esm.js") for f in js_files)
            is_owl = self._RX_OWL.search(added) or has_esm
            is_legacy = self._RX_LEGACY_WIDGET.search(added)

            if is_owl:
                yield ("owl_component", loc, symbols)
            elif is_legacy:
                yield ("js_widget", loc, symbols)
            elif js_files and not has_static_tests and not bundle_tags_seen:
                # Frontend file under static/src with no framework signal
                # and no manifest bundle match — generic widget.
                yield ("js_widget", loc, symbols)

            # ---- POS / website fallback (when manifest didn't catch) ---
            # Older Odoo, custom bundle names, or commits that touch JS
            # before the manifest's `assets` was declared.
            if "assets_pos" not in bundle_tags_seen and (
                self._RX_POS.search(added)
                or any("/point_of_sale/" in f or "/pos_" in f for f in file_paths)
            ):
                yield ("assets_pos", loc, symbols)
            if ("assets_frontend" not in bundle_tags_seen
                    and (self._RX_WEBSITE.search(added)
                         or any("/website/" in f or "/portal/" in f
                                for f in file_paths))):
                yield ("website", loc, symbols)

        # OWL XML templates
        for f in file_paths:
            if f.endswith(".xml") and "/static/src/" in f:
                yield ("owl_template", loc, [(f, "file")])
                break

        # Styles
        for f in file_paths:
            if "/static/src/" in f and f.endswith((".scss", ".css", ".less")):
                yield ("style", loc, [(f, "file")])
                break

        # JS tests + tours
        for f in file_paths:
            if "/static/tests/" not in f:
                continue
            if f.endswith((".js", ".esm.js")):
                if "/tours/" in f:
                    yield ("tour_test", loc, [(f, "file")])
                else:
                    yield ("js_test", loc, [(f, "file")])
                break

        # Migrations: emit pre/post/end subtag + parent. The user-facing
        # concept "I wrote N migrations" is just a count; the subtag tells
        # you what kind of work it was (schema change vs data fixup vs
        # cleanup). The version itself is NOT useful as a symbol — every
        # Odoo dev has hundreds of `16.0.1.0.0` files and version naming
        # drifts across teams (`16.0.1.0.0` vs `16.1`), so a query like
        # `cc who-knows 16.0.1.0.0` is meaningless.
        # Filename conventions across OCA / OpenUpgrade / Odoo core:
        # `pre-migration.py`, `pre-migrate.py`, `pre_migration.py`, `pre.py`.
        for f in file_paths:
            m = self._RX_MIGR_PATH.search(f)
            if not m:
                continue
            fname = m.group(2).lower()
            symbols = [(f, "file")]
            if re.match(r"^pre[-_.]", fname):
                yield ("migration_pre", loc, symbols)
            elif re.match(r"^post[-_.]", fname):
                yield ("migration_post", loc, symbols)
            elif re.match(r"^end[-_.]", fname):
                yield ("migration_end", loc, symbols)
            yield ("migration", loc, symbols)
            break

        for f in file_paths:
            fl = f.lower()
            if "/tests/" in fl and self._RX_TXNCASE.search(added):
                yield ("odoo_test", loc, [(f, "file")])
                break

        # Cross-cutting --------------------------------------------------
        if self._RX_EXTAPI.search(added):
            yield ("odoo_external_api", loc, [])

        if self._RX_PERF.search(added):
            yield ("performance", loc, [])

        if self._RX_CRON.search(added):
            yield ("cron_or_queue", loc, [])

        for f in file_paths:
            fl = f.lower()
            if (fl.endswith("ir.model.access.csv") or
                    fl.endswith("/ir.model.access.csv")):
                yield ("security", loc, [(f, "file")])
                break
        if self._RX_RULE.search(added):
            yield ("security", loc, [])


def _normalize_glob(entry: str, module_dir: str) -> str:
    """
    Asset entries can be relative ("static/src/foo.js") or absolute-ish
    ("module_name/static/src/foo.js"). Normalize to the latter form so
    fnmatch comparisons against `git log` paths work uniformly.
    """
    if not entry:
        return entry
    # Strip leading slashes and '/'-prefixes
    entry = entry.lstrip("/")
    # If it doesn't start with a module name, prepend the manifest's dir
    if "/" not in entry or not entry.split("/", 1)[0]:
        return f"{module_dir}/{entry}"
    # If first segment isn't the module dir, leave as-is — it might be
    # referencing another module (Odoo allows cross-module asset includes).
    return entry
