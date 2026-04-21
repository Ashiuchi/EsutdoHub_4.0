from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.pdf_service import PDFService
from app.services.ai_service import AIService
import os
import shutil

router = APIRouter()
ai_service = AIService()

@router.post('/upload')
async def upload_edital(file: UploadFile = File(...)):
    # 1. Salvar arquivo temporariamente no WSL
    temp_path = f'temp_{file.filename}'
    with open(temp_path, 'wb') as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 2. Converter PDF para Markdown com o 'olho' do sistema
        md_content = PDFService.to_markdown(temp_path)

        # 3. Extrair dados estruturados com o 'cérebro' Gemini
        result = await ai_service.extract_edital_data(md_content)

        # 4. Debug: Salvar JSON para conferência (conforme pedido pelo Arquiteto)
        os.makedirs('debug', exist_ok=True)
        with open(f'debug/{file.filename}.json', 'w', encoding='utf-8') as f:
            f.write(result.model_dump_json(indent=2))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Limpar rastro temporário
        if os.path.exists(temp_path):
            os.remove(temp_path)
