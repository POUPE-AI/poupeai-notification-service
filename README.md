# Notification Service

Serviço de notificações usando FastAPI.

## Estrutura do Projeto

```
poupeai-notification-service
├── requirements/
│   └── base.txt 
├── src/
│   ├── notification_service/
│   │   ├── __init__.py
│   │   ├── models.py      # Modelos do banco de dados
│   │   ├── router.py      # Endpoints
│   │   ├── schemas.py     # Modelos pydantic
│   │   ├── config.py      # Configurações locais
│   │   └── service.py     # Regras de négocio
│   │
│   ├── __init__.py
│   ├── config.py          # Configurações globais
│   ├── database.py        # Conexão com o banco de dados
│   └── main.py            
│
├── .gitignore
└──  README.md
```

## Instalação e Execução

### 1. Instalar dependências

```bash
pip install -r requirements\base.txt
```

### 2. Executar o serviço

```bash
uvicorn src.main:app --reload
```

### Health Check
- **GET** `/api/v1/health` - Verificar status

## Documentação

- Swagger: http://localhost:8000/api/v1/docs
