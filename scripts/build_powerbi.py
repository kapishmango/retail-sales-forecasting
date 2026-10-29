"""Build an editable PBIP/PBIR report with an embedded, refreshable import table.

No Windows-only tooling is needed to regenerate the text sources. Open and
refresh in Power BI Desktop to materialize data and perform final visual QA.
"""
from pathlib import Path
import csv
import json
import uuid

ROOT=Path(__file__).resolve().parents[1]
BASE="https://developer.microsoft.com/json-schemas/fabric/"
OUT=ROOT/"powerbi"

def write(path,value):
    target=OUT/path;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

def schema(path):return BASE+path+"/schema.json"

def field(name,measure=False):
    return {"Measure" if measure else "Column":{"Expression":{"SourceRef":{"Entity":"Forecasts"}},"Property":name}}

def projection(name,measure=False):
    return {"field":field(name,measure),"queryRef":"Forecasts."+name,"nativeQueryRef":name}

def literal(value):return {"expr":{"Literal":{"Value":value}}}

def visual(name,kind,title,x,y,w,h,roles):
    value={"$schema":schema("item/report/definition/visualContainer/1.0.0"),"name":name,
        "position":{"x":x,"y":y,"width":w,"height":h,"z":0,"tabOrder":0},
        "visual":{"visualType":kind,"query":{"queryState":{role:{"projections":projections} for role,projections in roles.items()}},
            "visualContainerObjects":{"title":[{"properties":{"show":literal("true"),"text":literal("'"+title.replace("'","''")+"'")}}]},
            "drillFilterOtherVisuals":True}}
    if kind=="lineChart":
        value["visual"]["query"]["sortDefinition"]={"sort":[{"field":field("Week"),"direction":"Ascending"}],"isDefaultSort":True}
    write(Path("RetailForecast.Report/definition/pages/overview/visuals")/name/"visual.json",value)

