"""Server-controlled catalog of locally managed historical datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ValidationStatus = Literal[
    "pending_validation", "descriptive_only", "historical_simulation"
]
AssetType = Literal["equity_etf", "fixed_income_etf", "commodity_etf"]


@dataclass(frozen=True)
class DatasetDefinition:
    dataset_id: str
    ticker: str
    name: str
    asset_type: AssetType
    exposure: str
    currency: str
    validation_status: ValidationStatus
    validation_note: str
    csv_filename: str | None = None
    metadata_filename: str | None = None
    requested_start: str | None = None
    requested_end: str | None = None
    expected_sha256: str | None = None

    @property
    def descriptive_analysis(self) -> bool:
        return self.validation_status in ("descriptive_only", "historical_simulation")

    @property
    def historical_simulation(self) -> bool:
        return self.validation_status == "historical_simulation"


DATASET_CATALOG: tuple[DatasetDefinition, ...] = (
    DatasetDefinition(
        dataset_id="spy-2020-2025",
        ticker="SPY",
        name="SPDR S&P 500 ETF Trust",
        asset_type="equity_etf",
        exposure="Acciones estadounidenses de gran capitalización; índice S&P 500.",
        currency="USD",
        validation_status="descriptive_only",
        validation_note=(
            "Análisis descriptivo disponible; simulación histórica bloqueada porque "
            "los dividendos no están procesados y reconciliados por el motor."
        ),
        csv_filename="SPY_2020-01-01_2025-01-01.csv",
        metadata_filename="SPY_2020-01-01_2025-01-01.metadata.json",
        requested_start="2020-01-01",
        requested_end="2025-01-01",
    ),
    DatasetDefinition(
        dataset_id="qqq-2020-2025",
        ticker="QQQ",
        name="Invesco QQQ Trust",
        asset_type="equity_etf",
        exposure="Acciones de grandes empresas no financieras del Nasdaq-100.",
        currency="USD",
        validation_status="descriptive_only",
        validation_note=(
            "Análisis descriptivo disponible para precios Close. La simulación histórica "
            "sigue bloqueada hasta reconciliar los eventos corporativos de QQQ."
        ),
        csv_filename="QQQ_2020-01-01_2025-01-01.csv",
        metadata_filename="QQQ_2020-01-01_2025-01-01.metadata.json",
        requested_start="2020-01-01",
        requested_end="2025-01-01",
        expected_sha256="317adb88957c3d14b001aa514413e73653e689f4b0560c471cff502c5504dbbb",
    ),
    DatasetDefinition(
        dataset_id="iwm-pending",
        ticker="IWM",
        name="iShares Russell 2000 ETF",
        asset_type="equity_etf",
        exposure="Acciones estadounidenses de pequeña capitalización del Russell 2000.",
        currency="USD",
        validation_status="pending_validation",
        validation_note="No hay datos históricos validados registrados para IWM.",
    ),
    DatasetDefinition(
        dataset_id="tlt-pending",
        ticker="TLT",
        name="iShares 20+ Year Treasury Bond ETF",
        asset_type="fixed_income_etf",
        exposure="Bonos del Tesoro de Estados Unidos con vencimientos superiores a 20 años.",
        currency="USD",
        validation_status="pending_validation",
        validation_note="No hay datos históricos validados registrados para TLT.",
    ),
    DatasetDefinition(
        dataset_id="gld-pending",
        ticker="GLD",
        name="SPDR Gold Shares",
        asset_type="commodity_etf",
        exposure="Exposición al precio del oro físico, menos gastos del fondo.",
        currency="USD",
        validation_status="pending_validation",
        validation_note="No hay datos históricos validados registrados para GLD.",
    ),
)

_BY_ID = {entry.dataset_id: entry for entry in DATASET_CATALOG}


def get_dataset_definition(dataset_id: str) -> DatasetDefinition | None:
    """Look up an ID; callers never receive or provide a filesystem path."""
    return _BY_ID.get(dataset_id)
