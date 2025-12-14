window.API_URL = null;
window.AMBIENTE = null;

// Detectar automáticamente el entorno
window.AMBIENTE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') 
  ? 'development' 
  : 'production';

// Configuración de URLs según el ambiente
if (window.AMBIENTE === 'development') {
  window.API_URL = 'http://127.0.0.1:8000';
} else {
  // ⭐ REEMPLAZA CON LA URL DE RAILWAY (después de desplegar)
  window.API_URL = 'https://pry-lectura-backend.up.railway.app';
}

console.log('🔧 Config cargada:', {
  ambiente: window.AMBIENTE,
  apiUrl: window.API_URL,
  hostname: window.location.hostname
});

// Función para obtener la URL del API dinámicamente
async function detectarApiUrl() {
    try {
        // Si estamos en localhost, usar localhost
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            window.API_URL = 'http://localhost:8000';
            window.AMBIENTE = 'desarrollo';
            console.log('✓ Ambiente: DESARROLLO (localhost)');
            console.log('✓ API URL: http://localhost:8000');
            return;
        }
        
        // En producción, cargar desde archivo de config
        try {
            const response = await fetch('/api-config.json?t=' + Date.now());
            const config = await response.json();
            window.API_URL = config.api_url;
            window.AMBIENTE = 'produccion';
            console.log('✓ Ambiente: PRODUCCIÓN');
            console.log(`✓ API URL: ${window.API_URL}`);
        } catch (configError) {
            console.warn('No se pudo cargar api-config.json, usando fallback');
            window.API_URL = 'http://localhost:8000';  // Fallback
        }
        
    } catch (error) {
        console.error('Error detectando API URL:', error);
        window.API_URL = 'http://localhost:8000';  // Fallback
    }
}

// Función para actualizar manualmente la URL (para debugging)
function actualizarUrlApi(nuevaUrl) {
    window.API_URL = nuevaUrl;
    localStorage.setItem('api_url_ngrok', nuevaUrl);
    console.log(`✓ URL API actualizada a: ${nuevaUrl}`);
}

// Llamar al cargar la página
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', detectarApiUrl);
} else {
    detectarApiUrl();
}