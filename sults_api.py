import requests
import os
from typing import Dict, List, Optional
from datetime import datetime

class SultsAPIClient:
    """
    Cliente para integração com a API da SULTS
    
    Documentação: https://developers.sults.com.br/
    
    IMPORTANTE: Ajuste a BASE_URL e o formato de autenticação conforme
    a documentação oficial da API da SULTS.
    
    Endpoints disponíveis na documentação:
    - Unidades
    - Expansão
    - Chamados
    - Checklist
    - Compras
    - Implantação
    - Projetos
    """
    
    # URL base da API SULTS conforme documentação: https://developers.sults.com.br/
    # Documentação oficial indica: https://developer.sults.com.br/api/v1
    BASE_URL = os.getenv('SULTS_API_BASE_URL', "https://developer.sults.com.br/api/v1")
    TOKEN = os.getenv('SULTS_API_TOKEN', 'O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=')
    
    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None):
        self.token = token or self.TOKEN
        self.BASE_URL = base_url or self.BASE_URL
        # TODO: Ajustar formato de autenticação conforme documentação
        # Pode ser Bearer, Basic Auth, ou outro formato
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    @staticmethod
    def test_connection(base_url: str, token: str, endpoint: str = "/chamados") -> Dict:
        """Método estático para testar conexão com diferentes configurações"""
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        url = f"{base_url}{endpoint}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            return {
                'success': response.status_code < 400,
                'status_code': response.status_code,
                'url': url,
                'message': f"Status {response.status_code}" if response.status_code < 400 else f"Erro {response.status_code}"
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': None,
                'url': url,
                'message': str(e)
            }
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """Faz uma requisição HTTP para a API da SULTS"""
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg = f"Erro HTTP {e.response.status_code} na requisição à API SULTS"
            if e.response.status_code == 404:
                error_msg += f"\nEndpoint não encontrado: {url}"
                error_msg += "\nVerifique a URL base e os endpoints na documentação: https://developers.sults.com.br/"
            elif e.response.status_code == 401:
                error_msg += "\nToken de autenticação inválido ou expirado"
            elif e.response.status_code == 403:
                error_msg += "\nAcesso negado. Verifique as permissões do token"
            
            if hasattr(e.response, 'text'):
                error_msg += f"\nResposta do servidor: {e.response.text[:200]}"
            
            print(error_msg)
            raise Exception(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"Erro na requisição à API SULTS: {str(e)}"
            print(error_msg)
            raise Exception(error_msg) from e
    
    def get_chamados(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Busca chamados da SULTS - endpoint conforme documentação: /chamados"""
        endpoint = "/chamados"
        params = filters or {}
        return self._make_request('GET', endpoint, params=params)
    
    def get_leads(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Busca leads da SULTS - endpoint conforme documentação: /leads"""
        endpoint = "/leads"
        params = filters or {}
        return self._make_request('GET', endpoint, params=params)
    
    def get_chamado_by_id(self, chamado_id: int) -> Dict:
        """Busca um chamado específico por ID"""
        endpoint = f"/chamados/{chamado_id}"
        return self._make_request('GET', endpoint)
    
    def get_lead_by_id(self, lead_id: int) -> Dict:
        """Busca um lead específico por ID"""
        endpoint = f"/leads/{lead_id}"
        return self._make_request('GET', endpoint)
    
    def get_unidades(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Busca unidades da SULTS"""
        endpoint = "/unidades"
        params = filters or {}
        return self._make_request('GET', endpoint, params=params)
    
    def get_projetos(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Busca projetos da SULTS"""
        endpoint = "/projetos"
        params = filters or {}
        return self._make_request('GET', endpoint, params=params)
    
    def get_leads_status(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict:
        """Busca status de leads em um período"""
        filters = {}
        if date_from:
            filters['data_inicio'] = date_from
        if date_to:
            filters['data_fim'] = date_to
        
        # Usar endpoint /leads conforme documentação
        try:
            leads = self.get_leads(filters=filters)
        except:
            # Fallback para chamados se /leads não existir
            leads = self.get_chamados(filters=filters)
        
        # Processar estatísticas
        total = len(leads)
        status_count = {}
        for lead in leads:
            status = lead.get('status', 'Sem Status')
            status_count[status] = status_count.get(status, 0) + 1
        
        return {
            'total': total,
            'por_status': status_count,
            'leads': leads
        }
    
    def get_leads_by_status(self, status_filter: Optional[str] = None) -> Dict:
        """
        Busca leads organizados por status (abertos, perdidos, etc.)
        
        Args:
            status_filter: Filtro opcional de status ('aberto', 'perdido', 'ganho', etc.)
        """
        # Usar endpoint /leads conforme documentação
        try:
            leads_data = self.get_leads()
        except:
            # Fallback para chamados se /leads não existir
            leads_data = self.get_chamados()
        
        # Categorizar leads por status
        leads_abertos = []
        leads_perdidos = []
        leads_ganhos = []
        leads_outros = []
        
        status_keywords = {
            'aberto': ['aberto', 'em andamento', 'pendente', 'novo', 'em análise'],
            'perdido': ['perdido', 'cancelado', 'desistiu', 'no show', 'falhou'],
            'ganho': ['ganho', 'won', 'fechado', 'concluído', 'concluido', 'cliente', 'converted']
        }
        
        for lead in leads_data:
            status = str(lead.get('status', '')).lower()
            
            if any(keyword in status for keyword in status_keywords['ganho']):
                leads_ganhos.append(lead)
            elif any(keyword in status for keyword in status_keywords['perdido']):
                leads_perdidos.append(lead)
            elif any(keyword in status for keyword in status_keywords['aberto']):
                leads_abertos.append(lead)
            else:
                leads_outros.append(lead)
        
        # Aplicar filtro se especificado
        if status_filter:
            status_lower = status_filter.lower()
            if status_lower == 'aberto':
                return {'leads': leads_abertos, 'total': len(leads_abertos), 'status': 'Aberto'}
            elif status_lower == 'perdido':
                return {'leads': leads_perdidos, 'total': len(leads_perdidos), 'status': 'Perdido'}
            elif status_lower == 'ganho':
                return {'leads': leads_ganhos, 'total': len(leads_ganhos), 'status': 'Ganho'}
        
        return {
            'abertos': {
                'leads': leads_abertos,
                'total': len(leads_abertos)
            },
            'perdidos': {
                'leads': leads_perdidos,
                'total': len(leads_perdidos)
            },
            'ganhos': {
                'leads': leads_ganhos,
                'total': len(leads_ganhos)
            },
            'outros': {
                'leads': leads_outros,
                'total': len(leads_outros)
            },
            'total_geral': len(leads_data)
        }
    
    def sync_lead_with_sults(self, lead_data: Dict) -> Dict:
        """Sincroniza um lead com a SULTS (cria ou atualiza lead)"""
        endpoint = "/leads"
        
        # Mapear dados do lead para formato da SULTS
        sults_data = {
            'nome': lead_data.get('nome', ''),
            'email': lead_data.get('email', ''),
            'telefone': lead_data.get('telefone', ''),
            'origem': lead_data.get('source', 'organico'),
            'status': lead_data.get('status', 'Novo'),
            'observacoes': lead_data.get('observacoes', '')
        }
        
        return self._make_request('POST', endpoint, data=sults_data)

