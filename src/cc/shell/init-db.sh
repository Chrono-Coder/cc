#! /bin/bash
# Check if the first argument exists
if [ $# -ne 4 ]; then
  echo "Error: Not Enough Arguments"
  exit 1
fi

# Define variables for convenience
FILE_NAME="$1"
FILE_PATH="$2"
DB_NAME="$3"
CLEANDB_PATH="$4"
DIR_PATH=$(dirname "$FILE_PATH")

if [ -d "$DIR_PATH/$DB_NAME" ]; then
    rm -rf "$DIR_PATH/$DB_NAME"
fi

mkdir -p "$DIR_PATH/$DB_NAME"
unzip "$FILE_PATH" -d "$DIR_PATH/$DB_NAME"


dropdb "$DB_NAME"
createdb "$DB_NAME"

psql "$DB_NAME" < "$DIR_PATH/$DB_NAME"/dump.sql
psql "$DB_NAME" < $CLEANDB_PATH

rm -rf ~/.local/share/Odoo/filestore/$DB_NAME/
mkdir ~/.local/share/Odoo/filestore/$DB_NAME/

SOURCE="$DIR_PATH/$DB_NAME/filestore"
TARGET="$HOME/.local/share/Odoo/filestore/$DB_NAME"

if [ -d "$SOURCE" ] && [ "$(find "$SOURCE" -type f -print -quit)" ]; then
    mkdir -p "$TARGET"

    cp -r "$SOURCE"/* "$TARGET"
    echo "Files copied successfully from $SOURCE to $TARGET."
else
    echo "No files to copy. Source directory $SOURCE is empty or does not exist."
fi

rm -rf "$DIR_PATH/$DB_NAME"
