from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import io
import json
import requests
import re
import unicodedata
from collections import defaultdict
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import hashlib
import gc
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

# Cache simples em memória
_DATA_CACHE = {}
_CACHE_TTL = 300  # 5 minutos
_CACHE_MAX_SIZE = 10  # Máximo de 10 entradas no cache

def _get_cache_key(data):
    """Gera chave de cache baseada nos dados"""
    if isinstance(data, bytes):
        return hashlib.md5(data).hexdigest()
    elif isinstance(data, str):
        return hashlib.md5(data.encode()).hexdigest()
    return None

def _clear_old_cache():
    """Remove entradas antigas do cache"""
    global _DATA_CACHE
    now = datetime.now()
    keys_to_remove = []
    for key, value in _DATA_CACHE.items():
        if (now - value['timestamp']).total_seconds() > _CACHE_TTL:
            keys_to_remove.append(key)
    for key in keys_to_remove:
        del _DATA_CACHE[key]
    
    # Se ainda estiver cheio, remove os mais antigos
    if len(_DATA_CACHE) > _CACHE_MAX_SIZE:
        sorted_items = sorted(_DATA_CACHE.items(), key=lambda x: x[1]['timestamp'])
        for key, _ in sorted_items[:len(_DATA_CACHE) - _CACHE_MAX_SIZE]:
            del _DATA_CACHE[key]
    
    # Força limpeza de memória
    gc.collect()

def _get_from_cache(key):
    """Recupera dados do cache"""
    _clear_old_cache()
    if key in _DATA_CACHE:
        entry = _DATA_CACHE[key]
        if (datetime.now() - entry['timestamp']).total_seconds() < _CACHE_TTL:
            return entry['data']
        else:
            del _DATA_CACHE[key]
    return None

def _save_to_cache(key, data):
    """Salva dados no cache"""
    _clear_old_cache()
    _DATA_CACHE[key] = {
        'data': data,
        'timestamp': datetime.now()
    }

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """Endpoint para limpar cache manualmente"""
    global _DATA_CACHE
    _DATA_CACHE.clear()
    gc.collect()
    return jsonify({'success': True, 'message': 'Cache limpo com sucesso'})


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


def normalize_sheet_title(title):
    if not title:
        return ''
    return ' '.join(str(title).strip().lower().split())


def load_google_ads_sheet(spreadsheet_id, credentials, preferred_sheets=None):
    """Carrega a planilha do Google Ads diretamente do Google Sheets (suporta múltiplas abas)."""
    if preferred_sheets is None:
        preferred_sheets = ['Controle Google ADS', 'Controle Google ADS 2']
    
    preferred_sheets = [sheet.strip() for sheet in (preferred_sheets or []) if sheet and sheet.strip()]
    sheets_service = build('sheets', 'v4', credentials=credentials)
    metadata = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    
    sheet_titles = [sheet.get('properties', {}).get('title', '') for sheet in metadata.get('sheets', [])]
    ordered_titles = []
    matched_titles = []
    
    for preferred in preferred_sheets:
        preferred_match = next(
            (title for title in sheet_titles if normalize_sheet_title(title) == normalize_sheet_title(preferred)),
            None
        )
        if preferred_match and preferred_match not in ordered_titles:
            ordered_titles.append(preferred_match)
            matched_titles.append(preferred_match)
    
    if not ordered_titles:
        raise ValueError(f"Nenhuma das abas solicitadas foi encontrada: {preferred_sheets}")
    
    frames = {}
    sheet_stats = []
    
    for title in ordered_titles:
        if not title:
            continue
        
        values_response = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=title
        ).execute()
        
        values = values_response.get('values', [])
        if not values or len(values) <= 1:
            print(f"[GOOGLE ADS][SheetsAPI] Aba '{title}' sem dados ou apenas cabeçalho.")
            continue
        
        header = _make_unique_headers(values[0])
        data_rows = values[1:]
        max_columns = max(len(row) for row in values)
        while len(header) < max_columns:
            header.append(f"Coluna_{len(header) + 1}")
        
        normalized_rows = []
        for row in data_rows:
            if len(row) < len(header):
                row = row + [''] * (len(header) - len(row))
            normalized_rows.append(row)
        
        df_sheet = pd.DataFrame(normalized_rows, columns=header)
        df_sheet.replace('', pd.NA, inplace=True)
        cleaned_df = df_sheet.dropna(how='all').dropna(axis=1, how='all').reset_index(drop=True)
        
        if cleaned_df.empty:
            print(f"[GOOGLE ADS][SheetsAPI] Aba '{title}' sem linhas após limpeza.")
            continue
        
        sheet_stats.append({'name': title, 'rows': int(cleaned_df.shape[0]), 'columns': int(cleaned_df.shape[1])})
        frames[title] = cleaned_df
        print(f"[GOOGLE ADS][SheetsAPI] Aba '{title}' carregada -> linhas: {cleaned_df.shape[0]}, colunas: {cleaned_df.shape[1]}")
    
    if not frames:
        raise ValueError("Nenhuma aba válida encontrada na planilha do Google Ads via Sheets API.")
    
    return frames, {
        'primary_sheets': matched_titles,
        'sheet_stats': sheet_stats,
        'sheet_count': len(frames),
        'loaded_sheets': list(frames.keys())
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
        # Usa openpyxl que é mais rápido para arquivos .xlsx
        try:
            sheets_dict = pd.read_excel(file_like, sheet_name=None, dtype=str, engine='openpyxl')
        except:
            # Fallback para engine padrão
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
    """Carrega credenciais do Google Drive - suporta arquivo ou variável de ambiente"""
    try:
        # Método 1: Tentar carregar de variável de ambiente (para Vercel/cloud)
        credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if credentials_json:
            try:
                print(f"[DEBUG] GOOGLE_CREDENTIALS_JSON encontrada (tamanho: {len(credentials_json)} chars)")
                # Limpa o JSON (remove espaços extras no início/fim)
                credentials_json = credentials_json.strip()
                
                # Parse do JSON da variável de ambiente
                import json as json_lib
                credentials_info = json_lib.loads(credentials_json)
                
                # Valida campos obrigatórios
                required_fields = ['type', 'project_id', 'private_key', 'client_email']
                missing_fields = [field for field in required_fields if field not in credentials_info]
                if missing_fields:
                    print(f"[ERROR] Campos obrigatórios faltando: {missing_fields}")
                    raise ValueError(f"Campos obrigatórios faltando: {missing_fields}")
                
                print(f"[DEBUG] JSON parseado com sucesso. Type: {credentials_info.get('type')}, Email: {credentials_info.get('client_email')}")
                
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info,
                    scopes=[
                        'https://www.googleapis.com/auth/drive.readonly',
                        'https://www.googleapis.com/auth/spreadsheets.readonly'
                    ]
                )
                print("[SUCCESS] Credenciais carregadas de variável de ambiente GOOGLE_CREDENTIALS_JSON")
                return credentials
            except json_lib.JSONDecodeError as json_error:
                print(f"[ERROR] Erro ao fazer parse do JSON: {json_error}")
                print(f"[DEBUG] Primeiros 200 chars do JSON: {credentials_json[:200]}")
                import traceback
                traceback.print_exc()
            except Exception as env_error:
                print(f"[ERROR] Erro ao carregar credenciais da variável de ambiente: {env_error}")
                import traceback
                traceback.print_exc()
                # Continua para tentar método 2
        else:
            print("[DEBUG] GOOGLE_CREDENTIALS_JSON não encontrada, tentando arquivo...")
        
        # Método 2: Tentar carregar de arquivo (para desenvolvimento local)
        credentials_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        # Se não estiver definido, tentar caminho relativo
        if not credentials_file:
            credentials_file = 'sixth-now-475017-k8-785034518ab7.json'
        
        # Verifica se o arquivo existe
        if os.path.exists(credentials_file):
            print(f"[DEBUG] Tentando carregar credenciais de arquivo: {credentials_file}")
            credentials = service_account.Credentials.from_service_account_file(
                credentials_file,
                scopes=[
                    'https://www.googleapis.com/auth/drive.readonly',
                    'https://www.googleapis.com/auth/spreadsheets.readonly'
                ]
            )
            print(f"[SUCCESS] Credenciais carregadas de arquivo: {credentials_file}")
            return credentials
        else:
            print(f"[ERROR] Arquivo de credenciais não encontrado: {credentials_file}")
            print(f"[DEBUG] Diretório atual: {os.getcwd()}")
            # Não lista diretório no Vercel para evitar erro
            if os.path.exists('.'):
                try:
                    files = [f for f in os.listdir('.') if f.endswith('.json')]
                    print(f"[DEBUG] Arquivos JSON encontrados: {files}")
                except Exception as list_error:
                    print(f"[DEBUG] Erro ao listar arquivos: {list_error}")
            return None
            
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

