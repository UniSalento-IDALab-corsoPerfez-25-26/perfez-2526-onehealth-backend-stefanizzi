"""Load the archived Master Dataset and the qualified DSS supplement."""

import pandas as pd

from services.analytics.app.repository import AnalyticsRepository


class DSSRepository(AnalyticsRepository):
    def load(self) -> pd.DataFrame:
        master = super().load()
        supplement_path = self.dataset_path.with_name("one_health_dss_2024.parquet")
        if not supplement_path.is_file() or master["year"].eq(2024).any():
            return master
        supplement = pd.read_parquet(supplement_path)
        return pd.concat([master, supplement], ignore_index=True)
