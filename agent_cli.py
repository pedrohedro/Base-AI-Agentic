#!/usr/bin/env python3
import sys
import argparse
import requests
import json

BASE_URL = "http://localhost:8000"

def get_status():
    try:
        r = requests.get(f"{BASE_URL}/api/status", timeout=5)
        if r.status_code == 200:
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        else:
            print(f"Erro: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Erro ao se conectar ao servidor: {e}")

def get_futures_state():
    try:
        r = requests.get(f"{BASE_URL}/api/futures/state", timeout=5)
        if r.status_code == 200:
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        else:
            print(f"Erro: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Erro ao se conectar ao servidor: {e}")

def get_performance():
    try:
        r = requests.get(f"{BASE_URL}/api/performance", timeout=5)
        if r.status_code == 200:
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        else:
            print(f"Erro: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Erro ao se conectar ao servidor: {e}")

def get_logs(limit=10):
    try:
        r = requests.get(f"{BASE_URL}/api/logs", timeout=5)
        if r.status_code == 200:
            logs = r.json().get("logs", [])
            for log in logs[-limit:]:
                print(f"[{log['timestamp']}] [{log['category'].upper()}] {log['message']}")
        else:
            print(f"Erro: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Erro ao se conectar ao servidor: {e}")

def toggle_autonomous():
    try:
        r = requests.post(f"{BASE_URL}/api/toggle", timeout=5)
        if r.status_code == 200:
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        else:
            print(f"Erro: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Erro ao se conectar ao servidor: {e}")

def close_position(asset):
    try:
        r = requests.post(
            f"{BASE_URL}/api/futures/close_manual", 
            json={"asset": asset.upper()},
            timeout=10
        )
        if r.status_code == 200:
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        else:
            print(f"Erro: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Erro ao se conectar ao servidor: {e}")

def chat_agent(message):
    try:
        r = requests.post(
            f"{BASE_URL}/api/chat", 
            json={"message": message},
            timeout=30
        )
        if r.status_code == 200:
            print(f"Resposta do Agente: {r.json().get('reply')}")
        else:
            print(f"Erro: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Erro ao se conectar ao servidor: {e}")

def main():
    parser = argparse.ArgumentParser(description="CLI de controle para o Base Autonomous Trading Agent.")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # Command: status
    subparsers.add_parser("status", help="Retorna o status geral e saldos spot do agente.")

    # Command: futures
    subparsers.add_parser("futures", help="Retorna o resumo da conta de futuros e posições ativas na Hyperliquid.")

    # Command: performance
    subparsers.add_parser("performance", help="Exibe métricas de desempenho contra benchmarks de mercado.")

    # Command: logs
    log_parser = subparsers.add_parser("logs", help="Exibe os últimos logs do terminal do agente.")
    log_parser.add_argument("--limit", type=int, default=15, help="Número máximo de logs a exibir (padrão: 15)")

    # Command: toggle
    subparsers.add_parser("toggle", help="Ativa ou pausa o loop autônomo de trading.")

    # Command: close
    close_parser = subparsers.add_parser("close", help="Encerra manualmente uma posição de futuros perpétuos.")
    close_parser.add_argument("asset", type=str, help="Ativo para fechar (ex: ETH, BTC).")

    # Command: chat
    chat_parser = subparsers.add_parser("chat", help="Envia uma mensagem direta de chat para o agente.")
    chat_parser.add_argument("message", type=str, help="Mensagem ou comando para o agente.")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "status":
        get_status()
    elif args.command == "futures":
        get_futures_state()
    elif args.command == "performance":
        get_performance()
    elif args.command == "logs":
        get_logs(args.limit)
    elif args.command == "toggle":
        toggle_autonomous()
    elif args.command == "close":
        close_position(args.asset)
    elif args.command == "chat":
        chat_agent(args.message)

if __name__ == "__main__":
    main()
