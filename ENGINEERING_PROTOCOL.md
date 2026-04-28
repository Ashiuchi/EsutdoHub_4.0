# Protocolo de Engenharia - EstudoHub Pro 4.0

Este documento define os papéis e responsabilidades na construção do projeto EstudoHub Pro 4.0.

## 🧠 Papéis e Responsabilidades

### 1. Antigravity (Arquiteto & Engenheiro Chefe)
- **Responsabilidade**: Visão técnica, planejamento estratégico, definição de arquitetura, revisão de design e orquestração de tarefas.
- **Restrição**: **Não realiza a escrita direta de código e não fornece blocos de código completos.** Sua função é definir a lógica, as bibliotecas, e as regras de negócio detalhadamente para que os agentes implementem.
- **Regra de Ouro**: **NUNCA cria scripts utilitários ou de teste ad-hoc.** Toda validação, ingestão ou extração em massa deve ser feita através da infraestrutura e dos pipelines oficiais do projeto.
- **Entregas**: 
    - Planos de Implementação (`implementation_plan.md`).
    - Checklist de Tarefas (`task.md`).
    - Diretrizes lógicas e ordens de execução detalhadas.

### 2. Agentes de Campo (Claude Code / Gemini CLI / Cursor)
- **Responsabilidade**: Execução técnica, escrita de código, criação de arquivos e refatoração.
- **Input**: Recebem as diretrizes e blocos de código validados pelo Antigravity.

### 3. Usuário (Alessandro)
- **Responsabilidade**: Validação final, execução de comandos privilegiados e ponte de comunicação entre os agentes.

---

## 🛠️ Workflow de Trabalho

1. **Planejamento**: Antigravity pesquisa e cria um `implementation_plan.md`.
2. **Aprovação**: O Usuário revisa e aprova o plano.
3. **Orquestração**: Antigravity quebra o plano em tarefas no `task.md`.
4. **Instrução**: Para cada tarefa, Antigravity fornece o comando exato ou o código formatado.
5. **Execução**: O Agente de Campo (Claude/Gemini CLI) executa a instrução.
6. **Validação via Pipeline**: Testes, extrações em massa ou processamentos pesados devem ser realizados exclusivamente via Pipeline de Produção (CI/CD), garantindo que o ambiente de teste reflita fielmente o ambiente de produção e evitando redundância de debug.
7. **Verificação**: Antigravity revisa os logs/arquivos criados para garantir que seguem a arquitetura.

---

## 🎨 Identidade Visual & Branding

O EstudoHub Pro 4.0 segue uma paleta rigorosa baseada na logo oficial:
1. **Cores Primárias**:
    - `Teal Principal`: `#007F8E` (Acentos, botões, links).
    - `Grafite Base`: `#2D2D2D` (Fundo de cards, sidebar).
    - `Off-white`: `#E0E0E0` (Texto principal, ícones secundários).
2. **Backgrounds**: Utilizar as imagens da pasta `/static/images` sempre com um **overlay de gradiente escuro** para garantir legibilidade (ex: `linear-gradient(to bottom, transparent, #030712)`).
3. **Layout**: Priorizar navegação lateral (Sidebar) para aplicações de dashboard e rede social.

---

## 🐳 Gerenciamento de Ambiente & Docker

Para garantir a consistência entre diferentes locais de trabalho, utilizamos uma estratégia de múltiplos arquivos Compose:

1. **`docker-compose.yml` (Padrão/Home)**:
    - Destinado ao ambiente principal com hardware completo.
    - Requisitos: Drive `K:\` mapeado e GPU NVIDIA disponível para o Ollama.
2. **`docker-compose.dev.yml` (Local/Portátil)**:
    - Destinado a máquinas de desenvolvimento sem hardware específico.
    - Ajustes: Mapeia `/storage_k` para uma pasta local (`./storage_k`) e desativa a exigência de GPU (roda Ollama via CPU).

**Comando para subir no ambiente Local**:
`docker-compose -f docker-compose.dev.yml up -d`

---

1. **Stack Unificado**: O arquivo `docker-compose.all.yml` é a fonte da verdade, unindo a App (Backend, Frontend, DB, Redis, Ollama) com as ferramentas de suporte (Jenkins, SonarQube, Vault).
2. **Entry Point**: O `Makefile` na raiz do projeto deve ser utilizado para todas as operações de infraestrutura.
    - `make up`: Sobe o stack completo unificado.
    - `make down`: Derruba todos os serviços.
3. **Persistência**: Volumes Docker são utilizados para persistir dados de banco, logs do Sonar e jobs do Jenkins.

---

## 🚫 Regra de Ouro
> Antigravity **NUNCA** deve modificar arquivos dentro das pastas `/frontend` ou `/backend` diretamente via ferramentas de escrita de arquivo, a menos que seja para correções críticas de configuração solicitadas explicitamente. Seu papel é **orientar a execução**.