def main():
    rows=list(csv.DictReader((ROOT/"reports/predictions.csv").open()))
    if not rows:raise ValueError("Generate forecast reports before building Power BI sources")
    columns=[("Store","store_id","string","text"),("Product","product_id","string","text"),
        ("Week","week","dateTime","date"),("Actual","actual","double","number"),
        ("Forecast","gradient_boosting","double","number"),("Seasonal naive","seasonal_naive","double","number"),
        ("Rolling mean","rolling_mean","double","number"),("Absolute error","absolute_error","double","number"),
        ("Baseline absolute error","baseline_absolute_error","double","number")]
    embedded=[]
    for row in rows:
        values=[]
        for name,key,dtype,mtype in columns:
            if mtype=="date":
                year,month,day=map(int,row[key][:10].split("-"));values.append(f"#date({year},{month},{day})")
            elif mtype=="text":values.append('"'+row[key].replace('"','""')+'"')
            else:values.append(str(float(row[key])))
        embedded.append("    {"+", ".join(values)+"}")
    tabletype=", ".join('#"'+name+'" = '+mtype for name,_,_,mtype in columns)
    expression="let\n  Source = #table(type table ["+tabletype+"], {\n"+",\n".join(embedded)+"\n  })\nin\n  Source"
    measures=[
        ("Actual units","SUM('Forecasts'[Actual])","#,0"),
        ("Forecast units","SUM('Forecasts'[Forecast])","#,0"),
        ("Seasonal baseline units","SUM('Forecasts'[Seasonal naive])","#,0"),
        ("Moving average units","SUM('Forecasts'[Rolling mean])","#,0"),
        ("MAE","AVERAGE('Forecasts'[Absolute error])","#,0.0"),
        ("WAPE","DIVIDE(SUM('Forecasts'[Absolute error]), SUMX('Forecasts', ABS('Forecasts'[Actual])))","0.0%"),
        ("Baseline WAPE","DIVIDE(SUM('Forecasts'[Baseline absolute error]), SUMX('Forecasts', ABS('Forecasts'[Actual])))","0.0%"),
        ("Forecast absolute error","SUM('Forecasts'[Absolute error])","#,0"),
        ("Seasonal absolute error","SUM('Forecasts'[Baseline absolute error])","#,0")]
    table={"name":"Forecasts","columns":[{"name":name,"dataType":dtype,"sourceColumn":name,
        "summarizeBy":"none" if dtype in {"string","dateTime"} else "sum",
        **({"formatString":"dd MMM yyyy"} if dtype=="dateTime" else {})} for name,_,dtype,_ in columns],
        "measures":[{"name":name,"expression":expr,"formatString":fmt} for name,expr,fmt in measures],
        "partitions":[{"name":"Forecasts","mode":"import","source":{"type":"m","expression":expression.splitlines()}}]}
    write(Path("RetailForecast.SemanticModel/model.bim"),{"name":"RetailForecast","compatibilityLevel":1600,
        "model":{"culture":"en-US","defaultPowerBIDataSourceVersion":"powerBI_V3","tables":[table],
        "annotations":[{"name":"Source","value":"Derived from UCI Online Retail II, Daqing Chen (2012), CC BY 4.0"}]}})
    write(Path("RetailForecast.SemanticModel/definition.pbism"),{"$schema":schema("item/semanticModel/definitionProperties/1.0.0"),"version":"4.0","settings":{}})
    write(Path("RetailForecast.pbip"),{"$schema":schema("pbip/pbipProperties/1.0.0"),"version":"1.0",
        "artifacts":[{"report":{"path":"RetailForecast.Report"}}],"settings":{"enableAutoRecovery":True}})
    write(Path("RetailForecast.Report/definition.pbir"),{"$schema":schema("item/report/definitionProperties/2.0.0"),"version":"4.0",
        "datasetReference":{"byPath":{"path":"../RetailForecast.SemanticModel"}}})
    definition=Path("RetailForecast.Report/definition")
    write(definition/"version.json",{"$schema":schema("item/report/definition/versionMetadata/1.0.0"),"version":"1.0.0"})
    write(definition/"report.json",{"$schema":schema("item/report/definition/report/1.0.0"),"layoutOptimization":"None",
        "themeCollection":{"baseTheme":{"name":"CY24SU06","reportVersionAtImport":"5.55","type":"SharedResources"}},
        "annotations":[{"name":"Validation","value":"Schema validated; final rendering requires Power BI Desktop on Windows."}]})
    write(definition/"pages/pages.json",{"$schema":schema("item/report/definition/pagesMetadata/1.0.0"),"pageOrder":["overview"],"activePageName":"overview"})
    write(definition/"pages/overview/page.json",{"$schema":schema("item/report/definition/page/1.0.0"),
        "name":"overview","displayName":"Sales and forecast error","displayOption":"FitToPage","height":900,"width":1440})
    visual("store_filter","slicer","Store / channel",24,16,320,100,{"Values":[projection("Store")]})
    visual("product_filter","slicer","Product",368,16,320,100,{"Values":[projection("Product")]})
    for index,(name,title) in enumerate([("Actual units","Observed sales"),("MAE","Mean absolute error"),("WAPE","Forecast WAPE"),("Baseline WAPE","Seasonal baseline WAPE")]):
        visual("metric_"+str(index),"card",title,24+index*354,136,330,112,{"Values":[projection(name,True)]})
    visual("forecast_trend","lineChart","Actual sales and one-week-ahead forecasts",24,272,910,320,
        {"Category":[projection("Week")],"Y":[projection(name,True) for name in ["Actual units","Forecast units","Seasonal baseline units","Moving average units"]]})
    visual("error_trend","lineChart","Absolute error over the holdout",958,272,458,320,
        {"Category":[projection("Week")],"Y":[projection("Forecast absolute error",True),projection("Seasonal absolute error",True)]})
    visual("product_detail","tableEx","Performance by product — positive sales, stock availability unknown",24,616,1392,260,
        {"Values":[projection("Store"),projection("Product"),projection("Actual units",True),projection("Forecast units",True),projection("MAE",True),projection("WAPE",True)]})
    print(f"Built Power BI project with {len(rows)} embedded evaluation rows and 9 visuals")

if __name__=="__main__":main()
