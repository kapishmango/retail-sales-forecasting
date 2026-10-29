"""Validate PBIP and PBIR JSON against Microsoft's public schemas.

Requires internet on first use; caches schema documents in data/cache/schemas.
Does not substitute for executing M/DAX and rendering in Power BI Desktop.
"""
from pathlib import Path
import hashlib
import json
import urllib.request
import jsonschema
from referencing import Registry,Resource

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/"data/cache/schemas"

def retrieve(uri):
    if not uri.startswith("https://developer.microsoft.com/json-schemas/"):
        raise ValueError("Only official Microsoft schema documents are allowed")
    CACHE.mkdir(parents=True,exist_ok=True)
    target=CACHE/(hashlib.sha256(uri.encode()).hexdigest()+".json")
    if target.exists():document=json.loads(target.read_text())
    else:
        with urllib.request.urlopen(uri,timeout=45) as response:document=json.load(response)
        target.write_text(json.dumps(document))
    return Resource.from_contents(document)

def main():
    registry=Registry(retrieve=retrieve);count=0
    for path in sorted((ROOT/"powerbi").rglob("*")):
        if not path.is_file() or path.suffix not in {".json",".pbip",".pbir",".pbism"}:continue
        value=json.loads(path.read_text())
        if "$schema" not in value:continue
        uri=value["$schema"];schema=retrieve(uri).contents
        active=registry.with_resource(uri,Resource.from_contents(schema))
        validator=jsonschema.validators.validator_for(schema)(schema,registry=active)
        errors=list(validator.iter_errors(value))
        if errors:raise ValueError(f"{path}: {errors[0].message}")
        count+=1
    print(f"Validated {count} project/report files against official schemas")

if __name__=="__main__":main()
