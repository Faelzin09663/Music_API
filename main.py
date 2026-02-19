import asyncio
import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from engine import search_audio  # busca o áudio no youtube via yt-dlp
import vlc  # player de audio

app = FastAPI(title="Music API")

# libera acesso de qualquer origem (útil pra testar direto do browser)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# onde salvamos o estado (música tocando + fila)
STATE_FILE = "estado_player.json"
PLAYLIST_DIR = "playlists"

# garante que a pasta de playlists existe
if not os.path.exists(PLAYLIST_DIR):
    os.makedirs(PLAYLIST_DIR)

# instância global do VLC — sem vídeo pra não abrir janela
vlc_instance = vlc.Instance('--no-video')
player = vlc_instance.media_player_new()

# estado global da aplicação
current_track_data = None  # dict com info da música tocando agora
fila_de_musicas = []        # lista de dicts com as próximas músicas
song_ended_flag = False     # flag que o callback do VLC seta quando a música acaba


def salvar_estado():
    # grava no disco o que tá tocando e a fila, pra não perder se reiniciar
    estado = {
        "current_track": current_track_data,
        "queue": fila_de_musicas
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=4)


def carregar_estado():
    # quando a API sobe, tenta restaurar o que estava tocando antes
    global current_track_data, fila_de_musicas
    if not os.path.exists(STATE_FILE):
        return
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            estado = json.load(f)
        fila_de_musicas = estado.get("queue", [])
        current_track_data = estado.get("current_track", None)

        if current_track_data:
            # carrega a mídia mas não dá play — deixa pronto pro /resume
            media = vlc_instance.media_new(current_track_data['url'])
            player.set_media(media)
            print(f"[MEMÓRIA] Última música carregada: {current_track_data['title']}")
    except Exception as e:
        print(f"Erro ao carregar estado: {e}")


# --- sistema de avanço automático de fila ---

def song_finished_callback(event):
    # o VLC chama isso quando a música termina naturalmente
    global song_ended_flag
    if current_track_data is not None:
        song_ended_flag = True

# registra o callback no evento de fim de mídia do VLC
player.event_manager().event_attach(
    vlc.EventType.MediaPlayerEndReached, song_finished_callback
)


async def queue_manager():
    # loop que roda em background e avança a fila quando a música acaba
    global song_ended_flag, current_track_data, fila_de_musicas
    while True:
        if song_ended_flag:
            song_ended_flag = False
            await asyncio.sleep(0.5)  # pequena pausa pra o VLC terminar de fato

            if fila_de_musicas:
                print("\n[VIGIA] Trocando para a próxima da fila...\n")
                next_song = fila_de_musicas.pop(0)
                media = vlc_instance.media_new(next_song['url'])
                player.set_media(media)
                player.play()
                current_track_data = next_song
                salvar_estado()
            else:
                print("\n[VIGIA] Fila acabou.\n")
                current_track_data = None
                player.stop()
                salvar_estado()

        await asyncio.sleep(1)  # checa a flag a cada 1 segundo


@app.on_event("startup")
async def startup_event():
    carregar_estado()
    asyncio.create_task(queue_manager())  # sobe o vigia de fila em background


# --- rotas de playlist ---