def clean_dataframe_for_json(df, max_rows=2000):
    """Limpa DataFrame removendo valores NaN para serialização JSON - OTIMIZADO"""
    # Limita quantidade de linhas para não travar
    if len(df) > max_rows:
        df = df.head(max_rows)
        print(f"Limitando dados JSON a {max_rows} linhas para melhor performance")
    
    # Otimização: converte direto para dict sem iterrows (muito mais rápido)
    try:
        # Substitui NaN por None de forma vetorizada
        df_cleaned = df.copy()
        
        # Identifica colunas numéricas
        numeric_keywords = ['CPL', 'CPMQL', 'CPC', 'CPM', 'CTR', 'LEAD', 'MQL', 'INVESTIMENTO', 'CLIQUES', 'IMPRESSÕES']
        numeric_cols = [col for col in df_cleaned.columns if any(kw in str(col).upper() for kw in numeric_keywords)]
        
        # Preenche NaN em colunas numéricas com 0
        for col in numeric_cols:
            if col in df_cleaned.columns:
                df_cleaned[col] = df_cleaned[col].fillna(0.0)
        
        # Preenche outras colunas com None
        df_cleaned = df_cleaned.where(pd.notnull(df_cleaned), None)
        
        # Converte tipos
        for col in df_cleaned.columns:
            if df_cleaned[col].dtype in ['int64', 'int32']:
                df_cleaned[col] = df_cleaned[col].astype('Int64')
            elif df_cleaned[col].dtype in ['float64', 'float32']:
                df_cleaned[col] = df_cleaned[col].astype('float64')
            elif df_cleaned[col].dtype == 'datetime64[ns]':
                df_cleaned[col] = df_cleaned[col].dt.strftime('%Y-%m-%d')
        
        # Converte para dict - muito mais rápido que iterrows
        result = df_cleaned.to_dict('records')
        return result
    except Exception as e:
        print(f"Erro na conversão otimizada, usando método fallback: {e}")
        # Fallback para método antigo se houver erro (limitado)
        cleaned_data = []
        for _, row in df.head(500).iterrows():  # Limita a 500 no fallback
            clean_row = {}
            for col, value in row.items():
                if pd.isna(value):
                    if any(keyword in col.upper() for keyword in numeric_keywords):
                        clean_row[col] = 0.0
                    else:
                        clean_row[col] = None
                elif isinstance(value, (int, float)):
                    clean_row[col] = float(value) if not pd.isna(value) else 0.0
                else:
                    clean_row[col] = str(value)
            cleaned_data.append(clean_row)
        return cleaned_data

def analyze_google_ads_funnels(df):
    """Gera métricas financeiras da aba Controle Google ADS 2."""
    result = {
        'records': [],
        'totals': {
            'investimento': 0.0,
            'clicks': 0,
            'impressions': 0,
            'ctr': 0.0,
            'cpc': 0.0
        },
        'has_data': False,
        'source': 'Controle Google ADS 2'
    }
    
    if df is None or df.empty:
        return result
    
    working_df = df.copy()
    
    def _find_column(keywords):
        for col in working_df.columns:
            lower_col = col.lower()
            if any(keyword in lower_col for keyword in keywords):
                return col
        return None
    
    def _to_numeric(series):
        if series is None:
            return pd.Series([0] * len(working_df))
        if series.dtype == object:
            cleaned = series.astype(str).str.replace(r'[^0-9,\.\-]', '', regex=True)
            cleaned = cleaned.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            return pd.to_numeric(cleaned, errors='coerce')
        return pd.to_numeric(series, errors='coerce')
    
    name_col = _find_column(['name', 'funil']) or working_df.columns[0]
    clicks_col = _find_column(['click'])
    impressions_col = _find_column(['impress'])
    cost_col = _find_column(['cost', 'invest'])
    
    if cost_col is None:
        return result
    
    working_df[cost_col] = _to_numeric(working_df[cost_col]).fillna(0)
    if clicks_col:
        working_df[clicks_col] = _to_numeric(working_df[clicks_col]).fillna(0)
    else:
        clicks_col = '__clicks__'
        working_df[clicks_col] = 0
    
    if impressions_col:
        working_df[impressions_col] = _to_numeric(working_df[impressions_col]).fillna(0)
    else:
        impressions_col = '__impressions__'
        working_df[impressions_col] = 0
    
    records = []
    total_entry = None
    
    for _, row in working_df.iterrows():
        name = str(row.get(name_col, '')).strip()
        if not name:
            continue
        
        clicks = float(row.get(clicks_col, 0) or 0)
        impressions = float(row.get(impressions_col, 0) or 0)
        investimento = float(row.get(cost_col, 0) or 0)
        ctr = (clicks / impressions * 100) if impressions else 0.0
        cpc = (investimento / clicks) if clicks else 0.0
        is_total = normalize_sheet_title(name) in {'total', 'totais', 'geral'}
        
        record = {
            'name': name,
            'investimento': round(investimento, 2),
            'clicks': int(clicks),
            'impressions': int(impressions),
            'ctr': round(ctr, 2),
            'cpc': round(cpc, 2),
            'is_total': bool(is_total)
        }
        
        if is_total:
            total_entry = record
        else:
            records.append(record)
    
    if not records and not total_entry:
        return result
    
    records.sort(key=lambda item: item['investimento'], reverse=True)
    if total_entry:
        total_entry['name'] = total_entry['name'] or 'Total'
        records.append(total_entry)
    
    total_invest = sum(item['investimento'] for item in records if not item.get('is_total'))
    total_clicks = sum(item['clicks'] for item in records if not item.get('is_total'))
    total_impressions = sum(item['impressions'] for item in records if not item.get('is_total'))
    total_ctr = (total_clicks / total_impressions * 100) if total_impressions else 0.0
    total_cpc = (total_invest / total_clicks) if total_clicks else 0.0
    
    result['records'] = records
    result['totals'] = {
        'investimento': round(total_invest, 2),
        'clicks': int(total_clicks),
        'impressions': int(total_impressions),
        'ctr': round(total_ctr, 2),
        'cpc': round(total_cpc, 2)
    }
    result['has_data'] = True
    return result

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

def detect_lead_email_column(df):
    """Detecta coluna de e-mail"""
    email_keywords = ['email', 'e-mail', 'mail']
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if any(keyword in col_lower for keyword in email_keywords):
            return col
    return None

def detect_lead_phone_column(df):
    """Detecta coluna de telefone"""
    phone_keywords = ['fone', 'telefone', 'phone', 'celular', 'whats', 'whatsapp', 'tel']
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if any(keyword in col_lower for keyword in phone_keywords):
            return col
    return None

STATUS_LABELS = {
    'aberto': 'Em andamento',
    'perdido': 'Perdido',
    'ganho': 'Ganho',
    'outros': 'Outros'
}

SULTS_LEADS_CACHE = {
    'timestamp': None,
    'leads': [],
    'total': 0
}
SULTS_CACHE_TTL_SECONDS = 300  # 5 minutos

