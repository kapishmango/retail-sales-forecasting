# Power BI report

Open `RetailForecast.pbip` in Power BI Desktop on Windows, then **Refresh** to load the embedded Power Query table. A project opened without `cache.abf` has its model definition but no cached data until refreshed.

The single page contains store and product slicers, sales/MAE/WAPE cards, a forecast trend, an error trend, and a product detail table. Measures use filtered row-level errors; they do not average product WAPEs. There is one store in the public dataset.

The model uses `model.bim` (TMSL) and the report uses PBIR JSON. `scripts/build_powerbi.py` rebuilds them from `reports/predictions.csv`. Close Power BI before regenerating sources to avoid overwriting unsaved Desktop changes.

Validation: JSON schemas and visual field references are checked programmatically. The Linux environment cannot run Power BI Desktop, so final opening, refresh, visual layout and DAX execution require a Windows check. No `.pbix` binary or fake Desktop screenshot is supplied.

References:

- [Microsoft PBIR project format](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report)
- [Microsoft semantic model project format](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset)

The source data is UCI Online Retail II, Daqing Chen (2012), CC BY 4.0; see the repository's data attribution.
