"""
API CONSULTA FATURAMENTO NFS-E
Endpoint para consulta de notas fiscais com detalhamento mensal
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict
import requests
import base64
import tempfile
import os
import re
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

# ============================================
# CONFIGURAÇÃO DA API
# ============================================

app = FastAPI(
    title="API Faturamento NFS-e",
    description="Consulta de faturamento com detalhamento mensal",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# MODELOS
# ============================================

class ConsultaRequest(BaseModel):
    """Modelo de requisição"""
    auth_method: int = Field(..., description="1=Certificado, 2=Login/Senha")
    ano: int = Field(..., description="Ano da competência (ex: 2025)")
    mes: Optional[int] = Field(None, description="Mês 1-12 (opcional, vazio=ano inteiro)")
    
    # Certificado
    cert_base64: Optional[str] = None
    cert_senha: Optional[str] = None
    
    # Login
    cnpj: Optional[str] = None
    senha: Optional[str] = None
    
    @validator('auth_method')
    def validar_auth(cls, v):
        if v not in [1, 2]:
            raise ValueError('auth_method deve ser 1 ou 2')
        return v
    
    @validator('ano')
    def validar_ano(cls, v):
        if v < 2000 or v > 2100:
            raise ValueError('Ano inválido')
        return v
    
    @validator('mes')
    def validar_mes(cls, v):
        if v is not None and (v < 1 or v > 12):
            raise ValueError('Mês deve ser entre 1 e 12')
        return v


class ConsultaResponse(BaseModel):
    """Modelo de resposta"""
    cnpj: str
    razao_social: str
    ano: int
    mes_filtrado: Optional[int]
    quantidade_autorizadas: int
    total_autorizado: float
    total_cancelado: float
    detalhamento_por_mes: Dict[str, float]


# ============================================
# AUTENTICAÇÃO
# ============================================

def autenticar_certificado(cert_base64: str, senha: str) -> requests.Session:
    """Autenticação via certificado digital"""
    try:
        cert_data = base64.b64decode(cert_base64)
        private_key, certificate, ca_certs = pkcs12.load_key_and_certificates(
            cert_data, senha.encode(), backend=default_backend()
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao carregar certificado: {str(e)}")
    
    temp_dir = tempfile.mkdtemp()
    cert_path = os.path.join(temp_dir, 'cert.pem')
    key_path = os.path.join(temp_dir, 'key.pem')
    
    with open(cert_path, 'wb') as f:
        f.write(certificate.public_bytes(serialization.Encoding.PEM))
    with open(key_path, 'wb') as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    session.cert = (cert_path, key_path)
    session.temp_cert_path = cert_path
    session.temp_key_path = key_path
    session.temp_dir = temp_dir
    
    try:
        resp = session.get("https://www.nfse.gov.br/EmissorNacional/Certificado", timeout=30)
        if 'Emissor' not in session.cookies:
            raise HTTPException(status_code=401, detail="Falha na autenticação")
        return session
    except Exception as e:
        limpar_temp(session)
        raise HTTPException(status_code=401, detail=str(e))


def autenticar_login(cnpj: str, senha: str) -> requests.Session:
    """Autenticação via login/senha"""
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    try:
        base_url = "https://www.nfse.gov.br"
        resp = session.get(f"{base_url}/EmissorNacional", timeout=30)
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        token_input = soup.find('input', {'name': '__RequestVerificationToken'})
        token = token_input.get('value', '') if token_input else ''
        
        cnpj_limpo = re.sub(r'[^\d]', '', cnpj)
        
        resp = session.post(
            f"{base_url}/EmissorNacional/Login?ReturnUrl=%2FEmissorNacional",
            data={'__RequestVerificationToken': token, 'Inscricao': cnpj_limpo, 'Senha': senha},
            allow_redirects=True,
            timeout=30
        )
        
        if 'Emissor' not in session.cookies:
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
        
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


def limpar_temp(session):
    """Limpa arquivos temporários"""
    try:
        if hasattr(session, 'temp_cert_path'): os.remove(session.temp_cert_path)
        if hasattr(session, 'temp_key_path'): os.remove(session.temp_key_path)
        if hasattr(session, 'temp_dir'): os.rmdir(session.temp_dir)
    except: pass


# ============================================
# SCRAPING
# ============================================

def processar_pagina(html: str, ano: int, mes_filtro: Optional[int]):
    """Processa uma página HTML e extrai notas"""
    notas = []
    continuar = True
    
    soup = BeautifulSoup(html, 'html.parser')
    tbody = soup.find('tbody')
    if not tbody: return notas, False
    
    for linha in tbody.find_all('tr'):
        try:
            td_comp = linha.find('td', class_='td-competencia')
            if not td_comp: continue
            
            match = re.search(r'(\d{2})/(\d{4})', td_comp.get_text(strip=True))
            if not match: continue
            
            mes_nota = int(match.group(1))
            ano_nota = int(match.group(2))
            
            # Se ano diferente, para
            if ano_nota != ano:
                continuar = False
                break
            
            # Se tem filtro de mês
            if mes_filtro is not None:
                # Se passou do mês filtrado (notas mais antigas), para
                if mes_nota < mes_filtro:
                    continuar = False
                    break
                # Se não é o mês filtrado, ignora
                if mes_nota != mes_filtro:
                    continue
            
            # Extrai status
            status_cod = linha.get('data-situacao', '')
            if 'GERADA' not in status_cod:  # Só considera autorizadas
                continue
            
            # Extrai valor
            td_valor = linha.find('td', class_='td-valor')
            if not td_valor: continue
            
            valor_txt = td_valor.get_text(strip=True)
            valor = float(valor_txt.replace('.', '').replace(',', '.'))
            
            notas.append({
                'mes': mes_nota,
                'ano': ano_nota,
                'valor': valor,
                'status': 'Autorizada'
            })
            
        except: continue
    
    return notas, continuar


def consultar_notas(session: requests.Session, ano: int, mes_filtro: Optional[int]):
    """Consulta todas as notas do período"""
    todas_notas = []
    pagina = 1
    base_url = "https://www.nfse.gov.br/EmissorNacional/Notas/Emitidas"
    
    while True:
        url = base_url if pagina == 1 else f"{base_url}?pg={pagina}"
        
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200: break
            
            notas, continuar = processar_pagina(resp.text, ano, mes_filtro)
            todas_notas.extend(notas)
            
            if not continuar: break
            
            # Verifica se tem próxima página
            soup = BeautifulSoup(resp.text, 'html.parser')
            pag_div = soup.find('div', class_='paginacao')
            if not pag_div or not pag_div.find('a', title='Próxima'): break
            
            pagina += 1
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao consultar página {pagina}: {str(e)}")
    
    return todas_notas


def extrair_contribuinte(session: requests.Session):
    """Extrai dados do contribuinte"""
    try:
        resp = session.get("https://www.nfse.gov.br/EmissorNacional/Notas/Emitidas", timeout=30)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        perfil = soup.find('li', class_='dropdown perfil')
        if perfil:
            header = perfil.find('li', class_='dropdown-header')
            if header:
                texto = header.get_text()
                linhas = texto.strip().split('\n')
                nome = linhas[0].strip() if linhas else 'N/A'
                
                cnpj_span = header.find('span', class_='cnpj')
                cnpj = cnpj_span.get_text(strip=True) if cnpj_span else 'N/A'
                
                return cnpj, nome
        
        return 'N/A', 'N/A'
    except:
        return 'N/A', 'N/A'


def totalizar_por_mes(notas: list, ano: int, mes_filtro: Optional[int]):
    """Totaliza valores por mês"""
    # Inicializa todos os meses do ano com zero
    meses = {}
    if mes_filtro is not None:
        # Apenas o mês filtrado
        meses[f"{mes_filtro:02d}/{ano}"] = 0.0
    else:
        # Ano inteiro
        for m in range(1, 13):
            meses[f"{m:02d}/{ano}"] = 0.0
    
    # Soma valores por mês
    for nota in notas:
        chave = f"{nota['mes']:02d}/{nota['ano']}"
        if chave in meses:
            meses[chave] += nota['valor']
    
    return meses


# ============================================
# ENDPOINTS
# ============================================

@app.get("/")
def root():
    """Informações da API"""
    return {
        "api": "Faturamento NFS-e",
        "version": "1.0.0",
        "endpoints": {
            "POST /consultar": "Consulta faturamento",
            "GET /health": "Status da API",
            "GET /docs": "Documentação interativa"
        }
    }


@app.get("/health")
def health():
    """Health check"""
    return {"status": "ok"}


@app.post("/consultar", response_model=ConsultaResponse)
def consultar(req: ConsultaRequest):
    """
    Consulta faturamento de NFS-e com detalhamento mensal
    
    Parâmetros obrigatórios:
    - auth_method: 1 (certificado) ou 2 (login/senha)
    - ano: Ano da competência
    
    Parâmetro opcional:
    - mes: 1-12 (vazio = ano inteiro, preenchido = apenas aquele mês)
    
    Retorna faturamento total e detalhamento por mês
    """
    
    session = None
    
    try:
        # Validação de campos obrigatórios
        if req.auth_method == 1:
            if not req.cert_base64:
                raise HTTPException(status_code=400, detail="Campo obrigatório: cert_base64")
            if not req.cert_senha:
                raise HTTPException(status_code=400, detail="Campo obrigatório: cert_senha")
            session = autenticar_certificado(req.cert_base64, req.cert_senha)
        
        elif req.auth_method == 2:
            if not req.cnpj:
                raise HTTPException(status_code=400, detail="Campo obrigatório: cnpj")
            if not req.senha:
                raise HTTPException(status_code=400, detail="Campo obrigatório: senha")
            session = autenticar_login(req.cnpj, req.senha)
        
        # Extrai dados do contribuinte
        cnpj, razao_social = extrair_contribuinte(session)
        
        # Consulta notas
        notas = consultar_notas(session, req.ano, req.mes)
        
        # Totaliza
        total_autorizado = sum(n['valor'] for n in notas)
        qtd_autorizadas = len(notas)
        
        # Detalhamento por mês
        detalhamento = totalizar_por_mes(notas, req.ano, req.mes)
        
        # Monta resposta
        return ConsultaResponse(
            cnpj=cnpj,
            razao_social=razao_social,
            ano=req.ano,
            mes_filtrado=req.mes,
            quantidade_autorizadas=qtd_autorizadas,
            total_autorizado=total_autorizado,
            total_cancelado=0.0,  # Canceladas não são contabilizadas
            detalhamento_por_mes=detalhamento
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro inesperado: {str(e)}")
    
    finally:
        if session:
            limpar_temp(session)


# ============================================
# EXECUÇÃO LOCAL
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
