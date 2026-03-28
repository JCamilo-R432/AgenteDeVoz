"""
Base de Conocimiento para RAG (Retrieval Augmented Generation).
Estructurada por categorías para búsqueda eficiente.
"""
from typing import List, Dict, Optional

class KnowledgeBase:
    """KB simple con búsqueda por keywords + categorías."""
    
    def __init__(self):
        # Conocimiento estructurado por categoría
        self.knowledge = {
            "facturacion": [
                {
                    "question": "¿Qué datos necesito para facturar?",
                    "answer": "Para generar una factura necesito: 1) Tu nombre o razón social, 2) CUIT/CUIL o DNI, 3) Email para enviártela, 4) Dirección de facturación.",
                    "keywords": ["factura", "facturación", "comprobante", "datos", "cuit", "dni", "razón social"]
                },
                {
                    "question": "¿Cómo recibo mi factura?",
                    "answer": "La factura se envía automáticamente por email después de confirmar tu compra. También podés descargarla desde tu cuenta en 'Mis Compras'.",
                    "keywords": ["recibir factura", "email factura", "descargar factura", "mi cuenta"]
                },
                {
                    "question": "¿Puedo facturar a nombre de empresa?",
                    "answer": "¡Sí! Hacemos factura A o B a nombre de empresa. Solo necesitamos tu razón social y CUIT. Podés solicitarlo al momento de la compra o después contactándonos.",
                    "keywords": ["empresa", "razón social", "factura a", "factura empresarial"]
                }
            ],
            "pagos": [
                {
                    "question": "¿Qué métodos de pago aceptan?",
                    "answer": "Aceptamos: 💳 Tarjetas de crédito y débito (Visa, Mastercard, American Express), 🏦 Transferencia bancaria, 💵 Efectivo en Rapipago/Pago Fácil, y 💰 Mercado Pago.",
                    "keywords": ["métodos de pago", "formas de pago", "aceptan", "puedo pagar", "tarjeta", "transferencia", "efectivo", "mercado pago"]
                },
                {
                    "question": "¿Aceptan American Express?",
                    "answer": "¡Sí! Aceptamos American Express (Amex) tanto en crédito como en débito. 💳",
                    "keywords": ["american express", "amex", "amex tarjeta"]
                },
                {
                    "question": "¿Hay descuento por pagar en efectivo?",
                    "answer": "¡Sí! Tenés un 10% de descuento pagando en efectivo o transferencia bancaria. 🎁 El descuento se aplica automáticamente al finalizar la compra.",
                    "keywords": ["descuento", "efectivo", "transferencia", "10%", "promo"]
                },
                {
                    "question": "¿Puedo pagar en cuotas?",
                    "answer": "¡Sí! Aceptamos hasta 12 cuotas sin interés con tarjetas seleccionadas (Visa, Mastercard, Amex). Las cuotas se procesan a través de nuestra pasarela de pago segura.",
                    "keywords": ["cuotas", "cuota", "sin interés", "pagar en cuotas", "financiación"]
                }
            ],
            "envios": [
                {
                    "question": "¿Hacen envíos a todo el país?",
                    "answer": "¡Sí! Enviamos a todo el país. 🚚 Tenemos dos opciones: Estándar (3-5 días hábiles, gratis en compras +$10.000) y Express (24-48 horas, costo adicional).",
                    "keywords": ["envíos", "envío", "todo el país", "domicilio", "delivery", "mandan"]
                },
                {
                    "question": "¿Cuánto tarda el envío?",
                    "answer": "Depende de la opción: 🚚 Estándar: 3-5 días hábiles | 🚀 Express: 24-48 horas. Una vez despachado, te enviamos el código de seguimiento por email.",
                    "keywords": ["cuánto tarda", "tiempo de entrega", "demora", "llega en", "seguimiento"]
                },
                {
                    "question": "¿El envío es gratis?",
                    "answer": "El envío estándar es GRATIS en compras mayores a $10.000. Para compras menores, el costo varía según tu ubicación (se calcula al finalizar la compra).",
                    "keywords": ["envío gratis", "gratis", "costo envío", "free shipping"]
                },
                {
                    "question": "¿Puedo retirar en sucursal?",
                    "answer": "¡Sí! Podés retirar tu compra gratis en cualquiera de nuestras sucursales. El pedido está listo en 2 horas. 📍 Av. Principal 1234, Shopping Norte Local 45, Galería Sur PB.",
                    "keywords": ["retirar", "sucursal", "pasar a buscar", "retiro", "recoger"]
                }
            ],
            "devoluciones": [
                {
                    "question": "¿Puedo devolver un producto?",
                    "answer": "¡Sí! Tenés 30 días para devolver cualquier producto desde que lo recibís. Es gratis: nosotros retiramos el producto de tu domicilio y te reembolsamos el 100% o te enviamos un reemplazo.",
                    "keywords": ["devolver", "devolución", "retorno", "cambio", "reembolso", "garantía"]
                },
                {
                    "question": "¿Qué pasa si el producto llegó roto?",
                    "answer": "Lamentamos mucho que te haya llegado así. 😔 Te ofrecemos: 1) Reenvío inmediato del producto sin costo, o 2) Reembolso completo a tu medio de pago original. Elegí lo que te convenga.",
                    "keywords": ["roto", "dañado", "defectuoso", "no funciona", "mal estado", "llegó mal"]
                }
            ],
            "pedidos": [
                {
                    "question": "¿Cómo rastreo mi pedido?",
                    "answer": "Podés rastrear tu pedido de 3 formas: 1) Con el número de pedido (#PED-XXXX) en 'Mis Compras', 2) Con tu email registrado, o 3) Contactándonos por WhatsApp. Te damos el estado en tiempo real.",
                    "keywords": ["rastrear", "seguimiento", "tracking", "dónde está", "estado del pedido", "mi pedido"]
                },
                {
                    "question": "¿Qué hago si mi pedido no llegó?",
                    "answer": "Si tu pedido no llegó en el plazo estimado, contactanos inmediatamente. Vamos a: 1) Rastrearlo con la transportista, 2) Si está perdido, reenviártelo gratis o reembolsarte, y 3) Un supervisor te contactará en menos de 2 horas.",
                    "keywords": ["no llegó", "nunca llegó", "perdido", "no recibí", "demorado", "retraso"]
                }
            ],
            "general": [
                {
                    "question": "¿Cuál es el horario de atención?",
                    "answer": "Atendemos: 🕐 Lunes a Viernes: 9:00 - 18:00 hs | 🕐 Sábados: 9:00 - 13:00 hs | 📧 Soporte online 24/7 por email y WhatsApp.",
                    "keywords": ["horario", "atención", "abierto", "cierra", "hora", "cuándo atienden"]
                },
                {
                    "question": "¿Dónde están ubicados?",
                    "answer": "Tenemos 3 sucursales: 📍 Casa Central: Av. Principal 1234, Ciudad | 📍 Sucursal Norte: Shopping del Norte, Local 45 | 📍 Sucursal Sur: Galería del Sur, Planta Baja. ¿Necesitás indicaciones?",
                    "keywords": ["ubicación", "dirección", "dónde están", "sucursales", "tienda", "local", "address"]
                }
            ]
        }
    
    def search(self, query: str, category: Optional[str] = None, top_k: int = 3) -> List[Dict]:
        """
        Busca en la KB por keywords.
        Retorna los top_k resultados más relevantes.
        """
        query_lower = query.lower()
        results = []
        
        # Si se especifica categoría, buscar solo ahí
        categories_to_search = [category] if category else self.knowledge.keys()
        
        for cat in categories_to_search:
            if cat not in self.knowledge:
                continue
                
            for item in self.knowledge[cat]:
                # Score simple por match de keywords
                score = sum(1 for kw in item["keywords"] if kw in query_lower)
                if score > 0:
                    results.append({
                        **item,
                        "category": cat,
                        "score": score
                    })
        
        # Ordenar por score y retornar top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def get_all_keywords(self) -> List[str]:
        """Retorna todas las keywords para debug."""
        keywords = []
        for items in self.knowledge.values():
            for item in items:
                keywords.extend(item["keywords"])
        return list(set(keywords))

# Singleton
kb = KnowledgeBase()
