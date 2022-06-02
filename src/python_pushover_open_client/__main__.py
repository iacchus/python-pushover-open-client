from . import PushoverOpenClient, PushoverOpenClientRealTime

def cli():
    print("not ready yet")

    pushover_client = PushoverOpenClientRealTime()
    pushover_client.run_forever()

if __name__ == "__main__":
    cli()