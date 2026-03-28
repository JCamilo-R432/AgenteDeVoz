"""
Reglas explícitas con contexto emocional.
Detecta intents + emoción para respuestas más precisas y empáticas.
"""
import sys
import os

# Agregar src al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from nlp.emotion_detector import detect_emotion, get_empathetic_prefix
except ImportError:
    def detect_emotion(text):
        return {"emotion": "neutral", "intensity": 0, "tone": "profesional_amable", "priority": "baja", "keywords": []}
    def get_empathetic_prefix(emotion_data):
        return ""

def get_explicit_intent(text):
    """Detecta intent + emoción. Prioriza PROBLEMAS sobre consultas genéricas."""
    text_lower = text.lower()
    emotion_data = detect_emotion(text)
    
    def with_empathy(base_response):
        prefix = get_empathetic_prefix(emotion_data)
        return prefix + base_response if prefix else base_response
    
    # ============================================
    # PRIORIDAD 1: PROBLEMAS Y RECLAMOS (primero!)
    # ============================================
    
    # Producto dañado/roto → Devolución o Reclamo
    if any(kw in text_lower for kw in ["roto", "dañado", "no funciona", "defectuoso", "mal estado"]):
        if emotion_data["emotion"] in ["enojo", "tristeza", "frustracion"]:
            return {
                "intent": "crear_reclamo_empatico",
                "emotion_data": emotion_data,
                "response": with_empathy("Lamento mucho que hayas tenido esta experiencia. Para ayudarte de inmediato:\n\n1. Voy a generar un ticket prioritario\n2. Un supervisor te contactará en menos de 2 horas\n3. Buscaremos la mejor solución para vos\n\n¿Me podés contar brevemente qué sucedió?"),
                "should_use_explicit": True
            }
        else:
            return {
                "intent": "consultar_devoluciones",
                "emotion_data": emotion_data,
                "response": with_empathy("Política de devoluciones:\n\n✅ 30 días para devolver sin preguntas\n✅ Producto sin usar y en su embalaje original\n✅ Reembolso completo en 5-7 días o cambio inmediato\n✅ Retiro gratis desde tu domicilio\n\n¿Necesitás iniciar una devolución?"),
                "should_use_explicit": True
            }
    
    # Pedido no llegó / Nunca llegó → Reclamo o Estado
    if any(kw in text_lower for kw in ["nunca llegó", "no llegó", "no me llegó", "perdido", "extraviado"]):
        if emotion_data["emotion"] in ["enojo", "frustracion", "ansiedad"]:
            return {
                "intent": "crear_reclamo_empatico",
                "emotion_data": emotion_data,
                "response": with_empathy("Entiendo tu preocupación y lamento la demora. Para ayudarte de inmediato:\n\n1. Voy a rastrear tu pedido ahora mismo\n2. Si está perdido, te reenviamos gratis o te reembolsamos\n3. Un supervisor te contactará en menos de 2 horas\n\n¿Me podés dar tu número de pedido o teléfono?"),
                "should_use_explicit": True
            }
        else:
            return {
                "intent": "consultar_estado_pedido",
                "emotion_data": emotion_data,
                "response": with_empathy("Para consultar el estado de tu pedido necesito:\n\n1. Número de pedido (ej: #PED-12345)\n2. O tu número de teléfono registrado\n3. O tu email de compra\n\n¿Me podés proporcionar alguno de estos datos?"),
                "should_use_explicit": True
            }
    
    # Reclamos explícitos
    if any(kw in text_lower for kw in ["reclamo", "queja", "molesto", "enojado", "hart", "inaceptable", "vergüenza"]):
        return {
            "intent": "crear_reclamo_empatico",
            "emotion_data": emotion_data,
            "response": with_empathy("Lamento mucho que hayas tenido esta experiencia. Para ayudarte de inmediato:\n\n1. Voy a generar un ticket prioritario\n2. Un supervisor te contactará en menos de 2 horas\n3. Buscaremos la mejor solución para vos\n\n¿Me podés contar brevemente qué sucedió?"),
            "should_use_explicit": True
        }
    
    # ============================================
    # PRIORIDAD 2: CONSULTAS ESPECÍFICAS
    # ============================================
    
    # ESTADO DE PEDIDO (antes de "pedido" genérico)
    if any(kw in text_lower for kw in ["estado", "seguimiento", "dónde está", "llegó", "rastrear", "tracking", "cuándo llega"]):
        return {
            "intent": "consultar_estado_pedido",
            "emotion_data": emotion_data,
            "response": with_empathy("Para consultar el estado de tu pedido necesito:\n\n1. Número de pedido (ej: #PED-12345)\n2. O tu número de teléfono registrado\n3. O tu email de compra\n\n¿Me podés proporcionar alguno de estos datos?"),
            "should_use_explicit": True
        }
    
    # DEVOLUCIONES
    if any(kw in text_lower for kw in ["devolución", "devolver", "retorno", "cambio", "garantía"]):
        return {
            "intent": "consultar_devoluciones",
            "emotion_data": emotion_data,
            "response": with_empathy("Política de devoluciones:\n\n✅ 30 días para devolver sin preguntas\n✅ Producto sin usar y en su embalaje original\n✅ Reembolso completo en 5-7 días o cambio inmediato\n✅ Retiro gratis desde tu domicilio\n\n¿Necesitás iniciar una devolución?"),
            "should_use_explicit": True
        }
    
    # FACTURACIÓN
    if any(kw in text_lower for kw in ["factura", "comprobante", "recibo", "datos de facturación"]):
        if not any(kw in text_lower for kw in ["pago", "tarjeta", "transferencia"]):
            return {
                "intent": "facturacion_solicitar",
                "emotion_data": emotion_data,
                "response": with_empathy("Para generar tu factura necesito:\n\n1. Tu nombre o razón social\n2. CUIT/CUIL o DNI\n3. Email para enviártela\n4. Dirección de facturación\n\n¿Me podés proporcionar esos datos?"),
                "should_use_explicit": True
            }
    
    # MÉTODOS DE PAGO
    if any(kw in text_lower for kw in ["tarjeta", "pago", "transferencia", "mercado pago", "cuotas", "efectivo"]):
        if "factura" not in text_lower and "comprobante" not in text_lower:
            return {
                "intent": "metodos_pago",
                "emotion_data": emotion_data,
                "response": with_empathy("Aceptamos los siguientes métodos de pago:\n\n💳 Tarjetas de crédito y débito (Visa, Mastercard, Amex)\n🏦 Transferencia bancaria\n💵 Efectivo en puntos de pago (Rapipago, Pago Fácil)\n💰 Mercado Pago\n\n¿Con cuál preferís pagar?"),
                "should_use_explicit": True
            }
    
    # HORARIOS
    if any(kw in text_lower for kw in ["horario", "atención", "abierto", "cierra", "abre"]):
        return {
            "intent": "consultar_horario",
            "emotion_data": emotion_data,
            "response": with_empathy("Nuestro horario de atención es:\n\n🕐 Lunes a Viernes: 9:00 - 18:00 hs\n🕐 Sábados: 9:00 - 13:00 hs\n📧 Soporte online 24/7\n\n¿Necesitás otra información?"),
            "should_use_explicit": True
        }
    
    # UBICACIÓN
    if any(kw in text_lower for kw in ["ubicación", "dirección", "dónde están", "sucursales", "local", "tienda"]):
        return {
            "intent": "consultar_ubicacion",
            "emotion_data": emotion_data,
            "response": with_empathy("Estamos ubicados en:\n\n📍 Av. Principal 1234, Ciudad\n📍 Sucursal Norte: Shopping del Norte, Local 45\n📍 Sucursal Sur: Galería del Sur, Planta Baja\n\n🗺️ ¿Necesitás indicaciones para llegar?"),
            "should_use_explicit": True
        }
    
    # ENVÍOS
    if any(kw in text_lower for kw in ["envío", "delivery", "entrega", "enviar", "mandar", "correo", "domicilio"]):
        return {
            "intent": "consultar_envios",
            "emotion_data": emotion_data,
            "response": with_empathy("Realizamos envíos a todo el país:\n\n🚚 Envío estándar: 3-5 días hábiles (gratis en compras +$10.000)\n🚀 Envío express: 24-48 hs (consultar costo)\n📦 Retiro en sucursal: gratis y disponible en 2hs\n\n¿A dónde necesitás el envío?"),
            "should_use_explicit": True
        }
    
    # PRECIOS
    if any(kw in text_lower for kw in ["precio", "cuánto cuesta", "valor", "costo", "barato", "caro", "oferta", "descuento"]):
        return {
            "intent": "consultar_precios",
            "emotion_data": emotion_data,
            "response": with_empathy("Tenemos productos para todos los presupuestos:\n\n💰 Productos desde $500\n💳 3, 6 y 12 cuotas sin interés con tarjetas seleccionadas\n🏦 10% descuento en transferencia/efectivo\n🎁 Promociones semanales en nuestra web\n\n¿Qué producto te interesa?"),
            "should_use_explicit": True
        }
    
    # PRODUCTOS
    if any(kw in text_lower for kw in ["producto", "catálogo", "stock", "disponible", "tenés", "variedad"]):
        return {
            "intent": "consultar_productos",
            "emotion_data": emotion_data,
            "response": with_empathy("Contamos con amplia variedad:\n\n📦 Más de 1.000 productos en stock\n🔍 Catálogo completo en econify.store\n📱 Asesoramiento personalizado por WhatsApp\n✨ Productos nuevos cada semana\n\n¿Qué tipo de producto buscás?"),
            "should_use_explicit": True
        }
    
    # HACER PEDIDO (genérico, después de problemas)
    if any(kw in text_lower for kw in ["quiero comprar", "hacer un pedido", "ordenar", "adquirir"]):
        return {
            "intent": "hacer_pedido",
            "emotion_data": emotion_data,
            "response": with_empathy("¡Perfecto! Para ayudarte con tu pedido necesito:\n\n1. ¿Qué producto te gustaría comprar?\n2. ¿Qué cantidad necesitas?\n3. ¿A dónde lo enviaremos?\n\nDéjame ayudarte con el proceso."),
            "should_use_explicit": True
        }
    
    # SALUDO
    if any(kw in text_lower for kw in ["hola", "buenos días", "buenas tardes", "buenas noches", "saludos", "hey", "hi"]):
        return {
            "intent": "saludo",
            "emotion_data": emotion_data,
            "response": with_empathy("¡Hola! 👋 Bienvenido/a a Econify.\n\nSoy tu asistente virtual y estoy aquí para ayudarte.\n\n¿En qué puedo asistirte hoy?\n\n💡 Puedo ayudarte con: Pedidos, Facturación, Envíos, Devoluciones, Consultas generales"),
            "should_use_explicit": True
        }
    
    # DESPEDIDA
    if any(kw in text_lower for kw in ["adiós", "chau", "gracias", "hasta luego", "nos vemos", "buen día", "que tengas"]):
        return {
            "intent": "despedida",
            "emotion_data": emotion_data,
            "response": with_empathy("¡Gracias por contactarnos! 😊\n\nQue tengas un excelente día.\n\n¿Necesitás algo más antes de finalizar? Estoy aquí para lo que necesites."),
            "should_use_explicit": True
        }
    
    # CONSULTA GENERAL
    if any(kw in text_lower for kw in ["ayuda", "información", "quiero saber", "me podés decir", "consulta", "pregunta", "duda"]):
        return {
            "intent": "consulta_general",
            "emotion_data": emotion_data,
            "response": with_empathy("Te puedo ayudar con:\n\n📋 Hacer o consultar un pedido\n🧾 Facturación y comprobantes\n💳 Métodos de pago y promociones\n🚚 Envíos, entregas y seguimiento\n🔄 Devoluciones y cambios\n❓ Consultas generales\n\n¿Sobre qué tema querés consultar?"),
            "should_use_explicit": True
        }
    
    # Sin match
    return {"intent": None, "emotion_data": emotion_data, "response": None, "should_use_explicit": False}

# Test
if __name__ == "__main__":
    tests = [
        "ESTOY MUY ENOJADO!!! NUNCA ME LLEGÓ MI PEDIDO!!!",
        "hola, estoy triste porque mi producto llegó roto",
        "¿cómo hago para devolver algo? no entiendo nada",
        "¡GRACIAS! TODO PERFECTO!!!",
        "necesito ayuda urgente con mi factura",
        "buenos días, quiero saber si hacen envíos a Córdoba",
        "quiero comprar algo",
        "¿dónde está mi pedido?",
        "me llegó un producto defectuoso"
    ]
    
    print("=== TEST REGLAS CON EMOCIÓN (CORREGIDO) ===\n")
    for test in tests:
        result = get_explicit_intent(test)
        print(f"Texto: '{test}'")
        print(f"→ Intent: {result['intent']}")
        print(f"→ Emoción: {result['emotion_data']['emotion']} | Intensidad: {result['emotion_data']['intensity']}/10")
        if result['response']:
            print(f"→ Respuesta: {result['response'][:150]}...")
        print()
