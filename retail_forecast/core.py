"""Weekly, one-step-ahead forecasting with chronological model selection."""
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

KEYS = ["store_id", "product_id"]
FEATURES = ["product_code", "store_code", "week_sin", "week_cos", "time_index",
            "lag_1", "lag_2", "lag_4", "lag_13", "lag_52", "mean_4", "mean_13", "std_4"]

def metrics(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if not len(actual) or actual.shape != predicted.shape:
        raise ValueError("Metrics require equal nonempty arrays")
    error = np.abs(actual - predicted)
    denominator = np.abs(actual).sum()
    return {"mae": float(error.mean()), "wape": float(error.sum()/denominator) if denominator else None,
            "bias": float((predicted-actual).mean()), "observations": len(actual)}

def aggregate_weekly(sales):
    if sales.empty:
        raise ValueError("No eligible sales")
    rows = sales.copy()
    rows["week"] = rows["date"].dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")
    with sqlite3.connect(":memory:") as connection:
        rows[["store_id", "product_id", "week", "quantity", "revenue"]].to_sql("sales", connection, index=False)
        sql = (Path(__file__).parent / "weekly_sales.sql").read_text()
        weekly = pd.read_sql_query(sql, connection, parse_dates=["week"])
    # Drop edge weeks: the extraction may begin/end part-way through a week.
    first = rows["date"].min().normalize()
    start = first.to_period("W-SUN").start_time
    if first != start:
        start += pd.Timedelta(weeks=1)
    end = rows["date"].max().to_period("W-SUN").start_time - pd.Timedelta(weeks=1)
    return weekly.loc[weekly["week"].between(start, end)].reset_index(drop=True)

def build_panel(weekly, test_weeks=12, validation_weeks=8, top_products=20):
    weeks = pd.date_range(weekly.week.min(), weekly.week.max(), freq="W-MON")
    if len(weeks) < 52 + test_weeks + validation_weeks + 8:
        raise ValueError("Need at least 52 history weeks, 8 fitting weeks and the requested holdouts")
    test_start, validation_start = weeks[-test_weeks], weeks[-test_weeks-validation_weeks]
    # Product selection uses only the earliest training period, before validation.
    candidates = weekly[weekly.week < validation_start]
    selected = (candidates.groupby("product_id").units.sum().sort_values(ascending=False)
                .head(top_products).index.astype(str).tolist())
    pairs = candidates[candidates.product_id.isin(selected)][KEYS].drop_duplicates().sort_values(KEYS)
    frames=[]
    for store, product in pairs.itertuples(index=False, name=None):
        item = weekly[(weekly.store_id == store) & (weekly.product_id == product)].set_index("week")
        item = item.reindex(weeks)
        item["week"] = weeks
        item["store_id"], item["product_id"] = store, product
        item["observed_transactions"] = item.units.notna()
        item[["units", "revenue"]] = item[["units", "revenue"]].fillna(0)
        frames.append(item.reset_index(drop=True))
    panel=pd.concat(frames, ignore_index=True)
    return panel, test_start, validation_start

def make_features(panel):
    panel=panel.sort_values(KEYS+["week"]).copy()
    grouped=panel.groupby(KEYS, sort=False)["units"]
    for lag in [1, 2, 4, 13, 52]:
        panel[f"lag_{lag}"]=grouped.shift(lag)
    for window in [4, 13]:
        panel[f"mean_{window}"]=grouped.transform(lambda values: values.shift(1).rolling(window).mean())
    panel["std_4"]=grouped.transform(lambda values: values.shift(1).rolling(4).std(ddof=0))
    week=panel.week.dt.isocalendar().week.astype(float)
    panel["week_sin"],panel["week_cos"]=np.sin(2*np.pi*week/52.18),np.cos(2*np.pi*week/52.18)
    panel["time_index"]=(panel.week-panel.week.min()).dt.days/7
    panel["product_code"]=pd.Categorical(panel.product_id, categories=sorted(panel.product_id.unique())).codes
    panel["store_code"]=pd.Categorical(panel.store_id, categories=sorted(panel.store_id.unique())).codes
    return panel

def fit_model(training, params):
    model=HistGradientBoostingRegressor(loss="poisson", early_stopping=False, random_state=42,
        max_iter=120, learning_rate=0.07, min_samples_leaf=15, **params)
    model.fit(training[FEATURES], training.units)
    return model

def run_backtest(weekly, test_weeks=12, top_products=20):
    panel,test_start,validation_start=build_panel(weekly,test_weeks=test_weeks,top_products=top_products)
    features=make_features(panel).dropna(subset=FEATURES)
    initial=features[features.week < validation_start]
    validation=features[features.week.between(validation_start,test_start,inclusive="left")]
    choices=[]
    for leaves,l2 in [(7,1.0),(15,5.0),(31,10.0)]:
        params={"max_leaf_nodes":leaves,"l2_regularization":l2}
        model=fit_model(initial,params)
        score=metrics(validation.units,model.predict(validation[FEATURES]))
        choices.append({"parameters":params,**score})
    best=min(choices,key=lambda result:result["mae"])
    train,test=features[features.week<test_start],features[features.week>=test_start].copy()
    model=fit_model(train,best["parameters"])
    test["gradient_boosting"]=np.maximum(0,model.predict(test[FEATURES]))
    test["seasonal_naive"]=test.lag_52
    test["rolling_mean"]=test.mean_4
    scores={name:metrics(test.units,test[name]) for name in ["gradient_boosting","seasonal_naive","rolling_mean"]}
    predictions=test[KEYS+["week","units","gradient_boosting","seasonal_naive","rolling_mean"]].rename(columns={"units":"actual"})
    predictions["absolute_error"]=(predictions.actual-predictions.gradient_boosting).abs()
    predictions["baseline_absolute_error"]=(predictions.actual-predictions.seasonal_naive).abs()
    per_product=[]
    for (store,product),part in predictions.groupby(KEYS):
        per_product.append({"store_id":store,"product_id":product,**metrics(part.actual,part.gradient_boosting)})
    # Next-week production example refits using all available complete weeks.
    future_week=panel.week.max()+pd.Timedelta(weeks=1)
    future=panel.groupby(KEYS,as_index=False).tail(1).copy()
    future["week"],future["units"],future["revenue"]=future_week,np.nan,np.nan
    future_features=make_features(pd.concat([panel,future],ignore_index=True))
    future_features=future_features[future_features.week==future_week]
    final=fit_model(features,best["parameters"])
    future_features["forecast_units"]=np.maximum(0,final.predict(future_features[FEATURES]))
    summary={"evaluation":"rolling one-week-ahead; frozen model; observed previous test weeks may enter lags",
        "target":"positive units sold, not latent demand", "train_start":str(train.week.min().date()),
        "train_end":str(train.week.max().date()),"test_start":str(test_start.date()),"test_end":str(test.week.max().date()),
        "validation_start":str(validation_start.date()),"training_rows":len(train),"products":panel.product_id.nunique(),
        "stores":panel.store_id.nunique(),"selected_parameters":best["parameters"],"validation_candidates":choices,
        "models":scores,"imputed_zero_weeks":int((~panel.observed_transactions).sum())}
    return predictions,panel,pd.DataFrame(per_product),future_features[KEYS+["week","forecast_units"]],summary

def demo_weekly():
    rng=np.random.default_rng(42)
    frames=[]
    weeks=pd.date_range("2022-01-03",periods=130,freq="W-MON")
    for store in ["DEMO_NORTH","DEMO_SOUTH"]:
        for product in range(8):
            t=np.arange(len(weeks)); scale=30+15*product
            units=rng.poisson(np.maximum(1,scale*(1+.35*np.sin(2*np.pi*t/52))+.12*t))
            frames.append(pd.DataFrame({"store_id":store,"product_id":str(10000+product),"week":weeks,
                                        "units":units,"revenue":units*(product+2)}))
    return pd.concat(frames,ignore_index=True)
