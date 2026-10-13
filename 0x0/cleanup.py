#!/usr/bin/env python3

"""
    Copyright © 2020 Mia Herkt
    Licensed under the EUPL, Version 1.2 or - as soon as approved
    by the European Commission - subsequent versions of the EUPL
    (the "License");
    You may not use this work except in compliance with the License.
    You may obtain a copy of the license at:

        https://joinup.ec.europa.eu/software/page/eupl

    Unless required by applicable law or agreed to in writing,
    software distributed under the License is distributed on an
    "AS IS" basis, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
    either express or implied.
    See the License for the specific language governing permissions
    and limitations under the License.
"""

import os
import sys
import time
import datetime
from fhost import app

def cleanup_expired(storage_path, maxs, mind=30, maxd=365):
    names = os.listdir(storage_path)
    systime = time.time()
    remaining = set()

    for name in names:
        path = os.path.join(storage_path, name)
        if not os.path.isfile(path):
            continue
        stat = os.stat(path)
        age = datetime.timedelta(seconds=(systime - stat.st_mtime)).days
        maxage = mind + (-maxd + mind) * (stat.st_size / maxs - 1) ** 3
        if age >= maxage:
            os.remove(path)
        else:
            remaining.add(name)

    index_dir = os.path.join(storage_path, ".csv-index")
    if not os.path.isdir(index_dir):
        return
    for name in os.listdir(index_dir):
        sha = name.split(".")[0]
        if sha not in remaining:
            os.remove(os.path.join(index_dir, name))


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
    cleanup_expired(app.config["FHOST_STORAGE_PATH"], app.config["MAX_CONTENT_LENGTH"])
