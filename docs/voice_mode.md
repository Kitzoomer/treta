# Voice Mode v1

Uso rápido:

1. Activa **Voice Mode** en la conversación.
2. Di: **"Treta, ..."** seguido de un comando o pregunta.
3. Para comandos mutables, Treta pedirá confirmación: **sí/no**.

Comandos soportados:

- `scan reddit` / `escanea reddit`
- `show opportunities` / `oportunidades`
- `today plan` / `plan de hoy`
- `integrity` / `integridad`
- `approve proposal <id>` / `aprueba propuesta <id>`
- `execute plan <id>` / `ejecuta plan <id>`
- `help` / `ayuda`
- `cancel` / `para`

Notas:

- Si el navegador no soporta Web Speech API, se muestra el banner `Voice not supported in this browser` y Voice Mode se desactiva.
- El toggle **Speak** controla si Treta responde por voz (TTS) o solo por texto.
