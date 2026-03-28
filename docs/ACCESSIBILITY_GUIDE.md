# Guia de Accesibilidad WCAG 2.1 - AgenteDeVoz
**Version:** 1.0 | **Actualizado:** 2026-03-22
**Nivel objetivo:** WCAG 2.1 AA

---

## Introduccion

AgenteDeVoz debe ser accesible para todos los usuarios, incluyendo aquellos con discapacidades visuales, auditivas, motoras o cognitivas. Esta guia define los estandares de accesibilidad para el dashboard web y las interfaces de usuario.

---

## 1. Principios POUR

WCAG 2.1 se basa en cuatro principios fundamentales:

| Principio | Descripcion | Ejemplos de criterios |
|-----------|-------------|----------------------|
| **Perceptible** | La informacion debe ser presentable de multiples formas | Alt text, subtitulos, contraste |
| **Operable** | Los componentes deben ser operables por todos | Navegacion por teclado, sin trampas de foco |
| **Comprensible** | Informacion y UI comprensibles | Idioma declarado, errores descriptivos |
| **Robusto** | Contenido interpretable por tecnologias asistivas | HTML valido, ARIA correcto |

---

## 2. Criterios de Exito Implementados (Nivel A)

### 1.1.1 Non-text Content

**Requisito:** Todo contenido no textual tiene alternativa de texto.

```html
<!-- CORRECTO -->
<img src="grafico-llamadas.png" alt="Grafico de barras: 1247 llamadas esta semana, tendencia creciente 8%">
<img src="logo.svg" alt="Logo AgenteDeVoz">
<img src="decorativo.png" alt="">  <!-- Decorativo: alt vacio -->

<!-- INCORRECTO -->
<img src="grafico.png">  <!-- Sin alt -->
<img src="icono.png" alt="img">  <!-- Alt no descriptivo -->
```

### 1.3.1 Info and Relationships

**Requisito:** La estructura e informacion se puede determinar programaticamente.

```html
<!-- CORRECTO: Tabla con headers -->
<table>
    <caption>Tickets de soporte activos</caption>
    <thead>
        <tr>
            <th scope="col">ID</th>
            <th scope="col">Estado</th>
            <th scope="col">Prioridad</th>
            <th scope="col">Cliente</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>TKT-001234</td>
            <td>Abierto</td>
            <td>Alto</td>
            <td>+573001234567</td>
        </tr>
    </tbody>
</table>

<!-- CORRECTO: Formulario con labels -->
<form>
    <div class="form-group">
        <label for="ticket-search">Buscar por numero de ticket:</label>
        <input type="text" id="ticket-search" name="search"
               placeholder="TKT-XXXXXX"
               aria-describedby="search-hint">
        <span id="search-hint" class="hint">Formato: TKT-seguido de 6 digitos</span>
    </div>
</form>
```

### 2.1.1 Keyboard

**Requisito:** Toda la funcionalidad disponible via teclado.

```javascript
// Implementacion de navegacion por teclado para el dashboard
document.addEventListener('keydown', function(e) {
    // Alt+N: ir a notificaciones
    if (e.altKey && e.key === 'n') {
        document.getElementById('notifications').focus();
        e.preventDefault();
    }
    // Escape: cerrar modal activo
    if (e.key === 'Escape') {
        const modal = document.querySelector('[role="dialog"][aria-modal="true"]');
        if (modal) {
            const trigger = document.querySelector('[data-modal-trigger]');
            modal.setAttribute('aria-hidden', 'true');
            if (trigger) trigger.focus();
        }
    }
});
```

### 2.4.2 Page Titled

**Requisito:** La pagina tiene un titulo descriptivo.

```html
<!-- CORRECTO: Titulo descriptivo y unico por pagina -->
<title>Conversaciones Activas (12) - Dashboard AgenteDeVoz</title>
<title>Ticket TKT-001234 - Sistema de Soporte AgenteDeVoz</title>
<title>Alertas del Sistema - Monitor AgenteDeVoz</title>
```

### 3.1.1 Language of Page

```html
<html lang="es-CO">  <!-- Espanol colombiano -->
<!-- o -->
<html lang="es">     <!-- Espanol generico -->
```

