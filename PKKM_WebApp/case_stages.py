"""Explicit case-stage classification; preserve unknown legacy status verbatim."""
import json
import re
from pathlib import Path
SCHEMA=json.loads((Path(__file__).parent/'case_stages.json').read_text())
STAGES=SCHEMA['stages']
REVIEW=SCHEMA['review']
def normalized(value):return ' '.join(re.sub(r'[^\w\s]',' ',value.casefold()).split())
ALIASES={normalized(value):value for value in STAGES}
ALIASES.update({normalized(key):value for key,value in SCHEMA['aliases'].items()})
def handling_stage(status):return ALIASES.get(normalized(status or ''))
def stage_counts(records):
    counts={label:0 for label in STAGES};review=0
    for item in records:
        label=handling_stage(item.status)
        if label:counts[label]+=1
        else:review+=1
    return {'stages':counts,'stageReview':review}
