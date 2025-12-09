import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2 import pool, extras
import bcrypt
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de logs
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Sistema de Fatiga Visual API")

# ⭐ CORS MEJORADO PARA PRODUCTION
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "https://*.vercel.app",
    os.getenv("FRONTEND_URL", "https://tu-proyecto.vercel.app")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HEALTH CHECK ENDPOINT ---
@app.get("/")
def health_check():
    """Endpoint para verificar que el servidor está funcionando"""
    return {
        "status": "ok",
        "ambiente": os.getenv("ENVIRONMENT", "production"),
        "mensaje": "Sistema de Fatiga Visual - Backend activo"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

# --- MODELOS DE DATOS ---
class Login(BaseModel):
    correo: str
    contrasena: str

class Register(BaseModel):
    nombre: str
    apellido: str
    correo: str
    contrasena: str

class FatigueResult(BaseModel):
    usuario_id: int
    tipo_medicion: str
    sebr: float
    perclos: float
    pct_incompletos: float
    tiempo_cierre: float
    num_bostezos: int
    velocidad_ocular: float
    nivel_subjetivo: int
    es_fatiga: bool

class DashboardRequest(BaseModel):
    usuario_id: int

class DetailRequest(BaseModel):
    sesion_id: int

# --- BASE DE DATOS (RAILWAY) ---
@app.on_event("startup")
def startup():
    try:
        # ⭐ RAILWAY proporciona estas variables automáticamente
        # Usa PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
        db_config = {
            "host": os.getenv("PGHOST", "localhost"),
            "port": int(os.getenv("PGPORT", "5432")),
            "database": os.getenv("PGDATABASE", "railway"),
            "user": os.getenv("PGUSER", "postgres"),
            "password": os.getenv("PGPASSWORD", ""),
        }
        
        log.info(f"🔌 Conectando a: {db_config['host']}:{db_config['port']}/{db_config['database']}")
        
        app.state.db_pool = pool.SimpleConnectionPool(1, 10, **db_config)
        log.info("✅ Conexión a base de datos Railway establecida.")
    except Exception as e:
        log.exception("❌ Error conectando a PostgreSQL en Railway")
        raise e

@app.on_event("shutdown")
def shutdown():
    db_pool = getattr(app.state, "db_pool", None)
    if db_pool:
        db_pool.closeall()
        log.info("🔌 Pool de conexiones cerrado.")

def _get_conn_from_pool():
    db_pool = getattr(app.state, "db_pool", None)
    if not db_pool:
        raise HTTPException(status_code=500, detail="Conexión BD no disponible")
    return db_pool.getconn()

def _put_conn_back(conn):
    db_pool = getattr(app.state, "db_pool", None)
    if db_pool:
        db_pool.putconn(conn)

# --- ENDPOINTS AUTH ---
@app.post("/register")
def register_user(data: Register):
    """Registrar nuevo usuario"""
    conn = None
    try:
        conn = _get_conn_from_pool()
        cur = conn.cursor(cursor_factory=extras.RealDictCursor)

        # Verificar correo único
        cur.execute("SELECT 1 FROM usuarios WHERE correo = %s", (data.correo,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="El correo ya está registrado")

        # Hash de contraseña
        hashed_pw = bcrypt.hashpw(data.contrasena.encode("utf-8"), bcrypt.gensalt())

        cur.execute(
            """
            INSERT INTO usuarios (nombre, apellido, correo, contrasena, rol_id)
            VALUES (%s, %s, %s, %s, 2) RETURNING id
            """,
            (data.nombre, data.apellido, data.correo, hashed_pw.decode("utf-8")),
        )
        conn.commit()
        log.info(f"✅ Usuario registrado: {data.correo}")
        return {"mensaje": "Usuario registrado correctamente"}
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        log.exception("Error en registro")
        raise HTTPException(status_code=500, detail="Error servidor")
    finally:
        if conn:
            _put_conn_back(conn)

@app.post("/login")
def login_user(data: Login):
    """Login de usuario"""
    conn = None
    try:
        conn = _get_conn_from_pool()
        cur = conn.cursor(cursor_factory=extras.RealDictCursor)

        cur.execute(
            """
            SELECT u.id, u.nombre, u.apellido, u.correo, u.contrasena,
                   r.nombre AS rol_nombre, u.rol_id
            FROM usuarios u
            INNER JOIN roles r ON r.id = u.rol_id
            WHERE correo = %s
            """,
            (data.correo,),
        )
        user = cur.fetchone()

        if not user or not bcrypt.checkpw(
            data.contrasena.encode("utf-8"), user["contrasena"].encode("utf-8")
        ):
            log.warning(f"⚠️ Login fallido: {data.correo}")
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")

        cur.execute("UPDATE usuarios SET ultimo_acceso = NOW() WHERE id = %s", (user["id"],))
        conn.commit()

        log.info(f"✅ Login exitoso: {data.correo}")
        return {
            "mensaje": "Login exitoso",
            "usuario": {
                "id": user["id"],
                "nombre": user["nombre"],
                "apellido": user["apellido"],
                "rol": user["rol_nombre"],
            },
        }
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        log.exception("Error en login")
        raise HTTPException(status_code=500, detail="Error interno")
    finally:
        if conn:
            _put_conn_back(conn)

# --- ENDPOINTS DATOS ---
@app.post("/save-fatigue")
def save_fatigue(data: FatigueResult):
    """Guardar medición de fatiga"""
    conn = None
    try:
        conn = _get_conn_from_pool()
        cur = conn.cursor(cursor_factory=extras.RealDictCursor)

        # 1. Buscar sesión activa del usuario
        cur.execute(
            """
            SELECT id
            FROM sesiones
            WHERE usuario_id = %s AND fecha_fin IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (data.usuario_id,),
        )
        row = cur.fetchone()

        if row:
            sesion_id = row["id"]
        else:
            cur.execute(
                "INSERT INTO sesiones (usuario_id, fecha_inicio) VALUES (%s, NOW()) RETURNING id",
                (data.usuario_id,),
            )
            sesion_id = cur.fetchone()["id"]

        etapa_db = "INICIAL" if data.tipo_medicion.lower() == "inicial" else "FINAL"
        estado_txt = "FATIGA" if data.es_fatiga else "NORMAL"
        nivel_val = 1 if data.es_fatiga else 0

        # 2. Insertar medición
        cur.execute(
            """
            INSERT INTO mediciones (
                sesion_id, etapa, parpadeos, perclos, pct_incompletos,
                tiempo_cierre, num_bostezos, velocidad_ocular,
                nivel_subjetivo, nivel_fatiga, estado_fatiga, ear_promedio
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
            """,
            (
                sesion_id, etapa_db, data.sebr, data.perclos, data.pct_incompletos,
                data.tiempo_cierre, data.num_bostezos, data.velocidad_ocular,
                data.nivel_subjetivo, nivel_val, estado_txt,
            ),
        )

        # 3. Cerrar sesión si es final
        if etapa_db == "FINAL":
            cur.execute(
                """
                UPDATE sesiones
                SET fecha_fin = NOW(), actividades_completadas = true
                WHERE id = %s
                """,
                (sesion_id,),
            )

        conn.commit()
        log.info(f"✅ Medición guardada: Usuario {data.usuario_id}, Etapa {etapa_db}")
        return {"mensaje": f"Datos guardados exitosamente como {etapa_db}"}
    except Exception as e:
        if conn:
            conn.rollback()
        log.exception("Error guardando fatiga")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            _put_conn_back(conn)

# --- ENDPOINT: HISTORIAL ---
@app.post("/get-user-history")
def get_user_history(data: DashboardRequest):
    """Obtener historial de sesiones del usuario"""
    conn = None
    try:
        conn = _get_conn_from_pool()
        cur = conn.cursor(cursor_factory=extras.RealDictCursor)

        query = """
            SELECT
                s.id as sesion_id,
                TO_CHAR(s.fecha_inicio, 'DD/MM/YYYY HH24:MI') as fecha,
                c.porcentaje_reduccion,
                m_ini.perclos as inicial,
                m_fin.perclos as final
            FROM sesiones s
            JOIN comparaciones c ON c.sesion_id = s.id
            JOIN mediciones m_ini
                ON m_ini.sesion_id = s.id AND m_ini.etapa = 'INICIAL'
            JOIN mediciones m_fin
                ON m_fin.sesion_id = s.id AND m_fin.etapa = 'FINAL'
            WHERE s.usuario_id = %s
            ORDER BY s.fecha_inicio DESC
        """
        cur.execute(query, (data.usuario_id,))
        historial = cur.fetchall()

        if not historial:
            return {"empty": True}

        count = len(historial)
        total_ini = sum(float(h["inicial"]) for h in historial)
        total_fin = sum(float(h["final"]) for h in historial)
        total_red = sum(float(h["porcentaje_reduccion"]) for h in historial)

        promedios = {
            "inicial": round(total_ini / count, 1),
            "final": round(total_fin / count, 1),
            "reduccion": round(total_red / count, 1),
        }

        return {"empty": False, "historial": historial, "promedios": promedios}
    except Exception as e:
        log.exception("Error historial")
        return {"error": str(e)}
    finally:
        if conn:
            _put_conn_back(conn)

# --- ENDPOINT: DETALLES DE SESIÓN ---
@app.post("/get-session-details")
def get_session_details(data: DetailRequest):
    """Obtener detalles de una sesión específica"""
    conn = None
    try:
        conn = _get_conn_from_pool()
        cur = conn.cursor(cursor_factory=extras.RealDictCursor)

        cur.execute(
            """
            SELECT
                etapa,
                perclos,
                parpadeos,
                velocidad_ocular,
                num_bostezos,
                nivel_subjetivo,
                estado_fatiga
            FROM mediciones
            WHERE sesion_id = %s
            """,
            (data.sesion_id,),
        )
        filas = cur.fetchall()

        datos = {}
        for fila in filas:
            datos[fila["etapa"]] = fila

        return datos
    except Exception as e:
        log.exception("Error detalle")
        return {"error": str(e)}
    finally:
        if conn:
            _put_conn_back(conn)

# --- ENDPOINT: ADMIN - TODAS LAS SESIONES ---
@app.get("/admin/all-sessions")
def admin_all_sessions():
    """Obtener todas las sesiones (solo admin)"""
    conn = None
    try:
        conn = _get_conn_from_pool()
        cur = conn.cursor(cursor_factory=extras.RealDictCursor)

        cur.execute("""
            SELECT 
                s.id AS sesion_id,
                CONCAT(u.nombre, ' ', u.apellido) AS estudiante,
                TO_CHAR(s.fecha_inicio, 'DD/MM/YYYY HH24:MI') AS fecha,
                m_ini.perclos AS inicial,
                m_fin.perclos AS final,
                c.porcentaje_reduccion
            FROM sesiones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN comparaciones c ON c.sesion_id = s.id
            JOIN mediciones m_ini ON m_ini.sesion_id = s.id AND m_ini.etapa = 'INICIAL'
            JOIN mediciones m_fin ON m_fin.sesion_id = s.id AND m_fin.etapa = 'FINAL'
            ORDER BY s.fecha_inicio DESC
        """)

        sesiones = cur.fetchall()
        return {"ok": True, "sesiones": sesiones}

    except Exception as e:
        log.exception("Error admin all-sessions")
        return {"ok": False, "error": str(e)}
    finally:
        if conn:
            _put_conn_back(conn)

