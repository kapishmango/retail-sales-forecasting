import argparse
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .core import aggregate_weekly, demo_weekly, run_backtest
from .data import download,load_transactions,clean_transactions,provenance,write_json

def main(argv=None):
    parser=argparse.ArgumentParser(description="Reproducible retail sales forecasting")
    commands=parser.add_subparsers(dest="command",required=True)
    fetch=commands.add_parser("download");fetch.add_argument("--directory",default="data/raw")
    run=commands.add_parser("run")
    source=run.add_mutually_exclusive_group(required=True)
    source.add_argument("--input",type=Path);source.add_argument("--demo",action="store_true")
    run.add_argument("--output",type=Path,default=Path("reports"))
    run.add_argument("--top-products",type=int,default=20)
    run.add_argument("--test-weeks",type=int,default=12)
    args=parser.parse_args(argv)
    if args.command=="download":
        print(download(args.directory));return
    if args.top_products<1 or args.test_weeks<1:
        parser.error("Product count and test weeks must be positive")
    args.output.mkdir(parents=True,exist_ok=True)
    if args.demo:
        weekly=demo_weekly();audit={"source":"SYNTHETIC DEMO","seed":42}
    else:
        sales,returns,audit=clean_transactions(load_transactions(args.input))
        weekly=aggregate_weekly(sales)
        audit={**provenance(args.input),"cleaning":audit,"returns_revenue_gbp":float(returns.revenue.sum())}
    predictions,panel,products,future,summary=run_backtest(weekly,args.test_weeks,args.top_products)
    summary["data_source"]=audit["source"]
    for name,frame in [("predictions",predictions),("weekly_sales",panel),("product_metrics",products),("next_week_forecast",future)]:
        frame.to_csv(args.output/f"{name}.csv",index=False,float_format="%.6f")
    write_json(args.output/"metrics.json",summary);write_json(args.output/"provenance.json",audit)
    render_plot(predictions,args.output,audit['source'])
    print(f"Saved {len(predictions)} evaluated forecasts to {args.output}")
    for name,result in summary["models"].items(): print(name,result)

def render_plot(predictions,output,source):
    totals=predictions.groupby("week")[["actual","gradient_boosting","seasonal_naive","rolling_mean"]].sum()
    plt.rcParams.update({"font.family":"DejaVu Sans","axes.spines.top":False,"axes.spines.right":False})
    fig,axes=plt.subplots(2,1,figsize=(11,7),gridspec_kw={"height_ratios":[2,1]},layout="constrained")
    for column,label,color in [("actual","Actual units","#193f48"),("gradient_boosting","Gradient boosting","#dc784c"),("seasonal_naive","Seasonal naive (52 weeks)","#9bb4b6"),("rolling_mean","Moving average (4 weeks)","#9381ac")]:
        axes[0].plot(totals.index,totals[column],label=label,color=color,linewidth=2.5)
    axes[0].set_title("Retail demand signals | chronological holdout",loc="left",fontweight="bold",fontsize=16)
    axes[0].set_ylabel("Units sold");axes[0].legend(frameon=False)
    errors=predictions.groupby("week")[["absolute_error","baseline_absolute_error"]].sum()
    axes[1].plot(errors.index,errors.absolute_error,label="Gradient boosting",color="#dc784c")
    axes[1].plot(errors.index,errors.baseline_absolute_error,label="Seasonal naive",color="#9bb4b6")
    axes[1].set_ylabel("Absolute error");axes[1].set_xlabel(f"{source} | positive sales; stock availability unknown")
    fig.savefig(output/"forecast.png",dpi=150);plt.close(fig)

if __name__=="__main__":main()
