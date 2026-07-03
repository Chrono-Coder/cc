import json
import logging
import os

from .constants import Constants

log = logging.getLogger("CC")


class JsonEditor:

    def __init__(self, path):
        """
        Initializes the JsonEditor instance with the specified file path.

        Args:
        ----
            path (str): The file path to the JSON file.

        """
        self.path = path
        self._init_dict()

    def _init_dict(self):
        """
        Initializes the dictionary for the JSON file. If the file doesn't exist,
        it creates a new one with the default data.
        """
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            log.debug(f"File not found. Creating new JSON file at: {self.path}")
            self._write({"CC Version": Constants.CC_VERSION})

        try:
            with open(self.path) as file:
                json.load(file)
        except json.JSONDecodeError:
            log.warning(f"Invalid JSON in {self.path}. Re-initializing file.")
            # self._write({"CC Version": Constants.CC_VERSION})

    def _read(self):
        """
        Reads the contents of the JSON file and returns it as a dictionary.

        Returns
        -------
            dict: The data from the JSON file.

        """
        try:
            with open(self.path) as file:
                res = json.load(file)
                file.close()
                return res
        except FileNotFoundError:
            log.error(f"Error: The file '{self.path}' was not found.")
            return {}
        except json.JSONDecodeError:
            log.error(f"Error: The file '{self.path}' contains invalid JSON.")
            return {}
        except Exception as e:
            log.error(f"An unexpected error occurred while reading the file: {e}")
            return {}

    def _write(self, data):
        """
        Writes the provided data to the JSON file.

        Args:
        ----
            data (dict): The data to write to the file.

        Returns:
        -------
            bool: True if the write operation was successful, otherwise False.

        """
        try:
            with open(self.path, "w") as file:
                json.dump(data, file, indent=4)
                file.close()
            return True
        except OSError as e:
            log.error(f"Error: Could not write to the file '{self.path}': {e}")
            return False
        except Exception as e:
            log.error(f"An unexpected error occurred while writing to the file: {e}")
            return False

    def _get(self, key, skips=0):
        """
        Retrieves a value from the nested structure (dict/list) based on the provided key,
        skipping any previous occurrences of the key.

        Args:
        ----
            key (str): The key to search for.
            skips (int): The number of times to skip the key before returning its value.

        Returns:
        -------
            The value corresponding to the key, or False if the key is not found.

        """
        data = self._read()
        skip_counter = 0
        queue = [data]

        while queue:
            curr_dict = queue.pop(0)

            for k, v in curr_dict.items():
                if key == k:
                    if skip_counter == skips:
                        return v
                    skip_counter += 1

                if isinstance(v, dict):
                    queue.append(v)

        return False

    def _get_strict(self, *args):
        """
        Retrieves a value from the nested structure (dict/list) based on a strict path of keys.

        Args:
        ----
            *args (str): A list of keys to traverse the structure.

        Returns:
        -------
            The value corresponding to the final key, or False if the key path is invalid.

        """
        data = self._read()
        queue = list(args)
        try:
            return_val = data.get(queue.pop(0))
            while queue:
                if isinstance(return_val, list):
                    key = queue.pop(0)
                    found = False
                    for item in return_val:
                        if isinstance(item, dict) and key in item:
                            return_val = item[key]
                            found = True
                            break
                    if not found:
                        return False
                elif isinstance(return_val, dict):
                    return_val = return_val.get(queue.pop(0))
                else:
                    return False
        except (KeyError, IndexError, AttributeError):
            return False
        return return_val

    def get(self, *args, **kwargs):
        """
        Retrieves a value from the nested structure, with options to either follow
        a strict or non-strict search.

        Args:
        ----
            *args (str): The list of keys to traverse the structure.
            strict (bool): Whether to use a strict search (default is True).
            skips (int): The number of occurrences of the key to skip (default is 0).

        Returns:
        -------
            The value corresponding to the final key, or False if not found.

        """
        strict = kwargs.get("strict", True)
        skips = kwargs.get("skips", 0)
        return self._get_strict(*args) if strict else self._get(args[0], skips)

    def read(self):
        """
        Reads and returns the entire data from the JSON file.

        Returns
        -------
            dict: The data from the JSON file.

        """
        return self._read()

    def write(self, data):
        """
        Writes the provided data to the JSON file.

        Args:
        ----
            data (dict): The data to write to the file.

        Returns:
        -------
            bool: True if the write operation was successful, otherwise False.

        """
        return self._write(data)

    def update(self, value, *args, new_list=False):
        """
        Updates a nested structure (dict or list) based on a given path.

        Args:
        ----
            value: The value to set at the target key.
            *args: The nested path to the key.
            new_list (bool): Whether to create a new list or use the first existing list.

        Returns:
        -------
            str | False: The last key in args if successful, otherwise False.

        """
        data = self._read()
        if not data:
            log.error(f"Cannot update JSON, file is empty or invalid: {self.path}")
            return False

        current_dict = data

        for key in args[:-1]:
            if isinstance(current_dict, list):
                found = False
                for item in current_dict:
                    if isinstance(item, dict) and key in item:
                        current_dict = item[key]
                        found = True
                        break
                if not found:
                    if new_list:
                        new_dict = {key: []}
                        current_dict.append(new_dict)
                        current_dict = new_dict[key]
                    else:
                        current_dict = []
            else:
                current_dict = current_dict.setdefault(key, {})

        if isinstance(current_dict, list):
            found = False
            for item in current_dict:
                if isinstance(item, dict):
                    if args[-1] in item:
                        item[args[-1]] = value
                        found = True
                        break
            if not found:
                if new_list or not current_dict:
                    current_dict.append({args[-1]: value})
                else:
                    current_dict[0][args[-1]] = value
        else:
            current_dict[args[-1]] = value

        if not self._write(data):
            log.error(f"Failed to write updates to JSON file: {self.path}")
            return False

        return args[-1]

    def remove(self, keys, *args):
        """
        Removes specified keys from a nested structure (dict/list) based on the provided path.

        Args:
        ----
            keys (list): A list of keys to remove.
            *args (str): The path to the dictionary to remove keys from.

        Returns:
        -------
            list | False: A list of removed keys if successful, otherwise False.

        """
        data = self._read()
        removed_keys = []
        if not data:
            log.error(f"Cannot remove keys, file is empty or invalid: {self.path}")
            return False

        current_dict = data
        for key in args:
            current_dict = current_dict.setdefault(key, {})

        for key in keys:
            if key in current_dict:
                removed_keys.append(key)
                del current_dict[key]
            else:
                log.warning(f"Key '{key}' not found in specified path. Cannot remove.")

        if not self._write(data):
            log.error(f"Failed to write removals to JSON file: {self.path}")
            return False

        return removed_keys

    def swap(self, path1, path2):
        """
        Swaps the values at two specified paths in the nested structure.

        Args:
        ----
            path1 (list): The path to the first value.
            path2 (list): The path to the second value.

        Returns:
        -------
            bool: True if the swap was successful, otherwise False.

        """
        val1 = self.get(*path1) or (self.update("", *path1) and "")
        val2 = self.get(*path2) or (self.update("", *path2) and "")
        if not self.update(val2, *path1):
            return False
        if not self.update(val1, *path2):
            return False
        return True
