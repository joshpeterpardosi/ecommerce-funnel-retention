import pandas as pd


def calculate_cohort_retention(df: pd.DataFrame, user_col: str, date_col: str, freq: str = 'ME') -> pd.DataFrame:
    """Calculate user cohort retention rates matrix over time periods."""
    data = df.copy()
    data[date_col] = pd.to_datetime(data[date_col])
    
    data['period'] = data[date_col].dt.to_period(freq[0] if freq in ['M', 'ME'] else freq)
    data['cohort'] = data.groupby(user_col)['period'].transform('min')

    cohort_group = data.groupby(['cohort', 'period'])[user_col].nunique().reset_index()
    cohort_group['period_idx'] = (cohort_group['period'] - cohort_group['cohort']).apply(lambda x: x.n)

    cohort_pivot = cohort_group.pivot(index='cohort', columns='period_idx', values=user_col)
    cohort_size = cohort_pivot.iloc[:, 0]
    retention_matrix = cohort_pivot.divide(cohort_size, axis=0).round(4) * 100

    return retention_matrix
