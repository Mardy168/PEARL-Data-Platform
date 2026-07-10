from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote_plus, urlparse
import feedparser
import pandas as pd

from src.utils.classifier import classify_topic, detect_country
from src.utils.dates import now_cambodia
from src.utils.duplicate import clean_text

ROOT=Path(__file__).resolve().parents[2]
KEYWORDS_FILE=ROOT/'config'/'keywords.json'
SOURCES_FILE=ROOT/'config'/'sources.json'


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _publisher_from_entry(entry, title: str, fallback: str='') -> tuple[str,str]:
    source=entry.get('source',{}) or {}
    name=clean_text(source.get('title','')) if isinstance(source,dict) else ''
    href=source.get('href','') if isinstance(source,dict) else ''
    domain=urlparse(href).netloc.lower().replace('www.','') if href else ''
    if not name and ' - ' in title: name=clean_text(title.rsplit(' - ',1)[-1])
    return name or fallback or 'Unknown Publisher', domain


def _published_value(entry) -> str:
    return str(entry.get('published') or entry.get('updated') or entry.get('created') or '')


def _base_row(entry,crop,query,source_type,source_name,source_url='') -> dict:
    now=now_cambodia(); raw_title=clean_text(entry.get('title','')); summary=clean_text(entry.get('summary',entry.get('description','')))
    link=str(entry.get('link','') or '')
    publisher,domain=_publisher_from_entry(entry,raw_title,source_name)
    if not domain and source_type=='Curated RSS': domain=urlparse(source_url).netloc.lower().replace('www.','')
    display=raw_title
    suffix=' - '+publisher
    if publisher and raw_title.lower().endswith(suffix.lower()): display=raw_title[:-len(suffix)].strip()
    all_text=f'{display} {summary} {publisher}'
    return {'date_collected':now.strftime('%Y-%m-%d'),'run_time_cambodia':now.strftime('%Y-%m-%d %H:%M:%S'),
            'published_date':_published_value(entry),'crop':crop,'country':detect_country(all_text),'topic':classify_topic(all_text),
            'title':display,'Summary':'','publisher_name':publisher,'publisher_domain':domain,'source_type':source_type,
            'source_name':source_name,'language':'en','url':link,'google_news_url':link if source_type=='Google News RSS' else '',
            'search_query':query,'summary_raw':summary,'status':'ARTICLE'}


def collect_google_news(query,crop,max_items=100):
    url='https://news.google.com/rss/search?q='+quote_plus(query)+'&hl=en-US&gl=US&ceid=US:en'
    feed=feedparser.parse(url)
    rows=[_base_row(e,crop,query,'Google News RSS','Google News',url) for e in feed.entries[:max_items]]
    return rows, {'source_name':f'Google News: {crop}','source_type':'Google News RSS','source_url':url,'success':not bool(feed.bozo),'articles_received':len(feed.entries),'articles_relevant':len(rows),'error':str(getattr(feed,'bozo_exception','')) if feed.bozo else ''}


def _detect_crop(text,crops):
    aliases={'Mango':['mango'],'Cashew':['cashew'],'Rice':['rice','paddy'],'Vegetables':['vegetable','vegetables','fresh produce']}
    low=text.lower()
    for crop in crops:
        if any(x in low for x in aliases.get(crop,[crop.lower()])): return crop
    return ''


def collect_curated_rss(source,crops,max_items=100):
    feed=feedparser.parse(source['url']); rows=[]
    for e in feed.entries[:max_items]:
        text=clean_text(f"{e.get('title','')} {e.get('summary','')}")
        crop=_detect_crop(text,crops)
        if crop: rows.append(_base_row(e,crop,source.get('name',''),'Curated RSS',source.get('name',''),source['url']))
    diag={'source_name':source.get('name',''),'source_type':'Curated RSS','source_url':source['url'],'success':not bool(feed.bozo),'articles_received':len(feed.entries),'articles_relevant':len(rows),'error':str(getattr(feed,'bozo_exception','')) if feed.bozo else ''}
    return rows,diag


def collect_all_news_with_diagnostics() -> tuple[pd.DataFrame,pd.DataFrame]:
    config=_load_json(KEYWORDS_FILE); sources=_load_json(SOURCES_FILE); crops=config.get('crops',{})
    rows=[]; diagnostics=[]
    for crop,queries in crops.items():
        for query in queries:
            print('Collecting Google News:',query)
            r,d=collect_google_news(query,crop); rows.extend(r); diagnostics.append(d)
    for source in sources.get('rss_sources',[]):
        print('Collecting curated RSS:',source.get('name'))
        r,d=collect_curated_rss(source,crops); rows.extend(r); diagnostics.append(d)
    return pd.DataFrame(rows),pd.DataFrame(diagnostics)


def collect_all_news() -> pd.DataFrame:
    return collect_all_news_with_diagnostics()[0]
