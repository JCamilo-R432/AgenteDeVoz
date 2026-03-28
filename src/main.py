"""
Agente de Voz - Punto de entrada principal (modo CLI / demo)

Para el modo producción con FastAPI + Twilio, ver:
  uvicorn main_api:app --reload

Para probar el agente en terminal sin APIs externas:
  python src/main.py
"""

import sys
import os

# Agregar src/ al path para que los imports funcionen
sys.path.insert(0, os.path.dirname(__file__))

from config.settings import settings
from core.agent import CustomerServiceAgent
from utils.logger import setup_logger


def run_cli_demo():
    """
    Modo demo en terminal: permite conversar con el agente escribiendo texto.
    Útil para probar los flujos sin configurar Twilio ni Google Cloud.
    """
    logger = setup_logger("main", settings.LOG_LEVEL)
    logger.info("=" * 60)
    logger.info("  AGENTE DE VOZ - Modo Demo CLI")
    logger.info("=" * 60)

    settings.validate()

    session_id = f"demo-{__import__('uuid').uuid4().hex[:8]}"

    try:
        agent = CustomerServiceAgent(session_id=session_id)
        greeting = agent.start_call()
        print(f"\n[AGENTE]: {greeting}\n")

        while agent.is_active:
            try:
                user_input = input("  [TÚ]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nInterrupción detectada.")
                break

            if not user_input:
                continue

            if user_input.lower() in ("salir", "exit", "quit"):
                agent.end_call()
                break

            response = agent.process_input(text_input=user_input)
            print(f"\n[AGENTE]: {response}\n")

        logger.info(
            f"Sesión finalizada | Duración: {agent.conversation.get_duration()}s | "
            f"Turnos: {len(agent.conversation.get_history())}"
        )

    except Exception as e:
        logger.error(f"Error crítico: {e}", exc_info=True)
        print(f"\n[ERROR]: {e}")
        sys.exit(1)


def main():
    """Punto de entrada principal."""
    print("\n" + "=" * 60)
    print("  AGENTE DE VOZ - Atención al Cliente")
    print("  Escribe 'salir' para terminar la demo")
    print("=" * 60 + "\n")

    run_cli_demo()


if __name__ == "__main__":
    main()
