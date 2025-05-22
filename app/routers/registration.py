from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/register", response_class=HTMLResponse)
async def show_registration_form():
    return '''
    <html><body>
    <h2>Registro Competencia SUP</h2>
    <form action="/register" method="post" enctype="multipart/form-data">
      Nombre: <input type="text" name="nombre"><br>
      Edad: <input type="number" name="edad"><br>
      Categoría: <select name="categoria">
        <option value="sub8">Sub 8</option>
        <option value="sub10">Sub 10</option>
        <option value="sub12">Sub 12</option>
        <option value="elite">Élite</option>
      </select><br>
      Justificante de pago: <input type="file" name="pago"><br>
      <input type="submit">
    </form></body></html>
    '''

@router.post("/register")
async def register(nombre: str = Form(...), edad: int = Form(...), categoria: str = Form(...), pago: UploadFile = File(...)):
    content = await pago.read()
    with open(f"static/payments/{pago.filename}", "wb") as f:
        f.write(content)
    return {"msg": "Registrado con éxito", "nombre": nombre, "categoria": categoria}