---

## 3. Criterios de Exito Implementados (Nivel AA)

### 1.4.3 Contrast (Minimum)

**Requisito:** Ratio de contraste minimo 4.5:1 para texto normal, 3:1 para texto grande.

```css
/* Paleta de colores del dashboard con contraste verificado */
:root {
    /* Texto sobre fondo oscuro (#1a1a2e) */
    --text-primary: #e0e0e0;    /* Ratio: 9.5:1 - PASA AA y AAA */
    --text-secondary: #a0a0b0;  /* Ratio: 4.8:1 - PASA AA */

    /* Alertas */
    --alert-critical: #ff4444; /* REVISAR contraste en fondos claros */
    --alert-warning: #ffaa00;
    --alert-ok: #00cc66;

    /* Texto sobre fondo del panel (#16213e) */
    --panel-text: #c8c8d4;     /* Ratio: 5.2:1 - PASA AA */
}

/* Verificar con la herramienta: https://webaim.org/resources/contrastchecker/ */
```

### 1.4.4 Resize Text

**Requisito:** El texto puede redimensionarse hasta 200% sin perder funcionalidad.

```css
/* Usar unidades relativas, no pixels fijos */
body { font-size: 1rem; }     /* Respeta configuracion del usuario */
h1 { font-size: 2rem; }      /* Escala con el cuerpo */
.btn { padding: 0.5em 1em; } /* em escala con el font-size del elemento */

/* EVITAR: font-size: 14px (no escala con preferencias del usuario) */
```

### 2.4.6 Headings and Labels

**Requisito:** Encabezados y labels son descriptivos.

```html
<!-- CORRECTO: Jerarquia de encabezados coherente -->
<h1>Dashboard AgenteDeVoz</h1>
    <h2>Conversaciones Activas</h2>
        <h3>Filtros de busqueda</h3>
    <h2>Tickets Pendientes</h2>
        <h3>Alta Prioridad (3)</h3>
        <h3>Media Prioridad (12)</h3>
    <h2>Metricas del Sistema</h2>

<!-- INCORRECTO: Saltar niveles -->
<h1>Dashboard</h1>
<h3>Conversaciones</h3>  <!-- Salto de h1 a h3 -->
```

### 2.4.7 Focus Visible

**Requisito:** El foco del teclado es visible.

```css
/* Estilos de foco visibles y atractivos */
*:focus {
    outline: 3px solid #0078d4;
    outline-offset: 2px;
    border-radius: 2px;
}

/* Para botones con fondo oscuro */
.btn-dark:focus {
    outline: 3px solid #ffffff;
    outline-offset: 2px;
}

/* NUNCA hacer esto sin proporcionar alternativa */
/* *:focus { outline: none; } */
```

---

## 4. ARIA - Accessible Rich Internet Applications

### Roles ARIA en el Dashboard

```html
<!-- Navegacion principal -->
<nav aria-label="Principal">
    <ul>
        <li><a href="/dashboard" aria-current="page">Dashboard</a></li>
        <li><a href="/conversations">Conversaciones</a></li>
        <li><a href="/tickets">Tickets</a></li>
        <li><a href="/alerts">Alertas</a></li>
    </ul>
</nav>

<!-- Region de contenido principal -->
<main id="main-content" aria-label="Contenido principal">
    ...
</main>

<!-- Alertas en tiempo real -->
<div role="alert" aria-live="assertive" aria-atomic="true" id="system-alerts">
    <!-- Las alertas criticas se anuncian inmediatamente -->
</div>

<!-- Notificaciones no criticas -->
<div role="status" aria-live="polite" aria-atomic="true" id="notifications">
    <!-- Las notificaciones se anuncian cuando el usuario este inactivo -->
</div>

<!-- Modal/Dialog -->
<div role="dialog"
     aria-modal="true"
     aria-labelledby="modal-title"
     aria-describedby="modal-desc">
    <h2 id="modal-title">Confirmar accion</h2>
    <p id="modal-desc">Esta accion es irreversible.</p>
    <button type="button" aria-label="Cerrar dialogo">X</button>
    ...
</div>
```

### Botones con Solo Iconos

