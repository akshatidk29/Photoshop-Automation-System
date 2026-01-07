from config import get_log_file

log_path = get_log_file()

def log_error(message):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(message + "\n")
    print("Logged:", message)
