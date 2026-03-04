
import os
import sys
import re
from os.path import dirname

ta_name = 'Splunk_TA_aws'
pattern = re.compile(r'[\\/]etc[\\/]apps[\\/][^\\/]+[\\/]bin[\\/]?$')
new_paths = [path for path in sys.path if not pattern.search(path) or ta_name in path]
new_paths.insert(0, os.path.join(dirname(dirname(__file__)), "lib"))
new_paths.insert(0, os.path.sep.join([os.path.dirname(__file__), ta_name]))
sys.path = new_paths

bindir = os.path.dirname(os.path.realpath(os.path.dirname(__file__)))
libdir = os.path.join(bindir, "lib")
platform = sys.platform
python_version = "".join(str(x) for x in sys.version_info[:2])

if python_version == "3.9.20":
	if platform.startswith("win"):
		sys.path.insert(0, os.path.join(libdir, "3rdparty/windows_x86_64/python39"))
	if platform.startswith("linux"):
		sys.path.insert(0, os.path.join(libdir, "3rdparty/linux_x86_64/python39"))
	if platform.startswith("darwin"):
		sys.path.insert(0, os.path.join(libdir, "3rdparty/darwin_x86_64/python39"))
