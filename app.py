import io, os, re, math, tempfile
from datetime import date
from typing import Dict, List, Tuple
import pandas as pd
import streamlit as st

try:
    import pdfplumber
except Exception:
    pdfplumber = None
try:
    from PIL import Image as PILImage
    import pytesseract
except Exception:
    PILImage = None; pytesseract = None
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
except Exception:
    SimpleDocTemplate = None

st.set_page_config(page_title='Marvento Rate Desk', page_icon='🚢', layout='wide')
APP_DIR=os.path.dirname(os.path.abspath(__file__))
DATA_DIR=os.path.join(APP_DIR,'data'); os.makedirs(DATA_DIR, exist_ok=True)
TARIFF_STORE=os.path.join(DATA_DIR,'saved_tariffs.csv')
LOGO_STORE=os.path.join(DATA_DIR,'marvento_logo.png')

AIR_DIVISOR=6000; COURIER_DIVISOR=5000; LAND_DIVISOR=3333; SEA_KG_PER_CBM=1000
INCOTERMS=['EXW','FCA','FOB','CIF','CPT','DAP','DDU','DDP']
CURRENCIES=['AED','USD','EUR','GBP','SAR','INR']
EQUIPMENT=['20DV','40STD','40HC','40RF','40 FR']
TARIFF_COLUMNS=['vendor','mode','origin','destination','equipment','service','currency','min_charge','rate_per_kg','rate_per_cbm','rate_per_container','doc_fee','fuel_pct','other_charges','transit_days','valid_from','valid_to','remarks','source_text']
NUM_COLS=['min_charge','rate_per_kg','rate_per_cbm','rate_per_container','doc_fee','fuel_pct','other_charges','transit_days']

SAMPLE_TARIFFS=pd.DataFrame([
 ['SkyLine Air','Air','DXB','RUH','', 'EXW','AED',180,4.2,0,0,35,12,50,2,'2026-01-01','2026-12-31','Air general cargo',''],
 ['Gulf Courier','Courier','Dubai','Riyadh','', 'DDP','AED',95,5.1,0,0,25,18,35,3,'2026-01-01','2026-12-31','Express courier',''],
 ['Desert Road','Land','Dubai','Dammam','', 'DAP','AED',250,0.8,90,0,40,0,80,4,'2026-01-01','2026-12-31','LTL road',''],
 ['Ocean Box','Sea','Jebel Ali','Mombasa','20DV','FOB','AED',0,0,0,4200,150,0,250,18,'2026-01-01','2026-12-31','20DV base',''],
 ['Ocean Box','Sea','Jebel Ali','Mombasa','40HC','CIF','AED',0,0,0,6200,150,0,250,18,'2026-01-01','2026-12-31','40HC base',''],
],columns=TARIFF_COLUMNS)

def get_secret(name, default):
    try: return str(st.secrets.get(name, default))
    except Exception: return default
APP_USERNAME=get_secret('APP_USERNAME','kiran.dxb@marventoshipping.com')
APP_PASSWORD=get_secret('APP_PASSWORD','ChangeMe123')
if 'logged_in' not in st.session_state: st.session_state.logged_in=False
if not st.session_state.logged_in:
    st.title('Marvento Rate Desk Login')
    st.info('Default username: kiran.dxb@marventoshipping.com | Default password: ChangeMe123')
    with st.form('login'):
        u=st.text_input('Username'); p=st.text_input('Password', type='password')
        if st.form_submit_button('Login'):
            if u.strip()==APP_USERNAME and p==APP_PASSWORD:
                st.session_state.logged_in=True; st.rerun()
            else: st.error('Wrong username or password')
    st.stop()


def normalize(x):
    return str(x or '').strip().lower()

def normkey(x):
    """Strong normalisation used for lane/equipment matching."""
    s=normalize(x)
    repl={
        'jebel ali':'jebelali','jebelali':'jebelali','jebel ali port':'jebelali',
        'dubai':'dubai','dxb':'dxb','mombasa':'mombasa','riyadh':'riyadh','ruh':'ruh',
        '40 std':'40std','40st':'40std','40 gp':'40std','40gp':'40std','40dc':'40std',
        '20 dc':'20dv','20gp':'20dv','20 gp':'20dv','20 ft':'20dv','20ft':'20dv',
        '40 hq':'40hc','40hq':'40hc','40 high cube':'40hc','40hc':'40hc',
        '40 rf':'40rf','40reefer':'40rf','40 reefer':'40rf',
        '40 fr':'40fr','40 flat rack':'40fr','40fr':'40fr'
    }
    for k,v in repl.items():
        s=s.replace(k,v)
    return re.sub(r'[^a-z0-9]+','',s)

def tokens(x): return re.findall(r'[a-z0-9]+', normalize(x))

def contains_match(value, query):
    v=normalize(value); q=normalize(query)
    if not q: return True
    if not v: return False
    vk=normkey(v); qk=normkey(q)
    if qk and (qk in vk or vk in qk): return True
    if q in v or v in q: return True
    qt=set(tokens(q)); vt=set(tokens(v))
    return bool(qt and vt and (qt & vt))

def cbm_from_cm(l,w,h,p): return (float(l)*float(w)*float(h)*int(p))/1000000 if l and w and h and p else 0.0

def chargeable_weight(mode,gross,cbm):
    m=normalize(mode)
    if m=='sea': return round(float(gross or 0),2)
    div=AIR_DIVISOR if m=='air' else COURIER_DIVISOR if m=='courier' else LAND_DIVISOR
    volumetric=float(cbm or 0)*1000000/div
    return round(max(float(gross or 0),volumetric),2)

def extract_text_from_upload(file):
    name=file.name.lower(); data=file.getvalue()
    if name.endswith('.pdf'):
        if pdfplumber is None: return 'PDF extraction unavailable. Install pdfplumber.'
        parts=[]
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages: parts.append(page.extract_text() or '')
        return '\n'.join(parts)
    if name.endswith(('.png','.jpg','.jpeg','.webp')):
        if PILImage is None or pytesseract is None: return 'Image OCR unavailable. Paste text manually.'
        try: return pytesseract.image_to_string(PILImage.open(io.BytesIO(data)))
        except Exception as e: return f'Image OCR failed: {e}'
    if name.endswith(('.xlsx','.xls')):
        try:
            sheets=pd.read_excel(io.BytesIO(data), sheet_name=None)
            return '\n'.join([f'Sheet: {k}\n'+v.astype(str).to_csv(index=False) for k,v in sheets.items()])
        except Exception as e: return f'Excel extraction failed: {e}'
    return data.decode('utf-8', errors='ignore')

