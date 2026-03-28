"""
Detector de emociones y tono para respuestas empáticas.
Analiza texto y devuelve: emoción, intensidad, tono recomendado.
"""
import re

EMOTION_PATTERNS = {
    "enojo": {
        "keywords": ["enojado", "enojada", "furioso", "furiosa", "molesto", "molesta", 
                    "harto", " harta", "bronca", "rabia", "ira", "inaceptable", 
                    "vergüenza", "estafa", "fraude", "nunca más", "pésimo", "horrible"],
        "intensity_markers": ["!!!", "???", "MAYÚSCULAS", "nunca", "siempre", "jamás"],
        "tone": "calmado_profesional",
        "priority": "alta"
    },
    "frustracion": {
        "keywords": ["no funciona", "no puedo", "no me responden", "esperando", 
                    "tiempo", "lento", "difícil", "complicado", "confuso", "perdí"],
        "intensity_markers": ["otra vez", "de nuevo", "siempre", "nunca"],
        "tone": "paciente_guía",
        "priority": "media"
    },
    "tristeza": {
        "keywords": ["triste", "decepcionado", "decepcionada", "mal", "no está bien", 
                    "quería", "esperaba", "lamentablemente", "ojalá", "desilusión"],
        "intensity_markers": ["...", ":( ", "lloro", "no sé qué hacer"],
        "tone": "cálido_empático",
        "priority": "media"
    },
    "ansiedad": {
        "keywords": ["urgente", "necesito ya", "rápido", "prisa", "ansioso", "preocupado",
                    "nervioso", "temo", "miedo", "ayuda", "por favor", "urgencia"],
        "intensity_markers": ["!!!", "ahora", "ya", "inmediato", "urgente"],
        "tone": "tranquilizador_eficiente",
        "priority": "alta"
    },
    "confusion": {
        "keywords": ["no entiendo", "cómo", "qué", "dónde", "cuándo", "por qué", 
                    "explícame", "ayúdame a entender", "no me queda claro"],
        "intensity_markers": ["???", "????", "no sé", "alguien me explica"],
        "tone": "paciente_pedagógico",
        "priority": "baja"
    },
    "alegria": {
        "keywords": ["feliz", "contento", "contenta", "excelente", "genial", "increíble",
                    "gracias", "te quiero", "me encanta", "perfecto", "maravilloso"],
        "intensity_markers": ["!!!", ":)", "jaja", "😍", "🎉"],
        "tone": "entusiasta_cercano",
        "priority": "baja"
    },
    "neutral": {
        "keywords": [],
        "intensity_markers": [],
        "tone": "profesional_amable",
        "priority": "baja"
    }
}

def detect_emotion(text):
    """
    Detecta emoción principal, intensidad y tono recomendado.
    Retorna: {emotion, intensity, tone, priority, keywords_found}
    """
    text_lower = text.lower()
    
    results = {}
    
    for emotion, config in EMOTION_PATTERNS.items():
        score = 0
        found_keywords = []
        
        # Puntos por keywords
        for kw in config["keywords"]:
            if kw in text_lower:
                score += 2
                found_keywords.append(kw)
        
        # Puntos por marcadores de intensidad
        for marker in config["intensity_markers"]:
            if marker.lower() in text_lower or (marker.isupper() and marker in text):
                score += 1
        
        # Puntos por signos de puntuación
        if text.count("!") >= 3:
            score += 1
        if text.count("?") >= 3:
            score += 1
        
        # Puntos por mayúsculas sostenidas (gritos)
        if re.search(r'[A-Z]{3,}', text):
            score += 2
        
        if score > 0:
            results[emotion] = {
                "score": score,
                "tone": config["tone"],
                "priority": config["priority"],
                "keywords": found_keywords
            }
    
    if not results:
        return {
            "emotion": "neutral",
            "intensity": 0,
            "tone": "profesional_amable",
            "priority": "baja",
            "keywords": []
        }
    
    # Seleccionar emoción con mayor score
    primary = max(results.items(), key=lambda x: x[1]["score"])
    emotion_name = primary[0]
    data = primary[1]
    
    # Calcular intensidad (0-10)
    intensity = min(10, data["score"] * 2)
    
    return {
        "emotion": emotion_name,
        "intensity": intensity,
        "tone": data["tone"],
        "priority": data["priority"],
        "keywords": data["keywords"],
        "all_detected": list(results.keys())
    }

def get_empathetic_prefix(emotion_data):
    """Genera prefijo empático según la emoción detectada."""
    emotion = emotion_data["emotion"]
    intensity = emotion_data["intensity"]
    
    prefixes = {
        "enojo": [
            "Entiendo tu enojo y lamento mucho la situación. ",
            "Comprendo perfectamente tu frustración, no es para menos. ",
            "Tienes toda la razón en estar molesto, voy a ayudarte a resolver esto. "
        ],
        "frustracion": [
            "Sé que puede ser frustrante cuando las cosas no funcionan como esperas. ",
            "Entiendo que esto no es lo que esperabas, déjame guiarte paso a paso. ",
            "Lamento que hayas tenido esta experiencia, vamos a solucionarlo juntos. "
        ],
        "tristeza": [
            "Lamento escuchar que te sientes así, estoy aquí para ayudarte. ",
            "Entiendo que esto te afecte, cuenta conmigo para resolverlo. ",
            "Sé que no es fácil, pero juntos vamos a encontrar una solución. "
        ],
        "ansiedad": [
            "Tranquilo/a, estoy aquí para ayudarte a resolver esto rápidamente. ",
            "Entiendo la urgencia, voy a priorizar tu consulta ahora mismo. ",
            "Respira, vamos a solucionar esto paso a paso y lo más rápido posible. "
        ],
        "confusion": [
            "No te preocupes, voy a explicártelo de forma clara y sencilla. ",
            "Es normal tener dudas, déjame guiarte con calma. ",
            "Vamos por partes, te explico de forma fácil. "
        ],
        "alegria": [
            "¡Me alegra mucho saber eso! 😊 ",
            "¡Qué bueno! Me encanta ayudarte cuando todo va bien. ",
            "¡Excelente! Vamos a aprovechar este buen momento. "
        ],
        "neutral": [
            "",
            "",
            ""
        ]
    }
    
    # Seleccionar prefijo según intensidad
    options = prefixes.get(emotion, prefixes["neutral"])
    if intensity >= 7:
        return options[0]  # Más empático para alta intensidad
    elif intensity >= 4:
        return options[1]
    else:
        return options[2]
    
    return ""

# Test rápido
if __name__ == "__main__":
    tests = [
        "ESTOY MUY ENOJADO!!! NUNCA ME LLEGÓ MI PEDIDO!!!",
        "hola, estoy un poco triste porque mi producto llegó roto...",
        "¿cómo hago para devolver algo? no entiendo el proceso",
        "¡GRACIAS! TODO PERFECTO, LOS AMO!!!",
        "necesito ayuda urgente, tengo prisa",
        "buenos días, quiero consultar por un producto"
    ]
    
    print("=== TEST DETECTOR EMOCIONAL ===\n")
    for test in tests:
        result = detect_emotion(test)
        prefix = get_empathetic_prefix(result)
        print(f"Texto: '{test}'")
        print(f"→ Emoción: {result['emotion']} | Intensidad: {result['intensity']}/10")
        print(f"→ Tono: {result['tone']} | Prioridad: {result['priority']}")
        print(f"→ Prefijo: '{prefix}'")
        print()