def normalize_email(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    return str(value).strip().lower()

def normalize_phone(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    digits = re.sub(r'\D', '', str(value))
    if digits.startswith('55') and len(digits) > 11:
        digits = digits[-11:]
    if len(digits) > 11:
        digits = digits[-11:]
    return digits

def normalize_status_key(value):
    if not value:
        return 'outros'
    text = str(value).lower()
    if any(keyword in text for keyword in ['ganh', 'won', 'cliente', 'conclu']):
        return 'ganho'
    if any(keyword in text for keyword in ['perd', 'lost', 'cancel', 'desist', 'no show', 'no-show']):
        return 'perdido'
    if any(keyword in text for keyword in ['abert', 'andament', 'pendente', 'agendado', 'analise', 'andamento']):
        return 'aberto'
    return 'outros'

def build_status_label(key):
    return STATUS_LABELS.get(key, STATUS_LABELS['outros'])

def normalize_origin_label(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 'SULTS'
    if isinstance(value, dict):
        return value.get('nome') or value.get('name') or 'SULTS'
    text = str(value).strip()
    if not text:
        return 'SULTS'
    if text.startswith('{') and text.endswith('}'):
        try:
            parsed = json.loads(text)
            label = parsed.get('nome') or parsed.get('name')
            if label:
                return normalize_origin_label(label)
        except Exception:
            pass
    if text.startswith('[') and ']' in text:
        tokens = re.findall(r'\[([^\]]+)\]', text)
        cleaned = []
        for tok in tokens:
            if not tok or tok.upper() in ('V', 'VI', 'VII', 'VIII', 'IX', 'X'):
                continue
            token_clean = tok.replace('_', ' ').replace('-', ' ').strip()
            if not token_clean:
                continue
            cleaned.append(token_clean.title())
        if cleaned:
            return ' / '.join(cleaned[:3])
    friendly = text.replace('_', ' ').replace('-', ' ').strip()
    if friendly.lower() in ('google ads', 'googleads'):
        return 'Google Ads'
    if friendly.lower() in ('facebook ads', 'facebookads', 'facebook'):
        return 'Facebook'
    if friendly.lower() == 'organico':
        return 'Orgânico'
    return friendly.title()

def normalize_owner_label(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 'Sem responsável'
    text = str(value).strip()
    if not text:
        return 'Sem responsável'
    if text.startswith('{') and text.endswith('}'):
        try:
            parsed = json.loads(text)
            label = parsed.get('nome') or parsed.get('name')
            if label:
                return normalize_owner_label(label)
        except Exception:
            pass
    return text.title()

def summarize_distribution(items, limit=6):
    if not items:
        return [], 0
    sorted_items = sorted(items, key=lambda x: x['value'], reverse=True)
    total = sum(item['value'] for item in sorted_items)
    if total == 0:
        return (
            [
                {'label': item['label'], 'value': int(item['value']), 'percentage': 0.0}
                for item in sorted_items[:limit]
            ],
            0
        )
    summary = []
    for idx, item in enumerate(sorted_items):
        if idx < limit:
            percentage = round((item['value'] / total) * 100, 1)
            summary.append({
                'label': item['label'],
                'value': int(item['value']),
                'percentage': percentage
            })
        else:
            break
    outros_value = sum(item['value'] for item in sorted_items[limit:])
    if outros_value > 0:
        summary.append({
            'label': 'Outros',
            'value': int(outros_value),
            'percentage': round((outros_value / total) * 100, 1)
        })
    return summary, total

def normalize_name(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    text = str(value).strip().lower()
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _should_skip_project(projeto):
    nome = (projeto.get('nome') or projeto.get('titulo') or '').lower()
    etapa = projeto.get('etapa', {})
    funil = etapa.get('funil', {}) if isinstance(etapa, dict) else {}
    funil_nome = funil.get('nome', '').lower() if isinstance(funil, dict) else ''
    palavras_excluir = ['loja', 'extrabom']
    return any(palavra in nome or palavra in funil_nome for palavra in palavras_excluir)

def _extract_sults_lead_entry(projeto):
    if _should_skip_project(projeto):
        return None
    
    etapa = projeto.get('etapa', {}) if isinstance(projeto.get('etapa'), dict) else {}
    funil = etapa.get('funil', {}) if isinstance(etapa, dict) else {}
    funil_nome = funil.get('nome', '').lower() if isinstance(funil, dict) else ''
    categoria = projeto.get('categoria', {}) if isinstance(projeto.get('categoria'), dict) else {}
    categoria_nome = categoria.get('nome', 'Sem categoria') if isinstance(categoria, dict) else 'Sem categoria'
    responsavel = projeto.get('responsavel', {}) if isinstance(projeto.get('responsavel'), dict) else {}
    responsavel_nome = responsavel.get('nome', 'Sem responsável') if isinstance(responsavel, dict) else 'Sem responsável'
    
    contato_pessoa = projeto.get('contatoPessoa', [])
    contato_empresa = projeto.get('contatoEmpresa', {})
    
    email = ''
    telefone = ''
    if contato_pessoa and isinstance(contato_pessoa, list):
        primeiro = contato_pessoa[0]
        if isinstance(primeiro, dict):
            email = primeiro.get('email', '') or ''
            telefone = primeiro.get('phone', '') or ''
    if not email and isinstance(contato_empresa, dict):
        email = contato_empresa.get('email', '') or ''
    if not telefone and isinstance(contato_empresa, dict):
        telefone = contato_empresa.get('phone', '') or ''
    
    situacao = projeto.get('situacao', {}) if isinstance(projeto.get('situacao'), dict) else {}
    situacao_nome = situacao.get('nome', '').upper() if isinstance(situacao, dict) else ''
    situacao_id = situacao.get('id') if isinstance(situacao, dict) else None
    
    status_key = 'aberto'
    if situacao_id == 2 or situacao_nome == 'GANHO':
        status_key = 'ganho'
    elif situacao_id == 3 or situacao_nome == 'PERDA':
        status_key = 'perdido'
    elif situacao_id in (1, 4) or situacao_nome in ('ANDAMENTO', 'ADIADO'):
        status_key = 'aberto'
    elif projeto.get('concluido'):
        status_key = 'ganho'
    elif projeto.get('pausado'):
        status_key = 'perdido'
    
    etapa_nome = etapa.get('nome', 'Sem etapa') if isinstance(etapa, dict) else 'Sem etapa'
    origem_obj = projeto.get('origem', {}) if isinstance(projeto.get('origem'), dict) else {}
    origem_nome = origem_obj.get('nome', 'SULTS') if isinstance(origem_obj, dict) else 'SULTS'
    name_slug = normalize_name(projeto.get('titulo') or projeto.get('nome'))
    
    return {
        'id': projeto.get('id'),
        'nome': projeto.get('titulo') or projeto.get('nome', 'Sem nome'),
        'email': email,
        'email_norm': normalize_email(email),
        'telefone': telefone,
        'telefone_norm': normalize_phone(telefone),
        'name_slug': name_slug,
        'status_key': status_key,
        'status_label': build_status_label(status_key),
        'responsavel': responsavel_nome,
        'responsavel_id': responsavel.get('id') if isinstance(responsavel, dict) else None,
        'categoria': categoria_nome,
        'etapa': etapa_nome,
        'funil': funil_nome,
        'origem': origem_nome
    }

def fetch_sults_leads_contacts(max_records=None, use_cache=True):
    """Busca contatos da SULTS para conciliação."""
    if not SULTS_AVAILABLE:
        return {'success': False, 'error': 'Integração SULTS desabilitada', 'leads': [], 'total': 0}
    
    now = datetime.now()
    if use_cache and SULTS_LEADS_CACHE['timestamp']:
        delta = now - SULTS_LEADS_CACHE['timestamp']
        if delta.total_seconds() < SULTS_CACHE_TTL_SECONDS and SULTS_LEADS_CACHE['leads']:
            leads = SULTS_LEADS_CACHE['leads']
            total = SULTS_LEADS_CACHE['total']
            trimmed = leads[:max_records] if max_records else leads
            return {'success': True, 'leads': trimmed, 'total': total, 'cached': True}
    
    try:
        token = os.getenv('SULTS_API_TOKEN', '')
        base_url = "https://api.sults.com.br/api/v1"
        client = SultsAPIClient(token=token or None, base_url=base_url, auth_format='token')
        projetos = client.get_negocios_franqueados()
        if not projetos:
            projetos = client.get_projetos()
        
        leads = []
        for projeto in projetos or []:
            lead_entry = _extract_sults_lead_entry(projeto)
            if lead_entry:
                leads.append(lead_entry)
        
        SULTS_LEADS_CACHE['timestamp'] = now
        SULTS_LEADS_CACHE['leads'] = leads
        SULTS_LEADS_CACHE['total'] = len(leads)
        
        trimmed = leads[:max_records] if max_records else leads
        return {'success': True, 'leads': trimmed, 'total': len(leads), 'cached': False}
    except Exception as e:
        print(f"Erro ao buscar leads da SULTS para conciliação: {e}")
        return {'success': False, 'error': str(e), 'leads': [], 'total': 0}

def crosscheck_leads_with_sults(df, name_col, status_col, email_col, phone_col, preview_limit=30):
    """Concilia leads da planilha com dados da SULTS."""
    if not SULTS_AVAILABLE:
        return {
            'available': False,
            'message': 'Integração com a SULTS não está configurada neste servidor.'
        }
    
    if not email_col and not phone_col:
        return {
            'available': False,
            'message': 'Não foi possível conciliar com a SULTS: a planilha não possui colunas de e-mail ou telefone.'
        }
    
    sults_data = fetch_sults_leads_contacts()
    if not sults_data.get('success') or not sults_data.get('leads'):
        return {
            'available': False,
            'message': 'Não foi possível obter dados da SULTS para conciliação.',
            'error': sults_data.get('error')
        }
    
    sults_leads = sults_data['leads']
    total_sults = sults_data.get('total', len(sults_leads))
    
    email_lookup = {}
    phone_lookup = {}
    name_lookup = defaultdict(list)
    name_compact_lookup = defaultdict(list)
    token_lookup = defaultdict(list)
    lead_by_id = {}
    for lead in sults_leads:
        lead_id = lead.get('id')
        if lead_id:
            lead_by_id[lead_id] = lead
        email_norm = lead.get('email_norm')
        phone_norm = lead.get('telefone_norm')
        name_slug = lead.get('name_slug')
        if email_norm:
            email_lookup.setdefault(email_norm, []).append(lead)
        if phone_norm:
            phone_lookup.setdefault(phone_norm, []).append(lead)
        if name_slug:
            name_lookup[name_slug].append(lead)
            compact_slug = name_slug.replace(' ', '')
            if compact_slug:
                name_compact_lookup[compact_slug].append(lead)
            for token in name_slug.split():
                if len(token) >= 3:
                    token_lookup[token].append(lead)
    
    matched_ids = set()
    matches_preview = []
    matches_perdidos = []
    matches_ganhos = []
    status_counts = {'aberto': 0, 'perdido': 0, 'ganho': 0, 'outros': 0}
    divergent = 0
    
    total_rows = len(df)
    
    # Otimização: processa apenas uma amostra se tiver muitos leads
    max_rows_to_process = 5000  # Limite para não travar
    process_all = total_rows <= max_rows_to_process
    
    if not process_all:
        # Processa amostra representativa
        df_sample = df.sample(n=max_rows_to_process, random_state=42)
        print(f"Processando amostra de {max_rows_to_process} leads de {total_rows} total")
    else:
        df_sample = df
    
    # Otimização: pré-processa colunas de uma vez
    if email_col and email_col in df_sample.columns:
        df_sample['_email_norm'] = df_sample[email_col].fillna('').astype(str).str.strip().apply(normalize_email)
    else:
        df_sample['_email_norm'] = ''
    
    if phone_col and phone_col in df_sample.columns:
        df_sample['_phone_norm'] = df_sample[phone_col].fillna('').astype(str).str.strip().apply(normalize_phone)
    else:
        df_sample['_phone_norm'] = ''
    
    if status_col and status_col in df_sample.columns:
        df_sample['_status_key'] = df_sample[status_col].fillna('').astype(str).str.strip().apply(normalize_status_key)
    else:
        df_sample['_status_key'] = 'outros'
    
    if name_col and name_col in df_sample.columns:
        df_sample['_name_slug'] = df_sample[name_col].fillna('').astype(str).str.strip().apply(normalize_name)
    else:
        df_sample['_name_slug'] = ''
    
    # Processa linha por linha (ainda necessário para matching complexo)
    for idx, row in df_sample.iterrows():
        email_norm = row['_email_norm']
        phone_norm = row['_phone_norm']
        sheet_status_key = row['_status_key']
        sheet_slug = row['_name_slug']
        
        # Pega valores originais para exibição
        raw_email = row[email_col] if email_col in df_sample.columns else ''
        raw_phone = row[phone_col] if phone_col in df_sample.columns else ''
        raw_status = row[status_col] if status_col in df_sample.columns else ''
        raw_name = row[name_col] if name_col in df_sample.columns else ''
        
        sheet_email = '' if pd.isna(raw_email) else str(raw_email).strip()
        sheet_phone = '' if pd.isna(raw_phone) else str(raw_phone).strip()
        sheet_status = '' if pd.isna(raw_status) else str(raw_status).strip()
        sheet_name = '' if pd.isna(raw_name) else str(raw_name).strip()
        
        candidate = None
        match_source = None
        if email_norm and email_norm in email_lookup:
            candidate = email_lookup[email_norm][0]
            match_source = 'email'
        elif phone_norm and phone_norm in phone_lookup:
            candidate = phone_lookup[phone_norm][0]
            match_source = 'telefone'
        elif sheet_slug:
            if sheet_slug in name_lookup:
                candidate = name_lookup[sheet_slug][0]
                match_source = 'nome'
            else:
                compact_slug = sheet_slug.replace(' ', '')
                if compact_slug and compact_slug in name_compact_lookup:
                    candidate = name_compact_lookup[compact_slug][0]
                    match_source = 'nome_compacto'
                else:
                    tokens = [tok for tok in sheet_slug.split() if len(tok) >= 3]
                    potential_ids = None
                    for token in tokens:
                        token_ids = {lead.get('id') for lead in token_lookup.get(token, []) if lead.get('id')}
                        if not token_ids:
                            continue
                        if potential_ids is None:
                            potential_ids = token_ids
                        else:
                            potential_ids &= token_ids
                        if potential_ids and len(potential_ids) == 1:
                            break
                    if potential_ids:
                        candidate = lead_by_id.get(next(iter(potential_ids)))
                        match_source = 'nome_tokens'
                    elif tokens:
                        single_match = None
                        for token in tokens:
                            matches = token_lookup.get(token, [])
                            if len(matches) == 1:
                                single_match = matches[0]
                                break
                        if single_match:
                            candidate = single_match
                            match_source = 'nome_token'
                    if not candidate and sheet_slug:
                        candidate = next(
                            (leads_list[0] for slug_key, leads_list in name_lookup.items()
                             if sheet_slug in slug_key or slug_key in sheet_slug),
                            None
                        )
                        if candidate:
                            match_source = 'nome_parcial'
        
        if not candidate:
            continue
        
        matched_ids.add(candidate.get('id'))
        status_key = candidate.get('status_key', 'outros')
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        
        if sheet_status and sheet_status_key and sheet_status_key != status_key:
            divergent += 1
        
        match_entry = {
            'lead': str(sheet_name) if sheet_name else candidate.get('nome'),
            'sheet_status': sheet_status or 'Sem status',
            'sults_status': candidate.get('status_label'),
            'responsavel': candidate.get('responsavel'),
            'email': sheet_email or candidate.get('email') or '-',
            'telefone': sheet_phone or candidate.get('telefone') or '-',
            'match_source': match_source,
            'sults_id': candidate.get('id'),
            'status_key': status_key,
            'divergente': bool(sheet_status and sheet_status_key and sheet_status_key != status_key),
            'sults_origem': candidate.get('origem')
        }
        
        matches_preview.append(match_entry)
        
        if status_key == 'perdido':
            matches_perdidos.append(match_entry)
        elif status_key == 'ganho':
            matches_ganhos.append(match_entry)
    
    total_matched = sum(status_counts.values())
    summary = {
        'total_planilha': total_rows,
        'total_sults': total_sults,
        'matched': total_matched,
        'unmatched_planilha': total_rows - total_matched,
        'unmatched_sults': max(total_sults - len(matched_ids), 0),
        'status_counts': status_counts,
        'divergent': divergent
    }
    
    if total_matched == 0:
        return {
            'available': False,
            'message': 'Nenhum lead da planilha foi conciliado com a SULTS (tentamos e-mail, telefone e nome).',
            'summary': summary
        }
    
    return {
        'available': True,
        'message': f'{total_matched} leads conciliados com a SULTS.',
        'summary': summary,
        'matches': matches_preview,
        'matches_perdidos': matches_perdidos,
        'matches_ganhos': matches_ganhos,
        'last_sync': datetime.now().isoformat(),
        'source': 'SULTS API'
    }

def analyze_leads_dataframe(df):
    """Gera análises a partir de uma planilha de leads - OTIMIZADO"""
    # Limita processamento se tiver muitos dados
    max_rows = 50000  # Limite máximo de linhas para processar
    if len(df) > max_rows:
        print(f"Limitando processamento a {max_rows} linhas de {len(df)} total")
        df = df.head(max_rows)
    
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    
    date_col = detect_lead_date_column(df)
    status_col = detect_lead_status_column(df)
    source_col = detect_lead_source_column(df)
    owner_col = detect_lead_owner_column(df)
    name_col = detect_lead_name_column(df)
    email_col = detect_lead_email_column(df)
    phone_col = detect_lead_phone_column(df)
    
    if source_col:
        def _normalize_source(value):
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return 'organico'
            text = str(value).strip()
            return text if text else 'organico'
        # Otimização: usa operações vetorizadas ao invés de apply
        df[source_col] = df[source_col].fillna('organico').astype(str).str.strip()
        df[source_col] = df[source_col].replace({'': 'organico', 'nan': 'organico', 'None': 'organico', '<NA>': 'organico', 'None': 'organico'})
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
            
            # Comparação temporal: mês atual vs mês anterior
            current_month = datetime.now().to_period('M')
            previous_month = (current_month - 1)
            
            current_month_leads = monthly_counts.get(current_month, 0)
            previous_month_leads = monthly_counts.get(previous_month, 0)
            
            # Calcula variação percentual
            if previous_month_leads > 0:
                growth_rate = ((current_month_leads - previous_month_leads) / previous_month_leads) * 100
            else:
                growth_rate = 100.0 if current_month_leads > 0 else 0.0
            
            # Adiciona comparação temporal aos KPIs
            kpis['temporal_comparison'] = {
                'current_month': {
                    'period': current_month.strftime('%m/%Y'),
                    'leads': int(current_month_leads)
                },
                'previous_month': {
                    'period': previous_month.strftime('%m/%Y'),
                    'leads': int(previous_month_leads)
                },
                'growth_rate': round(growth_rate, 2),
                'growth_absolute': int(current_month_leads - previous_month_leads)
            }
    
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
        
        # Otimização: usa operações vetorizadas ao invés de apply
        status_lower = status_series.str.lower()
        won_keywords = ['ganho', 'won', 'fechado', 'concluído', 'concluido', 'cliente', 'converted']
        lost_keywords = ['perdido', 'lost', 'cancelado', 'desistiu', 'no show', 'no-show', 'falhou']
        
        # Cria máscaras booleanas de uma vez
        won_mask = status_lower.str.contains('|'.join(won_keywords), case=False, na=False)
        lost_mask = status_lower.str.contains('|'.join(lost_keywords), case=False, na=False)
        
        leads_won = int(won_mask.sum())
        leads_lost = int(lost_mask.sum())
        conversion_rate = round((leads_won / total_leads) * 100, 2) if total_leads > 0 else 0.0

    if source_col:
        source_series = df[source_col].astype(str).str.strip().apply(normalize_origin_label)
        source_counts = source_series.value_counts().head(15)
        source_distribution = [
            {'label': origem, 'value': int(count)}
            for origem, count in source_counts.items()
        ]

    if owner_col:
        owner_series = df[owner_col].fillna('Sem Responsável').astype(str).str.strip().apply(normalize_owner_label)
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

    # Conciliação SULTS - DESABILITADA por padrão para melhor performance
    # Pode ser habilitada depois via endpoint separado se necessário
    sults_crosscheck = {
        'available': False,
        'message': 'Conciliação com SULTS desabilitada para melhor performance. Use o botão "Carregar Dados SULTS" para conciliar manualmente.'
    }
    
    # Opcional: processa conciliação apenas se tiver poucos leads E se solicitado explicitamente
    # Comentado para melhor performance - descomente se necessário
    # if len(df) < 500 and request.args.get('sults_sync') == 'true':
    #     try:
    #         sults_crosscheck = crosscheck_leads_with_sults(
    #             df,
    #             name_col=name_col,
    #             status_col=status_col,
    #             email_col=email_col,
    #             phone_col=phone_col
    #         )
    #     except Exception as e:
    #         print(f"Erro na conciliação SULTS (não bloqueante): {e}")
    #         sults_crosscheck = {
    #             'available': False,
    #             'message': 'Conciliação com SULTS não disponível no momento.'
    #         }
    if sults_crosscheck.get('available'):
        summary = sults_crosscheck.get('summary', {})
        status_counts = summary.get('status_counts', {})
        if status_counts:
            sults_status_distribution = []
            for key in ['aberto', 'perdido', 'ganho', 'outros']:
                value = status_counts.get(key)
                if value:
                    sults_status_distribution.append({
                        'label': build_status_label(key),
                        'value': int(value)
                    })
            distributions['sults_status'] = sults_status_distribution
            kpis['sults_status_counts'] = status_counts
            kpis['sults_matched'] = summary.get('matched', 0)
            kpis['sults_divergent'] = summary.get('divergent', 0)
            kpis['sults_source'] = sults_crosscheck.get('source', 'SULTS API')
        matches_for_fallback = sults_crosscheck.get('matches') or []
        if matches_for_fallback:
            origem_counts = {}
            for entry in matches_for_fallback:
                origem = normalize_origin_label(entry.get('sults_origem'))
                origem_counts[origem] = origem_counts.get(origem, 0) + 1
            source_distribution = [
                {'label': label, 'value': count}
                for label, count in sorted(origem_counts.items(), key=lambda x: x[1], reverse=True)
            ]
            owner_counts = {}
            for entry in matches_for_fallback:
                owner_label = normalize_owner_label(entry.get('responsavel'))
                owner_counts[owner_label] = owner_counts.get(owner_label, 0) + 1
            owner_distribution = [
                {'label': label, 'value': count}
                for label, count in sorted(owner_counts.items(), key=lambda x: x[1], reverse=True)
            ]
    
    df = df.drop(columns=['_lead_date_dt'])
    if source_col:
        df[source_col] = df[source_col].replace(r'^\s*$', 'organico', regex=True).fillna('organico')

    source_total = sum(item['value'] for item in source_distribution)
    owner_summary, owner_total = summarize_distribution(owner_distribution)

    return {
        'columns': list(df.columns),
        'total_rows': total_leads,
        'date_column': date_col,
        'status_column': status_col,
        'source_column': source_col,
        'owner_column': owner_col,
        'name_column': name_col,
        'email_column': email_col,
        'phone_column': phone_col,
        'kpis': kpis,
        'distributions': {
            'status': status_distribution,
            'source': source_distribution,
            'owner': owner_summary
        },
        'totals': {
            'source': source_total,
            'owner': owner_total
        },
        'timeline': timeline,
        'insights': insights,
        'recent_leads': clean_dataframe_for_json(recent_preview, max_rows=20),
        'raw_data': clean_dataframe_for_json(df, max_rows=1000),  # Limita a 1000 linhas para não travar
        'sults_crosscheck': sults_crosscheck
    }
    
    # Limpa memória após retornar
    gc.collect()

@app.route('/api/debug/credentials')
def debug_credentials():
    """Endpoint de debug para verificar status das credenciais"""
    debug_info = {
        'has_google_credentials_json': bool(os.getenv('GOOGLE_CREDENTIALS_JSON')),
        'google_credentials_json_length': len(os.getenv('GOOGLE_CREDENTIALS_JSON', '')),
        'has_google_application_credentials': bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')),
        'google_application_credentials_value': os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''),
        'current_directory': os.getcwd(),
        'credentials_loaded': False,
        'credentials_source': None,
        'error': None
    }
    
    try:
        credentials = load_drive_credentials()
        if credentials:
            debug_info['credentials_loaded'] = True
            debug_info['credentials_source'] = 'GOOGLE_CREDENTIALS_JSON' if os.getenv('GOOGLE_CREDENTIALS_JSON') else 'file'
            debug_info['credentials_email'] = getattr(credentials, 'service_account_email', 'N/A')
        else:
            debug_info['error'] = 'Credenciais não foram carregadas'
    except Exception as e:
        debug_info['error'] = str(e)
        import traceback
        debug_info['traceback'] = traceback.format_exc()
    
    return jsonify(debug_info)

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
        
        # Lê o arquivo com otimizações
        file_bytes = file.read()
        cache_key = _get_cache_key(file_bytes)
        cached_data = _get_from_cache(cache_key)
        
        if cached_data:
            print("Usando dados do cache")
            return jsonify(cached_data)
        
        file_like = io.BytesIO(file_bytes)
        if file.filename.endswith('.csv'):
            # Otimizações para CSV
            df = pd.read_csv(file_like, dtype=str, low_memory=False, engine='c')
        else:
            # Otimizações para Excel - usa openpyxl que é mais rápido
            try:
                df = pd.read_excel(file_like, engine='openpyxl', dtype=str)
            except:
                # Fallback para engine padrão
                df = pd.read_excel(file_like, dtype=str)
        
        # Processa dados
        date_col = detect_date_column(df)
        creative_cols = detect_creative_columns(df)
        cost_cols = detect_cost_columns(df)
        leads_cols = detect_leads_columns(df)
        
        # Processa datas
        if date_col:
            df['Data_Processada'] = df[date_col].apply(parse_brazilian_date)
        
        # Otimização: processa apenas colunas necessárias
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            df[numeric_cols] = df[numeric_cols].fillna(0)
        
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
                
                # Análise de Performance e Otimização
                avg_cpl = creative_stats['CPL'].replace([np.inf, -np.inf, np.nan], 0).mean()
                avg_cpmql = creative_stats['CPMQL'].replace([np.inf, -np.inf, np.nan], 0).mean()
                
                # Identifica criativos com performance abaixo da média
                creative_stats['Performance_Status'] = 'Bom'
                creative_stats.loc[
                    (creative_stats['CPL'] > avg_cpl * 1.5) | 
                    (creative_stats['CPMQL'] > avg_cpmql * 1.5) |
                    (creative_stats['Total_Leads'] < 5),
                    'Performance_Status'
                ] = 'Ruim'
                
                creative_stats.loc[
                    (creative_stats['CPL'] <= avg_cpl * 0.7) & 
                    (creative_stats['CPMQL'] <= avg_cpmql * 0.7) &
                    (creative_stats['Total_Leads'] >= 10),
                    'Performance_Status'
                ] = 'Excelente'
                
                # Sugestões de otimização
                optimization_suggestions = {
                    'pause_creatives': creative_stats[
                        creative_stats['Performance_Status'] == 'Ruim'
                    ][['creative', 'CPL', 'CPMQL', 'Total_Leads']].to_dict('records'),
                    'scale_creatives': creative_stats[
                        creative_stats['Performance_Status'] == 'Excelente'
                    ][['creative', 'CPL', 'CPMQL', 'Total_Leads']].to_dict('records'),
                    'avg_cpl': float(avg_cpl),
                    'avg_cpmql': float(avg_cpmql)
                }
                
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
                    'optimization_suggestions': optimization_suggestions,
                    'performance_analysis': {
                        'total_creatives': len(creative_stats),
                        'excellent_count': len(creative_stats[creative_stats['Performance_Status'] == 'Excelente']),
                        'good_count': len(creative_stats[creative_stats['Performance_Status'] == 'Bom']),
                        'bad_count': len(creative_stats[creative_stats['Performance_Status'] == 'Ruim']),
                        'avg_cpl': float(avg_cpl),
                        'avg_cpmql': float(avg_cpmql)
                    },
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
                'raw_data': clean_dataframe_for_json(df, max_rows=2000)  # Limita para performance
            }
        }
        
        # Salva no cache se tiver chave
        if cache_key:
            _save_to_cache(cache_key, result)
        
        # Limpa memória
        del df
        gc.collect()
        
        print("Upload processing completed successfully")
        return jsonify(result)
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 500

@app.route('/auto-upload')
def auto_upload():
    # Limpa cache antes de carregar novos dados
    _clear_old_cache()
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
                    
                    # Top criativos para gráfico - otimizado
                    top_creatives = {}
                    top_10 = creative_stats.head(10)
                    if len(top_10) > 0:
                        top_creatives = dict(zip(
                            top_10['creative'].astype(str),
                            top_10['Total_Leads'].astype(int)
                        ))
                    
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
                        'raw_data': clean_dataframe_for_json(df, max_rows=2000)  # Limita para performance
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
        
        preferred_tabs = ['Controle Google ADS', 'Controle Google ADS 2']
        preferred_targets = [normalize_sheet_title(name) for name in preferred_tabs]
        sheets_data = {}
        leads_df = None
        funnels_df = None
        file_name = 'Planilha Google Ads'
        sheet_info = {}
        
        try:
            sheets_data, sheet_info = load_google_ads_sheet(file_id, credentials, preferred_sheets=preferred_tabs)
            loaded_tabs = ', '.join(sheet_info.get('loaded_sheets', []))
            file_name = f"Google Ads ({loaded_tabs}) via Sheets API"
            print(f"[GOOGLE ADS] Planilha carregada via Sheets API: {loaded_tabs}")
        except Exception as sheets_error:
            print(f"[GOOGLE ADS] Falha ao ler via Sheets API: {sheets_error}")
            # Fallback: baixar arquivo convertido (XLSX) do Drive
            file_content, downloaded_name = download_file_from_drive(file_id, credentials)
            if not file_content:
                return jsonify({'error': 'Erro ao baixar arquivo do Google Drive'}), 500
            
            file_name = downloaded_name or file_name
            print(f"Upload automático do Google Ads recebido: {file_name}")
            
            try:
                sheets_dict = pd.read_excel(io.BytesIO(file_content), sheet_name=None)
            except Exception as read_error:
                raise ValueError(f"Não foi possível ler o arquivo baixado: {read_error}")
            
            frames_map = {}
            sheet_stats = []
            for sheet_name, sheet_df in sheets_dict.items():
                normalized_name = normalize_sheet_title(sheet_name)
                if normalized_name not in preferred_targets:
                    continue
                cleaned_df = sheet_df.dropna(how='all').dropna(axis=1, how='all').reset_index(drop=True)
                if cleaned_df.empty:
                    continue
                frames_map[sheet_name] = cleaned_df
                sheet_stats.append({'name': sheet_name, 'rows': int(cleaned_df.shape[0]), 'columns': int(cleaned_df.shape[1])})
                print(f"[GOOGLE ADS][Download] Aba '{sheet_name}' carregada -> linhas: {cleaned_df.shape[0]}, colunas: {cleaned_df.shape[1]}")
            
            if not frames_map:
                raise ValueError("Nenhuma das abas solicitadas possuía dados válidos no arquivo baixado do Google Ads.")
            
            sheets_data = frames_map
            sheet_info = {
                'primary_sheets': list(frames_map.keys()),
                'sheet_stats': sheet_stats,
                'sheet_count': len(frames_map),
                'loaded_sheets': list(frames_map.keys())
            }
            print(f"Arquivo do Google Ads lido via download: {[k for k in frames_map.keys()]}")
        
        def pick_sheet(target_name):
            normalized_target = normalize_sheet_title(target_name)
            for title, data in sheets_data.items():
                if normalize_sheet_title(title) == normalized_target:
                    return data
            return None
        
        leads_df = pick_sheet('Controle Google ADS')
        funnels_df = pick_sheet('Controle Google ADS 2')
        
        if leads_df is None or leads_df.empty:
            return jsonify({'error': "Aba 'Controle Google ADS' não encontrada ou está vazia"}), 500
        
        df = leads_df.copy().reset_index(drop=True)
        
        # Processa o DataFrame independentemente da origem
        try:
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
            temporal_comparison = {}
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
                
                # Comparação temporal para Google Ads
                if not summary_df.empty:
                    summary_df['Data'] = pd.to_datetime(summary_df['Data'], errors='coerce')
                    summary_df = summary_df.dropna(subset=['Data'])
                    if not summary_df.empty:
                        summary_df['Period'] = summary_df['Data'].dt.to_period('M')
                        monthly_counts = summary_df.groupby('Period')['Criativos'].sum()
                        
                        current_month = datetime.now().to_period('M')
                        previous_month = (current_month - 1)
                        
                        current_month_count = int(monthly_counts.get(current_month, 0))
                        previous_month_count = int(monthly_counts.get(previous_month, 0))
                        
                        if previous_month_count > 0:
                            growth_rate = ((current_month_count - previous_month_count) / previous_month_count) * 100
                        else:
                            growth_rate = 100.0 if current_month_count > 0 else 0.0
                        
                        temporal_comparison = {
                            'current_month': {
                                'period': current_month.strftime('%m/%Y'),
                                'count': current_month_count
                            },
                            'previous_month': {
                                'period': previous_month.strftime('%m/%Y'),
                                'count': previous_month_count
                            },
                            'growth_rate': round(growth_rate, 2),
                            'growth_absolute': current_month_count - previous_month_count
                        }
            
            # Calcula KPIs - apenas contagens
            kpis = {}
            total_leads = df[leads_cols['lead']].sum()
            total_mqls = df[leads_cols['mql']].sum()
            kpis['total_leads'] = int(total_leads) if not pd.isna(total_leads) else 0
            kpis['total_mqls'] = int(total_mqls) if not pd.isna(total_mqls) else 0
            kpis['temporal_comparison'] = temporal_comparison
            
            funnels_analysis = analyze_google_ads_funnels(funnels_df)
            total_investimento = funnels_analysis['totals']['investimento']
            kpis['investimento_total'] = round(total_investimento, 2)
            if kpis['total_mqls'] > 0 and total_investimento > 0:
                kpis['custo_por_mql'] = round(total_investimento / kpis['total_mqls'], 2)
            else:
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
                    'sheet_info': sheet_info,
                    'date_column': date_col,
                    'creative_columns': creative_cols,
                    'cost_columns': cost_cols,
                    'leads_columns': leads_cols,
                    'summary': summary_data,
                    'kpis': kpis,
                    'creative_analysis': creative_analysis,
                    'funnels_analysis': funnels_analysis,
                    'funnels_raw_data': clean_dataframe_for_json(funnels_df) if funnels_df is not None else [],
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
        cache_key = _get_cache_key(file_bytes)
        cached_data = _get_from_cache(cache_key)
        
        if cached_data:
            print("Usando dados do cache para leads")
            return jsonify(cached_data)
        
        df, sheet_info = load_leads_dataframe_from_bytes(file_bytes, file.filename, priority_names)
        sheet_info = sheet_info or {}
        sheet_info.setdefault('source', 'manual_upload')
        sheet_info['file_name'] = file.filename
        sheet_info['priority_used'] = priority_names

        analysis = analyze_leads_dataframe(df)
        analysis['sheet_info'] = sheet_info
        analysis['file_name'] = file.filename

        result = {
            'success': True,
            'message': 'Planilha de leads processada com sucesso!',
            'sheet_info': sheet_info,
            'data': analysis
        }
        
        # Salva no cache
        if cache_key:
            _save_to_cache(cache_key, result)
        
        # Limpa memória
        del df
        gc.collect()

        return jsonify(result)
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
            
            # Ordem customizada das fases (definir uma vez para otimização)
            ordem_fases = {
                'lead': 1, 'mql': 2, 'conexao': 3, 'conexão': 3,
                'pre-call agendada': 4, 'pre call agendada': 4,
                'pre-call realizada': 5, 'pre call realizada': 5,
                'apresentação modelo agendada': 6, 'apresentacao modelo agendada': 6,
                'apresentação modelo realizada': 7, 'apresentacao modelo realizada': 7,
                'apresentação financeira agendada': 8, 'apresentacao financeira agendada': 8,
                'reunião financeira realizada': 9, 'reuniao financeira realizada': 9,
                'reunião fundador agendada': 10, 'reuniao fundador agendada': 10,
                'aguardando decisão': 11, 'aguardando decisao': 11,
                'contrato franquia': 12
            }
            
            # Palavras a excluir (definir uma vez)
            palavras_excluir = ['loja', 'lojas', 'extrabom']
            
            # Transformar projetos em leads para exibição
            leads_abertos = []
            leads_perdidos = []
            leads_ganhos = []
            leads_mql = []  # Leads com etiqueta MQL
            leads_por_fase = {}
            leads_por_fase_conversao = {}  # Para taxa de conversão: inclui todos os leads do mês atual
            leads_por_categoria = {}
            leads_por_responsavel = {}
            leads_por_unidade = {}
            total_mql = 0
            
            # Data atual para filtrar leads do mês atual
            data_atual = datetime.now()
            mes_atual = data_atual.month
            ano_atual = data_atual.year
            
            for projeto in projetos:
                # Verificação final: pular se for loja (otimizado)
                etapa = projeto.get('etapa', {})
                funil = etapa.get('funil', {}) if isinstance(etapa, dict) else {}
                funil_nome = funil.get('nome', '').lower() if isinstance(funil, dict) else ''
                projeto_nome = projeto.get('nome', '').lower()
                projeto_titulo = projeto.get('titulo', '').lower()
                
                # Excluir qualquer coisa relacionada a lojas (otimizado)
                if any(palavra in funil_nome or palavra in projeto_nome or palavra in projeto_titulo 
                       for palavra in palavras_excluir):
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
                
                # Determinar ordem da fase (otimizado - ordem_fases já definido fora do loop)
                fase_ordem = etapa_id if etapa_id is not None else 9999
                if fase_ordem == 9999:
                    fase_lower = fase.lower().strip()
                    for key, ordem in ordem_fases.items():
                        if key in fase_lower:
                            fase_ordem = ordem
                            break
                
                # Contar por responsável
                responsavel = projeto.get('responsavel', {})
                responsavel_nome = responsavel.get('nome', 'Sem responsável') if isinstance(responsavel, dict) else 'Sem responsável'
                responsavel_id = responsavel.get('id') if isinstance(responsavel, dict) else None
                
                # Contar por unidade (usar contatoEmpresa se disponível)
                contato_empresa = projeto.get('contatoEmpresa', {})
                unidade_nome = 'Sem unidade'
                if contato_empresa and isinstance(contato_empresa, dict):
                    unidade_nome = contato_empresa.get('nomeFantasia', 'Sem unidade')
                
                # Verificar se tem etiqueta MQL (otimizado)
                etiquetas = projeto.get('etiqueta', [])
                tem_mql = False
                etiquetas_nomes = []
                
                if etiquetas and isinstance(etiquetas, list):
                    for etiqueta in etiquetas:
                        if isinstance(etiqueta, dict):
                            etiqueta_nome = etiqueta.get('nome', '')
                            etiquetas_nomes.append(etiqueta_nome)
                            # Verificar se a etiqueta contém MQL (otimizado - sem upper() desnecessário)
                            if 'MQL' in etiqueta_nome.upper():
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
                
                # Otimizar extração de dados (evitar múltiplos .get() no mesmo objeto)
                origem_obj = projeto.get('origem', {})
                origem_nome = origem_obj.get('nome', 'SULTS') if isinstance(origem_obj, dict) else 'SULTS'
                temperatura_obj = projeto.get('temperatura', {})
                temperatura_nome = temperatura_obj.get('nome', '') if isinstance(temperatura_obj, dict) else ''
                
                lead_data = {
                    'id': projeto.get('id'),
                    'nome': projeto.get('titulo') or projeto.get('nome', 'Sem nome'),
                    'email': email,
                    'email_norm': normalize_email(email),
                    'telefone': telefone,
                    'telefone_norm': normalize_phone(telefone),
                    'responsavel': responsavel_nome,
                    'responsavel_id': responsavel_id,
                    'unidade': unidade_nome or (contato_empresa.get('nomeFantasia', '') if isinstance(contato_empresa, dict) else ''),
                    'categoria': categoria_nome,
                    'fase': fase,
                    'etapa': etapa_nome,
                    'funil': funil_nome,
                    'status': status,
                    'situacao': situacao_nome,
                    'ativo': True,
                    'data_criacao': projeto.get('dtCadastro', '') or projeto.get('dtCriacao', ''),
                    'data_inicio': projeto.get('dtInicio', ''),
                    'data_fim': projeto.get('dtConclusao', '') or projeto.get('dtFim', ''),
                    'cidade': projeto.get('cidade', ''),
                    'uf': projeto.get('uf', ''),
                    'valor': projeto.get('valor', 0.0),
                    'origem': origem_nome,
                    'temperatura': temperatura_nome,
                    'etiquetas': etiquetas_nomes,
                    'tem_mql': tem_mql,
                    'origem_tipo': 'SULTS - Franqueados'
                }
                
                # Verificar se o lead é do mês atual para taxa de conversão
                data_criacao_str = projeto.get('dtCadastro', '') or projeto.get('dtCriacao', '')
                is_mes_atual = False
                if data_criacao_str:
                    try:
                        if isinstance(data_criacao_str, str):
                            # Tentar diferentes formatos de data
                            for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%d-%m-%Y']:
                                try:
                                    data_criacao = datetime.strptime(data_criacao_str.split('T')[0] if 'T' in data_criacao_str else data_criacao_str.split(' ')[0], fmt)
                                    if data_criacao.month == mes_atual and data_criacao.year == ano_atual:
                                        is_mes_atual = True
                                        break
                                except:
                                    continue
                        elif isinstance(data_criacao_str, (int, float)):
                            # Timestamp
                            data_criacao = datetime.fromtimestamp(data_criacao_str / 1000 if data_criacao_str > 1e10 else data_criacao_str)
                            if data_criacao.month == mes_atual and data_criacao.year == ano_atual:
                                is_mes_atual = True
                    except:
                        pass
                
                # Classificar lead por status
                if status == 'perdido':
                    leads_perdidos.append(lead_data)
                elif status == 'ganho':
                    leads_ganhos.append(lead_data)
                
                # Para taxa de conversão: contar todos os leads do mês atual (abertos, perdidos, ganhos)
                # Isso deve ser feito ANTES do filtro de status para incluir todos
                if is_mes_atual:
                    if fase not in leads_por_fase_conversao:
                        leads_por_fase_conversao[fase] = {'count': 1, 'ordem': fase_ordem}
                    else:
                        leads_por_fase_conversao[fase]['count'] += 1
                
                # Filtrar apenas leads em aberto para estatísticas, exibição e MQLs
                if status != 'aberto':
                    continue
                
                # Contadores considerando apenas leads em aberto (otimizado)
                leads_por_categoria[categoria_nome] = leads_por_categoria.get(categoria_nome, 0) + 1
                
                # Armazenar fase com informação de ordenação (otimizado)
                if fase not in leads_por_fase:
                    leads_por_fase[fase] = {'count': 1, 'ordem': fase_ordem}
                else:
                    leads_por_fase[fase]['count'] += 1
                
                leads_por_responsavel[responsavel_nome] = leads_por_responsavel.get(responsavel_nome, 0) + 1
                leads_por_unidade[unidade_nome] = leads_por_unidade.get(unidade_nome, 0) + 1
                
                leads_abertos.append(lead_data)
                
                # Adicionar aos MQLs apenas se estiver em aberto E tiver etiqueta MQL
                if tem_mql:
                    leads_mql.append(lead_data)
                    total_mql += 1
            
            total_leads = len(leads_abertos)
            
            # Log final resumido
            print(f"✅ Processados: {len(projetos)} projetos → {len(leads_abertos)} leads abertos, {total_mql} MQLs")
            
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
            
            SULTS_LEADS_CACHE['timestamp'] = datetime.now()
            SULTS_LEADS_CACHE['leads'] = leads_abertos + leads_perdidos + leads_ganhos
            SULTS_LEADS_CACHE['total'] = len(SULTS_LEADS_CACHE['leads'])
            
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

@app.route('/api/sults/update-responsavel', methods=['POST'])
def update_negocio_responsavel():
    """Atualiza o responsável de um negócio na SULTS"""
    if not SULTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Integração SULTS não disponível'}), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400
        
        negocio_id = data.get('negocio_id')
        responsavel_id = data.get('responsavel_id')
        
        if not negocio_id or not responsavel_id:
            return jsonify({'success': False, 'error': 'negocio_id e responsavel_id são obrigatórios'}), 400
        
        client = SultsAPIClient()
        result = client.update_negocio_responsavel(int(negocio_id), int(responsavel_id))
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Responsável atualizado com sucesso',
                'data': result.get('data', {})
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro ao atualizar responsável')
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao atualizar responsável: {str(e)}'
        }), 500