def _standardize_columns(df):
    df=df.copy()
    df.columns=[str(c).strip().lower().replace('\n','_').replace(' ','_').replace('/','_').replace('-','_') for c in df.columns]
    aliases={
        'carrier':'vendor','agent':'vendor','shipping_line':'vendor','line':'vendor','airline':'vendor','vendor_name':'vendor',
        'aol':'origin','airport_of_loading':'origin','pol':'origin','port_of_loading':'origin','from':'origin','origin_port':'origin','origin_airport':'origin','load_port':'origin','pickup':'origin',
        'aod':'destination','airport_of_discharge':'destination','pod':'destination','port_of_discharge':'destination','to':'destination','destination_port':'destination','destination_airport':'destination','discharge_port':'destination','delivery':'destination',
        'eqp':'equipment','equip':'equipment','equipment_type':'equipment','container':'equipment','container_type':'equipment','cntr':'equipment','container_size':'equipment',
        'incoterm':'service','terms':'service','service_required':'service','tt':'transit_days','transit_time':'transit_days','validity_from':'valid_from','validity_to':'valid_to','valid_until':'valid_to','validity':'valid_to',
        'rate_kg':'rate_per_kg','per_kg':'rate_per_kg','kg_rate':'rate_per_kg','airfreight':'rate_per_kg','air_freight':'rate_per_kg','rate_cbm':'rate_per_cbm','per_cbm':'rate_per_cbm','cbm_rate':'rate_per_cbm',
        'container_rate':'rate_per_container','rate_container':'rate_per_container','of':'rate_per_container','ocean_freight':'rate_per_container','freight':'rate_per_container',
        'minimum':'min_charge','minimum_charge':'min_charge','min':'min_charge','m_min':'min_charge','fuel':'fuel_pct','fuel_surcharge':'fuel_pct','fsc':'fuel_pct','doc':'doc_fee','documentation':'doc_fee','doc_fee':'doc_fee','charges':'other_charges','other':'other_charges','local_charges':'other_charges','remarks_notes':'remarks'
    }
    df=df.rename(columns={k:v for k,v in aliases.items() if k in df.columns})
    return df

def _num(x):
    try:
        if pd.isna(x): return 0.0
        s=str(x).replace(',','')
        m=re.search(r'-?\d+(?:\.\d+)?', s)
        return float(m.group(0)) if m else 0.0
    except Exception:
        return 0.0

def _detect_currency_from_row(row):
    blob=' '.join(str(v) for v in row.values)
    if re.search(r'\bUSD\b|US\$', blob, re.I): return 'USD'
    if re.search(r'\bEUR\b', blob, re.I): return 'EUR'
    if re.search(r'\bGBP\b', blob, re.I): return 'GBP'
    if re.search(r'\bSAR\b', blob, re.I): return 'SAR'
    if re.search(r'\bINR\b', blob, re.I): return 'INR'
    return 'AED'

