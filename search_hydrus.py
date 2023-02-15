#!/usr/bin/env python3

# Copyright (C) 2021 cryzed
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import pprint
import sys
import os
import time
import dotenv

import hydrus_api
import hydrus_api.utils

ERROR_EXIT_CODE = 1
REQUIRED_PERMISSIONS = {
    hydrus_api.Permission.IMPORT_URLS,
    hydrus_api.Permission.IMPORT_FILES,
    hydrus_api.Permission.ADD_TAGS,
    hydrus_api.Permission.SEARCH_FILES,
    hydrus_api.Permission.MANAGE_PAGES,
}

dotenv.load_dotenv()

api_key = os.getenv("HYDRUS_ACCESS_KEY")
client = hydrus_api.Client(api_key)
print(f"Client API version: v{client.VERSION} | Endpoint API version: v{client.get_api_version()['version']}")

if not hydrus_api.utils.verify_permissions(client, REQUIRED_PERMISSIONS):
    print("The API key does not grant all required permissions:", REQUIRED_PERMISSIONS)
    sys.exit(ERROR_EXIT_CODE)

all_file_ids = client.search_files([sys.argv[1:]])
for file_ids in hydrus_api.utils.yield_chunks(all_file_ids, 100):
    print(client.get_file_metadata(file_ids=file_ids))
