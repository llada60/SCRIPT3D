# Copyright (C) 2023, Princeton University.
# This source code is licensed under the BSD 3-Clause license found in the LICENSE file in the root directory
# of this source tree.

# Authors: Alexander Raistrick

import os
import site
import sys

pwd = os.getcwd()
sys.path.append(pwd)

user_site = site.getusersitepackages()
if user_site not in sys.path:
    sys.path.insert(0, user_site)
