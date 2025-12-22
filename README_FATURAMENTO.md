# 🚀 API Faturamento NFS-e

API REST para consulta de faturamento de notas fiscais eletrônicas com detalhamento mensal.

## 📋 Funcionalidades

- ✅ Autenticação por **Certificado Digital** ou **Login/Senha**
- ✅ Consulta por **ano completo** ou **mês específico**
- ✅ Detalhamento mensal do faturamento
- ✅ Considera **apenas notas autorizadas**
- ✅ Retorno em JSON estruturado

---

## 🔧 Instalação Local

```bash
# Clonar repositório
git clone https://github.com/seu-usuario/api-faturamento-nfse.git
cd api-faturamento-nfse

# Instalar dependências
pip install -r requirements_faturamento.txt

# Rodar API
python api_faturamento_nfse.py
```

A API estará em: `http://localhost:8000`

Documentação interativa: `http://localhost:8000/docs`

---

## 🌐 Deploy no Render.com

### 1. Criar repositório no GitHub

```bash
git init
git add .
git commit -m "API Faturamento NFS-e"
git remote add origin https://github.com/seu-usuario/api-faturamento-nfse.git
git push -u origin main
```

### 2. Deploy no Render

1. Acesse [render.com](https://render.com)
2. Conecte seu repositório GitHub
3. O Render detecta automaticamente o `render_faturamento.yaml`
4. Clique em "Deploy"

**URL da API:** `https://seu-app.onrender.com`

---

## 📡 Endpoint Principal

### `POST /consultar`

Consulta faturamento de NFS-e com detalhamento mensal.

---

## 🔐 Autenticação

### Método 1: Certificado Digital

```json
{
  "auth_method": 1,
  "cert_base64": "MIIOOwIBAzCCC...",
  "cert_senha": "senha123",
  "ano": 2025,
  "mes": 3
}
```

### Método 2: Login/Senha

```json
{
  "auth_method": 2,
  "cnpj": "00000000000000",
  "senha": "senha123",
  "ano": 2025,
  "mes": null
}
```

---

## 📊 Parâmetros

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `auth_method` | int | ✅ Sim | `1` = Certificado, `2` = Login/Senha |
| `ano` | int | ✅ Sim | Ano da competência (ex: 2025) |
| `mes` | int | ❌ Não | Mês 1-12 (null = ano inteiro) |
| `cert_base64` | string | Se auth=1 | Certificado A1 em base64 |
| `cert_senha` | string | Se auth=1 | Senha do certificado |
| `cnpj` | string | Se auth=2 | CNPJ para login |
| `senha` | string | Se auth=2 | Senha do sistema |

---

## 📥 Exemplos de Requisição

### Exemplo 1: Consultar mês específico (Março/2025)

```bash
curl -X POST https://sua-api.onrender.com/consultar \
  -H "Content-Type: application/json" \
  -d '{
    "auth_method": 1,
    "cert_base64": "MIIOOwIBAzCCC...",
    "cert_senha": "senha123",
    "ano": 2025,
    "mes": 3
  }'
```

**Resposta:**

```json
{
  "cnpj": "35191511000112",
  "razao_social": "KATIANE DOS SANTOS MACEDO SILVA",
  "ano": 2025,
  "mes_filtrado": 3,
  "quantidade_autorizadas": 15,
  "total_autorizado": 4072.00,
  "total_cancelado": 0.00,
  "detalhamento_por_mes": {
    "03/2025": 4072.00
  }
}
```

### Exemplo 2: Consultar ano inteiro (2025)

```bash
curl -X POST https://sua-api.onrender.com/consultar \
  -H "Content-Type: application/json" \
  -d '{
    "auth_method": 1,
    "cert_base64": "MIIOOwIBAzCCC...",
    "cert_senha": "senha123",
    "ano": 2025,
    "mes": null
  }'
```

**Resposta:**

```json
{
  "cnpj": "35191511000112",
  "razao_social": "KATIANE DOS SANTOS MACEDO SILVA",
  "ano": 2025,
  "mes_filtrado": null,
  "quantidade_autorizadas": 150,
  "total_autorizado": 45678.90,
  "total_cancelado": 0.00,
  "detalhamento_por_mes": {
    "01/2025": 3500.00,
    "02/2025": 4200.00,
    "03/2025": 4072.00,
    "04/2025": 3800.00,
    "05/2025": 4100.00,
    "06/2025": 3900.00,
    "07/2025": 4300.00,
    "08/2025": 3700.00,
    "09/2025": 4000.00,
    "10/2025": 3600.00,
    "11/2025": 3506.90,
    "12/2025": 3000.00
  }
}
```

### Exemplo 3: Python

```python
import requests

response = requests.post(
    "https://sua-api.onrender.com/consultar",
    json={
        "auth_method": 1,
        "cert_base64": "MIIOOwIBAzCCC...",
        "cert_senha": "senha123",
        "ano": 2025,
        "mes": 3
    }
)

data = response.json()
print(f"Faturamento total: R$ {data['total_autorizado']:,.2f}")
print(f"Detalhamento: {data['detalhamento_por_mes']}")
```

### Exemplo 4: JavaScript

```javascript
const response = await fetch('https://sua-api.onrender.com/consultar', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    auth_method: 1,
    cert_base64: 'MIIOOwIBAzCCC...',
    cert_senha: 'senha123',
    ano: 2025,
    mes: 3
  })
});

const data = await response.json();
console.log('Faturamento:', data.total_autorizado);
console.log('Por mês:', data.detalhamento_por_mes);
```

---

## 🎯 Regras de Negócio

### 1. Filtro por Mês

- **`mes = null`**: Busca **ANO INTEIRO** (01/2025 até 12/2025)
- **`mes = 3`**: Busca **APENAS MARÇO** (03/2025)

### 2. Navegação de Páginas

Quando você solicita março/2025 em dezembro/2025:

```
Página 1: 12/2025 → IGNORA
Página 5: 03/2025 → ✅ CONSIDERA
Página 6: 02/2025 → ❌ PARA (passou de março)
```

### 3. Apenas Notas Autorizadas

- **Status AUTORIZADA**: Contabiliza no faturamento
- **Status CANCELADA**: Ignora (não soma)
- **total_cancelado**: Sempre retorna 0.00

### 4. Detalhamento por Mês

- **Mês filtrado**: Retorna apenas aquele mês
  ```json
  "detalhamento_por_mes": {
    "03/2025": 4072.00
  }
  ```

- **Ano inteiro**: Retorna todos os 12 meses (com zeros)
  ```json
  "detalhamento_por_mes": {
    "01/2025": 3500.00,
    "02/2025": 0.00,
    "03/2025": 4072.00,
    ...
  }
  ```

---

## 🔍 Outros Endpoints

### `GET /`
Informações da API

```bash
curl https://sua-api.onrender.com/
```

### `GET /health`
Health check

```bash
curl https://sua-api.onrender.com/health
```

### `GET /docs`
Documentação interativa (Swagger UI)

```
https://sua-api.onrender.com/docs
```

---

## ⚠️ Erros Comuns

### 400 - Bad Request

```json
{
  "detail": "Campo obrigatório: cert_base64"
}
```

**Solução:** Verifique se todos os campos obrigatórios foram enviados.

### 401 - Unauthorized

```json
{
  "detail": "Credenciais inválidas"
}
```

**Solução:** Verifique certificado/senha ou CNPJ/senha.

### 500 - Internal Server Error

```json
{
  "detail": "Erro ao consultar página 5: timeout"
}
```

**Solução:** Tente novamente. Pode ser instabilidade do portal NFS-e.

---

## 📝 Formato de Entrada do Mês

A API aceita múltiplos formatos:

- `1` → Janeiro
- `01` → Janeiro
- `"1"` → Janeiro
- `"01"` → Janeiro
- `12` → Dezembro

---

## 🛠️ Estrutura do Projeto

```
api-faturamento-nfse/
├── api_faturamento_nfse.py      # Código principal da API
├── requirements_faturamento.txt # Dependências
├── render_faturamento.yaml      # Configuração Render
└── README.md                    # Este arquivo
```

---

## 📄 Licença

MIT License

---

## 🤝 Contribuições

Pull requests são bem-vindos!

---

## 📧 Suporte

Dúvidas? Abra uma issue no GitHub.
