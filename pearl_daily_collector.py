from __future__ import annotations
from pathlib import Path
import pandas as pd
from src.collectors.collector import collect_all_news_with_diagnostics
from src.drive.drive import download_file_by_name, upload_file
from src.reports.daily import create_daily_word_report
from src.utils.dates import add_published_columns, now_cambodia, remove_timezone_columns, rolling_window
from src.utils.duplicate import deduplicate_articles, exclude_existing
from src.utils.excel import write_excel, write_qa_workbook
from src.utils.summarizer import make_summary

DAILY=Path('data/daily'); MASTER_DIR=Path('data/master'); LOGS=Path('data/logs'); QA=Path('data/qa')
MASTER_FILENAME='PEARL_master_news.csv'; MASTER=MASTER_DIR/MASTER_FILENAME

def load_master():
    try: return pd.read_csv(MASTER) if MASTER.exists() else pd.DataFrame()
    except Exception as exc: print('Could not read master:',exc); return pd.DataFrame()

def status_frame(now,message):
    return pd.DataFrame([{'date_collected':now.strftime('%Y-%m-%d'),'run_time_cambodia':now.strftime('%Y-%m-%d %H:%M:%S'),'Published Date':'','crop':'','country':'','topic':'INFO','title':message,'Summary':message,'publisher_name':'PEARL System','publisher_domain':'','source_type':'System','source_name':'PEARL System','language':'en','url':'','canonical_url':'','google_news_url':'','search_query':'','article_id':'','status':'NO_NEW_NEWS'}])

def main():
    for p in (DAILY,MASTER_DIR,LOGS,QA): p.mkdir(parents=True,exist_ok=True)
    now=now_cambodia(); start,end=rolling_window(now,hours=24); label=now.strftime('%Y-%m-%d')
    csv=DAILY/f'PEARL_daily_news_{label}.csv'; xlsx=DAILY/f'PEARL_daily_news_{label}.xlsx'; docx=DAILY/f'PEARL_daily_summary_{label}.docx'; log=LOGS/f'PEARL_daily_log_{label}.txt'; qa=QA/f'PEARL_daily_QA_{label}.xlsx'
    download_file_by_name(MASTER_FILENAME,str(MASTER)); master=load_master(); raw,source_health=collect_all_news_with_diagnostics()
    stats={'Run Time Cambodia':now.strftime('%Y-%m-%d %H:%M:%S'),'Window Start':start.strftime('%Y-%m-%d %H:%M:%S'),'Window End':end.strftime('%Y-%m-%d %H:%M:%S'),'Sources Configured':len(source_health),'Sources Successful':int(source_health.get('success',pd.Series(dtype=bool)).fillna(False).sum()),'Raw Articles':len(raw),'Invalid Dates':0,'Outside Window':0,'Inside Window':0,'Unique Inside Window':0,'Already In Master':0,'New Articles':0,'Master Total':len(master)}
    if raw.empty:
        export=status_frame(now,'No news collected from configured sources.')
    else:
        raw=add_published_columns(raw); stats['Invalid Dates']=int(raw['published_dt_kh'].isna().sum())
        window=raw[raw['published_dt_kh'].notna()&(raw['published_dt_kh']>=start)&(raw['published_dt_kh']<=end)].copy(); stats['Inside Window']=len(window); stats['Outside Window']=len(raw)-stats['Invalid Dates']-len(window)
        unique=deduplicate_articles(window); stats['Unique Inside Window']=len(unique)
        if not unique.empty: unique['Summary']=unique.apply(make_summary,axis=1)
        new=exclude_existing(unique,master); stats['Already In Master']=len(unique)-len(new); stats['New Articles']=len(new)
        export=new if not new.empty else status_frame(now,'No new unique news found in the last 24 hours.')
        combined=deduplicate_articles(pd.concat([master,new],ignore_index=True)); combined.to_csv(MASTER,index=False,encoding='utf-8-sig'); stats['Master Total']=len(combined)
    clean=remove_timezone_columns(export); clean.to_csv(csv,index=False,encoding='utf-8-sig'); write_excel(clean,str(xlsx)); create_daily_word_report(clean,str(docx),label); write_qa_workbook(stats,source_health,str(qa))
    with open(log,'w',encoding='utf-8') as f:
        f.write('PEARL Daily News QA Log\n'); [f.write(f'{k}: {v}\n') for k,v in stats.items()]
    for p in (csv,xlsx,docx,log,qa): upload_file(str(p))
    if MASTER.exists(): upload_file(str(MASTER),MASTER_FILENAME)
    print('Daily collection completed successfully.')

if __name__=='__main__': main()
