import sys

import pytest


def exit_on_failure(ret, message=None):
    if ret:
        sys.exit(ret)


if __name__ == "__main__":
    exit_on_failure(pytest.main())
