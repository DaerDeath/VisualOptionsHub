# Notas de uso

## En la terminal web

- **Cambiar símbolo:** escribe el ticker en el input de la barra superior y presiona Enter
- **Cambiar vencimiento:** selector desplegable (próxima semana, próximo mes, etc.)
- **Cambiar fuente de datos:** dropdown "Simulación/Yahoo/Tradier/IBKR"
- **Replay:** botón ⏪ para ver cómo se desarrolló la sesión en tiempo acelerado
- **Exportar:** botón 📷 guarda capturas de pantalla o datos de la vista actual
- **Guía:** dentro de la app hay una vista "Guía" que explica cada apartado

## Configuración

**Datos locales:** se guardan en `~/.visual-options/sessions.db`

**Tradier (opcional):** genera un token en [Tradier Broker](https://tradier.com/app/signup) y lánzalo así:
```bash
TRADIER_TOKEN=xxxx uv run voptions stream --mode tradier
```

**IBKR (opcional):** requiere Interactive Brokers y TWS/IB Gateway con la API activada.
Puerto por defecto: 7496 (TWS cuenta real); usa `--port 7497` para paper:
```bash
uv sync --extra ibkr
uv run voptions stream --mode ibkr
```

## Primeros pasos

1. Corre `uv run voptions stream` (simulador por defecto)
2. Elige un símbolo (ej: SPY) y una vista (ej: Flujo de opciones)
3. Explora con el selector de vista sin recargar
4. Abre la vista Guía para entender qué ves en cada panel
