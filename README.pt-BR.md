<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img alt="carimbo: memória de decisões para times de agentes de IA" src="assets/banner-light.svg" width="100%">
  </picture>
</p>

<p align="center"><a href="README.md">Read in English</a></p>

O **carimbo** é uma memória compartilhada para times de agentes de IA que guarda só o que foi decidido. Cada decisão é uma nota em Markdown num repositório git, com quem disse e quando. Quando a decisão muda, a versão nova é carimbada e a antiga vai para `archive/`. Toda sessão de agente começa do mesmo `INDEX.md`, e um hook avisa cada sessão do que outra carimbou enquanto ela trabalhava.

É um pacote Python pequeno, sem dependências. As notas são Markdown puro, que abre no Obsidian, e o git cuida do histórico e da sincronização.

## Por quê

Rode três sessões do Claude Code e uns agentes de chat ao mesmo tempo e a mesma coisa acontece sempre. Alguém muda o lançamento de quinta para sexta num chat. A sessão que está fazendo a landing page nunca fica sabendo e publica quinta. O histórico de chat é de cada sessão, e as ferramentas de memória que gravam tudo deixam difícil saber qual das cinco versões de um fato vale agora.

O carimbo responde uma pergunta para todo agente: **o que está decidido agora, quem decidiu e o que isso substituiu?** Ele não tenta lembrar de tudo. Conversa, pesquisa e rascunho ficam em outro lugar; só entram decisões, a situação de cada frente e as perguntas que esperam uma pessoa.

