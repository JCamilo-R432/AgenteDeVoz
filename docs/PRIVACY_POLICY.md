# Política de Privacidad — Agente de Voz Inteligente

**Última actualización:** Marzo 2026
**Responsable:** [Nombre/Razón Social del Proveedor]
**Jurisdicción:** República de Colombia — Ley 1581 de 2012

---

## 1. ¿Qué datos recopilamos?

### 1.1 Datos de la empresa Cliente (Business to Business)
- Nombre de la empresa y datos de contacto
- Información de facturación (NIT, dirección)
- Credenciales de acceso (email del administrador)
- Métricas de uso del Servicio

### 1.2 Datos de usuarios finales del Cliente (usuarios del agente)
- Número de teléfono (para autenticación OTP)
- Dirección de correo electrónico (opcional)
- Nombre y apellido
- Historial de conversaciones con el agente
- Datos de pedidos consultados (número, estado, dirección de entrega)

### 1.3 Datos técnicos
- Dirección IP y User-Agent de las solicitudes
- Logs de acceso (fecha, hora, endpoint consultado)
- Registros de auditoría de autenticación

---

## 2. ¿Para qué usamos los datos?

| Finalidad | Base legal |
|-----------|------------|
| Prestar el Servicio de agente de voz | Ejecución del contrato |
| Autenticar la identidad del usuario (OTP) | Ejecución del contrato |
| Facturación al Cliente | Obligación legal / Contrato |
| Soporte técnico y resolución de incidentes | Interés legítimo |
| Mejorar la precisión del agente | Interés legítimo (anonimizado) |
| Detección de fraude y abuso | Interés legítimo |
| Cumplimiento de obligaciones legales | Obligación legal |

**No usamos los datos para:**
- Publicidad de terceros
- Venta de datos
- Perfilamiento sin consentimiento

---

## 3. ¿Con quién compartimos los datos?

Únicamente con los siguientes proveedores estrictamente necesarios, quienes actúan como encargados del tratamiento:

| Proveedor | Servicio | País |
|-----------|----------|------|
| Twilio Inc. | Envío de SMS/OTP | Estados Unidos |
| SendGrid (Twilio) | Envío de emails | Estados Unidos |
| OpenAI / Anthropic | Procesamiento de lenguaje natural | Estados Unidos |
| [Proveedor VPS] | Infraestructura de servidores | [País] |

**No vendemos ni cedemos datos a terceros** con fines comerciales o publicitarios.

Podemos divulgar datos cuando lo exija la ley colombiana (p.ej., orden judicial, Fiscalía).

---

## 4. ¿Cuánto tiempo conservamos los datos?

| Tipo de dato | Período de retención |
|--------------|---------------------|
| Datos del Cliente activo | Mientras dure el contrato |
| Conversaciones del agente | 24 meses desde la conversación |
| Logs de acceso y auditoría | 12 meses |
| Codes OTP | 24 horas (luego se eliminan automáticamente) |
| Datos post-terminación del contrato | 30 días (exportables, luego eliminados) |

---

## 5. Seguridad de los datos

Implementamos las siguientes medidas técnicas y organizativas:

- **Cifrado en tránsito:** HTTPS/TLS 1.3 en todas las comunicaciones
- **Cifrado de contraseñas y OTPs:** SHA-256 (nunca almacenamos OTPs en texto plano)
- **Control de acceso:** API Keys únicas por cliente, JWT con expiración corta
- **Aislamiento de datos:** Arquitectura multi-tenant — cada cliente solo ve sus datos
- **Backups cifrados:** Copias de seguridad diarias
- **Acceso restringido:** Solo el personal necesario accede a datos de producción
- **Logs de auditoría:** Registramos todos los accesos y cambios

---

## 6. Sus derechos como titular de datos

Conforme a la Ley 1581 de 2012, los titulares de datos personales tienen los siguientes derechos:

**a) Derecho de acceso:** Puede solicitar qué datos tenemos sobre usted.

**b) Derecho de rectificación:** Puede solicitar corrección de datos inexactos.

**c) Derecho de supresión (olvido):** Puede solicitar la eliminación de sus datos cuando ya no sean necesarios para la finalidad por la que fueron recopilados.

**d) Derecho de portabilidad:** Puede solicitar sus datos en formato CSV o JSON.

**e) Derecho de oposición:** Puede oponerse al tratamiento de sus datos para finalidades específicas.

**Para ejercer sus derechos**, contáctenos en: **privacidad@[dominio-del-proveedor]**

Responderemos en un plazo máximo de **15 días hábiles**.

---

## 7. Cookies y tecnologías similares

El panel de administración web utiliza cookies de sesión estrictamente necesarias para el funcionamiento. No utilizamos cookies de rastreo o publicidad.

---

## 8. Menores de edad

El Servicio no está dirigido a menores de 18 años. No recopilamos intencionalmente datos de menores.

---

## 9. Transferencias internacionales

Algunos proveedores (Twilio, OpenAI) están ubicados en Estados Unidos. Estas transferencias se realizan bajo las salvaguardas adecuadas conforme al marco legal colombiano e internacional.

---

## 10. Cambios a esta política

Notificaremos cualquier cambio material con al menos 30 días de anticipación mediante email al administrador del Cliente.

---

## 11. Contacto

**Oficial de Protección de Datos:**
- Email: privacidad@[dominio-del-proveedor]
- Dirección: [Dirección del proveedor], Colombia

**Autoridad competente:** Superintendencia de Industria y Comercio (SIC) — www.sic.gov.co