@app.route('/api/sults/update-etapa', methods=['POST'])
def update_negocio_etapa():
    """Atualiza a fase/etapa de um negócio na SULTS"""
    if not SULTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Integração SULTS não disponível'}), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400
        
        negocio_id = data.get('negocio_id')
        etapa_id = data.get('etapa_id')
        
        if not negocio_id or not etapa_id:
            return jsonify({'success': False, 'error': 'negocio_id e etapa_id são obrigatórios'}), 400
        
        client = SultsAPIClient()
        result = client.update_negocio_etapa(int(negocio_id), int(etapa_id))
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Fase atualizada com sucesso',
                'data': result.get('data', {})
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro ao atualizar fase')
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao atualizar fase: {str(e)}'
        }), 500

@app.route('/api/sults/add-anotacao', methods=['POST'])
def add_negocio_anotacao():
    """Adiciona uma anotação/comentário a um negócio na SULTS"""
    if not SULTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Integração SULTS não disponível'}), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'}), 400
        
        negocio_id = data.get('negocio_id')
        anotacao = data.get('anotacao')
        usuario_id = data.get('usuario_id')
        
        if not negocio_id or not anotacao:
            return jsonify({'success': False, 'error': 'negocio_id e anotacao são obrigatórios'}), 400
        
        client = SultsAPIClient()
        result = client.add_negocio_anotacao(int(negocio_id), anotacao, usuario_id)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Anotação adicionada com sucesso',
                'data': result.get('data', {})
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro ao adicionar anotação')
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao adicionar anotação: {str(e)}'
        }), 500

