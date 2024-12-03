import os
from dotenv import load_dotenv
import requests
import time
import logging
import json
from typing import Set
from pathlib import Path

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ticket_monitor.log'),
        logging.StreamHandler()
    ]
)

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
BASE_URL = "https://atleta.cc"
EVENT_ID = "qPULQniKULIH"
CACHE_FILE = "known_tickets.json"

# Validate configuration
if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    raise ValueError("Missing required environment variables. Check .env file.")


class TicketMonitor:
    def __init__(self):
        self.known_tickets: Set[str] = self.load_known_tickets()

    def load_known_tickets(self) -> Set[str]:
        if Path(CACHE_FILE).exists():
            with open(CACHE_FILE, 'r') as f:
                return set(json.load(f))
        return set()

    def save_known_tickets(self):
        with open(CACHE_FILE, 'w') as f:
            json.dump(list(self.known_tickets), f)

    def send_telegram_message(self, message: str):
        try:
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(TELEGRAM_API_URL, json=payload)
            response.raise_for_status()
            logging.info("Telegram message sent successfully")
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {e}")

    def check_ticket_availability(self):
        try:
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9,nl;q=0.8,sv;q=0.7",
                "atleta-locale": "en",
                "content-type": "application/json",
                "origin": BASE_URL,
                "referer": f"{BASE_URL}/"
            }

            query = {
                "operationName": "GetRegistrationsForSale",
                "variables": {"id": EVENT_ID, "tickets": None, "limit": 10},
                "query": """query GetRegistrationsForSale($id: ID!, $tickets: [String!], $limit: Int!) {
                    event(id: $id) {
                        registrations_for_sale_count
                        registrations_for_sale(tickets: $tickets, limit: $limit) {
                            id
                            ticket { title }
                            resale {
                                available
                                total_amount
                                public_url
                            }
                        }
                    }
                }"""
            }

            response = requests.post(f"{BASE_URL}/api/graphql", json=query, headers=headers)
            response.raise_for_status()
            data = response.json()

            if 'errors' in data:
                logging.error(f"GraphQL errors: {data['errors']}")
                return

            available_tickets = data['data']['event']['registrations_for_sale']
            new_tickets = []
            current_ticket_ids = set()

            for ticket in available_tickets:
                if ticket['resale']['available']:
                    ticket_id = ticket['id']
                    current_ticket_ids.add(ticket_id)

                    if ticket_id not in self.known_tickets:
                        self.known_tickets.add(ticket_id)
                        new_tickets.append({
                            'title': ticket['ticket']['title'],
                            'price': ticket['resale']['total_amount'] / 100,
                            'url': ticket['resale']['public_url']
                        })

            # Remove tickets that are no longer available
            self.known_tickets.intersection_update(current_ticket_ids)
            self.save_known_tickets()

            if new_tickets:
                tickets_info = [f"• {t['title']} - €{t['price']:.2f}\n{t['url']}" for t in new_tickets]
                message = f"🎫 {len(new_tickets)} new ticket(s) available!\n\n{chr(10).join(tickets_info)}"
                self.send_telegram_message(message)
                logging.info(f"Found {len(new_tickets)} new tickets")

        except Exception as e:
            logging.error(f"Error checking ticket availability: {e}")

    def run(self):
        logging.info("Starting ticket availability monitor...")
        self.send_telegram_message("🤖 Ticket monitor bot started")

        while True:
            try:
                self.check_ticket_availability()
                time.sleep(60)
            except KeyboardInterrupt:
                logging.info("Monitor stopped by user")
                self.send_telegram_message("🛑 Ticket monitor bot stopped")
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                time.sleep(60)


if __name__ == "__main__":
    monitor = TicketMonitor()
    monitor.run()