def clean_tariff(df):
    """Map almost any CSV/Excel/PDF table into the internal tariff format.
    Also handles wide sea tariffs with columns like 20DV, 40HC, 40RF etc.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=TARIFF_COLUMNS)
    raw=_standardize_columns(df)
    rows=[]
    equipment_aliases={
        '20dv':['20dv','20_dc','20dc','20gp','20_ft','20ft','20'],
        '40std':['40std','40_st','40std','40_gp','40gp','40_dc','40dc','40_ft','40ft','40'],
        '40hc':['40hc','40_hc','40hq','40_hq','40_high_cube'],
        '40rf':['40rf','40_rf','40_reefer','reefer_40'],
        '40 FR':['40fr','40_fr','40_flat_rack','flat_rack_40']
    }
    eq_cols=[]
    for eq, names in equipment_aliases.items():
        for c in raw.columns:
            if normkey(c) in {normkey(n) for n in names}:
                eq_cols.append((eq,c))
    # If sea tariff is wide, create one row per equipment column.
    if eq_cols:
        base=raw.copy()
        for _,r in base.iterrows():
            for eq,c in eq_cols:
                rate=_num(r.get(c,0))
                if rate>0:
                    d={col:'' for col in TARIFF_COLUMNS}
                    for col in ['vendor','mode','origin','destination','service','currency','min_charge','doc_fee','fuel_pct','other_charges','transit_days','valid_from','valid_to','remarks','source_text']:
                        if col in raw.columns: d[col]=r.get(col,'')
                    d['equipment']=eq; d['rate_per_container']=rate
                    d['currency']=d.get('currency') or _detect_currency_from_row(r)
                    d['mode']=d.get('mode') or 'Sea'
                    rows.append(d)
    # Standard rows.
    for _,r in raw.iterrows():
        d={col:(0 if col in NUM_COLS else '') for col in TARIFF_COLUMNS}
        for col in raw.columns:
            if col in TARIFF_COLUMNS: d[col]=r.get(col,'')
        # Detect equipment if embedded in remarks/rate basis.
        blob=' '.join(str(v) for v in r.values)
        if not d.get('equipment'):
            for eq in EQUIPMENT:
                if contains_match(blob, eq): d['equipment']=eq; break
        if not d.get('mode'):
            d['mode']='Sea' if d.get('equipment') or re.search(r'\b(POL|POD|vessel|ocean|sea)\b', blob, re.I) else 'Air' if re.search(r'\b(AOL|AOD|airport|air|kg|kgs)\b', blob, re.I) else ''
        if not d.get('currency'): d['currency']=_detect_currency_from_row(r)
        # When a generic rate column was mapped as container but mode is air and no kg rate, switch.
        for c in NUM_COLS: d[c]=_num(d.get(c,0))
        if normalize(d.get('mode')) in ('air','courier') and d.get('rate_per_container',0)>0 and d.get('rate_per_kg',0)==0:
            d['rate_per_kg']=d['rate_per_container']; d['rate_per_container']=0
        rows.append(d)
    out=pd.DataFrame(rows)
    for c in TARIFF_COLUMNS:
        if c not in out.columns: out[c]=0 if c in NUM_COLS else ''
    for c in NUM_COLS: out[c]=pd.to_numeric(out[c], errors='coerce').fillna(0)
    for c in [x for x in TARIFF_COLUMNS if x not in NUM_COLS]: out[c]=out[c].fillna('').astype(str)
    out['currency']=out['currency'].replace('', 'AED')
    # Remove rows with no useful rate only if they have no source_text; keep source_text rows for AI fallback/debug.
    return out[TARIFF_COLUMNS]

def infer_tariff_from_text(text, source_name):
    """Best-effort AI-style extraction from tariff text/PDF/email.
    It extracts lanes, equipment rates, kg rates, minimum/doc/fuel, and stores source_text for fallback matching.
    """
    lines=[x.strip() for x in str(text or '').splitlines() if x.strip()]
    full='\n'.join(lines)
    rows=[]
    mode='Sea' if re.search(r'\b(POL|POD|20DV|20DC|20GP|40HC|40HQ|40STD|40GP|40RF|40FR|ocean|vessel|sea)\b', full, re.I) else 'Air' if re.search(r'\b(AOL|AOD|air|airport|airline|kgs?|/kg|per kg)\b', full, re.I) else ''
    curr='USD' if re.search(r'\bUSD\b|US\$|\$',full,re.I) else 'EUR' if re.search(r'\bEUR\b',full,re.I) else 'AED' if re.search(r'\bAED\b',full,re.I) else 'AED'
    vendors=re.findall(r'(?:carrier|airline|line|vendor|shipping line)\s*[:\-]\s*([A-Za-z0-9 .&-]+)', full, re.I)
    vendor=(vendors[0].strip()[:40] if vendors else os.path.splitext(source_name)[0][:40])
    lanes=[]
    patterns=[
        r'(?:POL|AOL|Origin|From)\s*[:\-]?\s*([A-Za-z0-9 .,-]{2,40}?)\s+(?:POD|AOD|Destination|Dest|To)\s*[:\-]?\s*([A-Za-z0-9 .,-]{2,40})',
        r'([A-Za-z][A-Za-z .]{2,30})\s+(?:to|TO|\-|–|>)\s+([A-Za-z][A-Za-z .]{2,30})',
        r'([A-Z]{3})\s*[-/]\s*([A-Z]{3})'
    ]
    for pat in patterns:
        for a,b in re.findall(pat, full, re.I):
            a=a.strip(' ,:;|'); b=b.strip(' ,:;|')
            if a and b and len(a)<45 and len(b)<45: lanes.append((a,b))
    if not lanes: lanes=[('','')]
    eq_patterns={'20DV':r'20\s*(?:DV|DC|GP|FT)?','40STD':r'40\s*(?:STD|ST|DC|GP|FT)?','40HC':r'40\s*(?:HC|HQ|HIGH\s*CUBE)','40RF':r'40\s*(?:RF|REEFER)','40 FR':r'40\s*(?:FR|FLAT\s*RACK)'}
    eq_rates=[]
    for eq,pat in eq_patterns.items():
        for m in re.finditer(pat+r'[^0-9]{0,40}(\d{2,7}(?:\.\d+)?)', full, re.I):
            val=float(m.group(1));
            if 50 <= val <= 999999: eq_rates.append((eq,val))
    kg_rates=[]
    for m in re.finditer(r'(?:rate|freight|airfreight|air freight|per kg|/kg|kg rate)[^0-9]{0,30}(\d+(?:\.\d+)?)', full, re.I):
        val=float(m.group(1))
        if 0 < val < 1000: kg_rates.append(val)
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(?:/\s*kg|per\s*kg)', full, re.I):
        val=float(m.group(1))
        if 0 < val < 1000: kg_rates.append(val)
    cbm_rates=[]
    for m in re.finditer(r'(?:cbm|w/m|rt|revenue ton)[^0-9]{0,30}(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:/\s*cbm|per\s*cbm|w/m)', full, re.I):
        val=float(m.group(1) or m.group(2))
        if 0 < val < 10000: cbm_rates.append(val)
    min_charge=0; mm=re.search(r'(?:min|minimum)[^0-9]{0,20}(\d+(?:\.\d+)?)', full, re.I)
    if mm: min_charge=float(mm.group(1))
    doc=0; dm=re.search(r'(?:doc|documentation)[^0-9]{0,20}(\d+(?:\.\d+)?)', full, re.I)
    if dm: doc=float(dm.group(1))
    fuel=0; fm=re.search(r'(?:fuel|fsc)[^0-9]{0,20}(\d+(?:\.\d+)?)\s*%', full, re.I)
    if fm: fuel=float(fm.group(1))
    service=''
    for inc in INCOTERMS:
        if re.search(r'\b'+inc+r'\b', full, re.I): service=inc; break
    for origin,dest in lanes[:30]:
        if eq_rates:
            for eq,rate in eq_rates:
                rows.append({'vendor':vendor,'mode':'Sea','origin':origin,'destination':dest,'equipment':eq,'service':service,'currency':curr,'min_charge':0,'rate_per_kg':0,'rate_per_cbm':0,'rate_per_container':rate,'doc_fee':doc,'fuel_pct':fuel,'other_charges':0,'transit_days':0,'valid_from':'','valid_to':'','remarks':'AI extracted from tariff text','source_text':full[:8000]})
        if kg_rates:
            for rate in sorted(set(kg_rates))[:10]:
                rows.append({'vendor':vendor,'mode':mode or 'Air','origin':origin,'destination':dest,'equipment':'','service':service,'currency':curr,'min_charge':min_charge,'rate_per_kg':rate,'rate_per_cbm':0,'rate_per_container':0,'doc_fee':doc,'fuel_pct':fuel,'other_charges':0,'transit_days':0,'valid_from':'','valid_to':'','remarks':'AI extracted from tariff text','source_text':full[:8000]})
        if cbm_rates and not eq_rates:
            for rate in sorted(set(cbm_rates))[:10]:
                rows.append({'vendor':vendor,'mode':mode or 'Land','origin':origin,'destination':dest,'equipment':'','service':service,'currency':curr,'min_charge':min_charge,'rate_per_kg':0,'rate_per_cbm':rate,'rate_per_container':0,'doc_fee':doc,'fuel_pct':fuel,'other_charges':0,'transit_days':0,'valid_from':'','valid_to':'','remarks':'AI extracted CBM/W-M rate from tariff text','source_text':full[:8000]})
    if not rows and full.strip():
        rows.append({'vendor':vendor,'mode':mode,'origin':'','destination':'','equipment':'','service':service,'currency':curr,'min_charge':0,'rate_per_kg':0,'rate_per_cbm':0,'rate_per_container':0,'doc_fee':0,'fuel_pct':0,'other_charges':0,'transit_days':0,'valid_from':'','valid_to':'','remarks':'Text stored for tariff debug; no rate confidently extracted','source_text':full[:8000]})
    return pd.DataFrame(rows)

def read_tariff_file(file):
    name=file.name.lower(); data=file.getvalue()
    try:
        if name.endswith('.csv'):
            raw=pd.read_csv(io.BytesIO(data))
            text=raw.astype(str).to_csv(index=False)
            inferred=infer_tariff_from_text(text, file.name)
            return pd.concat([raw, inferred], ignore_index=True, sort=False), 'CSV read and AI scan completed.'
        if name.endswith(('.xlsx','.xls')):
            sheets=pd.read_excel(io.BytesIO(data), sheet_name=None)
            frames=[]; text_parts=[]
            for sheet,df in sheets.items():
                df=df.copy(); df['remarks']=df.get('remarks','').astype(str) + f' Sheet: {sheet}' if 'remarks' in df.columns else f'Sheet: {sheet}'
                frames.append(df); text_parts.append(f'Sheet {sheet}\n'+df.astype(str).to_csv(index=False))
            raw=pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
            inferred=infer_tariff_from_text('\n'.join(text_parts), file.name)
            return pd.concat([raw, inferred], ignore_index=True, sort=False), 'Excel all sheets read and AI scan completed.'
        if name.endswith('.pdf'):
            if pdfplumber is None: return pd.DataFrame(), 'PDF tariff reading needs pdfplumber.'
            frames=[]; texts=[]
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables() or []:
                        if table and len(table)>1:
                            header=[str(x or '').strip() for x in table[0]]
                            frames.append(pd.DataFrame(table[1:], columns=header))
                    texts.append(page.extract_text() or '')
            text='\n'.join(texts)
            inferred=infer_tariff_from_text(text, file.name)
            all_frames=frames + ([inferred] if not inferred.empty else [])
            if all_frames:
                return pd.concat(all_frames, ignore_index=True, sort=False), 'PDF table/text AI scan completed.'
            if text.strip(): return pd.DataFrame([{'vendor':os.path.splitext(file.name)[0],'mode':'','origin':'','destination':'','currency':'AED','remarks':'PDF text extracted; no rate confidently extracted','source_text':text[:8000]}]), 'PDF text stored for review.'
            return pd.DataFrame(), 'No readable PDF text/table. It may be scanned/image PDF.'
    except Exception as e: return pd.DataFrame(), f'Could not read {file.name}: {e}'
    return pd.DataFrame(), f'Unsupported file: {file.name}'

def load_saved_tariffs():
    if os.path.exists(TARIFF_STORE):
        try: return clean_tariff(pd.read_csv(TARIFF_STORE))
        except Exception: return pd.DataFrame(columns=TARIFF_COLUMNS)
    return pd.DataFrame(columns=TARIFF_COLUMNS)
def save_tariffs(df): clean_tariff(df).to_csv(TARIFF_STORE,index=False)
def add_uploaded_tariffs(files):
    msgs=[]; frames=[load_saved_tariffs()]
    for f in files or []:
        raw,msg=read_tariff_file(f)
        if msg: msgs.append(f'{f.name}: {msg}')
        if raw is not None and not raw.empty:
            try:
                cl=clean_tariff(raw)
                cl['remarks']=cl['remarks'].astype(str)+f' | Source: {f.name}'
                frames.append(cl)
                rated=cl[(cl[['rate_per_kg','rate_per_cbm','rate_per_container']].sum(axis=1)>0)]
                msgs.append(f'{f.name}: mapped {len(cl)} row(s), {len(rated)} row(s) have usable rates.')
            except Exception as e: msgs.append(f'{f.name}: columns could not be mapped ({e})')
    if len(frames)>1:
        out=pd.concat(frames, ignore_index=True).drop_duplicates(keep='last')
        save_tariffs(out); msgs.append(f'Saved {len(out)} active tariff row(s).')
    return msgs
def active_tariffs():
    saved=load_saved_tariffs()
    return clean_tariff(SAMPLE_TARIFFS) if saved.empty else saved
def parse_dimensions_and_weight(text):
    rows=[]; t=text.replace('×','x').replace('*','x')
    pat=re.compile(r'(?:(\d+)\s*(?:pcs?|pieces?|ctns?|cartons?)\s*[xX@-]?\s*)?(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*(cm|mm|m|inch|in)?', re.I)
    for m in pat.finditer(t):
        p=int(m.group(1) or 1); l,w,h=float(m.group(2)),float(m.group(3)),float(m.group(4)); u=(m.group(5) or 'cm').lower()
        if u=='mm': l,w,h=l/10,w/10,h/10
        elif u=='m': l,w,h=l*100,w*100,h*100
        elif u in ('inch','in'): l,w,h=l*2.54,w*2.54,h*2.54
        rows.append({'pieces':p,'length_cm':round(l,2),'width_cm':round(w,2),'height_cm':round(h,2),'cbm':round(cbm_from_cm(l,w,h,p),4)})
    weights=[float(x) for x in re.findall(r'(\d+(?:\.\d+)?)\s*(?:kgs?|kg|kilograms?)\b', t, re.I)]
    cbms=re.findall(r'(\d+(?:\.\d+)?)\s*(?:cbm|m3|cubic meter|cubic metres)\b', t, re.I)
    return pd.DataFrame(rows), {'gross_kg':max(weights) if weights else 0.0,'cbm':float(cbms[-1]) if cbms else round(sum(r['cbm'] for r in rows),4),'pieces':sum(r['pieces'] for r in rows) if rows else 0}


def rate_total(row, chargeable_kg, cbm, containers):
    min_charge=float(row.get('min_charge',0) or 0)
    freight_candidates=[]
    if min_charge>0: freight_candidates.append(min_charge)
    if float(row.get('rate_per_kg',0) or 0)>0: freight_candidates.append(float(row.rate_per_kg)*float(chargeable_kg or 0))
    if float(row.get('rate_per_cbm',0) or 0)>0: freight_candidates.append(float(row.rate_per_cbm)*float(cbm or 0))
    if float(row.get('rate_per_container',0) or 0)>0: freight_candidates.append(float(row.rate_per_container)*max(int(containers or 0),1))
    if not freight_candidates: return 0.0
    freight=max(freight_candidates)
    fuel=freight*float(row.get('fuel_pct',0) or 0)/100
    return round(freight+fuel+float(row.get('doc_fee',0) or 0)+float(row.get('other_charges',0) or 0),2)

def row_score(r, mode, origin, dest, service, equipment):
    score=0; reasons=[]
    blob=' '.join(str(r.get(c,'')) for c in ['vendor','mode','origin','destination','equipment','service','remarks','source_text'])
    # Mode matching: blank mode is not rejected, but clear mode match gets priority.
    if contains_match(r.get('mode',''), mode) or (mode=='Sea' and contains_match(blob,'sea')) or (mode!='Sea' and contains_match(blob, mode)):
        score+=30; reasons.append('mode')
    elif not str(r.get('mode','')).strip():
        score+=8; reasons.append('mode blank')
    # Lane matching can come from mapped origin/destination OR raw source text.
    if contains_match(r.get('origin',''), origin): score+=35; reasons.append('origin')
    elif origin and contains_match(blob, origin): score+=18; reasons.append('origin in text')
    elif not str(r.get('origin','')).strip(): score+=5; reasons.append('origin blank')
    if contains_match(r.get('destination',''), dest): score+=35; reasons.append('destination')
    elif dest and contains_match(blob, dest): score+=18; reasons.append('destination in text')
    elif not str(r.get('destination','')).strip(): score+=5; reasons.append('destination blank')
    if service and contains_match(r.get('service',''), service): score+=5; reasons.append('service')
    if equipment:
        if contains_match(r.get('equipment',''), equipment): score+=25; reasons.append('equipment')
        elif contains_match(blob, equipment): score+=12; reasons.append('equipment in text')
    # Useful price present.
    if any(float(r.get(c,0) or 0)>0 for c in ['rate_per_kg','rate_per_cbm','rate_per_container','min_charge']):
        score+=10; reasons.append('rate present')
    return score, ', '.join(reasons)

def match_rates(tariffs, mode, origin, dest, chargeable_kg, cbm, containers, service='', equipment=''):
    df=clean_tariff(tariffs).copy()
    if df.empty: return df
    scores=df.apply(lambda r: row_score(r,mode,origin,dest,service,equipment),axis=1)
    df['_score']=[x[0] for x in scores]
    df['match_reason']=[x[1] for x in scores]
    df['buying_total_aed']=df.apply(lambda r: rate_total(r,chargeable_kg,cbm,containers),axis=1)
    # First exact/strong matches, then intelligent fallback by mode/equipment/rate.
    out=df[(df['_score']>=60) & (df['buying_total_aed']>0)].copy()
    if out.empty:
        out=df[(df['_score']>=40) & (df['buying_total_aed']>0)].copy()
    if out.empty:
        # Fallback: show any row with usable rate and same mode/equipment; this prevents silent zero when lane names differ.
        fallback=df[df['buying_total_aed']>0].copy()
        if mode:
            fb_mode=fallback[fallback.apply(lambda r: contains_match(r.get('mode',''), mode) or contains_match(' '.join(str(r.get(c,'')) for c in ['remarks','source_text']), mode), axis=1)]
            if not fb_mode.empty: fallback=fb_mode
        if equipment and mode=='Sea':
            fb_eq=fallback[fallback.apply(lambda r: contains_match(r.get('equipment',''), equipment) or contains_match(str(r.get('source_text','')), equipment), axis=1)]
            if not fb_eq.empty: fallback=fb_eq
        out=fallback.copy()
    if out.empty: return out.drop(columns=['_score'], errors='ignore')
    out=out.sort_values(['buying_total_aed','_score'], ascending=[True,False]).reset_index(drop=True)
    out.insert(0,'rank',range(1,len(out)+1))
    return out.drop(columns=['_score'], errors='ignore')
def default_manual_quote_lines():
    return pd.DataFrame([{'Description':'Freight Charges','Carrier':'','Unit':'Shipment','Unit Price':0.0,'VAT/Tax':0.0,'Currency':'AED','Total':0.0}])
def calculate_manual_totals(df):
    out=df.copy()
    for c in ['Description','Carrier','Unit','Currency']:
        if c not in out.columns: out[c]=''
    for c in ['Unit Price','VAT/Tax','Total']:
        if c not in out.columns: out[c]=0.0
        out[c]=pd.to_numeric(out[c], errors='coerce').fillna(0.0)
    out['Total']=(out['Unit Price']+out['VAT/Tax']).round(2)
    return out
def total_quote(df):
    q=calculate_manual_totals(df)
    return float(q['Total'].sum()) if not q.empty else 0.0
def build_auto_quote_lines(sel, selling):
    return pd.DataFrame([{'Description':f"Freight Charges - {sel.get('service','') or sel.get('equipment','')}",'Carrier':str(sel.get('vendor','')),'Unit':'Shipment','Unit Price':float(selling),'VAT/Tax':0.0,'Currency':str(sel.get('currency','AED') or 'AED'),'Total':float(selling)}])
def make_quote_text(enq, lines, total, validity):
    q=calculate_manual_totals(lines); items=[]
    for _,r in q.iterrows():
        if str(r.get('Description','')).strip():
            items.append(f"- {r.get('Description','')} | Carrier: {r.get('Carrier','') or 'TBA'} | Unit: {r.get('Unit','')} | Unit Price: {r.get('Currency','AED')} {float(r.get('Unit Price',0)):,.2f} | VAT/Tax: {r.get('Currency','AED')} {float(r.get('VAT/Tax',0)):,.2f} | Total: {r.get('Currency','AED')} {float(r.get('Total',0)):,.2f}")
    sea_extra=f"\nEquipment: {enq.get('equipment','')}\nContainer Qty: {enq.get('containers','')}" if enq.get('mode')=='Sea' else f"\nCBM: {float(enq.get('cbm') or 0):,.4f}\nChargeable Weight: {float(enq.get('chargeable_kg') or 0):,.2f} kg"
    return f"""Dear {enq.get('customer') or 'Customer'},