@app.get("/playlist/save")
async def save_playlist(name: str):
    # junta a música atual com a fila e salva tudo como um JSON
    if not current_track_data and not fila_de_musicas:
        return {"message": "Nada tocando para salvar."}

    playlist_completa = []
    if current_track_data:
        playlist_completa.append(current_track_data)
    playlist_completa.extend(fila_de_musicas)

    caminho = os.path.join(PLAYLIST_DIR, f"{name}.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(playlist_completa, f, ensure_ascii=False, indent=4)

    return {"message": f"Playlist '{name}' salva com {len(playlist_completa)} músicas!"}


@app.get("/playlist/load")
async def load_playlist(name: str):
    # carrega uma playlist do disco e já começa a tocar
    global current_track_data, fila_de_musicas
    caminho = os.path.join(PLAYLIST_DIR, f"{name}.json")

    if not os.path.exists(caminho):
        raise HTTPException(status_code=404, detail="Playlist não encontrada.")

    with open(caminho, "r", encoding="utf-8") as f:
        playlist_completa = json.load(f)

    if not playlist_completa:
        return {"message": "Playlist vazia."}

    player.stop()
    primeira_musica = playlist_completa[0]
    fila_de_musicas = playlist_completa[1:]  # o resto vai pra fila

    media = vlc_instance.media_new(primeira_musica['url'])
    player.set_media(media)
    player.play()

    current_track_data = primeira_musica
    salvar_estado()
    return {"message": f"Playlist '{name}' carregada! Tocando: {primeira_musica['title']}"}


# --- rotas principais do player ---

@app.get("/")
def home():
    return {"status": "Music API online"}


@app.get("/play")
async def play_music(query: str):
    # busca no youtube e já toca — limpa a fila antes pra não misturar
    global current_track_data, fila_de_musicas, song_ended_flag
    result = search_audio(query)
    if not result:
        raise HTTPException(status_code=404, detail="Audio not found")

    song_ended_flag = False
    player.stop()
    fila_de_musicas.clear()

    media = vlc_instance.media_new(result['url'])
    player.set_media(media)
    player.play()
    current_track_data = result
    salvar_estado()
    return {"message": f"Tocando: {result['title']}", "data": result}


@app.get("/add")
async def add_to_queue(query: str):
    # busca e adiciona no final da fila sem parar o que tá tocando
    result = search_audio(query)
    if not result:
        raise HTTPException(status_code=404, detail="Audio not found")

    fila_de_musicas.append(result)
    salvar_estado()
    return {"message": f"Adicionado: {result['title']}", "queue_length": len(fila_de_musicas)}


@app.get("/next")
async def next_song():
    # para o que tá tocando e pula pra próxima da fila
    # obs: player.stop() NÃO dispara o evento MediaPlayerEndReached do VLC,
    global current_track_data, fila_de_musicas
    player.stop()
    if fila_de_musicas:
        await asyncio.sleep(0.3)  # dá um tempo pro VLC parar de vez
        next_track = fila_de_musicas.pop(0)
        media = vlc_instance.media_new(next_track['url'])
        player.set_media(media)
        player.play()
        current_track_data = next_track
        salvar_estado()
        return {"message": f"Tocando: {next_track['title']}", "data": next_track}
    else:
        current_track_data = None
        salvar_estado()
        return {"message": "Fila vazia. Parando playback."}


@app.get("/seek")
async def seek_music(seconds: int):
    # pula pra um ponto específico em segundos
    if player.is_playing() or player.get_state() == vlc.State.Paused:
        player.set_time(seconds * 1000)  # VLC usa milissegundos
        return {"message": f"Pulou para {seconds} segundos"}
    return {"message": "Nada tocando para pular tempo."}


@app.get("/stop")
async def stop_music():
    # para tudo e limpa a fila
    global current_track_data, fila_de_musicas, song_ended_flag
    song_ended_flag = False
    player.stop()
    current_track_data = None
    fila_de_musicas.clear()
    salvar_estado()
    return {"message": "Stopped and cleared queue"}


@app.get("/pause")
async def pause_music():
    player.pause() 
    return {"message": "Music paused", "data": current_track_data}


@app.get("/resume")
async def resume_music():
    player.play()
    return {"message": "Music resumed", "data": current_track_data}


@app.get("/volume")
async def set_volume(level: int):
    level = max(0, min(100, level))  
    player.audio_set_volume(level)
    return {"message": f"Volume: {level}%"}


@app.get("/status")
async def get_status():
    # retorna tudo que o frontend precisa pra atualizar a interface
    titulo = current_track_data['title'] if current_track_data else "Nenhuma música tocando"
    nomes_na_fila = [f"{i+1}. {m['title']}" for i, m in enumerate(fila_de_musicas)]

    tempo_atual_sec = player.get_time() / 1000 if current_track_data else 0
    duracao_total_sec = player.get_length() / 1000 if current_track_data else 1
    if duracao_total_sec <= 0:
        duracao_total_sec = 1  

    return {
        "estado_do_player": str(player.get_state()),
        "musica_atual": titulo,
        "total_na_fila": len(fila_de_musicas),
        "proximas_musicas": nomes_na_fila,
        "tempo_atual": tempo_atual_sec,
        "duracao_total": duracao_total_sec,
        "thumbnail": current_track_data['thumbnail'] if current_track_data else ""
    }
