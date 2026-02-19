# Music API

API local para tocar música a partir de buscas no YouTube. Feita com FastAPI + VLC + yt-dlp.

---

## O que ela faz

- Busca e toca áudio direto do YouTube (sem baixar)
- Gerencia uma fila de músicas
- Salva e carrega playlists em JSON
- Persiste o estado — se reiniciar a API, ela lembra o que tava tocando
- Controles de play, pause, stop, próxima, seek e volume

---

## Requisitos

- Python 3.8+
- [VLC Media Player](https://www.videolan.org/) instalado no sistema
- ffmpeg (recomendado para o yt-dlp funcionar melhor)

Instale as dependências Python:

```bash
pip install fastapi uvicorn python-vlc yt-dlp
```

---

## Como rodar

```bash
uvicorn main:app --reload
```

Acesse `http://127.0.0.1:8000` no browser pra ver o player.

---

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Status da API |
| GET | `/play?query=` | Toca uma música (busca no YouTube) |
| GET | `/add?query=` | Adiciona à fila sem parar o que tá tocando |
| GET | `/next` | Pula pra próxima da fila |
| GET | `/pause` | Pausa / retoma (toggle) |
| GET | `/resume` | Retoma a reprodução |
| GET | `/stop` | Para tudo e limpa a fila |
| GET | `/seek?seconds=` | Pula para um ponto em segundos |
| GET | `/volume?level=` | Ajusta volume (0–100) |
| GET | `/status` | Retorna estado atual do player |
| GET | `/playlist/save?name=` | Salva a fila atual como playlist |
| GET | `/playlist/load?name=` | Carrega uma playlist salva |

### Exemplo de uso

```bash
# tocar uma música
curl "http://localhost:8000/play?query=bohemian+rhapsody"

# adicionar à fila
curl "http://localhost:8000/add?query=stairway+to+heaven"

# checar status
curl "http://localhost:8000/status"

# salvar playlist
curl "http://localhost:8000/playlist/save?name=rock_classico"
```

---

## Estrutura do projeto

```
msc_api/
├── main.py          # API principal (rotas + lógica do player)
├── engine.py        # busca o áudio no YouTube via yt-dlp
├── index.html       # frontend de exemplo
├── estado_player.json  # estado salvo automaticamente (não editar)
└── playlists/       # playlists salvas em JSON
```

---

## Observações

- O `/pause` funciona como toggle do VLC — se tiver tocando pausa, se tiver pausado retoma
- O endpoint `/next` avança a fila diretamente, sem depender de eventos do VLC
- As playlists ficam salvas na pasta `playlists/` como arquivos `.json`
