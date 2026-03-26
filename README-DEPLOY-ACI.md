# Publicar inventario (en vivo)

Tu página en Vercel necesita un **API público** (no puede usar `localhost`).

## 1) Publicar el API (Render)

1. Sube estos archivos a un repo (GitHub):
   - `aci_inventory_api.py`
   - `requirements.txt`
   - `render-start.sh`
2. En Render crea un **Web Service** desde tu repo.
3. Configura:
   - **Build Command**: `python3 -m pip install --user -r requirements.txt`
   - **Start Command**: `bash render-start.sh`
4. Cuando Render termine, copia tu URL (ejemplo): `https://aci-inventory.onrender.com`

Endpoints:
- JSON: `/inventory?limit=20`
- CSV: `/inventory.csv?limit=20`

## 2) Conectar tu página (Vercel)

En tu URL pública de Vercel, agrega el parámetro `api`.

Ejemplo:
`https://TU-SITIO.vercel.app/#galeria?api=https://aci-inventory.onrender.com`

O (mejor) entra a tu sitio así:
`https://TU-SITIO.vercel.app/?api=https://aci-inventory.onrender.com#galeria`

También puedes guardar el API en el navegador:
1. Abre la consola del navegador y ejecuta:
   `localStorage.setItem("INVENTORY_API_BASE","https://aci-inventory.onrender.com")`
2. Recarga la página.

