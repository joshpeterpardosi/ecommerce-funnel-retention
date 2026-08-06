import pandas as pd
from src.retention import calculate_cohort_retention


def test_calculate_cohort_retention():
    data = pd.DataFrame({
        'user_id': [1, 1, 1, 2, 2],
        'timestamp': ['2026-01-10', '2026-02-15', '2026-03-20', '2026-01-12', '2026-02-18']
    })
    matrix = calculate_cohort_retention(data, user_col='user_id', date_col='timestamp', freq='M')

    assert 0 in matrix.columns
    assert 1 in matrix.columns
    assert matrix.loc['2026-01', 0] == 100.0
    assert matrix.loc['2026-01', 1] == 100.0
