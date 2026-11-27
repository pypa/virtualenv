from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from virtualenv.app_data import ReadOnlyAppData

if TYPE_CHECKING:
    from pathlib import Path


def test_read_only_app_data_refuses_update_log_with_a_reason(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError, match=r"^read-only app data does not keep an embed update log$"):
        ReadOnlyAppData(str(tmp_path)).embed_update_log("pip", "3.12")