Thank you for your enquiry. Please find our quotation below:

Enquiry No: {enq.get('enquiry_no')}
Mode: {enq.get('mode')}
Service Required: {enq.get('service')}
Rate Validity: {validity or 'TBA'}
{enq.get('origin_label','Origin')}: {enq.get('origin')}
{enq.get('destination_label','Destination')}: {enq.get('destination')}
Gross Weight: {float(enq.get('gross_kg') or 0):,.2f} kg{sea_extra}

Quote Lines:
{chr(10).join(items) if items else '- TBA'}

Total Selling Quote: {q['Currency'].iloc[0] if not q.empty else 'AED'} {total:,.2f}

Remarks: Subject to space, carrier acceptance, customs approval, and final cargo details. Duties, taxes, storage, demurrage, inspection, destination charges, and insurance are excluded unless specifically mentioned.

Best regards,
Marvento Rate Desk"""

def make_pdf(enq, lines, total, validity):
    if SimpleDocTemplate is None: return b''
    buf=io.BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=12*mm,bottomMargin=14*mm)
    styles=getSampleStyleSheet(); title=ParagraphStyle('MarTitle', parent=styles['Title'], textColor=colors.HexColor('#123D6A'))
    story=[]
    if os.path.exists(LOGO_STORE):
        img=Image(LOGO_STORE, width=48*mm, height=20*mm)
        header=Table([[img, Paragraph('<b>FREIGHT QUOTATION</b>', title)]], colWidths=[60*mm,110*mm])
    else:
        logo=Paragraph('<b><font color="#123D6A">MARVENTO</font><font color="#F28C28"> SHIPPING</font></b>', styles['Title'])
        header=Table([[logo, Paragraph('<b>FREIGHT QUOTATION</b>', title)]], colWidths=[70*mm,100*mm])
    header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LINEBELOW',(0,0),(-1,-1),2,colors.HexColor('#F28C28'))]))
    story += [header, Spacer(1,6*mm)]
    det=[['Enquiry No',str(enq.get('enquiry_no','')),'Date',date.today().strftime('%d-%b-%Y')],['Customer',str(enq.get('customer','')),'Mode',str(enq.get('mode',''))],['Service',str(enq.get('service','')),'Validity',validity or 'TBA'],[str(enq.get('origin_label','Origin')),str(enq.get('origin','')),str(enq.get('destination_label','Destination')),str(enq.get('destination',''))],['Gross Weight',f"{float(enq.get('gross_kg') or 0):,.2f} kg",'Equipment' if enq.get('mode')=='Sea' else 'Chargeable Weight',str(enq.get('equipment','')) if enq.get('mode')=='Sea' else f"{float(enq.get('chargeable_kg') or 0):,.2f} kg"]]
    if enq.get('mode')=='Sea': det.append(['Containers',str(enq.get('containers',0)),'',''])
    t=Table(det,colWidths=[35*mm,55*mm,35*mm,45*mm]); t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.25,colors.grey),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#EAF4FB')),('BACKGROUND',(2,0),(2,-1),colors.HexColor('#EAF4FB')),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story += [t, Spacer(1,7*mm), Paragraph('<b>Quote Lines</b>', styles['Heading2'])]
    q=calculate_manual_totals(lines); data=[['Description','Carrier','Unit','Unit Price','VAT/Tax','Currency','Total']]
    for _,r in q.iterrows():
        if str(r.get('Description','')).strip(): data.append([str(r.get('Description','')),str(r.get('Carrier','')),str(r.get('Unit','')),f"{float(r.get('Unit Price',0)):,.2f}",f"{float(r.get('VAT/Tax',0)):,.2f}",str(r.get('Currency','AED')),f"{float(r.get('Total',0)):,.2f}"])
    data.append(['','','','','','Total',f'{total:,.2f}'])
    qt=Table(data,colWidths=[43*mm,25*mm,22*mm,24*mm,22*mm,20*mm,24*mm]); qt.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.25,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#123D6A')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('BACKGROUND',(-2,-1),(-1,-1),colors.HexColor('#FDE9D2')),('ALIGN',(3,1),(-1,-1),'RIGHT')]))
    story += [qt, Spacer(1,7*mm), Paragraph('Remarks: Subject to space, carrier acceptance, customs approval, and final cargo details. Duties, taxes, storage, demurrage, inspection, destination charges, and insurance are excluded unless specifically mentioned.', styles['Normal']), Spacer(1,5*mm), Paragraph('Best regards,<br/><b>Marvento Rate Desk</b>', styles['Normal'])]
    doc.build(story); return buf.getvalue()

with st.sidebar:
    st.markdown('### MARVENTO RATE DESK')
    st.success(f'Logged in as {APP_USERNAME}')
    if st.button('Logout'): st.session_state.logged_in=False; st.rerun()
    st.divider(); st.header('Tariff Data')
    logo_file=st.file_uploader('Upload Marvento logo for PDF', type=['png','jpg','jpeg'], key='logo_upload')
    if logo_file and st.button('Save logo'):
        img=PILImage.open(io.BytesIO(logo_file.getvalue())).convert('RGBA')
        img.save(LOGO_STORE); st.success('Logo saved.'); st.rerun()
    st.download_button('Download tariff CSV template', pd.DataFrame(columns=TARIFF_COLUMNS).to_csv(index=False), 'marvento_tariff_template.csv','text/csv')
    st.download_button('Download sample tariff CSV', SAMPLE_TARIFFS.to_csv(index=False), 'marvento_sample_tariffs.csv','text/csv')
    ups=st.file_uploader('Import tariff rates: CSV / Excel / PDF', type=['csv','xlsx','xls','pdf'], accept_multiple_files=True)
    if st.button('Save uploaded tariff files'):
        for m in add_uploaded_tariffs(ups): st.info(m)
        st.rerun()
    if st.button('Clear saved tariff database'):
        if os.path.exists(TARIFF_STORE): os.remove(TARIFF_STORE)
        st.warning('Saved tariffs cleared.'); st.rerun()

st.title('Marvento Rate Desk V5')
st.caption('Improved AI tariff extraction, visible match diagnostics, sea equipment quote, and PDF quotation')
tariffs=active_tariffs()
tab1,tab2,tab3=st.tabs(['Rate Desk','Tariff Table','Help'])
with tab1:
    st.subheader('1. Enquiry Details')
    c1,c2,c3,c4=st.columns(4)
    with c1:
        enquiry_no=st.text_input('Enquiry No', value=f"MRD-{date.today().strftime('%Y%m%d')}-001"); customer=st.text_input('Customer')
    with c2:
        mode=st.selectbox('Mode',['Air','Courier','Land','Sea']); service=st.selectbox('Service Required', INCOTERMS); rate_validity=st.text_input('Rate Validity', 'Valid for 7 days')
    if mode=='Air': origin_label,dest_label='AOL','AOD'; origin_default,dest_default='DXB','RUH'
    elif mode=='Sea': origin_label,dest_label='POL','POD'; origin_default,dest_default='Jebel Ali','Mombasa'
    else: origin_label,dest_label='Origin','Destination'; origin_default,dest_default='Dubai','Riyadh'
    with c3:
        origin=st.text_input(origin_label, origin_default); dest=st.text_input(dest_label, dest_default)
    with c4:
        if mode=='Sea': equipment=st.selectbox('Equipment', EQUIPMENT); containers=st.number_input('No. of Containers', min_value=1, value=1, step=1)
        else: equipment=''; containers=st.number_input('Containers', min_value=0, value=0, step=1)
    if mode=='Sea':
        st.subheader('2. Sea Cargo Details')
        if 'sea_cargo_lines' not in st.session_state: st.session_state.sea_cargo_lines=pd.DataFrame([{'Equipment':equipment,'Qty':containers,'Gross Weight KG':0.0}])
        add=st.button('＋ Add further cargo details')
        if add:
            st.session_state.sea_cargo_lines=pd.concat([st.session_state.sea_cargo_lines,pd.DataFrame([{'Equipment':equipment,'Qty':1,'Gross Weight KG':0.0}])], ignore_index=True)
        sea_df=st.data_editor(st.session_state.sea_cargo_lines, num_rows='dynamic', use_container_width=True, column_config={'Equipment':st.column_config.SelectboxColumn('Equipment', options=EQUIPMENT),'Qty':st.column_config.NumberColumn('Qty', min_value=1, step=1),'Gross Weight KG':st.column_config.NumberColumn('Gross Weight KG', min_value=0.0, step=1.0)}, key='sea_cargo_editor')
        gross_kg=float(pd.to_numeric(sea_df['Gross Weight KG'], errors='coerce').fillna(0).sum()) if not sea_df.empty else 0.0; cbm=0.0; pieces=0; chargeable_kg=gross_kg
        equipment=sea_df['Equipment'].iloc[0] if not sea_df.empty else equipment; containers=int(pd.to_numeric(sea_df['Qty'], errors='coerce').fillna(0).sum()) if not sea_df.empty else containers
        st.metric('Total Gross Weight', f'{gross_kg:,.2f} kg')
    else:
        st.subheader('2. Source Dimensions and Weight')
        src=st.file_uploader('Upload screenshot/image, email, PDF, CSV, Excel, TXT or EML', type=['pdf','txt','eml','csv','xlsx','xls','png','jpg','jpeg','webp'])
        pasted=st.text_area('Or paste enquiry/email text here', height=100)
        txt=(extract_text_from_upload(src) if src else '') + ('\n'+pasted if pasted else '')
        summary={'gross_kg':0.0,'cbm':0.0,'pieces':0}; dims=pd.DataFrame()
        if txt.strip():
            dims,summary=parse_dimensions_and_weight(txt)
            with st.expander('View AI extracted text and dimensions'):
                st.text_area('Extracted text', txt[:15000], height=150)
                if not dims.empty: st.dataframe(dims, use_container_width=True)
        w1,w2,w3=st.columns(3)
        gross_kg=w1.number_input('Gross Weight KG', min_value=0.0, value=float(summary['gross_kg']), step=1.0)
        cbm=w2.number_input('CBM', min_value=0.0, value=float(summary['cbm']), step=.01, format='%.4f')
        pieces=w3.number_input('Pieces', min_value=0, value=int(summary['pieces']), step=1)
        with st.expander('Manual dimension calculator'):
            d1,d2,d3,d4=st.columns(4); p=d1.number_input('Pieces per line', min_value=1, value=1); l=d2.number_input('Length cm', min_value=0.0); w=d3.number_input('Width cm', min_value=0.0); h=d4.number_input('Height cm', min_value=0.0); st.info(f'Manual line CBM: {cbm_from_cm(l,w,h,p):.4f}')
        chargeable_kg=chargeable_weight(mode,gross_kg,cbm)
        k1,k2,k3=st.columns(3); k1.metric('Gross Weight',f'{gross_kg:,.2f} kg'); k2.metric('CBM',f'{cbm:,.4f}'); k3.metric('Chargeable Weight',f'{chargeable_kg:,.2f} kg')
    st.subheader('3. Margin')
    mc1,mc2=st.columns(2); method=mc1.radio('Margin Method',['% Markup on Buying','Fixed AED Margin'], horizontal=True)
    margin_pct=mc2.number_input('Margin %', min_value=0.0, value=15.0, step=.5) if method=='% Markup on Buying' else 0.0
    fixed_margin=mc2.number_input('Fixed Margin AED', min_value=0.0, value=250.0, step=50.0) if method!='% Markup on Buying' else 0.0
    enq={'enquiry_no':enquiry_no,'customer':customer,'mode':mode,'service':service,'origin':origin,'destination':dest,'origin_label':origin_label,'destination_label':dest_label,'gross_kg':gross_kg,'cbm':cbm,'chargeable_kg':chargeable_kg,'containers':containers,'equipment':equipment}
    st.subheader('4. Quote Source')
    qsource=st.radio('Choose quotation method',['Auto quote from saved tariff','Manual quote'], horizontal=True)
    final_lines=pd.DataFrame(); final_total=0.0
    if qsource.startswith('Auto'):
        ranked=match_rates(tariffs,mode,origin,dest,chargeable_kg,cbm,containers,service,equipment)
        if ranked.empty:
            st.warning('No matching auto tariff found.')
            st.info('Below is a diagnostic view of imported tariff rows. Check that mode, origin, destination, equipment, and rate columns are mapped.')
            dbg=clean_tariff(tariffs).copy()
            if not dbg.empty:
                tmp=dbg.apply(lambda r: row_score(r,mode,origin,dest,service,equipment),axis=1)
                dbg['match_score']=[x[0] for x in tmp]; dbg['match_reason']=[x[1] for x in tmp]
                dbg['calculated_buying']=dbg.apply(lambda r: rate_total(r,chargeable_kg,cbm,containers),axis=1)
                st.dataframe(dbg.sort_values('match_score', ascending=False).head(25), use_container_width=True)
            st.info('If rates are in PDF but not extracted, open Tariff Table and manually fill origin/destination/equipment/rate_per_container or rate_per_kg once, then Save tariff table changes.')
        else:
            st.success(f'{len(ranked)} matching tariff option(s) found.')
            st.dataframe(ranked, use_container_width=True)
            idx=st.selectbox('Select rate option for quote', list(ranked.index), format_func=lambda i: f"Rank {int(ranked.loc[i,'rank'])} | {ranked.loc[i,'vendor']} | {ranked.loc[i,'equipment'] or ranked.loc[i,'service']} | Buying {ranked.loc[i,'currency']} {float(ranked.loc[i,'buying_total_aed']):,.2f}")
            best=ranked.loc[idx]; buying=float(best['buying_total_aed']); selling=round(buying*(1+margin_pct/100),2) if method=='% Markup on Buying' else round(buying+fixed_margin,2)
            final_lines=build_auto_quote_lines(best,selling); final_total=total_quote(final_lines); ma=selling-buying
            a,b,c,d=st.columns(4); a.metric('Buying Cost',f"{best.get('currency','AED')} {buying:,.2f}"); b.metric('Total Selling Quote',f"{best.get('currency','AED')} {final_total:,.2f}"); c.metric('Margin',f"{best.get('currency','AED')} {ma:,.2f}"); d.metric('Margin on Selling',f'{(ma/selling*100 if selling else 0):.2f}%')
            st.dataframe(final_lines, use_container_width=True)
    else:
        st.info('Total is calculated automatically as Unit Price + VAT/Tax for each line.')
        if 'manual_quote_lines_v5' not in st.session_state: st.session_state.manual_quote_lines_v5=default_manual_quote_lines()
        manual=st.data_editor(st.session_state.manual_quote_lines_v5, num_rows='dynamic', use_container_width=True, column_config={'Description':st.column_config.TextColumn('Description'),'Carrier':st.column_config.TextColumn('Carrier'),'Unit':st.column_config.TextColumn('Unit'),'Unit Price':st.column_config.NumberColumn('Unit Price', min_value=0.0, step=1.0),'VAT/Tax':st.column_config.NumberColumn('VAT/Tax', min_value=0.0, step=1.0),'Currency':st.column_config.SelectboxColumn('Currency', options=CURRENCIES),'Total':st.column_config.NumberColumn('Total', disabled=True)}, key='manual_editor_v5')
        final_lines=calculate_manual_totals(manual); final_total=total_quote(final_lines)
        st.dataframe(final_lines, use_container_width=True); st.metric('Total Selling Quote', f"{final_lines['Currency'].iloc[0] if not final_lines.empty else 'AED'} {final_total:,.2f}")
    st.subheader('5. Prepared Quote Text and PDF')
    st.metric('Final Total Selling Quote', f"{final_lines['Currency'].iloc[0] if not final_lines.empty else 'AED'} {final_total:,.2f}")
    qtext=make_quote_text(enq,final_lines,final_total,rate_validity); st.text_area('Prepared Quote Text', qtext, height=340)
    st.download_button('Download quote text', qtext, f'{enquiry_no}_quote.txt', 'text/plain')
    pdf=make_pdf(enq,final_lines,final_total,rate_validity)
    if pdf: st.download_button('Create / Download PDF quote with Marvento logo', pdf, f'{enquiry_no}_marvento_quote.pdf', 'application/pdf')
    else: st.error('PDF package not installed. Ensure reportlab is in requirements.txt.')
with tab2:
    st.subheader('Active Tariff Table')
    st.caption('V5 shows imported/mapped tariff rows. For Sea, usable rates must have Equipment and rate_per_container. For Air/Courier, usable rates must have rate_per_kg.')
    tview=clean_tariff(tariffs).copy()
    if not tview.empty:
        tview['usable_rate_total_test']=tview.apply(lambda r: rate_total(r,100,1,1), axis=1)
        st.info(f'Active tariff rows: {len(tview)} | Rows with usable rate: {(tview["usable_rate_total_test"]>0).sum()}')
    edited=st.data_editor(tariffs, num_rows='dynamic', use_container_width=True, key='tariff_editor_v5')
    c1,c2=st.columns(2)
    if c1.button('Save tariff table changes'): save_tariffs(edited); st.success('Tariff table saved.'); st.rerun()
    c2.download_button('Download active tariff table', clean_tariff(edited).to_csv(index=False), 'active_marvento_tariffs.csv','text/csv')
with tab3:
    st.subheader('How to use V5')
    st.markdown('''
1. Upload multiple CSV, Excel, or PDF tariff files on the left, then click **Save uploaded tariff files**.
2. V5 reads CSV, all Excel sheets, PDF tables, and PDF text. It also tries to detect wide sea columns like 20DV / 40HC / 40RF.
3. Auto quote now shows match diagnostics and fallback options if the lane text is different, so you can see why a rate was or was not selected.
4. For Sea mode, only **Gross Weight** and **Equipment** cargo details are shown. Use **＋ Add further cargo details** for more container/cargo lines.
5. Manual quote total is calculated automatically and shown in quote text and PDF.
6. Upload Marvento logo in the left menu to place it at the top-left of the PDF quotation.

Note: Streamlit free file storage can reset after redeployment/sleep. For production, store tariffs in SharePoint, OneDrive, or SQL.
''')
