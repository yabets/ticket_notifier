import requests
import time
import logging
import os
from dotenv import load_dotenv

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


def send_telegram_message(message):
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


def check_ticket_availability():
    try:
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,nl;q=0.8,sv;q=0.7",
            "atleta-locale": "en",
            "content-type": "application/json",
            "dnt": "1",
            "origin": BASE_URL,
            "referer": f"{BASE_URL}/"
        }

        query = {
            "operationName": "GetRegistrationsForSale",
            "variables": {
                "id": EVENT_ID,
                "tickets": None,
                "limit": 10
            },
            "query": """query GetRegistrationsForSale($id: ID!, $tickets: [String!], $limit: Int!) {
  event(id: $id) {
    registrations_for_sale_count
    filtered_registrations_for_sale_count: registrations_for_sale_count(
      tickets: $tickets
    )
    registrations_for_sale(tickets: $tickets, limit: $limit) {
      ticket {
        title
      }
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
            return False

        tickets_available = data['data']['event']['registrations_for_sale_count']

        if tickets_available > 0:
            available_tickets = data['data']['event']['registrations_for_sale']
            tickets_info = []
            for ticket in available_tickets:
                if ticket['resale']['available']:
                    price = ticket['resale']['total_amount'] / 100
                    url = ticket['resale']['public_url']
                    title = ticket['ticket']['title']
                    tickets_info.append(f"• {title} - €{price:.2f}\n{url}")

            message = (
                f"🎫 {tickets_available} ticket(s) available!\n\n"
                f"{chr(10).join(tickets_info)}"
            )
            send_telegram_message(message)
            logging.info(f"Found {tickets_available} tickets available")
            return True

        logging.info("No tickets available")
        return False

    except Exception as e:
        logging.error(f"Error checking ticket availability: {e}")
        return False


def main():
    logging.info("Starting ticket availability monitor...")
    send_telegram_message("🤖 Ticket monitor bot started")

    while True:
        try:
            check_ticket_availability()
            time.sleep(60)
        except KeyboardInterrupt:
            logging.info("Monitor stopped by user")
            send_telegram_message("🛑 Ticket monitor bot stopped")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()