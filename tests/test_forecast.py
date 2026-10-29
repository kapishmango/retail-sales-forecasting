import numpy as np
import pandas as pd
import pytest
from retail_forecast.core import demo_weekly,make_features,build_panel,metrics,run_backtest
from retail_forecast.data import clean_transactions

def test_features_do_not_use_current_or_future_sales():
    panel,_,_=build_panel(demo_weekly())
    cutoff=pd.Timestamp("2024-01-01")
    before=make_features(panel)
    changed=panel.copy();changed.loc[changed.week>=cutoff,"units"]+=1_000_000
    after=make_features(changed)
    columns=["lag_1","lag_2","lag_4","lag_13","lag_52","mean_4","mean_13","std_4"]
    pd.testing.assert_frame_equal(before.loc[before.week<=cutoff,columns],after.loc[after.week<=cutoff,columns])

def test_product_selection_ignores_holdout_sales():
    weekly=demo_weekly()
    original,_,_=build_panel(weekly,top_products=2)
    weekly.loc[weekly.week>=weekly.week.max()-pd.Timedelta(weeks=10),"units"]*=100_000
    changed,_,_=build_panel(weekly,top_products=2)
    assert set(original.product_id)==set(changed.product_id)

def test_wape_is_weighted_and_zero_denominator_is_explicit():
    assert metrics([1,99],[0,100])["wape"]==pytest.approx(.02)
    assert metrics([0,0],[1,2])["wape"] is None

def test_returns_duplicates_and_bad_dates_are_separated():
    base={"invoice_id":"1","product_id":"10001","description":"Item","quantity":2,
          "date":"2011-01-01","unit_price":3,"customer_id":"1","country":"UK"}
    frame=pd.DataFrame([base,base,{**base,"invoice_id":"C1","quantity":-2},
                        {**base,"invoice_id":"2","date":"invalid"}])
    sales,returns,audit=clean_transactions(frame)
    assert len(sales)==1 and len(returns)==1
    assert audit["duplicate_rows"]==1 and audit["invalid_rows"]==1

def test_backtest_is_chronological_and_forecasts_nonnegative():
    predictions,panel,products,future,summary=run_backtest(demo_weekly(),top_products=3)
    assert summary["train_end"]<summary["test_start"]
    assert len(predictions)==2*3*12
    assert (predictions.gradient_boosting>=0).all()
    assert future.week.min()>predictions.week.max()
    np.testing.assert_allclose(predictions.absolute_error,(predictions.actual-predictions.gradient_boosting).abs())
