# Marketing por email y WhatsApp (fase futura)

## Email

- Enviar solo a clientes con `marketing_email_consent = true` y `consent_at` registrado.
- Respetar Ley 25.326 (Argentina): consentimiento libre, informado y revocable.
- Recomendado: doble opt-in (confirmación por link en el primer correo).
- Servicio sugerido: SendGrid, Resend o Amazon SES (fuera del alcance del bot PyWa).

## WhatsApp

- Fuera de la ventana de 24h desde el último mensaje del cliente, usar **plantillas** aprobadas en Meta.
- PyWa: ver [Templates](https://pywa.readthedocs.io/en/latest/content/templates/overview.html).
- No usar respuestas libres del bot para campañas masivas.

## Datos en `customers`

| Campo | Uso |
|-------|-----|
| `email` | Contacto y transaccional |
| `marketing_email_consent` | Publicidad por correo |
| `marketing_whatsapp_consent` | Campañas WA con template (futuro) |
