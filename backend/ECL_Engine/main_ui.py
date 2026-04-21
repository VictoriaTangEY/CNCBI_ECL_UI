##############################################################################################
"""
CNCBI ECL Tool — UI entry point.

Loads run config from --configPath, ensures config_path is set for data_merge, then runs
the same pipeline as main_batch.main without BatchFolderMaintain (no extra batch DB record).
"""
##############################################################################################

import argparse
import json
from pathlib import Path
from main_batch import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--configPath", type=str, required=True)
    args = parser.parse_args()

    config_path = str(Path(args.configPath).resolve())
    with open(config_path, "r", encoding="utf-8") as f:
        run_config = json.load(f)

    run_config["config_path"] = config_path
    main(run_config)
