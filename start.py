import threading
import health
import bot

t = threading.Thread(target=health.run, daemon=True)
t.start()

bot.main()
