from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

DEFAULT_STATE_CODE = "SC"
DEFAULT_GOLD_REPORT_SOURCE_TABLE = "trade_gold"
REPORT_VOLUME_NAME = "comex_reports"


@dataclass(frozen=True)
class Project:
    catalog: str
    schema: str
    state_code: str = DEFAULT_STATE_CODE
    gold_table: str | None = None

    def table(self, table_name: str) -> str:
        return f"{self.catalog}.{self.schema}.{table_name}"

    def volume_path(self, volume_name: str) -> str:
        return str(PurePosixPath("/Volumes") / self.catalog / self.schema / volume_name)

    @property
    def gold_source_table(self) -> str:
        return self.gold_table or self.table(DEFAULT_GOLD_REPORT_SOURCE_TABLE)

    @property
    def report_volume_path(self) -> str:
        return self.volume_path(REPORT_VOLUME_NAME)

    @property
    def default_report_path(self) -> str:
        file_name = f"comex_report_{self.state_code.lower()}.xlsx"
        return str(PurePosixPath(self.report_volume_path) / file_name)
