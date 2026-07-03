import Database from "better-sqlite3";
import path from "path";
import os from "os";

const DB_PATH = path.join(/* turbopackIgnore: true */ os.homedir(), ".cc-cli", "cc_cli.db");

let _db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!_db) {
    _db = new Database(DB_PATH, { readonly: true });
    _db.pragma("query_only = ON");
  }
  return _db;
}
