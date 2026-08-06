import pandas as pd


def calculate_funnel_conversion(df: pd.DataFrame, stage_col: str, user_col: str, stage_order: list[str]) -> pd.DataFrame:
    """Calculate unique users and conversion rates across sequential funnel stages."""
    counts = []
    for stage in stage_order:
        unique_users = df[df[stage_col] == stage][user_col].nunique()
        counts.append(unique_users)

    funnel_df = pd.DataFrame({'stage': stage_order, 'users': counts})
    top_stage_users = counts[0] if counts and counts[0] > 0 else 1
    
    funnel_df['overall_conversion'] = (funnel_df['users'] / top_stage_users * 100).round(2)
    funnel_df['step_conversion'] = (funnel_df['users'] / funnel_df['users'].shift(1).fillna(funnel_df['users'].iloc[0]) * 100).round(2)
    funnel_df['dropoff_rate'] = (100 - funnel_df['step_conversion']).round(2)

    return funnel_df
