import subprocess
import os
import psutil
from email.message import EmailMessage
import smtplib
from config import *
import os
from dotenv import load_dotenv

os.chdir("/home/lightecho/LightEcho")

load_dotenv()

try:
    output = subprocess.check_output(["git", "pull"]).decode()
    if not "Already up to date" in output:
        for pc in psutil.process_iter():
            if "python3" in pc.name() and not "git" in pc.name():
                try:
                    pc.kill()
                except Exception:
                    print("Unable to kill")
                    output += "\n\nUnable to kill process"
                break
    with open(FOLDER + "last_send_log.txt") as f:
        last_send_log = int(f.read())
    i = last_send_log + 1
    if os.path.exists(FOLDER + f"log{i:03d}.txt"):
        msg = EmailMessage()
        msg["Subject"] = "Logs from KL"
        msg["From"] = "lightecho@gmx.de"
        msg["To"] = os.getenv("EMAIL")
        while os.path.exists(FOLDER + f"log{i:03d}.txt"):
            with open(FOLDER + f"log{i:03d}.txt") as f:
                output += "\n\n\n"
                output += f.read()
                print(f"Written log {i}")
            i += 1
        i -= 2
        msg.set_content(output)
    
        with smtplib.SMTP("mail.gmx.net", 587) as server:
            server.starttls()
            server.login("lightecho@gmx.de", os.getenv("GMX_PASSWORD"))
            server.send_message(msg)
            print("Sent email")

        with open(FOLDER + "last_send_log.txt", "w") as f:
            f.write(str(i))

        print("Worked perfectly")
        # with open(FOLDER + "msg.txt", "w") as f:
        #     f.write("Vielen Dank fuer das Internet, es hat alles funktioniert!")
    print("No new logs")
except subprocess.SubprocessError as e:
    raise e
except Exception as e:
    with open(FOLDER + "msg.txt", "w") as f:
        f.write(f"Fehler: {e}")
    raise e