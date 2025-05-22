from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import time

router = APIRouter()
start_times = {}

@router.get("/race", response_class=HTMLResponse)
def show_race_panel():
    return '''
    <html><body>
    <h2>Panel de Carrera</h2>
    <form action="/race/start" method="post">
      Categoría: <input name="categoria" type="text" />
      <button type="submit">Iniciar</button>
    </form><br>
    <form action="/race/finish" method="post">
      Dorsal: <input name="dorsal" type="text" />
      Categoría: <input name="categoria" type="text" />
      <button type="submit">Registrar Meta</button>
    </form></body></html>
    '''

@router.post("/race/start")
def start_category(categoria: str):
    start_times[categoria] = time.time()
    return {"msg": f"Categoría {categoria} iniciada"}

@router.post("/race/finish")
def finish_racer(dorsal: str, categoria: str):
    now = time.time()
    start = start_times.get(categoria, now)
    elapsed = now - start
    return {"msg": f"Dorsal {dorsal} llegó con {elapsed:.2f} segundos"}
