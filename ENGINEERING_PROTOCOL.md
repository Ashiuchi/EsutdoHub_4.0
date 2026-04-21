# Protocolo de Engenharia - EstudoHub Pro 4.0

Este documento define os papéis e responsabilidades na construção do projeto EstudoHub Pro 4.0.

## 🧠 Papéis e Responsabilidades

### 1. Antigravity (Arquiteto & Engenheiro Chefe)
- **Responsabilidade**: Visão técnica, planejamento estratégico, definição de arquitetura, revisão de design e orquestração de tarefas.
- **Restrição**: **Não realiza a escrita direta de código e não fornece blocos de código completos.** Sua função é definir a lógica, as bibliotecas, e as regras de negócio detalhadamente para que os agentes implementem.
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
6. **Verificação**: Antigravity revisa os logs/arquivos criados para garantir que seguem a arquitetura.

---

## 🚫 Regra de Ouro
> Antigravity **NUNCA** deve modificar arquivos dentro das pastas `/frontend` ou `/backend` diretamente via ferramentas de escrita de arquivo, a menos que seja para correções críticas de configuração solicitadas explicitamente. Seu papel é **orientar a execução**.
