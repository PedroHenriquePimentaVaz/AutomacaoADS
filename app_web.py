from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import io
import json
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
try:
    from sults_api import SultsAPIClient
    SULTS_AVAILABLE = True
except ImportError:
    SULTS_AVAILABLE = False
    print("Aviso: Módulo sults_api não disponível. Integração SULTS desabilitada.")

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
app.jinja_env.cache = {}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


def _make_unique_headers(headers):
    """Garante cabeçalhos únicos e não vazios."""
    normalized = []
    seen = {}
    for header in headers:
        base = str(header).strip() if header is not None else ''
        if base == '':
            base = 'Coluna'
        count = seen.get(base, 0)
        seen[base] = count + 1
        normalized.append(base if count == 0 else f"{base}_{count + 1}")
    return normalized


def load_leads_dataframe_from_google_sheets(spreadsheet_id, credentials, priority_names=None):
    """Carrega todas as abas diretamente da API do Google Sheets."""
    sheets_service = build('sheets', 'v4', credentials=credentials)
    metadata = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

    priority_names = [name.strip().lower() for name in (priority_names or []) if name.strip()]
    frames_map = {}
    sheet_stats = []

    for sheet in metadata.get('sheets', []):
        properties = sheet.get('properties', {})
        title = properties.get('title', f"Aba_{len(sheet_stats) + 1}")

        values_response = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=title
        ).execute()

        values = values_response.get('values', [])
        if not values:
            sheet_stats.append({'name': title, 'rows': 0, 'columns': 0})
            print(f"[LEADS][SheetsAPI] Aba '{title}' sem dados.")
            continue

        header = _make_unique_headers(values[0])
        data_rows = values[1:] if len(values) > 1 else []
        max_columns = max(len(row) for row in values)
        while len(header) < max_columns:
            header.append(f"Coluna_{len(header) + 1}")

        if not data_rows:
            sheet_stats.append({'name': title, 'rows': 0, 'columns': len(header)})
            print(f"[LEADS][SheetsAPI] Aba '{title}' somente com cabeçalho.")
            continue

        normalized_rows = []
        for row in data_rows:
            if len(row) < len(header):
                row = row + [''] * (len(header) - len(row))
            normalized_rows.append(row)

        df_sheet = pd.DataFrame(normalized_rows, columns=header)
        df_sheet.replace('', pd.NA, inplace=True)
        cleaned_df = df_sheet.dropna(how='all').dropna(axis=1, how='all')

        rows = int(cleaned_df.shape[0])
        cols = int(cleaned_df.shape[1])
        sheet_stats.append({'name': title, 'rows': rows, 'columns': cols})
        print(f"[LEADS][SheetsAPI] Aba '{title}' -> linhas: {rows}, colunas: {cols}")

        if rows == 0 or cols == 0:
            continue

        frames_map[title] = cleaned_df

    if not frames_map:
        raise ValueError("Nenhuma aba com dados relevantes via Sheets API")

    ordered_titles = []
    matched_priority = []
    
    if priority_names:
        for name in priority_names:
            match = next((title for title in frames_map.keys() if title.lower() == name.lower()), None)
            if match and match not in ordered_titles:
                ordered_titles.append(match)
                matched_priority.append(match)
    else:
        for title in frames_map.keys():
            ordered_titles.append(title)

    frames = [frames_map[title] for title in ordered_titles]
    combined_df = pd.concat(frames, ignore_index=True, sort=False)
    combined_df = combined_df.dropna(how='all').reset_index(drop=True)
    combined_rows = int(combined_df.shape[0])

    primary_sheet = matched_priority[0] if matched_priority else ordered_titles[0]

    return combined_df, {
        'primary_sheet': primary_sheet,
        'sheet_stats': sheet_stats,
        'sheet_count': len(sheet_stats),
        'combined_rows': combined_rows,
        'source': 'google_sheets_api',
        'matched_priority': matched_priority,
        'ordered_sheets': ordered_titles
    }


def load_leads_dataframe_from_bytes(file_bytes, filename='planilha.xlsx', priority_names=None):
    """Lê planilhas locais combinando todas as abas com dados válidos."""
    file_like = io.BytesIO(file_bytes)
    lower_filename = filename.lower()
    priority_names = [name.strip().lower() for name in (priority_names or []) if name.strip()]

    sheet_stats = []
    frames_map = {}

    # CSV
    if lower_filename.endswith('.csv'):
        file_like.seek(0)
        df = pd.read_csv(file_like, dtype=str)
        df.replace('', pd.NA, inplace=True)
        sheet_stats.append({
            'name': 'CSV',
            'rows': int(df.dropna(how='all').shape[0]),
            'columns': int(df.dropna(axis=1, how='all').shape[1])
        })
        return df, {
            'primary_sheet': 'CSV',
            'sheet_stats': sheet_stats,
            'sheet_count': 1,
            'combined_rows': int(df.dropna(how='all').shape[0]),
            'source': 'csv_upload',
            'matched_priority': ['CSV'] if 'csv' in priority_names else [],
            'ordered_sheets': ['CSV']
        }

    try:
        file_like.seek(0)
        sheets_dict = pd.read_excel(file_like, sheet_name=None, dtype=str)

        for sheet_name, sheet_df in sheets_dict.items():
            cleaned_df = sheet_df.dropna(how='all').dropna(axis=1, how='all')
            cleaned_df.replace('', pd.NA, inplace=True)
            rows = int(cleaned_df.shape[0])
            cols = int(cleaned_df.shape[1])

            sheet_stats.append({'name': sheet_name, 'rows': rows, 'columns': cols})
            print(f"[LEADS] Aba '{sheet_name}' -> linhas: {rows}, colunas: {cols}")

            if rows == 0 or cols == 0:
                continue

            frames_map[sheet_name] = cleaned_df

        if not frames_map:
            raise ValueError("Nenhuma aba com dados foi encontrada")

        ordered_titles = []
        matched_priority = []
        
        if priority_names:
            for name in priority_names:
                match = next((title for title in frames_map.keys() if title.lower() == name.lower()), None)
                if match and match not in ordered_titles:
                    ordered_titles.append(match)
                    matched_priority.append(match)
        else:
            for title in frames_map.keys():
                ordered_titles.append(title)

        frames = [frames_map[title] for title in ordered_titles]
        combined_df = pd.concat(frames, ignore_index=True, sort=False)
        combined_df = combined_df.dropna(how='all').reset_index(drop=True)
        combined_rows = int(combined_df.shape[0])

        primary_sheet = matched_priority[0] if matched_priority else ordered_titles[0]

        return combined_df, {
            'primary_sheet': primary_sheet,
            'sheet_stats': sheet_stats,
            'sheet_count': len(sheet_stats),
            'combined_rows': combined_rows,
            'source': 'xlsx_export',
            'matched_priority': matched_priority,
            'ordered_sheets': ordered_titles
        }
    except Exception as exc:
        print(f"[LEADS] Falha ao combinar abas ({exc}), tentando leitura simples.")
        file_like.seek(0)
        df = pd.read_excel(file_like, dtype=str)
        df.replace('', pd.NA, inplace=True)
        df = df.dropna(how='all').dropna(axis=1, how='all').reset_index(drop=True)
        sheet_stats.append({'name': 'Sheet1', 'rows': int(df.shape[0]), 'columns': int(df.shape[1])})
        return df, {
            'primary_sheet': 'Sheet1',
            'sheet_stats': sheet_stats,
            'sheet_count': len(sheet_stats),
            'combined_rows': int(df.shape[0]),
            'source': 'xlsx_export_fallback',
            'matched_priority': [],
            'ordered_sheets': ['Sheet1']
        }

def load_drive_credentials():
    """Carrega credenciais do Google Drive"""
    try:
        credentials_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        # Se não estiver definido, tentar caminho relativo
        if not credentials_file:
            credentials_file = 'sixth-now-475017-k8-785034518ab7.json'
        
        # Verifica se o arquivo existe
        if not os.path.exists(credentials_file):
            print(f"Arquivo de credenciais não encontrado: {credentials_file}")
            print(f"Diretório atual: {os.getcwd()}")
            print(f"Conteúdo do diretório: {os.listdir('.')}")
            return None
        
        credentials = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        print(f"Credenciais carregadas de: {credentials_file}")
        return credentials
    except Exception as e:
        print(f"Erro ao carregar credenciais: {e}")
        import traceback
        traceback.print_exc()
        return None