```html
<!-- CORRECTO: aria-label en boton con icono -->
<button type="button" aria-label="Cerrar sesion">
    <span aria-hidden="true">&#x23F9;</span>
</button>

<button type="button" aria-label="Exportar reporte como PDF">
    <span aria-hidden="true">PDF</span>
</button>

<!-- INCORRECTO: Sin texto accesible -->
<button>X</button>
<button><img src="delete.png"></button>
```

---

## 5. Formularios Accesibles

```html
<!-- Patron completo de formulario accesible -->
<form novalidate aria-label="Crear nuevo ticket de soporte">
    <div class="form-group">
        <!-- Label SIEMPRE asociado con for/id -->
        <label for="customer-phone">
            Telefono del cliente
            <span class="required" aria-hidden="true">*</span>
        </label>
        <input
            type="tel"
            id="customer-phone"
            name="customer_phone"
            required
            aria-required="true"
            aria-describedby="phone-hint phone-error"
            pattern="^\+[0-9]{10,15}$"
            placeholder="+573001234567"
        >
        <span id="phone-hint" class="hint">
            Formato internacional: +57 seguido del numero
        </span>
        <!-- Error: visible solo cuando hay error -->
        <span id="phone-error" role="alert" class="error" aria-live="polite" hidden>
            Por favor ingrese un numero valido en formato +573001234567
        </span>
    </div>

    <button type="submit">Crear Ticket</button>
</form>
```

---

## 6. Testing de Accesibilidad

### Herramientas Automaticas

```bash
# 1. Usar el WCAGChecker incluido en el proyecto
python3 -c "
from src.accessibility.wcag_checker import WCAGChecker
with open('src/dashboard/templates/index.html') as f:
    html = f.read()
checker = WCAGChecker()
violations = checker.check_dashboard(html)
report = checker.generate_report()
print(f'Score: {report[\"summary\"][\"score\"]}/100')
print(f'Violaciones: {report[\"summary\"][\"total_violations\"]}')
"

# 2. Tests automaticos
python3 -m pytest tests/test_accessibility.py -v

# 3. Lighthouse CLI (requiere Node.js)
# npm install -g lighthouse
# lighthouse http://localhost:8000 --only-categories=accessibility --output html
```

### Pruebas Manuales con Lector de Pantalla

1. **NVDA (Windows, gratuito):** https://www.nvaccess.org/
2. **VoiceOver (macOS/iOS, incluido):** Cmd+F5 para activar
3. **TalkBack (Android, incluido):** Configuracion > Accesibilidad

**Pruebas basicas con lector de pantalla:**
- [ ] Navegar todo el dashboard solo con teclado (Tab, Shift+Tab, Enter, Espacio, Arrows)
- [ ] Todas las imagenes tienen alt text auditivo
- [ ] Las tablas se leen con headers de columna
- [ ] Los formularios se pueden completar completamente
- [ ] Las alertas del sistema se anuncian automaticamente
- [ ] Los modales pueden cerrarse con Escape

---

## 7. Checklist de Accesibilidad para Nuevos Componentes

Antes de merge de cualquier PR con UI:

- [ ] Imagenes tienen alt text descriptivo (o alt="" si decorativas)
- [ ] Inputs tienen labels asociados (for/id o aria-label)
- [ ] Botones con solo icono tienen aria-label
- [ ] Encabezados siguen jerarquia logica (h1 > h2 > h3)
- [ ] Tablas tienen th con scope
- [ ] El componente es navegable por teclado
- [ ] Los estados de error tienen rol="alert" o aria-live
- [ ] No se elimina outline de foco sin alternativa visible
- [ ] Se verifico contraste con WebAIM Color Contrast Checker
- [ ] Ejecutar WCAGChecker y score >= 80/100

---

## 8. Recursos

- **WCAG 2.1:** https://www.w3.org/TR/WCAG21/
- **WebAIM:** https://webaim.org/
- **Contrast Checker:** https://webaim.org/resources/contrastchecker/
- **ARIA Patterns:** https://www.w3.org/WAI/ARIA/apg/patterns/
- **Screen Reader Testing Guide:** https://webaim.org/articles/screenreader_testing/

**Responsable:** Frontend Lead
**Revision:** Con cada release mayor
