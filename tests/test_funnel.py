import pandas as pd
from src.funnel import calculate_funnel_conversion


def test_calculate_funnel_conversion():
    data = pd.DataFrame({
        'user_id': [1, 2, 3, 4, 1, 2, 3, 1, 2, 1],
        'stage': [
            'homepage', 'homepage', 'homepage', 'homepage',
            'product_view', 'product_view', 'product_view',
            'cart', 'cart',
            'checkout'
        ]
    })
    stages = ['homepage', 'product_view', 'cart', 'checkout']
    result = calculate_funnel_conversion(data, stage_col='stage', user_col='user_id', stage_order=stages)

    assert len(result) == 4
    assert result.loc[result['stage'] == 'homepage', 'users'].values[0] == 4
    assert result.loc[result['stage'] == 'product_view', 'users'].values[0] == 3
    assert result.loc[result['stage'] == 'cart', 'users'].values[0] == 2
    assert result.loc[result['stage'] == 'checkout', 'users'].values[0] == 1
    assert result.loc[result['stage'] == 'checkout', 'overall_conversion'].values[0] == 25.0
