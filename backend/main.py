from app.logging_config import setup_logging

# Initialize logging before anything else
setup_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router
from app.core.config import settings
import uvicorn

app = FastAPI(title='EstudoHub Pro API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Incluir as novas rotas de processamento
app.include_router(api_router, prefix='/api/v1')

@app.get('/health')
async def health_check():
    return {'status': 'healthy', 'service': 'backend'}

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
