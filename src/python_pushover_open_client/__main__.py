from . import PushoverOpenClient, PushoverOpenClientRealTime

@click.group
def cli():
    pass

if __name__ == "__main__":

    cli()

    #pushover_open_client = PushoverOpenClient()
    #pushover_open_client.login()
    #pushover_open_client.register_device()
    #pushover_open_client.download_messages()
    #pushover_open_client.delete_all_messages()

    #pushover_realtime_client =\
            #    PushoverOpenClientRealTime(pushover_open_client=pushover_open_client)
    #pushover_realtime_client.run_forever()

