from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.pdf_service import PDFService
from app.services.ai_service import AIService
import os
import shutil

router = APIRouter()
ai_service = AIService()

@router.post('/upload')
async def upload_edital(file: UploadFile = File(...)):
    """
    Endpoint principal para upload e extração de dados de editais.
    """
    temp_path = f'temp_{file.filename}'
    with open(temp_path, 'wb') as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Converter PDF para Markdown
        md_content = PDFService.to_markdown(temp_path)

        # Extrair dados estruturados (Failover local/cloud automático)
        result = await ai_service.extract_edital_data(md_content)

        # Salvamento de debug (Útil para validação técnica)
        os.makedirs('debug', exist_ok=True)
        debug_file = f'debug/{file.filename}.json'
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(result.model_dump_json(indent=2))
        
        return result
    except Exception as e:
        # Log detalhado no servidor, erro genérico para o cliente por segurança
        print(f"Erro no processamento do edital: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Falha ao processar o edital: {str(e)}"
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
