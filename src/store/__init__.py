import common
import copy
import importlib
import datetime
from collections import defaultdict

experiment_filter = {}
benchmark_mode = False

DEFAULT_MODE = "mpi_benchmark"
def parse_argv(argv):
    for expe_filter in argv:
        if expe_filter == "run":
            key, value = "__run__", True
        elif expe_filter == "clean":
            key, value = "__clean__", True
        elif expe_filter == "parse_only":
            key, value = "__parse_only__", True
        elif "=" not in expe_filter:
            if "expe" in experiment_filter:
                raise ValueError(f"Unexpected argument '{expe_filter}'")
            key, value = "expe", expe_filter
        else:
            key, _, value = expe_filter.partition("=")

        experiment_filter[key] = value

    return experiment_filter.pop("mode", DEFAULT_MODE)

def load_store():
    print("Loading storage module ...")
    store_pkg_name = f"workload.store"
    try: store_module = importlib.import_module(store_pkg_name)
    except ModuleNotFoundError as e:
        print(f"FATAL: Failed to load the storage module: {e}")
        raise e

    print(f"Loading the storage module ... done")
    return store_module

def add_to_matrix(import_settings, location, results):
    import_key = common.Matrix.settings_to_key(import_settings)
    if import_key in common.Matrix.import_map:
        print(f"WARNING: duplicated results key: {import_key}")
        try:
            old_location = common.Matrix.import_map[import_key].location
        except AttributeError:
            _, old_location = common.Matrix.import_map[import_key]

        print(f"WARNING:   old: {old_location}")
        print(f"WARNING:   new: {location}")
        return

    try: processed_settings = custom_rewrite_settings(dict(import_settings))
    except Exception as e:
        print(f"ERROR: failed to rewrite settings for entry at '{location}'")
        raise e

    if not processed_settings:
        #print(f"INFO: entry '{import_key}' skipped by rewrite_settings()")
        common.Matrix.import_map[import_key] = True, location
        return

    keep = True
    for k, v in experiment_filter.items():
        if k.startswith("__"): continue
        if str(processed_settings.get(k, None)) != v:
            return None

    processed_key = common.Matrix.settings_to_key(processed_settings)

    if processed_key in common.Matrix.processed_map:
        print(f"WARNING: duplicated processed key: {processed_key}")
        print(f"WARNING: duplicated import key:    {import_key}")
        entry = common.Matrix.processed_map[processed_key]
        print(f"WARNING:   old: {entry.location}")
        print(f"WARNING:   new: {location}")
        common.Matrix.import_map[import_key] = entry

        processed_settings["run"] = (str(processed_settings.get("run")) + "_" +
                                     datetime.datetime.now().strftime("%H%M%S.%f"))
        processed_key = common.Matrix.settings_to_key(processed_settings)
        return

    entry = common.MatrixEntry(location, results,
                              processed_key, import_key,
                              processed_settings, import_settings)

    gather_rolling_entries(entry)

    return entry

def gather_rolling_entries(entry):
    gathered_settings = dict(entry.params.__dict__)
    gathered_keys = []
    for k in gathered_settings.keys():
        if not k.startswith("@"): continue
        gathered_settings[k] = "<all>"
        gathered_keys.append(k)

    if not gathered_keys: return

    gathered_entry = common.Matrix.get_record(gathered_settings)
    if not gathered_entry:
        processed_key = common.Matrix.settings_to_key(gathered_settings)
        import_key = None
        import_settings = None
        location = entry.location + f"({', '.join(gathered_keys)} gathered)"
        gathered_entry = common.MatrixEntry(
            location, [],
            processed_key, import_key,
            gathered_settings, import_settings
        )
        gathered_entry.is_gathered = True
        gathered_entry.gathered_keys = defaultdict(set)

    gathered_entry.results.append(entry)
    for gathered_key in gathered_keys:
        gathered_entry.gathered_keys[gathered_key].add(entry.params.__dict__[gathered_key])

custom_rewrite_settings = lambda x:x # may be overriden
