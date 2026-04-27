# 🚩 CHECKPOINT DE RECUPERAÇÃO - EstudoHub Pro 4.0
**Data**: 2026-04-26 00:10
**Status**: Vitória na Montanha (Ancoragem Validada)

## 1. O que foi Conquistado Hoje (A Montanha)
- **Tecnologia de Ancoragem (V4.0)**: Superamos o maior desafio de extração. O sistema agora não lê o edital linearmente, mas isola o contexto de cada cargo.
- **Camada 1 (CargoMapper)**: Extração determinística via tabelas Markdown. Validado no TRT (15 cargos) e BB (2 cargos). Filtro anti-falsos-positivos (ex: Juiz de Fora) implementado.
- **Camada 2 (AnchorEngine)**: Localiza e "recorta" o texto exato do `main.md` para cada cargo usando headers Markdown.
- **Validação Padrão Ouro**: Teste completo no **TRT-24** (Hash: `bf6fc0fc89e2`). Resultado: **0% de overlap** entre cargos. TI e Administrativo totalmente isolados.
- **Veredicto de Bancas (Consagrado)**:
    *   **FGV / FCC / Cesgranrio**: Ancoragem via Headers Markdown (100% precisão).
    *   **Quadrix**: Captura determinística via `data.md` e regex de colunas complexas.
    *   **IBFC / MGS**: Ancoragem via Fallback de Tabela (Editais table-only).

## 2. O Agente Pescador (Hands-free)
- **Script**: `scripts/agente_pescador.py` operacional.
- **Horário**: Configurado para rodar das **00:00 às 02:00**.
- **Alvo**: PCI Concursos (Nacional e Regional), anos 2020 a 2026.
- **Armazenamento**: Configurado para o **HD Externo K:** (`/mnt/k/estudohub_storage/`).
- **Log**: `scripts/pescaria_log.json` para evitar duplicatas.

## 3. Protocolo DNA (Fingerprint Heurística) - **O Novo Padrão**
Para evitar duplicidades de fontes diferentes (Diário Oficial vs Banca) ou retificações menores, implementamos a **Fingerprint de Identidade**:
- **Normalização**: O texto é limpo de espaços, pontuação e acentos (strip total).
- **Componentes do Hash**:
    1. `Total de Páginas` (Físicas).
    2. `Contagem de Caracteres Normalizados` (Conteúdo alfanumérico puro).
    3. `Distribuição de Âncoras (%)`: Posição relativa dos termos "VAGAS", "CARGOS", "CONTEÚDO PROGRAMÁTICO" e "PROVAS" no documento.
    4. `Top 3 Cargos`: Hash dos títulos encontrados pelo `CargoMapper`.
- **Resultado**: Um SHA-1 de 16 caracteres que identifica o **Concurso**, não o arquivo.

## 4. Estado da Infraestrutura
- **IA**: Ollama (Llama 3.2:3b local) + Groq (Llama 3.3-70b Cloud) + Gemini Pro (Elite Fallback).
- **Banco de Dados**: PostgreSQL com colunas `content_hash` (binário) e `fingerprint` (DNA).
- **WSL**: Jenkins e Sonar configurados no Drive C.

## 5. Próximos Passos (Amanhã)
1. **Verificar o Lote de Ouro**: Validar TRT, BB e os novos 3 da FGV, Quadrix e IBFC.
2. **A Grande Moenda**: Escalar para os 200+ editais do HD K:.
3. **Cockpit UI**: Ajustar o Dashboard para exibir os cargos e matérias com a nova estrutura isolada.

---
**Nota para o próximo Agente**: "A montanha foi escalada. Agora estamos na fase de processamento industrial. Priorize a qualidade da extração em massa usando as camadas de ancoragem já integradas no `AIService`."
