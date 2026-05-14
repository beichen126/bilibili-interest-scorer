import sys
import os

if __package__ is None:
    __package__ = "bilibili_judge"
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from .cli import main

sys.exit(main())
