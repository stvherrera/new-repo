#Import Libreries
import requests
from bs4 import BeautifulSoup
from twilio.rest import Client


#webscrapping
def scrape_espn_boxing_schedule():
    url = "https://www.espn.com.mx/boxeo/nota/_/id/592138/calendario-de-boxeo"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    schedule = []
    table = soup.find("table")
    if table:
        rows = table.find_all("tr")[1:]
        for row in rows:
            columns = row.find_all("td")
            time = columns[0].text.strip()
            name_1 = columns[1].text.strip()
            fighter2 = columns[3].text.strip()
            location = columns[4].text.strip()

            schedule.append({
                "time": time,
                "name_1": name_1,
                "fighter2": fighter2,
                "location": location
            })

    return schedule

#Whatsapp notifications via Twilio
def send_whatsapp_notification(schedule):
    # Twilio account details
    account_sid = "AC061eebec5defb6fc7c5725d9e389074a"
    auth_token = "0a2663fff995e88ae9b4a54a89bd8a3e"
    twilio_phone_number = "+12294045441"
    your_phone_number = "+50689077447"

    client = Client(account_sid, auth_token)

    message = "\n".join([
        f"{fight['time']} - {fight['name_1']} vs {fight['fighter2']} at {fight['location']}"
        for fight in schedule
    ])

    client.messages.create(
        body=message,
        from_=twilio_phone_number,
        to=your_phone_number,
        via="whatsapp"
    )

if __name__ == "__main__":
    schedule = scrape_espn_boxing_schedule()
    if schedule:
        send_whatsapp_notification(schedule)
        print("WhatsApp notifications sent successfully!")
    else:
        print("No fight schedule found.")