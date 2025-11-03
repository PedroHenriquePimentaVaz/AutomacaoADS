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

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

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
        elif 'investimento' in col_lower or 'investido' in col_lower:
            cost_cols['total'] = col
        elif 'custo' in col_lower or 'cost' in col_lower:
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
            
            # Processa dados (mesma lógica da função de upload)
            date_col = detect_date_column(df)
            creative_cols = detect_creative_columns(df)
            cost_cols = detect_cost_columns(df)
            
            # Processa datas
            if date_col:
                df['Data_Processada'] = df[date_col].apply(parse_brazilian_date)
            
            # Preenche coluna Term vazia com 'organico'
            df = fill_term_column(df)
            
            # Processa coluna MQL? para criar colunas de contagem
            has_mql_col, lead_count_col, mql_count_col = process_mql_column_to_leads(df)
            
            if has_mql_col:
                # Usa as colunas de contagem criadas
                leads_cols = {'lead': lead_count_col, 'mql': mql_count_col}
                print(f"Usando colunas de contagem: {leads_cols}")
            else:
                # Tenta detectar colunas tradicionais
                leads_cols = detect_leads_columns(df)
                print(f"Colunas de leads detectadas: {leads_cols}")
            
            # Preenche campos em branco com 0 APÓS detectar as colunas
            df = fill_empty_fields_with_zero(df)
            
            # Preenche especificamente colunas de leads e MQLs com 0 se estiverem vazias
            df = fill_lead_mql_columns(df, leads_cols)
            
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
                        'creative_details': clean_dataframe_for_json(creative_stats.head(20)),
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
                    'raw_data': clean_dataframe_for_json(df.head(100))
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
