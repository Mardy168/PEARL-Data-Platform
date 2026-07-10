from __future__ import annotations
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

PREFERRED_COLUMNS=['Date Collected','Run Time Cambodia','Published Date','Crop','Country','Topic','Title','Summary','Publisher','Publisher Domain','Source Type','Source Name','Language','URL','Canonical URL','Google News URL','Search Query','Article ID','Status']
COLUMN_MAP={'date_collected':'Date Collected','run_time_cambodia':'Run Time Cambodia','crop':'Crop','country':'Country','topic':'Topic','title':'Title','Summary':'Summary','publisher_name':'Publisher','publisher_domain':'Publisher Domain','source_type':'Source Type','source_name':'Source Name','language':'Language','url':'URL','canonical_url':'Canonical URL','google_news_url':'Google News URL','search_query':'Search Query','article_id':'Article ID','status':'Status'}

def prepare_excel_dataframe(df):
    out=df.copy().rename(columns=COLUMN_MAP)
    for c in PREFERRED_COLUMNS:
        if c not in out.columns: out[c]=''
    return out[PREFERRED_COLUMNS]

def write_excel(df,path,sheet_name='News'):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    export=prepare_excel_dataframe(df); export.to_excel(path,index=False,sheet_name=sheet_name)
    wb=load_workbook(path); ws=wb[sheet_name]; fill=PatternFill('solid',fgColor='1F4E78')
    for cell in ws[1]: cell.font=Font(color='FFFFFF',bold=True); cell.fill=fill; cell.alignment=Alignment(horizontal='center',vertical='center')
    ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
    widths=[15,22,22,14,14,20,55,65,28,28,18,24,12,55,55,55,45,28,18]
    for idx,width in enumerate(widths,1): ws.column_dimensions[chr(64+idx) if idx<=26 else 'A'].width=width
    for row in ws.iter_rows(min_row=2):
        for cell in row: cell.alignment=Alignment(vertical='top',wrap_text=True)
    wb.save(path); return path

def write_qa_workbook(metrics:dict,source_health:pd.DataFrame,path:str):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with pd.ExcelWriter(path,engine='openpyxl') as writer:
        pd.DataFrame([{'Metric':k,'Value':v} for k,v in metrics.items()]).to_excel(writer,index=False,sheet_name='Run Summary')
        source_health.to_excel(writer,index=False,sheet_name='Source Health')
    wb=load_workbook(path)
    for ws in wb.worksheets:
        ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
        for c in ws[1]: c.font=Font(color='FFFFFF',bold=True); c.fill=PatternFill('solid',fgColor='1F4E78')
        for col in ws.columns:
            letter=col[0].column_letter; ws.column_dimensions[letter].width=min(max(len(str(x.value or '')) for x in col)+2,70)
    wb.save(path); return path
