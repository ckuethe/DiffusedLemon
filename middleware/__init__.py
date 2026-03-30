import sys
import os

sys_path_added = False
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))
    sys_path_added = True
