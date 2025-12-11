// =====================================================
// DETAILS.JS – DETALLE DE UNA SESIÓN
// =====================================================

// Obtener ID desde la URL
const params = new URLSearchParams(window.location.search);
const sesionId = params.get("sesion");

if (!sesionId) {
    alert("ID de sesión no proporcionado.");
    window.location.href = "index.html";
}

// =====================================================
// Cargar datos de la sesión
// =====================================================
document.addEventListener("DOMContentLoaded", async () => {
    try {
        const resp = await fetch("http://localhost:8000/get-session-details", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sesion_id: parseInt(sesionId) })
        });

        if (!resp.ok) {
            throw new Error("Error al obtener los datos de la sesión");
        }

        const datos = await resp.json();

        if (!datos.INICIAL || !datos.FINAL) {
            alert("Los datos de esta sesión están incompletos.");
            return;
        }

        renderGraficos(datos);
        renderEstado(datos.FINAL.estado_fatiga);

    } catch (err) {
        console.error(err);
        alert("Error cargando los detalles de la sesión.");
    }
});

// =====================================================
// Gráficos de detalle
// =====================================================
function renderGraficos(d) {
    const colorInicial = "#FFC300";
    const colorFinal = "#4DA3FF";

    // PERCLOS
    new Chart(document.getElementById("chartPerclos"), {
        type: "bar",
        data: {
            labels: ["Inicial", "Final"],
            datasets: [{
                label: "PERCLOS (%)",
                data: [d.INICIAL.perclos, d.FINAL.perclos],
                backgroundColor: [colorInicial, colorFinal],
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { 
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => `${context.parsed.y}%`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => value + '%'
                    }
                }
            }
        }
    });

    // PARPADEOS
    new Chart(document.getElementById("chartParpadeos"), {
        type: "line",
        data: {
            labels: ["Inicial", "Final"],
            datasets: [{
                label: "Parpadeos",
                data: [d.INICIAL.parpadeos, d.FINAL.parpadeos],
                borderColor: colorFinal,
                backgroundColor: "rgba(77,163,255,0.2)",
                fill: true,
                tension: 0.3,
                pointRadius: 6,
                pointHoverRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });

    // VELOCIDAD OCULAR
    new Chart(document.getElementById("chartVelocidad"), {
        type: "line",
        data: {
            labels: ["Inicial", "Final"],
            datasets: [{
                label: "Velocidad Ocular",
                data: [d.INICIAL.velocidad_ocular, d.FINAL.velocidad_ocular],
                borderColor: "#FF9800",
                backgroundColor: "rgba(255,152,0,0.2)",
                fill: true,
                tension: 0.3,
                pointRadius: 6,
                pointHoverRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });

    // KSS (Nivel subjetivo)
    new Chart(document.getElementById("chartKSS"), {
        type: "bar",
        data: {
            labels: ["Inicial", "Final"],
            datasets: [{
                label: "KSS (1-9)",
                data: [d.INICIAL.nivel_subjetivo, d.FINAL.nivel_subjetivo],
                backgroundColor: [colorInicial, colorFinal],
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 9,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

// =====================================================
// Mensaje de estado final
// =====================================================
function renderEstado(estado) {
    const box = document.getElementById("estadoFatiga");

    if (estado && estado.toUpperCase().includes("FATIGA")) {
        box.className = "alert alert-danger";
        box.innerHTML = '<strong><i class="fas fa-exclamation-triangle me-2"></i>Fatiga detectada</strong> en la medición final.';
    } else {
        box.className = "alert alert-success";
        box.innerHTML = '<strong><i class="fas fa-check-circle me-2"></i>Estado normal</strong> en la medición final.';
    }
}
