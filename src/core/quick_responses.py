"""
Respuestas con keywords AMPLIAS para máximo match.
Orden: Saludos/Despedidas PRIMERO, luego específicos.
"""
from typing import Optional

def get_quick_response(text):
    """Detecta con keywords amplias y responde específicamente."""
    t = text.lower().strip()
    
    # ============================================
    # DESPEDIDAS - PRIMERO (antes de que caiga en fallback)
    # ============================================
    if any(k in t for k in ["adios", "adiós", "chau", "chao", "hasta luego", "nos vemos", "me voy", "me retiro", "buen dia me voy", "buen día me voy", "que tengas", "q tengas", "hasta pronto", "hasta la proxima", "hasta la próxima"]):
        return "¡Gracias por contactarnos! 😊 Que tengas un excelente día. ¿Necesitás algo más antes de finalizar?"
    
    # ============================================
    # SALUDOS
    # ============================================
    if any(k in t for k in ["hola", "buenos dias", "buenos días", "buenas tardes", "buenas noches", "hey", "hi", "buenas", "q tal", "que tal", "como estas", "cómo estás", "como andas", "cómo andas"]):
        if any(k in t for k in ["como estas", "cómo estás", "q tal", "que tal", "como andas", "cómo andas"]):
            return "¡Hola! Muy bien, gracias. 😊 ¿Y vos? ¿En qué te ayudo hoy?"
        return "¡Hola! 👋 Bienvenido/a a Econify. ¿En qué puedo ayudarte?"
    
    # ============================================
    # CUOTAS - Lógica específica
    # ============================================
    if any(k in t for k in ["cuotas", "cuota", "pagar en cuotas", "pago en cuotas", "cuotas sin interes", "cuotas sin interés"]):
        if any(k in t for k in ["puedo", "aceptan", "tienen", "hay", "pueden"]):
            return "¡Sí! Aceptamos hasta 12 cuotas sin interés con tarjetas seleccionadas. 💳 ¿En cuántas cuotas querés pagar?"
        if any(k in t for k in ["cuantas", "cuántas", "maximo", "máximo"]):
            return "Podés pagar en 3, 6 o 12 cuotas sin interés. ¿En cuántas te conviene?"
        return "Aceptamos hasta 12 cuotas sin interés. ¿En cuántas querés pagar?"
    
    # ============================================
    # MÉTODOS DE PAGO ESPECÍFICOS
    # ============================================
    
    # Transferencia
    if any(k in t for k in ["transferencia bancaria", "transferencia", "transferencias", "transferir"]):
        if any(k in t for k in ["aceptan", "aceptas", "tienen", "puedo pagar", "pagan", "pueden"]):
            return "¡Sí! Aceptamos transferencias bancarias. 💳 ¿Vas a pagar así? Te paso los datos."
        return "Aceptamos transferencias. ¿Necesitás los datos de la cuenta?"
    
    # Mercado Pago
    if any(k in t for k in ["mercado pago", "mercadopago", "mp", "mercadopago"]):
        if any(k in t for k in ["aceptan", "aceptas", "tienen", "puedo pagar", "hay", "pueden"]):
            return "¡Sí! Aceptamos Mercado Pago. 💰 ¿Vas a pagar por MP? Es rápido y seguro."
        return "Sí, trabajamos con Mercado Pago. ¿Necesitás el link de pago?"
    
    # Tarjetas
    if any(k in t for k in ["tarjeta", "tarjetas", "credit card", "debit card"]):
        if any(k in t for k in ["aceptan", "aceptas", "tienen", "puedo pagar con", "pagan"]):
            if "credito" in t or "crédito" in t:
                return "¡Sí! Aceptamos Visa, Mastercard y Amex en crédito. 💳 ¿Con cuál pagás?"
            if "debito" in t or "débito" in t:
                return "¡Sí! Aceptamos débito de todos los bancos. 💳 ¿Tenés alguna?"
            return "¡Sí! Aceptamos Visa, Mastercard y Amex (crédito/débito). 💳 ¿Con cuál pagás?"
        return "Aceptamos Visa, Mastercard y Amex. ¿Tenés alguna preferida?"
    
    # Efectivo
    if any(k in t for k in ["efectivo", "cash", "billete", "plata"]):
        if any(k in t for k in ["aceptan", "puedo pagar", "pagan", "pueden"]):
            return "¡Sí! Aceptamos efectivo en Rapipago y Pago Fácil. 💵 ¿Te queda cómodo?"
        return "Podés pagar en efectivo en Rapipago o Pago Fácil. ¿Necesitás el cupón?"
    
    # Descuento
    if any(k in t for k in ["descuento", "descuentos", "discount", "promo", "promoción", "promocion"]):
        if any(k in t for k in ["efectivo", "cash", "transferencia"]):
            return "¡Sí! Tenés 10% de descuento pagando en efectivo o transferencia. 🎁 ¿Te conviene?"
        if any(k in t for k in ["hay", "tienen", "tienen"]):
            return "¡Sí! 10% descuento en efectivo/transferencia y promos semanales. 🎁 ¿Querés saber más?"
        return "Tenés 10% de descuento pagando en efectivo o transferencia. ¿Te sirve?"
    
    # Medios de pago general
    if any(k in t for k in ["medios de pago", "formas de pago", "como pago", "cómo pago", "puedo pagar", "metodos de pago", "métodos de pago"]):
        return "Aceptamos: 💳 Tarjetas, 🏦 Transferencia, 💵 Efectivo (Rapipago/Pago Fácil) y 💰 Mercado Pago. ¿Con cuál preferís?"
    
    # ============================================
    # FACTURACIÓN
    # ============================================
    
    # No me llegó
    if any(k in t for k in ["no me llego", "no me llegó", "no recibí", "no recibi"]):
        if any(k in t for k in ["factura", "comprobante", "recibo"]):
            if any(k in t for k in ["email", "mail", "correo"]):
                return "Disculpa el inconveniente. Te la reenviamos ahora. ¿A qué email la envío?"
            return "Disculpa. Te la reenviamos ya. ¿Me confirmás tu email?"
    
    # Quiero/Necesito comprobante
    if any(k in t for k in ["quiero", "necesito", "me das", "me dan", "podes", "podés"]):
        if any(k in t for k in ["mi comprobante", "mi factura", "comprobante de pago", "la factura"]):
            return "¡Por supuesto! ¿Es de una compra reciente? Te la envío por email. ¿A qué dirección?"
    
    # Factura a nombre de
    if any(k in t for k in ["factura", "facturacion", "facturación"]):
        if any(k in t for k in ["nombre de empresa", "razon social", "razón social", "a nombre de"]):
            return "¡Sí! Hacemos factura a nombre de empresa. Necesito: 1) Razón social, 2) CUIT, 3) Email. ¿Me los das?"
        if any(k in t for k in ["puedes", "podés", "me envias", "me envías", "enviarme"]):
            return "¡Por supuesto! ¿A qué email la envío?"
        if any(k in t for k in ["necesito", "quiero", "me das"]):
            return "¡Claro! Para generarla necesito: 1) Tu nombre o razón social, 2) CUIT/DNI, 3) Email. ¿Me los das?"
        if any(k in t for k in ["como", "cómo", "donde", "dónde"]):
            return "La factura llega por email después de la compra. ¿La necesitás ahora?"
    
    # ============================================
    # ENVÍOS
    # ============================================
    
    # Envío a ciudad
    if any(k in t for k in ["envian a", "envían a", "hacen envios a", "hacen envíos a", "llega a", "mandan a", "llegan a"]):
        if any(k in t for k in ["cordoba", "córdoba"]):
            return "¡Sí! Enviamos a Córdoba. 🚚 Tarda 3-5 días hábiles. ¿A qué CP lo enviemos?"
        if any(k in t for k in ["buenos aires", "bs as", "bsas", "capital", "cba"]):
            return "¡Sí! Enviamos a Buenos Aires. 🚚 Tenemos express 24-48hs. ¿Lo necesitás urgente?"
        return "¡Sí! Enviamos a todo el país. 🚚 ¿A qué ciudad y CP lo enviemos?"
    
    # Envío gratis
    if any(k in t for k in ["envio gratis", "envío gratis", "free shipping", "es gratis", "gratis"]):
        if any(k in t for k in ["hacen", "tienen", "hay", "es"]):
            return "¡Sí! Envío GRATIS en compras mayores a $10.000. 🚚 ¿Tu compra supera ese monto?"
        return "El envío es gratis en compras +$10.000. ¿Necesitás ayuda para llegar?"
    
    # Envío a domicilio
    if any(k in t for k in ["envio a domicilio", "envío a domicilio", "delivery", "a domicilio"]):
        if any(k in t for k in ["hacen", "tienen", "llega", "llegan"]):
            return "¡Sí! Hacemos envíos a domicilio a todo el país. 🚚 ¿A qué dirección?"
        return "Hacemos envíos a domicilio. ¿A dónde lo necesitás?"
    
    # Tiempo de envío
    if any(k in t for k in ["cuanto tarda", "cuánto tarda", "tiempo de entrega", "dias de entrega", "llega en", "demora"]):
        return "Estándar: 3-5 días hábiles. Express: 24-48hs. ¿Cuál preferís?"
    
    # Retiro en sucursal
    if any(k in t for k in ["retirar", "retiro", "pasar a buscar", "sucursal"]):
        if any(k in t for k in ["puedo", "pueden"]):
            return "¡Sí! Podés retirar gratis en nuestras sucursales. Está listo en 2hs. 📦 ¿En cuál te queda cómodo?"
        return "Podés retirar en sucursal gratis. ¿En cuál te viene bien?"
    
    # Envíos general
    if any(k in t for k in ["hacen envios", "hacen envíos", "envian", "envían", "mandan"]):
        return "¡Sí! Enviamos a todo el país. 🚚 Estándar 3-5 días, express 24-48hs. ¿A dónde lo enviemos?"
    
    # ============================================
    # PEDIDOS
    # ============================================
    
    # Estado de pedido
    if any(k in t for k in ["donde esta", "dónde está", "estado del pedido", "seguimiento", "tracking", "rastrear"]):
        if any(k in t for k in ["mi pedido", "mi compra", "mi orden"]):
            return "Para rastrearlo necesito el número (ej: #PED-12345) o tu teléfono. ¿Me lo das?"
        return "¿Tenés el número de pedido? Con eso te digo dónde está. 📦"
    
    # Pedido no llegó
    if any(k in t for k in ["no llego", "no llegó", "nunca llego", "nunca llegó", "no recibí", "no recibi"]):
        if any(k in t for k in ["pedido", "compra", "envio", "envío", "producto"]):
            return "Entiendo tu preocupación. 😟 Voy a rastrearlo ya. ¿Me das el número o tu teléfono?"
        return "¿Qué no te llegó? Decime y lo busco inmediatamente."
    
    # Hacer pedido
    if any(k in t for k in ["quiero comprar", "hacer un pedido", "ordenar", "comprar algo", "adquirir"]):
        return "¡Perfecto! 😊 ¿Qué producto te gustaría comprar? Te ayudo con el proceso."
    
    # ============================================
    # DEVOLUCIONES
    # ============================================
    
    # Devolución
    if any(k in t for k in ["devolver", "devolucion", "devolución", "retorno", "cambio", "cambiar"]):
        if any(k in t for k in ["puedo", "como", "cómo"]):
            return "¡Sí! Podés devolver en 30 días. Es gratis y te reembolsamos todo. ✅ ¿Necesitás iniciar una?"
        if any(k in t for k in ["cuantos dias", "cuántos días", "tiempo", "plazo", "dias"]):
            return "Tenés 30 días desde que recibís. ✅ ¿Estás dentro del plazo?"
        return "Podés devolver sin preguntas en 30 días. ¿El producto está sin usar?"
    
    # Producto roto
    if any(k in t for k in ["roto", "dañado", "defectuoso", "no funciona", "mal estado", "no anda", "rota"]):
        return "Lamento mucho que te haya llegado así. 😔 Te lo cambiamos ya o te reembolsamos. ¿Reenvío o reembolso?"
    
    # Garantía
    if any(k in t for k in ["garantia", "garantía", "warranty"]):
        return "Todos tienen garantía. Si hay problema, lo cambiamos o reembolsamos. ✅ ¿Tu producto tiene algún problema?"
    
    # ============================================
    # HORARIOS Y UBICACIÓN
    # ============================================
    
    # Horario
    if any(k in t for k in ["horario", "atencion", "atención", "abierto", "cierra", "abre", "hora"]):
        if any(k in t for k in ["cual es", "cuál es", "que horario", "qué horario", "cual es el", "cuál es el"]):
            return "Lunes a Viernes: 9-18hs | Sábados: 9-13hs. 🕐 ¿Necesitás algo fuera de horario?"
        return "Lunes-Viernes: 9-18hs | Sábados: 9-13hs. 🕐 ¿En qué te ayudo?"
    
    # Ubicación
    if any(k in t for k in ["donde estan", "dónde están", "ubicacion", "ubicación", "direccion", "dirección", "address"]):
        if any(k in t for k in ["ubicados", "tienda", "local", "sucursal"]):
            return "Av. Principal 1234, Shopping Norte Local 45 y Galería Sur PB. 📍 ¿Necesitás indicaciones?"
        return "¿Necesitás la dirección de alguna sucursal?"
    
    # ============================================
    # PRECIOS Y PRODUCTOS
    # ============================================
    
    # Precio
    if any(k in t for k in ["cuanto cuesta", "cuánto cuesta", "precio", "valor", "cuanto sale", "cuánto sale", "cuesta"]):
        return "Los productos arrancan en $500. ¿Qué producto específico te interesa?"
    
    # Productos
    if any(k in t for k in ["que productos", "qué productos", "que venden", "qué venden", "catalogo", "catálogo", "productos"]):
        return "Tenemos +1.000 productos. 📦 ¿Qué tipo buscás? Te muestro opciones."
    
    # Stock
    if any(k in t for k in ["stock", "disponible", "tienen", "hay", "tenes", "tenés"]):
        return "¿Qué producto querés consultar? Te digo si tenemos stock."
    
    # ============================================
    # CONSULTAS GENERALES
    # ============================================
    
    # Consulta general
    if any(k in t for k in ["ayuda", "informacion", "información", "consulta", "duda", "pregunta", "asistencia", "soporte"]):
        return "¡Claro! Te ayudo con: 📋 Pedidos, 🧾 Facturación, 💳 Pagos, 🚚 Envíos, 🔄 Devoluciones. ¿Sobre qué tema?"
    
    # No entiendo
    if any(k in t for k in ["no entiendo", "no comprendo", "explicame", "explícame", "como funciona", "cómo funciona", "me perdí", "me perdi"]):
        return "No te preocupes, te explico. 😊 ¿Sobre qué tema? Pedidos, pagos, envíos... Decime y te guío."
    
    # Urgente
    if any(k in t for k in ["urgente", "rapido", "rápido", "ya", "ahora", "prisa", "inmediato"]):
        return "Entiendo que es urgente. ⚡ Decime qué necesitás y lo resolvemos ya."
    
    # Enojo
    if any(k in t for k in ["enojado", "enojada", "molesto", "molesta", "harto", "harta", "inaceptable", "pesimo", "pésimo", "vergüenza", "verguenza"]):
        return "Entiendo tu enojo y lamento la situación. 😟 Voy a ayudarte YA. ¿Qué pasó?"
    
    # ============================================
    # SIN MATCH → None
    # ============================================
    return None

if __name__ == "__main__":
    tests = [
        "adios", "hasta luego", "nos vemos", "buen dia me voy",
        "puedo pagar en cuotas", "aceptan transferencias",
        "tienen mercado pago", "hacen envios a cordoba"
    ]
    print("=== TEST FINAL ===\n")
    for t in tests:
        r = get_quick_response(t)
        print(f"'{t}'\n→ {r}\n")