@app.route('/api/sults/etapas', methods=['GET'])
def get_etapas_disponiveis():
    """Busca as etapas/fases disponíveis para um funil"""
    if not SULTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Integração SULTS não disponível'}), 503
    
    try:
        funil_id = request.args.get('funil_id', 1, type=int)
        client = SultsAPIClient()
        etapas = client.get_etapas_disponiveis(funil_id)
        
        return jsonify({
            'success': True,
            'data': etapas
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar etapas: {str(e)}'
        }), 500

@app.route('/api/sults/usuarios', methods=['GET'])
def get_usuarios_disponiveis():
    """Busca os usuários/responsáveis disponíveis na SULTS"""
    if not SULTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Integração SULTS não disponível'}), 503
    
    try:
        client = SultsAPIClient()
        usuarios = client.get_usuarios_disponiveis()
        
        return jsonify({
            'success': True,
            'data': usuarios
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar usuários: {str(e)}'
        }), 500

@app.route('/api/kanban/leads', methods=['GET'])
def get_kanban_leads():
    """Retorna leads organizados por fase para pipeline Kanban"""
    try:
        # Busca leads do SULTS ou da última análise de leads
        leads = []
        
        # Tenta buscar do SULTS primeiro
        if SULTS_AVAILABLE:
            try:
                client = SultsAPIClient()
                sults_data = client.get_leads_by_status()
                if sults_data.get('abertos'):
                    for lead in sults_data['abertos'].get('leads', []):
                        leads.append({
                            'id': lead.get('id'),
                            'nome': lead.get('nome', 'Sem nome'),
                            'fase': lead.get('etapa', 'Sem fase'),
                            'email': lead.get('email', ''),
                            'telefone': lead.get('telefone', ''),
                            'responsavel': lead.get('responsavel', ''),
                            'status': 'aberto',
                            'origem': lead.get('origem', ''),
                            'data': lead.get('data_criacao', ''),
                            'valor': lead.get('valor', 0),
                            'cidade': lead.get('cidade', ''),
                            'uf': lead.get('uf', '')
                        })
            except:
                pass
        
        if not leads:
            return jsonify({
                'error': 'Nenhum lead encontrado. Carregue dados do SULTS primeiro.',
                'columns': []
            }), 404
        
        # Ordem das fases (customizável)
        ordem_fases = {
            'Lead MQL': 1, 'MQL': 1, 'Conexão': 2, 'Pre-call agendada': 3,
            'Pre-call realizada': 4, 'Apresentação Modelo Agendada': 5,
            'Apresentação Modelo Realizada': 6, 'Apresentação Financeira agendada': 7,
            'Reunião Financeira Realizada': 8, 'Reunião Fundador agendada': 9,
            'Aguardando decisão': 10, 'Contrato Franquia': 11
        }
        
        # Agrupa leads por fase
        kanban_columns = {}
        for lead in leads:
            fase = lead.get('fase', 'Sem fase') or 'Sem fase'
            if fase not in kanban_columns:
                kanban_columns[fase] = {
                    'id': fase,
                    'title': fase,
                    'order': ordem_fases.get(fase, 999),
                    'leads': []
                }
            
            kanban_columns[fase]['leads'].append({
                'id': lead.get('id') or f"lead_{len(kanban_columns[fase]['leads'])}",
                'nome': lead.get('nome', 'Sem nome'),
                'email': lead.get('email', ''),
                'telefone': lead.get('telefone', ''),
                'responsavel': lead.get('responsavel', ''),
                'status': lead.get('status', ''),
                'origem': lead.get('origem', ''),
                'data': lead.get('data', ''),
                'valor': lead.get('valor', 0),
                'cidade': lead.get('cidade', ''),
                'uf': lead.get('uf', '')
            })
        
        # Ordena colunas
        sorted_columns = sorted(kanban_columns.values(), key=lambda x: x['order'])
        
        return jsonify({
            'success': True,
            'columns': sorted_columns,
            'total_leads': len(leads)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/integrations/meta-ads', methods=['GET'])
def get_meta_ads_integration():
    """Endpoint para integração com Meta Ads API"""
    try:
        # Requer: META_ADS_ACCESS_TOKEN, META_ADS_ACCOUNT_ID
        meta_token = os.getenv('META_ADS_ACCESS_TOKEN')
        account_id = os.getenv('META_ADS_ACCOUNT_ID')
        
        if not meta_token or not account_id:
            return jsonify({
                'available': False,
                'message': 'Integração Meta Ads não configurada. Configure META_ADS_ACCESS_TOKEN e META_ADS_ACCOUNT_ID',
                'setup_required': True,
                'instructions': {
                    'step1': 'Obtenha um Access Token do Meta Ads Manager',
                    'step2': 'Configure META_ADS_ACCESS_TOKEN no .env',
                    'step3': 'Configure META_ADS_ACCOUNT_ID no .env',
                    'step4': 'Reinicie o servidor'
                }
            })
        
        # Estrutura para futura implementação da API real
        # API do Meta: https://developers.facebook.com/docs/marketing-apis
        return jsonify({
            'available': True,
            'message': 'Integração Meta Ads configurada',
            'account_id': account_id,
            'endpoints': {
                'campaigns': '/api/integrations/meta-ads/campaigns',
                'ads': '/api/integrations/meta-ads/ads',
                'insights': '/api/integrations/meta-ads/insights',
                'ad_sets': '/api/integrations/meta-ads/ad-sets'
            },
            'note': 'Implementação completa da API requer configuração adicional. Por enquanto, use o botão "Carregar Meta ADS" para upload manual.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/integrations/list', methods=['GET'])
def list_integrations():
    """Lista todas as integrações disponíveis"""
    integrations = {
        'google_drive': {
            'name': 'Google Drive',
            'available': bool(os.getenv('GOOGLE_CREDENTIALS_JSON') or os.path.exists('sixth-now-475017-k8-785034518ab7.json')),
            'status': 'active' if (os.getenv('GOOGLE_CREDENTIALS_JSON') or os.path.exists('sixth-now-475017-k8-785034518ab7.json')) else 'not_configured'
        },
        'sults': {
            'name': 'SULTS API',
            'available': SULTS_AVAILABLE,
            'status': 'active' if SULTS_AVAILABLE and os.getenv('SULTS_API_TOKEN') else 'not_configured'
        },
        'meta_ads': {
            'name': 'Meta Ads API',
            'available': bool(os.getenv('META_ADS_ACCESS_TOKEN') and os.getenv('META_ADS_ACCOUNT_ID')),
            'status': 'active' if (os.getenv('META_ADS_ACCESS_TOKEN') and os.getenv('META_ADS_ACCOUNT_ID')) else 'not_configured'
        }
    }
    
    return jsonify({
        'success': True,
        'integrations': integrations,
        'total_available': sum(1 for i in integrations.values() if i['available']),
        'total_configured': len(integrations)
    })

@app.route('/api/performance/optimization', methods=['GET'])
def get_performance_optimization():
    """Retorna sugestões de otimização de performance"""
    try:
        # Busca dados de criativos se disponíveis
        if not currentData or not currentData.get('creative_analysis'):
            return jsonify({
                'available': False,
                'message': 'Carregue dados de criativos primeiro'
            })
        
        creative_analysis = currentData.get('creative_analysis', {})
        optimization = creative_analysis.get('optimization_suggestions', {})
        performance = creative_analysis.get('performance_analysis', {})
        
        return jsonify({
            'success': True,
            'optimization': optimization,
            'performance': performance,
            'recommendations': [
                {
                    'type': 'pause',
                    'title': 'Pausar Criativos com Baixa Performance',
                    'count': len(optimization.get('pause_creatives', [])),
                    'creatives': optimization.get('pause_creatives', [])
                },
                {
                    'type': 'scale',
                    'title': 'Aumentar Investimento em Criativos Excelentes',
                    'count': len(optimization.get('scale_creatives', [])),
                    'creatives': optimization.get('scale_creatives', [])
                }
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print(f"Templates path: {app.template_folder}")
    app.run(debug=True, host='0.0.0.0', port=5000)