Nasceu na [BOMA](https://www.instagram.com/weare_boma/), empresa de eventos de música de São Paulo, onde um time de agentes e várias sessões de código em paralelo planejam e vendem os nossos festivais. É a memória do nosso time desde outubro de 2026.

## Como funciona

<p align="center"><img alt="sessões carimbam decisões, a versão antiga vai para o arquivo, o INDEX.md alimenta todas as sessões, um hook avisa o que mudou" src="assets/how-it-works.svg" width="100%"></p>

- **Uma nota por chave.** `acme.launch.date` mora em `acme/decisions/launch-date.md`. Nunca existe uma segunda cópia para divergir.
- **Substitui, não edita.** `carimbo set` numa chave que já existe move a nota antiga para `acme/archive/launch-date--2026-11-24-183000.md` e liga as duas; a cadeia de mudanças aparece no git e no grafo do Obsidian.
- **Quem e quando.** `--source` grava quem disse e quando; `--discarded` grava as opções que perderam e por quê, para ninguém reabrir sem fato novo.
- **Um commit por carimbo.** A gravação trava, puxa, faz o commit e o push; várias máquinas dividem o mesmo cofre por qualquer remoto git.
- **O índice é gerado.** `INDEX.md` (completo) e `INDEX-SHORT.md` (uma linha por chave, para contexto pequeno) são refeitos a cada carimbo.
- **Os hooks sincronizam as sessões.** Ao abrir, o agente recebe o estado atual do projeto dele. Antes de cada mensagem, recebe só o que outras sessões carimbaram desde a última.
- **Dado pessoal é recusado.** E-mail, telefone e CPF são barrados na gravação e por um hook de pre-commit, porque o cofre vai para remotos, servidores e modelos.

## Começar

```bash
uv tool install git+https://github.com/MarcoFanganielloBessa/carimbo   # ou: pipx install git+https://...
carimbo init ~/carimbo --timezone America/Sao_Paulo
export CARIMBO_VAULT=~/carimbo
```

```bash
carimbo set acme.launch.date "Venda abre quinta 03/12 às 10h." \
  --source "Ana na call de lançamento, 24/11 18h30" \
  --discarded "sexta 27/11: mesmo dia da venda do concorrente"

carimbo set acme.launch.date "Venda abre sexta 04/12 às 10h." --source "Ana, 25/11 09h10"
carimbo set acme.ads.budget "Subir a verba diária depois do primeiro relatório de vendas?" --type pending

carimbo show acme.
```

```
### Waiting for a decision
- `acme.ads.budget` (2026-11-25): Subir a verba diária depois do primeiro relatório de vendas?

### Decided
- `acme.launch.date` (2026-11-25): Venda abre sexta 04/12 às 10h. · source: Ana, 25/11 09h10
```

Com um remoto (`git -C ~/carimbo remote add origin …`), cada carimbo sobe sozinho. Para um cofre de verdade, use um repositório privado.

## Comandos

| Comando | O que faz |
|---|---|
| `carimbo init [pasta] [--timezone TZ]` | Cria o cofre: repo git, `carimbo.toml`, `agents/` e a checagem de pre-commit |
| `carimbo set CHAVE TEXTO [--type decision\|status\|pending] [--source S] [--discarded D] [--links k1,k2]` | Carimba uma nota; a anterior vai para `archive/` |
| `carimbo end CHAVE MOTIVO` | Tira a chave do estado atual, com o motivo |
| `carimbo show [PREFIXO] [--short]` | Estado atual: esperando, decidido e situação |
| `carimbo history CHAVE` | Todas as versões de uma chave, da mais antiga para a mais nova |
| `carimbo approve` | Carimba um bloco JSON ` ```carimbo ` lido do stdin (o agente propõe, a pessoa aprova) |
| `carimbo check [--staged] [ARQUIVOS]` | Recusa dado pessoal nas notas; instalado como pre-commit do cofre |
| `carimbo hook session-start\|prompt` | Hooks do Claude Code |
| `carimbo index` | Refaz `INDEX.md` e `INDEX-SHORT.md` |

A chave é `projeto.tema.assunto`, em minúsculas. A primeira parte é a pasta do projeto no cofre.

## Ligar nos agentes

- **Claude Code:** dois hooks no `settings.json`. [docs/claude-code.md](docs/claude-code.md)
- **Codex, Cursor, OpenBot e qualquer agente com shell:** um bloco curto no `AGENTS.md` ou no prompt. [docs/other-agents.md](docs/other-agents.md)
- **O arquivista:** com muitos agentes escrevendo, o que faz funcionar é cada página ter um dono só. Os agentes escrevem livre em `agents/<nome>/`; um agente arquivista promove o que importa com `carimbo set` e resolve contradição. O manual dele, pronto para colar: [docs/archivist.md](docs/archivist.md)

O formato das notas e das pastas está em [docs/note-format.md](docs/note-format.md), e um cofre de exemplo em [examples/vault](examples/vault).

## Busca no cofre inteiro

O carimbo mantém o estado atual pequeno o bastante para entrar em toda sessão. Para busca de texto e semântica no resto da mesma pasta (atas, pesquisa, anotações dos agentes), usamos junto o [Open Second Brain](https://github.com/itechmeat/open-second-brain), que serve um cofre do Obsidian para agentes por MCP. Os dois convivem: o carimbo só escreve nas pastas de projeto e nos índices.

## Projetos parecidos

- [Open Second Brain](https://github.com/itechmeat/open-second-brain): cofre do Obsidian como memória de agente, com servidores MCP e uma passada noturna que transforma correções repetidas em preferências.
- [claude-mem](https://github.com/thedotmack/claude-mem): grava o que o agente faz em cada sessão, comprime e devolve depois.
- [Basic Memory](https://github.com/basicmachines-co/basic-memory): grafo de conhecimento local em Markdown que agentes leem e escrevem por MCP.
- [mem0](https://github.com/mem0ai/mem0) e [Letta](https://github.com/letta-ai/letta): camadas de memória e plataformas de agentes com estado para aplicações.

Use o carimbo quando o problema é agentes e pessoas discordando do que foi decidido, e você quer um registro que uma pessoa lê, compara e desfaz.

## Limites

- macOS e Linux (a trava de arquivo usa `fcntl`).
- Os hooks seguem o formato do Claude Code; os outros agentes leem o estado com `carimbo show`.
- A checagem de dado pessoal é feita com expressões regulares. Pega os formatos comuns e serve de rede de proteção; o critério sobre o que entra num repositório compartilhado continua sendo de quem grava.

## Desenvolvimento

```bash
git clone https://github.com/MarcoFanganielloBessa/carimbo && cd carimbo
python3 -m unittest discover -s tests
```

Issues e pull requests são bem-vindos. Veja [CONTRIBUTING.md](CONTRIBUTING.md).

## Licença

[MIT](LICENSE). Feito pela [BOMA](https://www.instagram.com/weare_boma/) em São Paulo.