def download_file_from_drive(file_id, credentials):
    """Baixa arquivo do Google Drive"""
    try:
        service = build('drive', 'v3', credentials=credentials)
        
        # Busca informações do arquivo
        file_metadata = service.files().get(fileId=file_id).execute()
        file_name = file_metadata.get('name', 'planilha.xlsx')
        mime_type = file_metadata.get('mimeType', '')
        
        print(f"Arquivo encontrado: {file_name}")
        print(f"Tipo MIME: {mime_type}")
        
        # Determina o método de download baseado no tipo de arquivo
        if mime_type == 'application/vnd.google-apps.spreadsheet':
            # Google Sheets - precisa exportar
            print("Detectado Google Sheets, exportando como Excel...")
            request = service.files().export_media(
                fileId=file_id,
                mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            file_name = file_name.replace('.xlsx', '') + '.xlsx'
        else:
            # Arquivo binário normal (Excel, CSV, etc.)
            print("Arquivo binário detectado, baixando diretamente...")
            request = service.files().get_media(fileId=file_id)
        
        # Baixa o conteúdo do arquivo
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(f"Progresso: {int(status.progress() * 100)}%")
        
        print(f"Download concluído: {file_name}")
        return file_content.getvalue(), file_name
        
    except Exception as e:
        print(f"Erro ao baixar arquivo: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def clean_dataframe_for_json(df):
    """Limpa DataFrame removendo valores NaN para serialização JSON"""
    cleaned_data = []
    for _, row in df.iterrows():
        clean_row = {}
        for col, value in row.items():
            if pd.isna(value):
                # Se for uma coluna que deveria ser numérica, usa 0
                if any(keyword in col.upper() for keyword in ['CPL', 'CPMQL', 'CPC', 'CPM', 'CTR', 'LEAD', 'MQL', 'INVESTIMENTO', 'CLIQUES', 'IMPRESSÕES']):
                    clean_row[col] = 0.0
                else:
                    clean_row[col] = None
            elif isinstance(value, (int, float)):
                clean_row[col] = float(value) if not pd.isna(value) else 0.0
            else:
                clean_row[col] = str(value)
        cleaned_data.append(clean_row)
    return cleaned_data

def fill_empty_fields_with_zero(df):
    """Preenche campos em branco com 0"""
    # Identifica colunas numéricas
    numeric_columns = df.select_dtypes(include=[np.number]).columns
    
    # Preenche valores NaN com 0 nas colunas numéricas
    df[numeric_columns] = df[numeric_columns].fillna(0)
    
    # Para colunas de texto, verifica se contém valores que podem ser convertidos para números
    text_columns = df.select_dtypes(include=['object']).columns
    for col in text_columns:
        # Verifica se a coluna contém principalmente números (ignorando NaN)
        non_null_values = df[col].dropna()
        if len(non_null_values) > 0:
            try:
                # Tenta converter valores não-nulos para numérico
                # Usa astype('str') primeiro para garantir que é string, não objeto concatenado
                numeric_values = pd.to_numeric(non_null_values.astype('str'), errors='coerce')
                # Se mais de 50% dos valores não-nulos são numéricos, trata como numérica
                if len(numeric_values.dropna()) / len(non_null_values) > 0.5:
                    # Converte toda a coluna para numérica e preenche NaN com 0
                    # Usa apply para converter item por item
                    try:
                        df[col] = df[col].apply(lambda x: pd.to_numeric(x, errors='coerce') if pd.notna(x) else 0).fillna(0)
                    except:
                        # Se der erro, mantém como string e preenche com string vazia
                        df[col] = df[col].fillna('')
                else:
                    # Preenche com string vazia
                    df[col] = df[col].fillna('')
            except Exception as e:
                # Se houver erro, preenche com string vazia
                print(f"Erro ao processar coluna {col}: {e}")
                df[col] = df[col].fillna('')
        else:
            # Se todos os valores são NaN, preenche com string vazia
            df[col] = df[col].fillna('')
    
    return df

def fill_lead_mql_columns(df, leads_cols):
    """Preenche especificamente colunas de leads e MQLs com 0"""
    # Preenche coluna de leads
    if leads_cols.get('lead'):
        lead_col = leads_cols['lead']
        if lead_col in df.columns:
            # Converte para numérico e preenche NaN com 0
            df[lead_col] = pd.to_numeric(df[lead_col], errors='coerce').fillna(0)
    
    # Preenche coluna de MQLs
    if leads_cols.get('mql'):
        mql_col = leads_cols['mql']
        if mql_col in df.columns:
            # Converte para numérico e preenche NaN com 0
            df[mql_col] = pd.to_numeric(df[mql_col], errors='coerce').fillna(0)
    
    # Preenche outras colunas que podem ter valores numéricos vazios
    for col in df.columns:
        # Se o nome da coluna sugere que é numérico (CPL, CPMQL, etc.)
        # Mas só converte se não for uma das colunas de leads/mqls já processadas
        col_upper = col.upper()
        if (any(keyword in col_upper for keyword in ['CPL', 'CPMQL', 'CPC', 'CPM', 'CTR']) and 
            col != lead_col and col != mql_col):
            # Tenta converter para numérico e preenche NaN com 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df

def fill_term_column(df):
    """Preenche coluna Term vazia com 'organico'"""
    # Procura pela coluna Term (case insensitive)
    for col in df.columns:
        if col.lower() == 'term':
            df[col] = df[col].fillna('organico')
            # Também preenche strings vazias
            df[col] = df[col].replace('', 'organico')
            print(f"Coluna '{col}' preenchida com 'organico' onde estava vazio")
            break
    return df

def process_mql_column_to_leads(df):
    """Processa coluna MQL? para criar colunas de contagem de LEADS e MQLs"""
    # Procura pela coluna MQL? (case insensitive)
    mql_col = None
    for col in df.columns:
        if 'mql' in col.lower():
            mql_col = col
            break
    
    if mql_col:
        print(f"Encontrada coluna MQL: {mql_col}")
        
        # Cria colunas temporárias de contagem
        df['COUNT_LEAD'] = df[mql_col].apply(lambda x: 1 if str(x).upper().strip() == 'LEAD' else 0)
        df['COUNT_MQL'] = df[mql_col].apply(lambda x: 1 if str(x).upper().strip() == 'MQL' else 0)
        
        print(f"Total de LEADS (contados): {df['COUNT_LEAD'].sum()}")
        print(f"Total de MQLs (contados): {df['COUNT_MQL'].sum()}")
        
        return True, 'COUNT_LEAD', 'COUNT_MQL'
    
    return False, None, None

def parse_brazilian_date(date_str):
    """Mantém data brasileira DD/MM/YYYY no formato original"""
    if pd.isna(date_str) or date_str == '':
        return ""
    
    try:
        if isinstance(date_str, pd.Timestamp):
            return date_str.strftime('%d/%m/%Y')
        
        date_str = str(date_str).strip()
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 3:
                day, month, year = parts
                return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
        
        if ' ' in date_str and len(date_str) > 10:
            date_part = date_str.split(' ')[0]
            if '/' in date_part:
                parts = date_part.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
        
        parsed_date = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
        if pd.notna(parsed_date):
            return parsed_date.strftime('%d/%m/%Y')
        
        return str(date_str)[:10] if date_str else ""
        
    except Exception as e:
        return str(date_str)[:10] if date_str else ""

def detect_date_column(df):
    """Detecta automaticamente a coluna de data"""
    for col in df.columns:
        col_lower = str(col).lower()
        if any(keyword in col_lower for keyword in ['data', 'date', 'dia']):
            return col
    return None

def detect_creative_columns(df):
    """Detecta automaticamente as colunas de criativo"""
    detected = {
        'campaign': None,
        'creative': None
    }
    
    # Lista de colunas que devem ser ignoradas (métricas numéricas)
    metrics_keywords = ['lead', 'leads', 'mql', 'mqls', 'cliques', 'impressoes', 'impressão', 
                       'investimento', 'custo', 'cpl', 'cpmql', 'cpc', 'cpm', 'ctr', 
                       'conversao', 'conversão', 'taxa', 'alcance', 'reach']
    
    for col in df.columns:
        col_lower = str(col).lower().strip()
        
        # Pular colunas que são métricas numéricas
        if col_lower in metrics_keywords or any(keyword == col_lower for keyword in metrics_keywords):
            continue
            
        # Priorizar colunas que contenham "criativo" ou "creative"
        if any(keyword in col_lower for keyword in ['criativo', 'creative']):
            detected['creative'] = col
        elif any(keyword in col_lower for keyword in ['campaign', 'campanha']):
            detected['campaign'] = col
        elif any(keyword in col_lower for keyword in ['content', 'conteudo', 'conteúdo', 'anuncio', 'anúncio']):
            detected['creative'] = col
    
    # Se não encontrar nenhuma, tentar outras colunas que podem ser criativos
    if not detected['creative'] and not detected['campaign']:
        for col in df.columns:
            col_lower = str(col).lower().strip()
            
            # Pular métricas
            if col_lower in metrics_keywords or any(keyword == col_lower for keyword in metrics_keywords):
                continue
                
            # Procurar por outras palavras-chave que podem indicar criativos
            if any(keyword in col_lower for keyword in ['banner', 'imagem', 'video', 'vídeo', 'texto', 'titulo', 'título', 'copy', 'headline']):
                detected['creative'] = col
                break
    
    # Se ainda não encontrar, usar a primeira coluna de texto que não seja data nem métrica
    if not detected['creative'] and not detected['campaign']:
        for col in df.columns:
            col_lower = str(col).lower().strip()
            
            # Pular datas e métricas
            if col_lower in ['data', 'date', 'dia']:
                continue
            if col_lower in metrics_keywords or any(keyword == col_lower for keyword in metrics_keywords):
                continue
            
            # Usar primeira coluna de texto
            if df[col].dtype == 'object':
                detected['creative'] = col
                break
    
    return detected

def detect_cost_columns(df):
    """Detecta colunas de custo"""
    cost_cols = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if col_lower == 'cpl':
            cost_cols['lead'] = col
        elif col_lower == 'cpmql':
            cost_cols['mql'] = col
        elif ('investimento' in col_lower or 'investido' in col_lower) and 'habilidade' not in col_lower:
            cost_cols['total'] = col
        elif ('custo' in col_lower or 'cost' in col_lower) and 'habilidade' not in col_lower:
            if 'total' not in cost_cols:
                cost_cols['total'] = col
    return cost_cols

def detect_leads_columns(df):
    """Detecta colunas de leads e MQLs"""
    leads_cols = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if col_lower == 'lead' or col_lower == 'leads':
            leads_cols['lead'] = col
        elif col_lower == 'mql' or col_lower == 'mqls':
            leads_cols['mql'] = col
    
    if not leads_cols.get('lead'):
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if 'lead' in col_lower and 'cpl' not in col_lower:
                leads_cols['lead'] = col
                break
    
    if not leads_cols.get('mql'):
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if 'mql' in col_lower and 'cpmql' not in col_lower and 'custo' not in col_lower:
                leads_cols['mql'] = col
                break
    
    return leads_cols

def detect_lead_date_column(df):
    """Detecta coluna de data em planilhas de leads"""
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if any(keyword in col_lower for keyword in ['data', 'date', 'criado', 'cadastro', 'entrada', 'created']):
            return col
    return None

def detect_lead_status_column(df):
    """Detecta coluna de status em planilhas de leads"""
    status_keywords = ['status', 'etapa', 'stage', 'situação', 'situacao', 'fase', 'pipeline', 'andamento', 'mql']
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if any(keyword in col_lower for keyword in status_keywords):
            return col
    return None

def detect_lead_source_column(df):
    """Detecta coluna de origem em planilhas de leads"""
    source_keywords = ['origem', 'source', 'fonte', 'canal', 'utm', 'campanha', 'midia', 'mídia', 'procedência']
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if any(keyword in col_lower for keyword in source_keywords):
            return col
    return None

def detect_lead_owner_column(df):
    """Detecta coluna de responsável em planilhas de leads"""
    owner_keywords = ['respons', 'consultor', 'vendedor', 'owner', 'account', 'atendente', 'agente', 'seller', 'executivo']
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if any(keyword in col_lower for keyword in owner_keywords):
            return col
    return None

def detect_lead_name_column(df):
    """Detecta coluna de nome do lead"""
    name_keywords = ['nome', 'name', 'lead', 'contato', 'cliente']
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if any(keyword in col_lower for keyword in name_keywords):
            return col
    return df.columns[0] if len(df.columns) > 0 else None

def analyze_leads_dataframe(df):
    """Gera análises a partir de uma planilha de leads"""
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    
    date_col = detect_lead_date_column(df)
    status_col = detect_lead_status_column(df)
    source_col = detect_lead_source_column(df)
    owner_col = detect_lead_owner_column(df)
    name_col = detect_lead_name_column(df)
    
    if source_col:
        def _normalize_source(value):
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return 'organico'
            text = str(value).strip()
            return text if text else 'organico'
        df[source_col] = df[source_col].apply(_normalize_source)
        df[source_col] = df[source_col].astype(str).str.strip()
        df[source_col] = df[source_col].replace({'': 'organico', 'nan': 'organico', 'None': 'organico', '<NA>': 'organico'})
        df[source_col] = df[source_col].fillna('organico')

    if date_col:
        df['_lead_date_dt'] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        if 'Data_Lead' not in df.columns:
            df['Data_Lead'] = df[date_col].apply(parse_brazilian_date)
    else:
        df['_lead_date_dt'] = pd.NaT
    
    total_leads = int(len(df))
    
    leads_last_30_days = 0
    leads_without_date = total_leads
    monthly_trend = []
    timeline = []
    
    if date_col:
        now = datetime.now()
        last_30 = now - timedelta(days=30)
        valid_dates = df['_lead_date_dt'].dropna()
        leads_last_30_days = int(((df['_lead_date_dt'] >= last_30) & (df['_lead_date_dt'] <= now)).sum())
        leads_without_date = int(df['_lead_date_dt'].isna().sum())
        
        if not valid_dates.empty:
            monthly_counts = df.loc[df['_lead_date_dt'].notna(), '_lead_date_dt'].dt.to_period('M').value_counts().sort_index()
            timeline = [
                {
                    'period': period.strftime('%m/%Y'),
                    'leads': int(count)
                }
                for period, count in monthly_counts.items()
            ]
    
    status_distribution = []
    source_distribution = []
    owner_distribution = []
    leads_won = 0
    leads_lost = 0
    conversion_rate = 0.0
    tag_leads = 0
    tag_mqls = 0
    
    # Detecta coluna MQL? especificamente
    mql_col = None
    for col in df.columns:
        if str(col).strip() == 'MQL?':
            mql_col = col
            break
    
    if mql_col:
        mql_series = df[mql_col].fillna('').astype(str).str.strip()
        mql_upper = mql_series.str.upper()
        tag_leads = int((mql_upper == 'LEAD').sum())
        tag_mqls = int((mql_upper == 'MQL').sum())
    
    if status_col:
        status_series = df[status_col].fillna('Sem Status').astype(str).str.strip()
        status_counts = status_series.value_counts().head(15)
        status_distribution = [
            {'label': status, 'value': int(count)}
            for status, count in status_counts.items()
        ]
        
        status_lower = status_series.str.lower()
        won_keywords = ['ganho', 'won', 'fechado', 'concluído', 'concluido', 'cliente', 'converted']
        lost_keywords = ['perdido', 'lost', 'cancelado', 'desistiu', 'no show', 'no-show', 'falhou']
        
        leads_won = int(status_lower.apply(lambda x: any(keyword in x for keyword in won_keywords)).sum())
        leads_lost = int(status_lower.apply(lambda x: any(keyword in x for keyword in lost_keywords)).sum())
        conversion_rate = round((leads_won / total_leads) * 100, 2) if total_leads > 0 else 0.0

    if source_col:
        source_series = df[source_col].astype(str).str.strip()

    if owner_col:
        owner_series = df[owner_col].fillna('Sem Responsável').astype(str).str.strip()
        owner_counts = owner_series.value_counts().head(15)
        owner_distribution = [
            {'label': owner, 'value': int(count)}
            for owner, count in owner_counts.items()
        ]
    
    unique_statuses = len(df[status_col].dropna().unique()) if status_col else 0
    unique_sources = len(df[source_col].dropna().unique()) if source_col else 0
    
    leads_active = total_leads - leads_won - leads_lost
    leads_active = leads_active if leads_active >= 0 else 0
    
    recent_preview = df.copy()
    if date_col and df['_lead_date_dt'].notna().any():
        recent_preview = recent_preview.sort_values(by=['_lead_date_dt'], ascending=False)
    else:
        recent_preview = recent_preview.reset_index(drop=True)
    
    preview_columns = []
    rename_map = {}
    
    if name_col:
        preview_columns.append(name_col)
        rename_map[name_col] = 'Lead'
    if status_col and status_col not in preview_columns:
        preview_columns.append(status_col)
        rename_map[status_col] = 'Status'
    if source_col and source_col not in preview_columns:
        preview_columns.append(source_col)
        rename_map[source_col] = 'Origem'
    if owner_col and owner_col not in preview_columns:
        preview_columns.append(owner_col)
        rename_map[owner_col] = 'Responsável'
    if date_col and date_col not in preview_columns:
        preview_columns.append(date_col)
        rename_map[date_col] = 'Data'
    
    if preview_columns:
        recent_preview = recent_preview[preview_columns].head(20).rename(columns=rename_map)
    else:
        recent_preview = recent_preview.head(20)
    
    insights = {
        'top_status': status_distribution[0] if status_distribution else None,
        'top_source': source_distribution[0] if source_distribution else None,
        'top_owner': owner_distribution[0] if owner_distribution else None
    }
    
    mql_to_lead_rate = round((tag_mqls / total_leads) * 100, 2) if total_leads > 0 else 0.0
    
    kpis = {
        'total_leads': total_leads,
        'leads_last_30_days': leads_last_30_days,
        'leads_without_date': leads_without_date,
        'unique_statuses': unique_statuses,
        'unique_sources': unique_sources,
        'leads_won': leads_won,
        'leads_lost': leads_lost,
        'leads_active': leads_active,
        'conversion_rate': conversion_rate,
        'mql_to_lead_rate': mql_to_lead_rate,
        'tag_leads': tag_leads,
        'tag_mqls': tag_mqls
    }
    
    distributions = {
        'status': status_distribution,
        'source': source_distribution,
        'owner': owner_distribution
    }
    
    df = df.drop(columns=['_lead_date_dt'])
    if source_col:
        df[source_col] = df[source_col].replace(r'^\s*$', 'organico', regex=True).fillna('organico')

    return {
        'columns': list(df.columns),
        'total_rows': total_leads,
        'date_column': date_col,
        'status_column': status_col,
        'source_column': source_col,
        'owner_column': owner_col,
        'name_column': name_col,
        'kpis': kpis,
        'distributions': distributions,
        'timeline': timeline,
        'insights': insights,
        'recent_leads': clean_dataframe_for_json(recent_preview),
        'raw_data': clean_dataframe_for_json(df)
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        print("Upload request received")
        if 'file' not in request.files:
            print("No file part in request")
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        if file.filename == '':
            print("No filename provided")
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        print(f"Processing file: {file.filename}")
        
        # Lê o arquivo
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Processa dados
        date_col = detect_date_column(df)
        creative_cols = detect_creative_columns(df)
        cost_cols = detect_cost_columns(df)
        leads_cols = detect_leads_columns(df)
        
        # Processa datas
        if date_col:
            df['Data_Processada'] = df[date_col].apply(parse_brazilian_date)
        
        # Preenche campos em branco com 0 APÓS detectar as colunas
        df = fill_empty_fields_with_zero(df)
        
        # Preenche especificamente colunas de leads e MQLs com 0 se estiverem vazias
        df = fill_lead_mql_columns(df, leads_cols)
        
        # Preenche coluna Term vazia com 'organico'
        df = fill_term_column(df)
        
        # Cria identificador único do criativo
        if creative_cols['campaign'] and creative_cols['creative']:
            df['Criativo_Completo'] = df[creative_cols['campaign']].astype(str) + " | " + df[creative_cols['creative']].astype(str)
        
        # Calcula resumos
        summary_data = {}
        
        if date_col:
            if creative_cols['campaign'] and creative_cols['creative']:
                date_creative_counts = df.groupby('Data_Processada')['Criativo_Completo'].nunique().sort_index()
            else:
                date_creative_counts = df['Data_Processada'].value_counts().sort_index()
            
            summary_df = pd.DataFrame({
                'Data': date_creative_counts.index,
                'Criativos': date_creative_counts.values
            })
            summary_df = summary_df[summary_df['Data'] != ''].reset_index(drop=True)
            # Converte para dict e limpa valores NaN
            temporal_records = []
            for _, row in summary_df.iterrows():
                temporal_records.append({
                    'Data': str(row['Data']) if pd.notna(row['Data']) else '',
                    'Criativos': int(row['Criativos']) if pd.notna(row['Criativos']) else 0
                })
            summary_data['temporal'] = temporal_records
        
        # Calcula KPIs
        kpis = {}
        if leads_cols.get('lead'):
            try:
                total_leads = pd.to_numeric(df[leads_cols['lead']], errors='coerce').sum()
                if pd.isna(total_leads) or total_leads == 0:
                    total_leads = df[leads_cols['lead']].notna().sum()
            except:
                total_leads = df[leads_cols['lead']].notna().sum()
            kpis['total_leads'] = int(total_leads) if not pd.isna(total_leads) else 0
        
        if leads_cols.get('mql'):
            try:
                total_mqls = pd.to_numeric(df[leads_cols['mql']], errors='coerce').sum()
                if pd.isna(total_mqls) or total_mqls == 0:
                    total_mqls = df[leads_cols['mql']].notna().sum()
            except:
                total_mqls = df[leads_cols['mql']].notna().sum()
            kpis['total_mqls'] = int(total_mqls) if not pd.isna(total_mqls) else 0
        
        if cost_cols.get('total'):
            investimento = df[cost_cols['total']].sum()
            kpis['investimento_total'] = float(investimento) if not pd.isna(investimento) else 0.0
        
        # Calcula Custo por MQL
        if cost_cols.get('total') and leads_cols.get('mql') and kpis.get('total_mqls', 0) > 0:
            kpis['custo_por_mql'] = float(investimento) / kpis['total_mqls'] if not pd.isna(investimento) else 0.0
        else:
            kpis['custo_por_mql'] = 0.0
        
        # Análise de criativos
        creative_analysis = {}
        print(f"Creative columns detected: {creative_cols}")
        print(f"Leads columns detected: {leads_cols}")
        
        if leads_cols.get('lead'):
            # Usar coluna de criativo se disponível, senão usar campanha
            creative_col = creative_cols['creative'] if creative_cols['creative'] else creative_cols['campaign']
            print(f"Using creative column: {creative_col}")
            
            # Se não encontrar coluna de criativo, tentar encontrar manualmente
            if not creative_col:
                for col in df.columns:
                    if col.lower() not in ['data', 'date', 'dia', 'leads', 'mql', 'investimento', 'custo', 'cpl', 'cpmql', 'cpc', 'cpm', 'ctr'] and df[col].dtype == 'object':
                        creative_col = col
                        print(f"Auto-detected creative column: {creative_col}")
                        break
            
            if creative_col:
                # Análise detalhada de criativos
                print(f"Analyzing creatives with column: {creative_col}")
                creative_stats = df.groupby(creative_col).agg({
                    leads_cols['lead']: ['sum', 'count'],
                    leads_cols['mql']: 'sum' if leads_cols.get('mql') else lambda x: 0,
                    cost_cols['total']: 'sum' if cost_cols.get('total') else lambda x: 0
                }).round(2)
            
                # Flatten column names
                creative_stats.columns = ['Total_Leads', 'Qtd_Aparicoes', 'Total_MQLs', 'Total_Investimento']
                creative_stats = creative_stats.reset_index()
                
                # Renomear a coluna do criativo para 'creative' para o frontend
                if creative_col in creative_stats.columns:
                    creative_stats = creative_stats.rename(columns={creative_col: 'creative'})
                
                print(f"Creative stats shape: {creative_stats.shape}")
                print(f"Creative stats columns: {creative_stats.columns.tolist()}")
                print(f"Creative stats sample:")
                print(creative_stats.head())
                
                # Calcula métricas adicionais
                creative_stats['Leads_por_Aparicao'] = (creative_stats['Total_Leads'] / creative_stats['Qtd_Aparicoes']).round(2)
                creative_stats['MQLs_por_Aparicao'] = (creative_stats['Total_MQLs'] / creative_stats['Qtd_Aparicoes']).round(2)
                creative_stats['Taxa_Conversao_Lead_MQL'] = (creative_stats['Total_MQLs'] / creative_stats['Total_Leads'] * 100).round(2)
                
                # Calcula custos por criativo
                creative_stats['CPL'] = (creative_stats['Total_Investimento'] / creative_stats['Total_Leads']).round(2)
                creative_stats['CPMQL'] = (creative_stats['Total_Investimento'] / creative_stats['Total_MQLs']).round(2)
                
                # Substitui inf e NaN por 0
                creative_stats = creative_stats.replace([np.inf, -np.inf], 0).fillna(0)
                
                # Ordena por total de leads
                creative_stats = creative_stats.sort_values('Total_Leads', ascending=False)
                
                print(f"Sorted creative stats:")
                print(creative_stats.head())
                
                # Top criativos para gráfico
                top_creatives = {}
                for _, row in creative_stats.head(10).iterrows():
                    creative_name = str(row['creative'])
                    top_creatives[creative_name] = int(row['Total_Leads'])
                
                # Criativo com mais leads
                top_lead_creative = creative_stats.iloc[0] if len(creative_stats) > 0 else None
                
                # Criativo com mais MQLs
                top_mql_creative = creative_stats.loc[creative_stats['Total_MQLs'].idxmax()] if len(creative_stats) > 0 else None
                
                print(f"Top lead creative: {top_lead_creative['creative'] if top_lead_creative is not None else 'None'}")
                print(f"Top MQL creative: {top_mql_creative['creative'] if top_mql_creative is not None else 'None'}")
                
                # Estatísticas gerais
                total_leads_all = creative_stats['Total_Leads'].sum()
                total_mqls_all = creative_stats['Total_MQLs'].sum()
                
                creative_analysis = {
                    'top_creatives': top_creatives,
                    'creative_details': clean_dataframe_for_json(creative_stats.head(20)),  # Top 20 criativos
                    'top_lead_creative': {
                        'name': str(top_lead_creative['creative']) if top_lead_creative is not None else 'N/A',
                        'leads': int(top_lead_creative['Total_Leads']) if top_lead_creative is not None else 0,
                        'mqls': int(top_lead_creative['Total_MQLs']) if top_lead_creative is not None else 0,
                        'investimento': float(top_lead_creative['Total_Investimento']) if top_lead_creative is not None else 0,
                        'appearances': int(top_lead_creative['Qtd_Aparicoes']) if top_lead_creative is not None else 0,
                        'leads_per_appearance': float(top_lead_creative['Leads_por_Aparicao']) if top_lead_creative is not None else 0,
                        'mqls_per_appearance': float(top_lead_creative['MQLs_por_Aparicao']) if top_lead_creative is not None else 0,
                        'conversion_rate': float(top_lead_creative['Taxa_Conversao_Lead_MQL']) if top_lead_creative is not None else 0,
                        'cpl': float(top_lead_creative['CPL']) if top_lead_creative is not None else 0,
                        'cpmql': float(top_lead_creative['CPMQL']) if top_lead_creative is not None else 0
                    } if top_lead_creative is not None else None,
                    'top_mql_creative': {
                        'name': str(top_mql_creative['creative']) if top_mql_creative is not None else 'N/A',
                        'leads': int(top_mql_creative['Total_Leads']) if top_mql_creative is not None else 0,
                        'mqls': int(top_mql_creative['Total_MQLs']) if top_mql_creative is not None else 0,
                        'investimento': float(top_mql_creative['Total_Investimento']) if top_mql_creative is not None else 0,
                        'appearances': int(top_mql_creative['Qtd_Aparicoes']) if top_mql_creative is not None else 0,
                        'leads_per_appearance': float(top_mql_creative['Leads_por_Aparicao']) if top_mql_creative is not None else 0,
                        'mqls_per_appearance': float(top_mql_creative['MQLs_por_Aparicao']) if top_mql_creative is not None else 0,
                        'conversion_rate': float(top_mql_creative['Taxa_Conversao_Lead_MQL']) if top_mql_creative is not None else 0,
                        'cpl': float(top_mql_creative['CPL']) if top_mql_creative is not None else 0,
                        'cpmql': float(top_mql_creative['CPMQL']) if top_mql_creative is not None else 0
                    } if top_mql_creative is not None else None,
                    'total_creatives': len(creative_stats),
                    'avg_leads_per_creative': float(creative_stats['Total_Leads'].mean()) if len(creative_stats) > 0 else 0,
                    'avg_mqls_per_creative': float(creative_stats['Total_MQLs'].mean()) if len(creative_stats) > 0 else 0
                }
            else:
                print("No creative column found, skipping creative analysis")
                creative_analysis = {}
        
        result = {
            'success': True,
            'data': {
                'columns': list(df.columns),
                'total_rows': len(df),
                'date_column': date_col,
                'creative_columns': creative_cols,
                'cost_columns': cost_cols,
                'leads_columns': leads_cols,
                'summary': summary_data,
                'kpis': kpis,
                'creative_analysis': creative_analysis,
                'raw_data': clean_dataframe_for_json(df)  # Todas as linhas
            }
        }
        print("Upload processing completed successfully")
        return jsonify(result)
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500

@app.route('/auto-upload')
def auto_upload():
    """Rota para upload automático da planilha do Google Drive"""
    try:
        # Carrega variáveis de ambiente
        file_id = os.getenv('DRIVE_FILE_ID', '1JIFkoM-GkxDKCu0AuF84jPqkqURgr8H3E0eKcrUkkrY')
        
        # Carrega credenciais
        credentials = load_drive_credentials()
        if not credentials:
            return jsonify({'error': 'Credenciais do Google Drive não encontradas'}), 500
        
        # Baixa arquivo do Google Drive
        file_content, file_name = download_file_from_drive(file_id, credentials)
        if not file_content:
            return jsonify({'error': 'Erro ao baixar arquivo do Google Drive'}), 500
        
        # Simula upload do arquivo
        print(f"Upload automático recebido: {file_name}")
        
        # Processa o arquivo como se fosse um upload normal
        try:
            df = pd.read_excel(io.BytesIO(file_content))
            print(f"Arquivo lido com sucesso: {df.shape}")
            
            # Processa dados (mesma lógica da função de upload)
            date_col = detect_date_column(df)
            creative_cols = detect_creative_columns(df)
            cost_cols = detect_cost_columns(df)
            leads_cols = detect_leads_columns(df)
            
            # Processa datas
            if date_col:
                df['Data_Processada'] = df[date_col].apply(parse_brazilian_date)
            
            # Preenche campos em branco com 0 APÓS detectar as colunas
            df = fill_empty_fields_with_zero(df)
            
            # Preenche especificamente colunas de leads e MQLs com 0 se estiverem vazias
            df = fill_lead_mql_columns(df, leads_cols)
            
            # Preenche coluna Term vazia com 'organico'
            df = fill_term_column(df)
            
            # Cria identificador único do criativo
            if creative_cols['campaign'] and creative_cols['creative']:
                df['Criativo_Completo'] = df[creative_cols['campaign']].astype(str) + " | " + df[creative_cols['creative']].astype(str)
            
            # Calcula resumos
            summary_data = {}
            
            if date_col:
                if creative_cols['campaign'] and creative_cols['creative']:
                    date_creative_counts = df.groupby('Data_Processada')['Criativo_Completo'].nunique().sort_index()
                else:
                    date_creative_counts = df['Data_Processada'].value_counts().sort_index()
                
                summary_df = pd.DataFrame({
                    'Data': date_creative_counts.index,
                    'Criativos': date_creative_counts.values
                })
                summary_df = summary_df[summary_df['Data'] != ''].reset_index(drop=True)
                # Converte para dict e limpa valores NaN
                temporal_records = []
                for _, row in summary_df.iterrows():
                    temporal_records.append({
                        'Data': str(row['Data']) if pd.notna(row['Data']) else '',
                        'Criativos': int(row['Criativos']) if pd.notna(row['Criativos']) else 0
                    })
                summary_data['temporal'] = temporal_records
            
            # Calcula KPIs
            kpis = {}
            if leads_cols.get('lead'):
                try:
                    total_leads = pd.to_numeric(df[leads_cols['lead']], errors='coerce').sum()
                    if pd.isna(total_leads) or total_leads == 0:
                        total_leads = df[leads_cols['lead']].notna().sum()
                except:
                    total_leads = df[leads_cols['lead']].notna().sum()
                kpis['total_leads'] = int(total_leads) if not pd.isna(total_leads) else 0
            
            if leads_cols.get('mql'):
                try:
                    total_mqls = pd.to_numeric(df[leads_cols['mql']], errors='coerce').sum()
                    if pd.isna(total_mqls) or total_mqls == 0:
                        total_mqls = df[leads_cols['mql']].notna().sum()
                except:
                    total_mqls = df[leads_cols['mql']].notna().sum()
                kpis['total_mqls'] = int(total_mqls) if not pd.isna(total_mqls) else 0
            
            if cost_cols.get('total'):
                investimento = df[cost_cols['total']].sum()
                kpis['investimento_total'] = float(investimento) if not pd.isna(investimento) else 0.0
            
            # Calcula Custo por MQL
            if cost_cols.get('total') and leads_cols.get('mql') and kpis.get('total_mqls', 0) > 0:
                kpis['custo_por_mql'] = float(investimento) / kpis['total_mqls'] if not pd.isna(investimento) else 0.0
            else:
                kpis['custo_por_mql'] = 0.0
            
            # Análise de criativos
            creative_analysis = {}
            print(f"Creative columns detected: {creative_cols}")
            print(f"Leads columns detected: {leads_cols}")
            
            if leads_cols.get('lead'):
                # Usar coluna de criativo se disponível, senão usar campanha
                creative_col = creative_cols['creative'] if creative_cols['creative'] else creative_cols['campaign']
                print(f"Using creative column: {creative_col}")
                
                # Se não encontrar coluna de criativo, tentar encontrar manualmente
                if not creative_col:
                    for col in df.columns:
                        if col.lower() not in ['data', 'date', 'dia', 'leads', 'mql', 'investimento', 'custo', 'cpl', 'cpmql', 'cpc', 'cpm', 'ctr'] and df[col].dtype == 'object':
                            creative_col = col
                            print(f"Auto-detected creative column: {creative_col}")
                            break
                
                if creative_col:
                    # Análise detalhada de criativos
                    print(f"Analyzing creatives with column: {creative_col}")
                    creative_stats = df.groupby(creative_col).agg({
                        leads_cols['lead']: ['sum', 'count'],
                        leads_cols['mql']: 'sum' if leads_cols.get('mql') else lambda x: 0,
                        cost_cols['total']: 'sum' if cost_cols.get('total') else lambda x: 0
                    }).round(2)
                
                    # Flatten column names
                    creative_stats.columns = ['Total_Leads', 'Qtd_Aparicoes', 'Total_MQLs', 'Total_Investimento']
                    creative_stats = creative_stats.reset_index()
                    
                    # Renomear a coluna do criativo para 'creative' para o frontend
                    if creative_col in creative_stats.columns:
                        creative_stats = creative_stats.rename(columns={creative_col: 'creative'})
                    
                    print(f"Creative stats shape: {creative_stats.shape}")
                    print(f"Creative stats columns: {creative_stats.columns.tolist()}")
                    print(f"Creative stats sample:")
                    print(creative_stats.head())
                    
                    # Calcula métricas adicionais
                    creative_stats['Leads_por_Aparicao'] = (creative_stats['Total_Leads'] / creative_stats['Qtd_Aparicoes']).round(2)
                    creative_stats['MQLs_por_Aparicao'] = (creative_stats['Total_MQLs'] / creative_stats['Qtd_Aparicoes']).round(2)
                    creative_stats['Taxa_Conversao_Lead_MQL'] = (creative_stats['Total_MQLs'] / creative_stats['Total_Leads'] * 100).round(2)
                    
                    # Calcula custos por criativo
                    creative_stats['CPL'] = (creative_stats['Total_Investimento'] / creative_stats['Total_Leads']).round(2)
                    creative_stats['CPMQL'] = (creative_stats['Total_Investimento'] / creative_stats['Total_MQLs']).round(2)
                    
                    # Substitui inf e NaN por 0
                    creative_stats = creative_stats.replace([np.inf, -np.inf], 0).fillna(0)
                    
                    # Ordena por total de leads
                    creative_stats = creative_stats.sort_values('Total_Leads', ascending=False)
                    
                    print(f"Sorted creative stats:")
                    print(creative_stats.head())
                    
                    # Top criativos para gráfico
                    top_creatives = {}
                    for _, row in creative_stats.head(10).iterrows():
                        creative_name = str(row['creative'])
                        top_creatives[creative_name] = int(row['Total_Leads'])
                    
                    # Criativo com mais leads
                    top_lead_creative = creative_stats.iloc[0] if len(creative_stats) > 0 else None
                    
                    # Criativo com mais MQLs
                    top_mql_creative = creative_stats.loc[creative_stats['Total_MQLs'].idxmax()] if len(creative_stats) > 0 else None
                    
                    print(f"Top lead creative: {top_lead_creative['creative'] if top_lead_creative is not None else 'None'}")
                    print(f"Top MQL creative: {top_mql_creative['creative'] if top_mql_creative is not None else 'None'}")
                    
                    # Estatísticas gerais
                    total_leads_all = creative_stats['Total_Leads'].sum()
                    total_mqls_all = creative_stats['Total_MQLs'].sum()
                    
                    creative_analysis = {
                        'top_creatives': top_creatives,
                        'creative_details': clean_dataframe_for_json(creative_stats.head(20)),  # Top 20 criativos
                        'top_lead_creative': {
                            'name': str(top_lead_creative['creative']) if top_lead_creative is not None else 'N/A',
                            'leads': int(top_lead_creative['Total_Leads']) if top_lead_creative is not None else 0,
                            'mqls': int(top_lead_creative['Total_MQLs']) if top_lead_creative is not None else 0,
                            'investimento': float(top_lead_creative['Total_Investimento']) if top_lead_creative is not None else 0,
                            'appearances': int(top_lead_creative['Qtd_Aparicoes']) if top_lead_creative is not None else 0,
                            'leads_per_appearance': float(top_lead_creative['Leads_por_Aparicao']) if top_lead_creative is not None else 0,
                            'mqls_per_appearance': float(top_lead_creative['MQLs_por_Aparicao']) if top_lead_creative is not None else 0,
                            'conversion_rate': float(top_lead_creative['Taxa_Conversao_Lead_MQL']) if top_lead_creative is not None else 0,
                            'cpl': float(top_lead_creative['CPL']) if top_lead_creative is not None else 0,
                            'cpmql': float(top_lead_creative['CPMQL']) if top_lead_creative is not None else 0
                        } if top_lead_creative is not None else None,
                        'top_mql_creative': {
                            'name': str(top_mql_creative['creative']) if top_mql_creative is not None else 'N/A',
                            'leads': int(top_mql_creative['Total_Leads']) if top_mql_creative is not None else 0,
                            'mqls': int(top_mql_creative['Total_MQLs']) if top_mql_creative is not None else 0,
                            'investimento': float(top_mql_creative['Total_Investimento']) if top_mql_creative is not None else 0,
                            'appearances': int(top_mql_creative['Qtd_Aparicoes']) if top_mql_creative is not None else 0,
                            'leads_per_appearance': float(top_mql_creative['Leads_por_Aparicao']) if top_mql_creative is not None else 0,
                            'mqls_per_appearance': float(top_mql_creative['MQLs_por_Aparicao']) if top_mql_creative is not None else 0,
                            'conversion_rate': float(top_mql_creative['Taxa_Conversao_Lead_MQL']) if top_mql_creative is not None else 0,
                            'cpl': float(top_mql_creative['CPL']) if top_mql_creative is not None else 0,
                            'cpmql': float(top_mql_creative['CPMQL']) if top_mql_creative is not None else 0
                        } if top_mql_creative is not None else None,
                        'total_creatives': len(creative_stats),
                        'avg_leads_per_creative': float(creative_stats['Total_Leads'].mean()) if len(creative_stats) > 0 else 0,
                        'avg_mqls_per_creative': float(creative_stats['Total_MQLs'].mean()) if len(creative_stats) > 0 else 0
                    }
                else:
                    print("No creative column found, skipping creative analysis")
                    creative_analysis = {}
                
                result = {
                    'success': True,
                    'data': {
                        'columns': list(df.columns),
                        'total_rows': len(df),
                        'date_column': date_col,
                        'creative_columns': creative_cols,
                        'cost_columns': cost_cols,
                        'leads_columns': leads_cols,
                        'summary': summary_data,
                        'kpis': kpis,
                        'creative_analysis': creative_analysis,
                        'raw_data': clean_dataframe_for_json(df)  # Todas as linhas
                    }
                }
                
                return jsonify({
                    'success': True,
                    'message': f'Planilha {file_name} carregada automaticamente do Google Drive!',
                    'data': result['data']
                })
                
        except Exception as e:
            print(f"Erro ao processar arquivo Excel: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500
            
    except Exception as e:
        print(f"Erro no upload automático: {str(e)}")
        return jsonify({'error': f'Erro no upload automático: {str(e)}'}), 500

@app.route('/google-ads-upload')
def google_ads_upload():
    """Rota para upload automático da planilha do Google Ads"""
    try:
        # Carrega variáveis de ambiente
        file_id = os.getenv('GOOGLE_ADS_FILE_ID', '1JIFkoM-GkxDKCu0AuF84jPqkqURgr8H3E0eKcrUkkrY')
        
        # Carrega credenciais
        credentials = load_drive_credentials()
        if not credentials:
            return jsonify({'error': 'Credenciais do Google Drive não encontradas'}), 500
        
        # Baixa arquivo do Google Drive
        file_content, file_name = download_file_from_drive(file_id, credentials)
        if not file_content:
            return jsonify({'error': 'Erro ao baixar arquivo do Google Drive'}), 500
        
        # Simula upload do arquivo
        print(f"Upload automático do Google Ads recebido: {file_name}")
        
        # Processa o arquivo como se fosse um upload normal
        try:
            # Tenta ler a aba específica "Controle Google ADS", se não encontrar, lê a primeira
            try:
                df = pd.read_excel(io.BytesIO(file_content), sheet_name='Controle Google ADS')
                print(f"Arquivo do Google Ads lido com sucesso (aba 'Controle Google ADS'): {df.shape}")
            except:
                df = pd.read_excel(io.BytesIO(file_content))
                print(f"Arquivo do Google Ads lido com sucesso (primeira aba): {df.shape}")
            
            print("Colunas da planilha:", list(df.columns))
            
            # Processa APENAS as colunas necessárias: Dia, MQL?, Term
            # Define estruturas vazias para não quebrar
            creative_cols = {}
            cost_cols = {}
            
            # Detecta coluna de data
            date_col = detect_date_column(df)
            if date_col:
                df['Data_Processada'] = df[date_col].apply(parse_brazilian_date)
                print(f"Coluna de data detectada: {date_col}")
            
            # Preenche coluna Term vazia com 'organico'
            df = fill_term_column(df)
            
            # Processa coluna MQL? para criar colunas de contagem
            has_mql_col, lead_count_col, mql_count_col = process_mql_column_to_leads(df)
            
            if not has_mql_col:
                return jsonify({'error': 'Coluna MQL? não encontrada na planilha'}), 500
            
            # Usa as colunas de contagem criadas
            leads_cols = {'lead': lead_count_col, 'mql': mql_count_col}
            print(f"Usando colunas de contagem: {leads_cols}")
            
            # Calcula resumos baseado em Data_Processada
            summary_data = {}
            if date_col:
                # Conta registros únicos de data
                date_counts = df['Data_Processada'].value_counts().sort_index()
                summary_df = pd.DataFrame({
                    'Data': date_counts.index,
                    'Criativos': date_counts.values
                })
                summary_df = summary_df[summary_df['Data'] != ''].reset_index(drop=True)
                temporal_records = []
                for _, row in summary_df.iterrows():
                    temporal_records.append({
                        'Data': str(row['Data']) if pd.notna(row['Data']) else '',
                        'Criativos': int(row['Criativos']) if pd.notna(row['Criativos']) else 0
                    })
                summary_data['temporal'] = temporal_records
            
            # Calcula KPIs - apenas contagens
            kpis = {}
            total_leads = df[leads_cols['lead']].sum()
            total_mqls = df[leads_cols['mql']].sum()
            kpis['total_leads'] = int(total_leads) if not pd.isna(total_leads) else 0
            kpis['total_mqls'] = int(total_mqls) if not pd.isna(total_mqls) else 0
            kpis['investimento_total'] = 0.0  # Não temos coluna de investimento
            kpis['custo_por_mql'] = 0.0
            
            # Análise de criativos usando coluna Term
            creative_analysis = {}
            
            # Encontra coluna Term para usar como criativo
            term_col = None
            for col in df.columns:
                if col.lower() == 'term':
                    term_col = col
                    break
            
            if term_col and leads_cols.get('lead'):
                # Análise detalhada de criativos usando Term
                print(f"Analyzing creatives with column: {term_col}")
                if leads_cols.get('mql'):
                    creative_stats = df.groupby(term_col).agg({
                        leads_cols['lead']: ['sum', 'count'],
                        leads_cols['mql']: 'sum'
                    }).round(2)
                    # Flatten column names
                    creative_stats.columns = ['Total_Leads', 'Qtd_Aparicoes', 'Total_MQLs']
                else:
                    creative_stats = df.groupby(term_col).agg({
                        leads_cols['lead']: ['sum', 'count']
                    }).round(2)
                    # Flatten column names
                    creative_stats.columns = ['Total_Leads', 'Qtd_Aparicoes']
                    creative_stats['Total_MQLs'] = 0
                
                creative_stats = creative_stats.reset_index()
                
                # Renomear a coluna do criativo para 'creative' para o frontend
                creative_stats = creative_stats.rename(columns={term_col: 'creative'})
                
                # Adiciona coluna de investimento vazia
                creative_stats['Total_Investimento'] = 0.0
                
                print(f"Creative stats shape: {creative_stats.shape}")
                print(f"Creative stats columns: {creative_stats.columns.tolist()}")
                print(f"Creative stats sample:")
                print(creative_stats.head())
                
                # Calcula métricas adicionais
                creative_stats['Leads_por_Aparicao'] = (creative_stats['Total_Leads'] / creative_stats['Qtd_Aparicoes']).round(2)
                creative_stats['MQLs_por_Aparicao'] = (creative_stats['Total_MQLs'] / creative_stats['Qtd_Aparicoes']).round(2) if leads_cols.get('mql') else 0
                creative_stats['Taxa_Conversao_Lead_MQL'] = (creative_stats['Total_MQLs'] / creative_stats['Total_Leads'] * 100).round(2) if leads_cols.get('mql') else 0
                
                # Calcula custos por criativo (sempre 0)
                creative_stats['CPL'] = 0.0
                creative_stats['CPMQL'] = 0.0
                
                # Substitui inf e NaN por 0
                creative_stats = creative_stats.replace([np.inf, -np.inf], 0).fillna(0)
                
                # Ordena por total de leads
                creative_stats = creative_stats.sort_values('Total_Leads', ascending=False)
                
                print(f"Sorted creative stats:")
                print(creative_stats.head())
                
                # Top criativos para gráfico
                top_creatives = {}
                for _, row in creative_stats.head(10).iterrows():
                    creative_name = str(row['creative'])
                    top_creatives[creative_name] = int(row['Total_Leads'])
                
                # Criativo com mais leads
                top_lead_creative = creative_stats.iloc[0] if len(creative_stats) > 0 else None
                
                # Criativo com mais MQLs
                top_mql_creative = creative_stats.loc[creative_stats['Total_MQLs'].idxmax()] if len(creative_stats) > 0 else None
                
                print(f"Top lead creative: {top_lead_creative['creative'] if top_lead_creative is not None else 'None'}")
                print(f"Top MQL creative: {top_mql_creative['creative'] if top_mql_creative is not None else 'None'}")
                
                # Estatísticas gerais
                total_leads_all = creative_stats['Total_Leads'].sum()
                total_mqls_all = creative_stats['Total_MQLs'].sum()
                
                creative_analysis = {
                    'top_creatives': top_creatives,
                    'creative_details': clean_dataframe_for_json(creative_stats.head(20)),
                    'top_lead_creative': {
                        'name': str(top_lead_creative['creative']) if top_lead_creative is not None else 'N/A',
                        'leads': int(top_lead_creative['Total_Leads']) if top_lead_creative is not None else 0,
                        'mqls': int(top_lead_creative['Total_MQLs']) if top_lead_creative is not None else 0,
                        'investimento': 0.0,
                        'appearances': int(top_lead_creative['Qtd_Aparicoes']) if top_lead_creative is not None else 0,
                        'leads_per_appearance': float(top_lead_creative['Leads_por_Aparicao']) if top_lead_creative is not None else 0,
                        'mqls_per_appearance': float(top_lead_creative['MQLs_por_Aparicao']) if top_lead_creative is not None else 0,
                        'conversion_rate': float(top_lead_creative['Taxa_Conversao_Lead_MQL']) if top_lead_creative is not None else 0,
                        'cpl': 0.0,
                        'cpmql': 0.0
                    } if top_lead_creative is not None else None,
                    'top_mql_creative': {
                        'name': str(top_mql_creative['creative']) if top_mql_creative is not None else 'N/A',
                        'leads': int(top_mql_creative['Total_Leads']) if top_mql_creative is not None else 0,
                        'mqls': int(top_mql_creative['Total_MQLs']) if top_mql_creative is not None else 0,
                        'investimento': 0.0,
                        'appearances': int(top_mql_creative['Qtd_Aparicoes']) if top_mql_creative is not None else 0,
                        'leads_per_appearance': float(top_mql_creative['Leads_por_Aparicao']) if top_mql_creative is not None else 0,
                        'mqls_per_appearance': float(top_mql_creative['MQLs_por_Aparicao']) if top_mql_creative is not None else 0,
                        'conversion_rate': float(top_mql_creative['Taxa_Conversao_Lead_MQL']) if top_mql_creative is not None else 0,
                        'cpl': 0.0,
                        'cpmql': 0.0
                    } if top_mql_creative is not None else None,
                    'total_creatives': len(creative_stats),
                    'avg_leads_per_creative': float(creative_stats['Total_Leads'].mean()) if len(creative_stats) > 0 else 0,
                    'avg_mqls_per_creative': float(creative_stats['Total_MQLs'].mean()) if len(creative_stats) > 0 else 0
                }
            else:
                print("No Term column found, skipping creative analysis")
                creative_analysis = {}
            
            result = {
                'success': True,
                'data': {
                    'columns': list(df.columns),
                    'total_rows': len(df),
                    'date_column': date_col,
                    'creative_columns': creative_cols,
                    'cost_columns': cost_cols,
                    'leads_columns': leads_cols,
                    'summary': summary_data,
                    'kpis': kpis,
                    'creative_analysis': creative_analysis,
                    'raw_data': clean_dataframe_for_json(df)
                }
            }
            
            return jsonify({
                'success': True,
                'message': f'Planilha do Google Ads {file_name} carregada automaticamente!',
                'data': result['data']
            })
                
        except Exception as e:
            print(f"Erro ao processar arquivo Excel do Google Ads: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500
            
    except Exception as e:
        print(f"Erro no upload automático do Google Ads: {str(e)}")
        return jsonify({'error': f'Erro no upload automático do Google Ads: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    # Implementar download de relatórios se necessário
    pass

@app.route('/favicon.ico')
def favicon():
    return send_file('static/favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/auto-upload-leads')
def auto_upload_leads():
    try:
        file_id = os.getenv('LEADS_FILE_ID', os.getenv('DRIVE_FILE_ID', '1f-dvv2zLKbey__rug-T5gJn-NkNmf7EWcQv3Tb9IvM8'))
        priority_env = os.getenv('LEADS_SHEETS_PRIORITY', 'Leads Be Honest 2')
        priority_names = [name.strip() for name in priority_env.split(',')] if priority_env else []

        credentials = load_drive_credentials()
        if not credentials:
            return jsonify({'error': 'Credenciais do Google Drive não encontradas'}), 500

        df = None
        sheet_info = None
        file_name = None

        try:
            df, sheet_info = load_leads_dataframe_from_google_sheets(file_id, credentials, priority_names)
            file_name = sheet_info.get('primary_sheet', 'Google Sheet')
            print(f"[LEADS] Carregado via Sheets API com {sheet_info.get('combined_rows', len(df))} linhas." )
        except Exception as sheet_error:
            print(f"[LEADS] Falha Sheets API, tentando exportação XLSX: {sheet_error}")

        if df is None:
            file_content, file_name = download_file_from_drive(file_id, credentials)
            if not file_content:
                return jsonify({'error': 'Erro ao baixar arquivo de leads do Google Drive'}), 500

            df, sheet_info = load_leads_dataframe_from_bytes(file_content, file_name, priority_names)

        sheet_info = sheet_info or {}
        sheet_info['file_name'] = file_name
        sheet_info['priority_used'] = priority_names

        analysis = analyze_leads_dataframe(df)
        analysis['sheet_info'] = sheet_info
        analysis['file_name'] = file_name

        return jsonify({
            'success': True,
            'message': f'Planilha de leads {file_name} carregada automaticamente!',
            'sheet_info': sheet_info,
            'data': analysis
        })
    except Exception as e:
        print(f"Erro no upload automático de leads: {str(e)}")
        return jsonify({'error': f'Erro no upload automático de leads: {str(e)}'}), 500

@app.route('/upload-leads', methods=['POST'])
def upload_leads():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

        priority_env = os.getenv('LEADS_SHEETS_PRIORITY', '')
        priority_names = [name.strip() for name in priority_env.split(',')] if priority_env else []

        file_bytes = file.read()
        df, sheet_info = load_leads_dataframe_from_bytes(file_bytes, file.filename, priority_names)
        sheet_info = sheet_info or {}
        sheet_info.setdefault('source', 'manual_upload')
        sheet_info['file_name'] = file.filename
        sheet_info['priority_used'] = priority_names

        analysis = analyze_leads_dataframe(df)
        analysis['sheet_info'] = sheet_info
        analysis['file_name'] = file.filename

        return jsonify({
            'success': True,
            'message': 'Planilha de leads processada com sucesso!',
            'sheet_info': sheet_info,
            'data': analysis
        })
    except Exception as e:
        print(f"Erro ao processar planilha de leads: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro ao processar planilha de leads: {str(e)}'}), 500

@app.route('/api/sults/test', methods=['GET'])
def test_sults_connection():
    """Testa a conexão com a API da SULTS"""
    if not SULTS_AVAILABLE:
        return jsonify({'error': 'Integração SULTS não disponível'}), 503
    
    # Permitir testar URL customizada via query param
    test_url = request.args.get('base_url')
    test_endpoint = request.args.get('endpoint', '/chamados')
    
    try:
        if test_url:
            # Testar URL específica
            token = os.getenv('SULTS_API_TOKEN', 'O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=')
            result = SultsAPIClient.test_connection(test_url, token, test_endpoint)
            return jsonify(result)
        else:
            # Teste padrão
            client = SultsAPIClient()
            # Tentar buscar unidades como teste
            unidades = client.get_unidades()
            return jsonify({
                'success': True,
                'message': 'Conexão com SULTS estabelecida com sucesso',
                'unidades_count': len(unidades) if isinstance(unidades, list) else 0,
                'base_url': client.BASE_URL
            })
    except Exception as e:
        import traceback
        error_details = str(e)
        return jsonify({
            'success': False,
            'error': f'Erro ao conectar com SULTS: {error_details}',
            'base_url_used': test_url or os.getenv('SULTS_API_BASE_URL', 'https://app.sults.com.br/api'),
            'suggestion': 'Tente diferentes URLs base usando: ?base_url=https://api.sults.com.br'
        }), 500

@app.route('/api/sults/diagnose', methods=['GET'])
def diagnose_sults_auth():
    """Diagnóstico detalhado da autenticação SULTS"""
    if not SULTS_AVAILABLE:
        return jsonify({'error': 'Integração SULTS não disponível'}), 503
    
    token = os.getenv('SULTS_API_TOKEN', 'O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=')
    base_url = "https://developer.sults.com.br/api/v1"
    endpoint = "/leads"
    
    import base64
    try:
        decoded_token = base64.b64decode(token).decode('utf-8')
    except:
        decoded_token = "Não foi possível decodificar"
    
    results = []
    
    # Testar diferentes formatos
    formats_to_test = [
        {'name': 'Bearer Token', 'header': {'Authorization': f'Bearer {token}'}},
        {'name': 'Token', 'header': {'Authorization': f'Token {token}'}},
        {'name': 'API Key', 'header': {'X-API-Key': token}},
        {'name': 'Auth Token Header', 'header': {'X-Auth-Token': token}},
        {'name': 'Token na URL', 'url_param': f'?token={token}'},
    ]
    
    for fmt in formats_to_test:
        try:
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            }
            headers.update(fmt.get('header', {}))
            
            url = f"{base_url}{endpoint}{fmt.get('url_param', '')}"
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
            
            content_type = response.headers.get('Content-Type', '')
            is_json = 'application/json' in content_type
            is_html = 'text/html' in content_type
            
            results.append({
                'format': fmt['name'],
                'status_code': response.status_code,
                'content_type': content_type,
                'is_json': is_json,
                'is_html': is_html,
                'url': url,
                'success': is_json and response.status_code == 200
            })
        except Exception as e:
            results.append({
                'format': fmt['name'],
                'error': str(e),
                'success': False
            })
    
    return jsonify({
        'token_info': {
            'original': token[:30] + '...',
            'decoded': decoded_token,
            'format': 'Base64' if '=' in token else 'Plain'
        },
        'base_url': base_url,
        'endpoint': endpoint,
        'test_results': results,
        'recommendation': 'Verifique a documentação em https://developers.sults.com.br/ para o formato correto de autenticação'
    })

@app.route('/api/sults/test-all', methods=['GET'])
def test_all_sults_urls():
    """Testa várias URLs e endpoints da SULTS automaticamente"""
    if not SULTS_AVAILABLE:
        return jsonify({'error': 'Integração SULTS não disponível'}), 503
    
    token = os.getenv('SULTS_API_TOKEN', 'O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=')
    
    base_urls = [
        "https://developer.sults.com.br/api/v1",  # URL correta conforme documentação
        "https://api.sults.com.br",
        "https://app.sults.com.br/api",
        "https://sults.com.br/api",
        "https://api.sults.com.br/v1",
        "https://app.sults.com.br",
        "https://sults.com.br",
        "https://api.sults.com.br/api",
    ]
    
    endpoints = [
        "/leads",  # Endpoint principal conforme documentação
        "/chamados",
        "/unidades",
        "/projetos",
        "/api/chamados",
        "/v1/chamados",
        "/api/leads",
        "/tickets",
    ]
    
    results = []
    
    for base_url in base_urls:
        for endpoint in endpoints:
            result = SultsAPIClient.test_connection(base_url, token, endpoint)
            results.append({
                'url': result['url'],
                'status_code': result['status_code'],
                'success': result['success'],
                'message': result['message']
            })
            
            # Se encontrar uma URL que funciona, retornar imediatamente
            if result['success']:
                return jsonify({
                    'success': True,
                    'working_url': result['url'],
                    'status_code': result['status_code'],
                    'message': f'URL funcionando encontrada: {result["url"]}',
                    'all_results': results
                })
    
    # Se nenhuma funcionou, retornar todas as tentativas
    return jsonify({
        'success': False,
        'message': 'Nenhuma URL funcionou. Verifique a documentação: https://developers.sults.com.br/',
        'results': results,
        'suggestion': 'Verifique a documentação oficial ou entre em contato com o suporte da SULTS para obter a URL base correta'
    })

@app.route('/api/sults/chamados', methods=['GET'])
def get_sults_chamados():
    """Busca chamados da SULTS"""
    if not SULTS_AVAILABLE:
        return jsonify({'error': 'Integração SULTS não disponível'}), 503
    
    try:
        client = SultsAPIClient()
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        status_data = client.get_leads_status(date_from=date_from, date_to=date_to)
        
        return jsonify({
            'success': True,
            'data': status_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar chamados: {str(e)}'
        }), 500

@app.route('/api/sults/verificar-leads', methods=['GET'])
def verificar_sults_leads():
    """Endpoint simplificado para verificar leads abertos e perdidos da SULTS"""
    if not SULTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Integração SULTS não disponível'
        }), 503
    
    try:
        token = os.getenv('SULTS_API_TOKEN', '')
        token_status = '✅ Configurado' if token else '❌ Não configurado'
        
        # Testar diferentes URLs base e endpoints
        base_urls = [
            "https://behonestbrasil.sults.com.br/api/v1",
            "https://behonestbrasil.sults.com.br/api",
            "https://behonestbrasil.sults.com.br/analytics/api",
            "https://api.sults.com.br/v1",
            "https://app.sults.com.br/api/v1",
            "https://developer.sults.com.br/api/v1"
        ]
        
        endpoints = ["/chamados", "/leads", "/api/chamados", "/api/leads"]
        auth_formats = ['token', 'bearer']
        
        # Limitar tentativas para evitar carregamento infinito
        # Testar apenas as combinações mais prováveis
        tested_combinations = []
        
        # Usar endpoints que sabemos que funcionam: projetos e empresas
        try:
            client = SultsAPIClient(token=token, base_url="https://api.sults.com.br/api/v1", auth_format="token")
            
            # Primeiro tentar buscar negócios de franqueados via endpoint de expansão
            projetos = []
            try:
                negocios = client.get_negocios_franqueados()
                if negocios:
                    projetos = negocios
                    print(f"✅ Encontrados {len(negocios)} negócios de franqueados via expansão")
            except Exception as e:
                print(f"⚠️ Erro ao buscar negócios via expansão: {e}")
            
            # Se não encontrou via expansão, buscar projetos e filtrar
            if not projetos:
                projetos = client.get_projetos()
                
                # Filtrar apenas projetos de franqueados
                # Excluir explicitamente lojas e manter apenas franqueados
                projetos_franqueados = []
                for projeto in projetos:
                    etapa = projeto.get('etapa', {})
                    funil = etapa.get('funil', {}) if isinstance(etapa, dict) else {}
                    funil_nome = funil.get('nome', '').lower() if isinstance(funil, dict) else ''
                    funil_id = funil.get('id') if isinstance(funil, dict) else None
                    projeto_nome = projeto.get('nome', '').lower()
                    
                    # Excluir lojas explicitamente
                    if 'loja' in funil_nome or 'loja' in projeto_nome:
                        continue
                    
                    # Incluir apenas projetos do funil "Franqueados" (ID 1) ou que tenham "franqueado" no nome
                    # Funil ID 1 geralmente é "Franqueados"
                    if funil_id == 1 or ('franqueado' in funil_nome and 'loja' not in funil_nome) or ('franqueado' in projeto_nome and 'loja' not in projeto_nome):
                        projetos_franqueados.append(projeto)
                
                projetos = projetos_franqueados
                print(f"✅ Encontrados {len(projetos)} projetos de franqueados após filtro (lojas excluídas)")
            
            # Filtro final para garantir que não há lojas
            projetos_filtrados_final = []
            for projeto in projetos:
                etapa = projeto.get('etapa', {})
                funil = etapa.get('funil', {}) if isinstance(etapa, dict) else {}
                funil_nome = funil.get('nome', '').lower() if isinstance(funil, dict) else ''
                funil_id = funil.get('id') if isinstance(funil, dict) else None
                projeto_nome = projeto.get('nome', '').lower()
                projeto_titulo = projeto.get('titulo', '').lower()
                
                # Excluir qualquer coisa relacionada a lojas
                if any(palavra in funil_nome or palavra in projeto_nome or palavra in projeto_titulo 
                       for palavra in ['loja', 'lojas', 'extrabom']):
                    continue
                
                # Incluir apenas se for franqueado (funil ID 1 ou nome contém franqueado)
                if funil_id == 1 or 'franqueado' in funil_nome or 'franqueado' in projeto_nome or 'franqueado' in projeto_titulo:
                    projetos_filtrados_final.append(projeto)
            
            projetos = projetos_filtrados_final
            print(f"✅ Após filtro final: {len(projetos)} negócios de franqueados (sem lojas)")
            
            # Contar projetos com etiquetas antes do processamento
            projetos_com_etiquetas = 0
            projetos_com_mql = 0
            for p in projetos:
                etiquetas = p.get('etiqueta', [])
                if etiquetas and len(etiquetas) > 0:
                    projetos_com_etiquetas += 1
                    for etq in etiquetas:
                        if isinstance(etq, dict):
                            nome_etq = etq.get('nome', '').upper().strip()
                            if 'MQL' in nome_etq:
                                projetos_com_mql += 1
                                break
            print(f"🔍 Projetos com etiquetas: {projetos_com_etiquetas}")
            print(f"🔍 Projetos com etiqueta MQL (antes do filtro de status): {projetos_com_mql}")
            
            # Transformar projetos em leads para exibição
            leads_abertos = []
            leads_perdidos = []
            leads_ganhos = []
            leads_mql = []  # Leads com etiqueta MQL
            leads_por_fase = {}
            leads_por_categoria = {}
            leads_por_responsavel = {}
            leads_por_unidade = {}
            total_mql = 0
            
            for projeto in projetos:
                # Verificação final: pular se for loja
                etapa = projeto.get('etapa', {})
                funil = etapa.get('funil', {}) if isinstance(etapa, dict) else {}
                funil_nome = funil.get('nome', '').lower() if isinstance(funil, dict) else ''
                projeto_nome = projeto.get('nome', '').lower()
                projeto_titulo = projeto.get('titulo', '').lower()
                
                # Excluir qualquer coisa relacionada a lojas
                if any(palavra in funil_nome or palavra in projeto_nome or palavra in projeto_titulo 
                       for palavra in ['loja', 'lojas', 'extrabom']):
                    continue
                
                status = 'aberto'
                if projeto.get('concluido'):
                    status = 'ganho'
                elif projeto.get('pausado'):
                    status = 'perdido'
                
                # Extrair etapa/fase do projeto
                etapa_nome = etapa.get('nome', 'Sem etapa') if isinstance(etapa, dict) else 'Sem etapa'
                etapa_id = etapa.get('id') if isinstance(etapa, dict) else None
                
                # Extrair categoria
                categoria = projeto.get('categoria', {})
                categoria_nome = categoria.get('nome', 'Sem categoria') if isinstance(categoria, dict) else 'Sem categoria'
                
                # Fase: usar etapa se disponível, senão usar categoria + status
                # Garantir que não inclui lojas no nome da fase
                if etapa_nome and etapa_nome != 'Sem etapa':
                    fase = etapa_nome
                    if funil_nome and 'loja' not in funil_nome.lower():
                        fase = f"{funil_nome} - {etapa_nome}"
                    # Se funil contém loja, já foi filtrado acima
                else:
                    fase = f"{categoria_nome} - {status.title()}"
                
                # Ordem customizada das fases
                ordem_fases = {
                    'lead': 1,
                    'mql': 2,
                    'conexao': 3,
                    'conexão': 3,
                    'pre-call agendada': 4,
                    'pre call agendada': 4,
                    'pre-call realizada': 5,
                    'pre call realizada': 5,
                    'apresentação modelo agendada': 6,
                    'apresentacao modelo agendada': 6,
                    'apresentação modelo realizada': 7,
                    'apresentacao modelo realizada': 7,
                    'apresentação financeira agendada': 8,
                    'apresentacao financeira agendada': 8,
                    'reunião financeira realizada': 9,
                    'reuniao financeira realizada': 9,
                    'reunião fundador agendada': 10,
                    'reuniao fundador agendada': 10,
                    'aguardando decisão': 11,
                    'aguardando decisao': 11,
                    'contrato franquia': 12
                }
                
                # Determinar ordem da fase (case insensitive) - otimizado
                fase_lower = fase.lower().strip()
                fase_ordem = etapa_id if etapa_id is not None else 9999
                
                # Procurar correspondência apenas se não tiver etapa_id
                if fase_ordem == 9999:
                    for key, ordem in ordem_fases.items():
                        if key in fase_lower:
                            fase_ordem = ordem
                            break
                
                # Contar por responsável
                responsavel = projeto.get('responsavel', {})
                responsavel_nome = responsavel.get('nome', 'Sem responsável') if isinstance(responsavel, dict) else 'Sem responsável'
                
                # Contar por unidade (usar contatoEmpresa se disponível)
                contato_empresa = projeto.get('contatoEmpresa', {})
                unidade_nome = 'Sem unidade'
                if contato_empresa and isinstance(contato_empresa, dict):
                    unidade_nome = contato_empresa.get('nomeFantasia', 'Sem unidade')
                
                # Verificar se tem etiqueta MQL
                etiquetas = projeto.get('etiqueta', [])
                tem_mql = False
                etiquetas_nomes = []
                
                if etiquetas and isinstance(etiquetas, list):
                    for etiqueta in etiquetas:
                        if isinstance(etiqueta, dict):
                            etiqueta_nome = etiqueta.get('nome', '')
                            etiquetas_nomes.append(etiqueta_nome)
                            # Verificar se a etiqueta contém MQL (case insensitive)
                            # Aceitar variações: MQL, mql, Mql, etc.
                            etiqueta_upper = etiqueta_nome.upper().strip()
                            if 'MQL' in etiqueta_upper:
                                tem_mql = True
                                break  # Otimização: parar ao encontrar MQL
                
                # Extrair informações de contato (para negócios de franqueados)
                contato_pessoa = projeto.get('contatoPessoa', [])
                contato_empresa = projeto.get('contatoEmpresa', {})
                
                # Pegar primeiro contato se houver
                email = ''
                telefone = ''
                if contato_pessoa and isinstance(contato_pessoa, list) and len(contato_pessoa) > 0:
                    primeiro_contato = contato_pessoa[0]
                    email = primeiro_contato.get('email', '') if isinstance(primeiro_contato, dict) else ''
                    telefone = primeiro_contato.get('phone', '') if isinstance(primeiro_contato, dict) else ''
                
                # Se não tiver contato pessoa, tentar contato empresa
                if not email and contato_empresa and isinstance(contato_empresa, dict):
                    email = contato_empresa.get('email', '')
                    telefone = contato_empresa.get('phone', '')
                
                # Determinar status baseado na situação do negócio
                situacao = projeto.get('situacao', {})
                situacao_nome = situacao.get('nome', '').upper() if isinstance(situacao, dict) else ''
                situacao_id = situacao.get('id') if isinstance(situacao, dict) else None
                
                # Mapear situação para status
                if situacao_id == 2 or situacao_nome == 'GANHO':
                    status = 'ganho'
                elif situacao_id == 3 or situacao_nome == 'PERDA':
                    status = 'perdido'
                elif situacao_id == 4 or situacao_nome == 'ADIADO':
                    status = 'aberto'
                elif situacao_id == 1 or situacao_nome == 'ANDAMENTO':
                    status = 'aberto'
                # Se não tiver situação definida, usar lógica anterior
                elif not situacao_id:
                    if projeto.get('concluido'):
                        status = 'ganho'
                    elif projeto.get('pausado'):
                        status = 'perdido'
                    else:
                        status = 'aberto'
                
                lead_data = {
                    'id': projeto.get('id'),
                    'nome': projeto.get('titulo') or projeto.get('nome', 'Sem nome'),
                    'email': email,
                    'telefone': telefone,
                    'responsavel': responsavel_nome,
                    'unidade': unidade_nome or contato_empresa.get('nomeFantasia', '') if isinstance(contato_empresa, dict) else '',
                    'categoria': categoria_nome,
                    'fase': fase,
                    'etapa': etapa_nome,
                    'funil': funil_nome,
                    'status': status,
                    'situacao': situacao_nome,
                    'ativo': True,  # Negócios ativos são os que não estão concluídos/perdidos
                    'data_criacao': projeto.get('dtCadastro', '') or projeto.get('dtCriacao', ''),
                    'data_inicio': projeto.get('dtInicio', ''),
                    'data_fim': projeto.get('dtConclusao', '') or projeto.get('dtFim', ''),
                    'cidade': projeto.get('cidade', ''),
                    'uf': projeto.get('uf', ''),
                    'valor': projeto.get('valor', 0.0),
                    'origem': projeto.get('origem', {}).get('nome', 'SULTS') if isinstance(projeto.get('origem'), dict) else 'SULTS',
                    'temperatura': projeto.get('temperatura', {}).get('nome', '') if isinstance(projeto.get('temperatura'), dict) else '',
                    'etiquetas': etiquetas_nomes,
                    'tem_mql': tem_mql,
                    'origem_tipo': 'SULTS - Franqueados'
                }
                
                # Filtrar apenas leads em aberto para estatísticas, exibição e MQLs
                if status != 'aberto':
                    continue
                
                # Contadores considerando apenas leads em aberto
                leads_por_categoria[categoria_nome] = leads_por_categoria.get(categoria_nome, 0) + 1
                
                # Armazenar fase com informação de ordenação
                if fase not in leads_por_fase:
                    leads_por_fase[fase] = {'count': 0, 'ordem': fase_ordem}
                leads_por_fase[fase]['count'] += 1
                
                leads_por_responsavel[responsavel_nome] = leads_por_responsavel.get(responsavel_nome, 0) + 1
                leads_por_unidade[unidade_nome] = leads_por_unidade.get(unidade_nome, 0) + 1
                
                leads_abertos.append(lead_data)
                
                # Adicionar aos MQLs apenas se estiver em aberto E tiver etiqueta MQL
                if tem_mql:
                    leads_mql.append(lead_data)
                    total_mql += 1
                    print(f"📊 MQL em andamento encontrado: ID {projeto.get('id')}, Etiquetas: {etiquetas_nomes}")
            
            total_leads = len(leads_abertos)
            
            # Log final para debug
            print(f"\n📊 RESUMO FINAL:")
            print(f"   Total de projetos processados: {len(projetos)}")
            print(f"   Leads em aberto: {len(leads_abertos)}")
            print(f"   MQLs em andamento (apenas status 'aberto'): {total_mql}")
            
            resultado = {
                'token_status': token_status,
                'token_preview': token[:20] + '...' if len(token) > 20 else token,
                'base_url': 'https://api.sults.com.br/api/v1',
                'endpoint_used': '/projeto',
                'auth_format': 'token',
                'timestamp': datetime.now().isoformat(),
                'leads': {
                    'abertos': {
                        'total': len(leads_abertos),
                        'dados': leads_abertos[:50]
                    },
                    'perdidos': {
                        'total': len(leads_perdidos),
                        'dados': leads_perdidos[:50]
                    },
                    'ganhos': {
                        'total': len(leads_ganhos),
                        'dados': leads_ganhos[:50]
                    },
                    'mql': {
                        'total': total_mql,
                        'dados': leads_mql[:50]
                    }
                },
                'resumo': {
                    'total_leads': total_leads,
                    'total_projetos': len(leads_abertos),
                    'leads_abertos': len(leads_abertos),
                    'leads_perdidos': len(leads_perdidos),
                    'leads_ganhos': len(leads_ganhos),
                    'leads_mql': total_mql
                },
                'estatisticas': {
                    'leads_por_fase': {k: v['count'] if isinstance(v, dict) else v for k, v in leads_por_fase.items()},
                    'leads_por_fase_ordem': {k: v['ordem'] if isinstance(v, dict) else 9999 for k, v in leads_por_fase.items()},
                    'leads_por_categoria': leads_por_categoria,
                    'leads_por_responsavel': leads_por_responsavel,
                    'leads_por_unidade': leads_por_unidade
                }
            }
            
            return jsonify({
                'success': True,
                'message': f'✅ Dados carregados da SULTS! ({total_leads} projetos encontrados)',
                'data': resultado
            })
        except Exception as main_error:
            print(f"Erro ao buscar dados principais: {main_error}")
            import traceback
            traceback.print_exc()
            
            # Se falhar, tentar combinações antigas
            priority_combinations = [
                ("https://api.sults.com.br/api/v1", "/negocio", "token"),
                ("https://api.sults.com.br/api/v1", "/negocios", "token"),
                ("https://api.sults.com.br/api/v1", "/chamado", "token"),
                ("https://api.sults.com.br/api/v1", "/chamados", "token"),
                ("https://api.sults.com.br/api/v1", "/lead", "token"),
                ("https://api.sults.com.br/api/v1", "/leads", "token"),
            ]
            
            for base_url, endpoint, auth_format in priority_combinations:
                try:
                    client = SultsAPIClient(token=token, base_url=base_url, auth_format=auth_format)
                    leads_data = client.get_leads_by_status()
                    
                    # Se chegou aqui, funcionou!
                    resultado = {
                        'token_status': token_status,
                        'token_preview': token[:20] + '...' if len(token) > 20 else token,
                        'base_url': base_url,
                        'endpoint_used': endpoint,
                        'auth_format': auth_format,
                        'timestamp': datetime.now().isoformat(),
                        'leads': {
                            'abertos': {
                                'total': len(leads_data.get('abertos', {}).get('leads', [])) if isinstance(leads_data.get('abertos'), dict) else (len(leads_data.get('abertos', [])) if isinstance(leads_data.get('abertos'), list) else 0),
                                'dados': (leads_data.get('abertos', {}).get('leads', [])[:10] if isinstance(leads_data.get('abertos'), dict) else leads_data.get('abertos', [])[:10]) if isinstance(leads_data.get('abertos'), (dict, list)) else []
                            },
                            'perdidos': {
                                'total': len(leads_data.get('perdidos', {}).get('leads', [])) if isinstance(leads_data.get('perdidos'), dict) else (len(leads_data.get('perdidos', [])) if isinstance(leads_data.get('perdidos'), list) else 0),
                                'dados': (leads_data.get('perdidos', {}).get('leads', [])[:10] if isinstance(leads_data.get('perdidos'), dict) else leads_data.get('perdidos', [])[:10]) if isinstance(leads_data.get('perdidos'), (dict, list)) else []
                            },
                            'ganhos': {
                                'total': len(leads_data.get('ganhos', {}).get('leads', [])) if isinstance(leads_data.get('ganhos'), dict) else (len(leads_data.get('ganhos', [])) if isinstance(leads_data.get('ganhos'), list) else 0),
                                'dados': (leads_data.get('ganhos', {}).get('leads', [])[:10] if isinstance(leads_data.get('ganhos'), dict) else leads_data.get('ganhos', [])[:10]) if isinstance(leads_data.get('ganhos'), (dict, list)) else []
                            }
                        },
                        'resumo': {
                            'total_leads': leads_data.get('total_geral', 0)
                        }
                    }
                    
                    return jsonify({
                        'success': True,
                        'message': f'✅ Conexão com SULTS funcionando! (URL: {base_url}{endpoint})',
                        'data': resultado
                    })
                except Exception as test_error:
                    error_msg = str(test_error)[:200]  # Limitar tamanho do erro
                    tested_combinations.append({
                        'url': f"{base_url}{endpoint}",
                        'auth_format': auth_format,
                        'error': error_msg
                    })
                    print(f"❌ Falhou: {base_url}{endpoint} ({auth_format}) - {error_msg}")
                    continue
        
        # Se nenhuma combinação funcionou, retornar erro detalhado
        return jsonify({
            'success': False,
            'token_status': token_status,
            'token_preview': token[:20] + '...' if len(token) > 20 else token,
            'error': 'Nenhuma combinação de URL/endpoint funcionou',
            'message': 'A API SULTS pode não estar acessível via REST tradicional ou requer autenticação diferente',
            'sugestao': 'Verifique a documentação em https://developers.sults.com.br/ ou entre em contato com o suporte da SULTS',
            'tested_combinations': tested_combinations,
            'total_tested': len(tested_combinations),
            'next_steps': [
                '1. Verifique na documentação da SULTS a URL base correta',
                '2. Confirme o formato de autenticação (Bearer, Token, API Key, etc.)',
                '3. Verifique se o token está ativo e tem as permissões necessárias',
                '4. Tente acessar a API manualmente via curl ou Postman para testar'
            ]
        }), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Erro geral: {str(e)}'
        }), 500

@app.route('/api/sults/leads-status', methods=['GET'])
def get_sults_leads_status():
    """Busca leads da SULTS organizados por status (abertos, perdidos, ganhos)"""
    if not SULTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Integração SULTS não disponível',
            'message': 'Módulo sults_api não encontrado'
        }), 503
    
    # URL padrão agora é a correta conforme documentação: https://developer.sults.com.br/api/v1
    try:
        client = SultsAPIClient()
        status_filter = request.args.get('status')  # 'aberto', 'perdido', 'ganho' ou None para todos
        
        leads_data = client.get_leads_by_status(status_filter=status_filter)
        
        return jsonify({
            'success': True,
            'data': leads_data
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        
        # Se for erro 404, dar instruções mais claras
        if '404' in error_msg:
            return jsonify({
                'success': False,
                'error': f'Erro ao buscar leads da SULTS: {error_msg}',
                'message': 'A URL base ou os endpoints estão incorretos',
                'instructions': {
                    'step1': 'Execute: curl http://localhost:5003/api/sults/test-all',
                    'step2': 'Ou consulte a documentação: https://developers.sults.com.br/',
                    'step3': 'Configure a URL correta no arquivo .env',
                    'step4': 'Entre em contato com o suporte da SULTS se necessário'
                }
            }), 500
        
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar leads da SULTS: {error_msg}'
        }), 500

@app.route('/api/sults/sync-lead', methods=['POST'])
def sync_lead_to_sults():
    """Sincroniza um lead com a SULTS"""
    if not SULTS_AVAILABLE:
        return jsonify({'error': 'Integração SULTS não disponível'}), 503
    
    try:
        lead_data = request.get_json()
        if not lead_data:
            return jsonify({'error': 'Dados do lead não fornecidos'}), 400
        
        client = SultsAPIClient()
        result = client.sync_lead_with_sults(lead_data)
        
        return jsonify({
            'success': True,
            'message': 'Lead sincronizado com SULTS',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao sincronizar lead: {str(e)}'
        }), 500

if __name__ == '__main__':
    print(f"Templates path: {app.template_folder}")
    app.run(debug=True, host='0.0.0.0', port=5000)
